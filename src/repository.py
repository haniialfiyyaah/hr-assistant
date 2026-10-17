"""Repository contracts. MemoryRepository for tests; PostgreSQL comes later."""
from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Literal, Protocol

from .contracts import (
    ActionProposal,
    ActionResult,
    AuthContext,
    LeaveBalance,
    LeaveRequestView,
    PolicyChunk,
)
from .security import token_hash

ROOT = Path(__file__).resolve().parents[1]
EMPLOYEES_PATH = ROOT / "data" / "employees.json"


class Repository(Protocol):
    def health(self) -> bool: ...
    def authenticate(self, token: str) -> AuthContext | None: ...
    def lexical_search(self, query: str, limit: int) -> list[PolicyChunk]: ...
    def vector_search(self, embedding: list[float], limit: int) -> list[PolicyChunk]: ...
    def get_balances(self, employee_id: str) -> list[LeaveBalance]: ...
    def has_overlap(self, employee_id: str, start: date, end: date) -> bool: ...
    def save_proposal(self, employee_id: str, proposal: ActionProposal) -> None: ...
    def get_proposal(self, proposal_id: str) -> tuple[str, ActionProposal] | None: ...
    def confirm_proposal(self, employee_id: str, proposal_id: str, idempotency_key: str) -> ActionResult: ...
    def list_leave_requests(self, employee_id: str) -> list[LeaveRequestView]: ...
    def create_ticket(self, employee_id: str, category: str, summary: str) -> str: ...
    def save_trace(self, trace: dict[str, Any]) -> None: ...
    def get_trace(self, trace_id: str) -> dict[str, Any] | None: ...
    def monitoring_summary(self) -> dict[str, Any]: ...


class ConflictError(RuntimeError):
    pass


class MemoryRepository:
    """In-memory store for deterministic tests. Identity is bound via hashed demo tokens."""

    def __init__(self, employees_path: Path | None = None) -> None:
        self.chunks: list[PolicyChunk] = []
        self._token_to_auth: dict[str, AuthContext] = {}
        self._balances: dict[str, list[LeaveBalance]] = {}
        self._proposals: dict[str, dict[str, Any]] = {}
        self._requests: list[dict[str, Any]] = []
        self._tickets: list[dict[str, Any]] = []
        self._traces: dict[str, dict[str, Any]] = {}
        self._load_employees(employees_path or EMPLOYEES_PATH)

    def _load_employees(self, path: Path) -> None:
        rows = json.loads(path.read_text(encoding="utf-8"))
        as_of = date(2026, 1, 1)
        for row in rows:
            role: Literal["employee", "monitoring_admin"] = row["role"]
            auth = AuthContext(
                employee_id=row["employee_id"],
                display_name=row["display_name"],
                role=role,
            )
            self._token_to_auth[token_hash(row["token"])] = auth
            self._balances[row["employee_id"]] = [
                LeaveBalance(leave_type=leave_type, available_days=days, as_of_date=as_of)
                for leave_type, days in row.get("balances", {}).items()
            ]

    def health(self) -> bool:
        return True

    def authenticate(self, token: str) -> AuthContext | None:
        return self._token_to_auth.get(token_hash(token))

    def lexical_search(self, query: str, limit: int) -> list[PolicyChunk]:
        terms = [term.lower() for term in query.split() if term.strip()]
        scored: list[tuple[float, PolicyChunk]] = []
        for chunk in self.chunks:
            haystack = f"{chunk.title} {chunk.section} {chunk.content}".lower()
            hits = sum(1 for term in terms if term in haystack)
            if hits:
                scored.append((float(hits), chunk.model_copy(update={"score": float(hits)})))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [chunk for _, chunk in scored[:limit]]

    def vector_search(self, embedding: list[float], limit: int) -> list[PolicyChunk]:
        # Memory tests rely on lexical ranking; return a weak uniform score for fusion.
        return [
            chunk.model_copy(update={"score": 0.1})
            for chunk in self.chunks[:limit]
        ]

    def get_balances(self, employee_id: str) -> list[LeaveBalance]:
        return list(self._balances.get(employee_id, []))

    def has_overlap(self, employee_id: str, start: date, end: date) -> bool:
        for row in self._requests:
            if row["employee_id"] != employee_id:
                continue
            if row["status"] == "cancelled":
                continue
            if start <= row["end_date"] and end >= row["start_date"]:
                return True
        return False

    def save_proposal(self, employee_id: str, proposal: ActionProposal) -> None:
        self._proposals[proposal.proposal_id] = {
            "employee_id": employee_id,
            "proposal": proposal,
            "idempotency_key": None,
            "request_id": None,
            "audit_reference": None,
        }

    def get_proposal(self, proposal_id: str) -> tuple[str, ActionProposal] | None:
        row = self._proposals.get(proposal_id)
        if row is None:
            return None
        return row["employee_id"], row["proposal"]

    def confirm_proposal(
        self, employee_id: str, proposal_id: str, idempotency_key: str
    ) -> ActionResult:
        row = self._proposals.get(proposal_id)
        if row is None or row["employee_id"] != employee_id:
            raise KeyError(proposal_id)

        proposal: ActionProposal = row["proposal"]
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise ConflictError("proposal expired")

        # Idempotent replay: same owner + same key returns the original pending request.
        if row["request_id"] is not None:
            if row["idempotency_key"] == idempotency_key:
                return ActionResult(
                    request_id=row["request_id"],
                    status="pending_manager_review",
                    idempotent_replay=True,
                    audit_reference=row["audit_reference"],
                )
            raise ConflictError("idempotency key conflict")

        request_id = f"LR-{uuid.uuid4().hex[:12].upper()}"
        audit_reference = f"AUD-{uuid.uuid4().hex[:10].upper()}"
        created_at = datetime.now(timezone.utc)
        self._requests.insert(
            0,
            {
                "employee_id": employee_id,
                "request_id": request_id,
                "leave_type": proposal.leave_type,
                "start_date": proposal.start_date,
                "end_date": proposal.end_date,
                "business_days": proposal.business_days,
                "status": "pending_manager_review",
                "created_at": created_at,
            },
        )
        row["request_id"] = request_id
        row["idempotency_key"] = idempotency_key
        row["audit_reference"] = audit_reference
        return ActionResult(
            request_id=request_id,
            status="pending_manager_review",
            idempotent_replay=False,
            audit_reference=audit_reference,
        )

    def list_leave_requests(self, employee_id: str) -> list[LeaveRequestView]:
        return [
            LeaveRequestView(
                request_id=row["request_id"],
                leave_type=row["leave_type"],
                start_date=row["start_date"],
                end_date=row["end_date"],
                business_days=row["business_days"],
                status=row["status"],
                created_at=row["created_at"],
            )
            for row in self._requests
            if row["employee_id"] == employee_id
        ]

    def create_ticket(self, employee_id: str, category: str, summary: str) -> str:
        ticket_id = f"TKT-{uuid.uuid4().hex[:10].upper()}"
        self._tickets.append(
            {
                "ticket_id": ticket_id,
                "employee_id": employee_id,
                "category": category,
                "summary": summary,
                "created_at": datetime.now(timezone.utc),
            }
        )
        return ticket_id

    def save_trace(self, trace: dict[str, Any]) -> None:
        trace_id = trace.get("trace_id")
        if not trace_id:
            raise ValueError("trace_id is required")
        self._traces[str(trace_id)] = dict(trace)

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        row = self._traces.get(trace_id)
        return dict(row) if row is not None else None

    def monitoring_summary(self) -> dict[str, Any]:
        traces = list(self._traces.values())
        run_count = len(traces)
        error_count = sum(1 for item in traces if item.get("error"))
        latencies = [int(item.get("latency_ms") or 0) for item in traces]
        p95 = sorted(latencies)[int(0.95 * (len(latencies) - 1))] if latencies else 0
        tool_calls = sum(len(item.get("tool_calls") or []) for item in traces)
        return {
            "run_count": run_count,
            "error_rate": (error_count / run_count) if run_count else 0.0,
            "p95_latency_ms": p95,
            "tool_calls": tool_calls,
        }


class PostgresRepository:
    def __init__(self, database_url: str, embedding_dimensions: int) -> None:
        # TODO(M2): Create a psycopg connection pool. Do not interpolate user input into SQL.
        raise NotImplementedError

    # TODO(M2): Implement transaction-safe persistence and pgvector/full-text queries.
