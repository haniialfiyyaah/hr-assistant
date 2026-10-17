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

    def index_ready(self) -> bool:
        return len(self.chunks) > 0

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


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in embedding) + "]"


class PostgresRepository:
    """PostgreSQL + pgvector persistence for runtime use."""

    def __init__(self, database_url: str, embedding_dimensions: int) -> None:
        from psycopg_pool import ConnectionPool

        self.database_url = database_url
        self.embedding_dimensions = embedding_dimensions
        self.pool = ConnectionPool(
            conninfo=database_url,
            min_size=1,
            max_size=8,
            kwargs={"autocommit": True},
            open=True,
        )

    def close(self) -> None:
        self.pool.close()

    def health(self) -> bool:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                    cur.fetchone()
            return True
        except Exception:
            return False

    def index_ready(self) -> bool:
        try:
            with self.pool.connection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM policy_chunks")
                    row = cur.fetchone()
                    return bool(row and int(row[0]) > 0)
        except Exception:
            return False

    def authenticate(self, token: str) -> AuthContext | None:
        digest = token_hash(token)
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT employee_id, display_name, role
                    FROM employees
                    WHERE token_hash = %s
                    """,
                    (digest,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return AuthContext(employee_id=row[0], display_name=row[1], role=row[2])

    def lexical_search(self, query: str, limit: int) -> list[PolicyChunk]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_id, document_id, title, section, version, effective_date,
                           content, ts_rank(tsv, plainto_tsquery('simple', %s)) AS score
                    FROM policy_chunks
                    WHERE tsv @@ plainto_tsquery('simple', %s)
                    ORDER BY score DESC
                    LIMIT %s
                    """,
                    (query, query, limit),
                )
                rows = cur.fetchall()
        return [
            PolicyChunk(
                chunk_id=row[0],
                document_id=row[1],
                title=row[2],
                section=row[3],
                version=row[4],
                effective_date=row[5],
                content=row[6],
                score=float(row[7] or 0.0),
            )
            for row in rows
        ]

    def vector_search(self, embedding: list[float], limit: int) -> list[PolicyChunk]:
        if len(embedding) != self.embedding_dimensions:
            raise ValueError(
                f"Embedding dimension {len(embedding)} does not match "
                f"configured {self.embedding_dimensions}"
            )
        literal = _vector_literal(embedding)
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT chunk_id, document_id, title, section, version, effective_date,
                           content, 1.0 / (1.0 + (embedding <=> %s::vector)) AS score
                    FROM policy_chunks
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                    """,
                    (literal, literal, limit),
                )
                rows = cur.fetchall()
        return [
            PolicyChunk(
                chunk_id=row[0],
                document_id=row[1],
                title=row[2],
                section=row[3],
                version=row[4],
                effective_date=row[5],
                content=row[6],
                score=float(row[7] or 0.0),
            )
            for row in rows
        ]

    def get_balances(self, employee_id: str) -> list[LeaveBalance]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT leave_type, available_days, as_of_date
                    FROM leave_balances
                    WHERE employee_id = %s
                    ORDER BY leave_type
                    """,
                    (employee_id,),
                )
                rows = cur.fetchall()
        return [
            LeaveBalance(leave_type=row[0], available_days=row[1], as_of_date=row[2])
            for row in rows
        ]

    def has_overlap(self, employee_id: str, start: date, end: date) -> bool:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM leave_requests
                    WHERE employee_id = %s
                      AND status <> 'cancelled'
                      AND start_date <= %s
                      AND end_date >= %s
                    LIMIT 1
                    """,
                    (employee_id, end, start),
                )
                return cur.fetchone() is not None

    def save_proposal(self, employee_id: str, proposal: ActionProposal) -> None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO action_proposals (
                        proposal_id, employee_id, leave_type, start_date, end_date,
                        business_days, reason, validation_summary, expires_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)
                    ON CONFLICT (proposal_id) DO UPDATE SET
                        employee_id = EXCLUDED.employee_id,
                        leave_type = EXCLUDED.leave_type,
                        start_date = EXCLUDED.start_date,
                        end_date = EXCLUDED.end_date,
                        business_days = EXCLUDED.business_days,
                        reason = EXCLUDED.reason,
                        validation_summary = EXCLUDED.validation_summary,
                        expires_at = EXCLUDED.expires_at,
                        idempotency_key = NULL,
                        request_id = NULL,
                        audit_reference = NULL
                    """,
                    (
                        proposal.proposal_id,
                        employee_id,
                        proposal.leave_type,
                        proposal.start_date,
                        proposal.end_date,
                        proposal.business_days,
                        proposal.reason,
                        json.dumps(proposal.validation_summary),
                        proposal.expires_at,
                    ),
                )

    def get_proposal(self, proposal_id: str) -> tuple[str, ActionProposal] | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT employee_id, proposal_id, leave_type, start_date, end_date,
                           business_days, reason, validation_summary, expires_at
                    FROM action_proposals
                    WHERE proposal_id = %s
                    """,
                    (proposal_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        proposal = ActionProposal(
            proposal_id=row[1],
            leave_type=row[2],
            start_date=row[3],
            end_date=row[4],
            business_days=row[5],
            reason=row[6],
            validation_summary=list(row[7] or []),
            expires_at=row[8],
        )
        return row[0], proposal

    def confirm_proposal(
        self, employee_id: str, proposal_id: str, idempotency_key: str
    ) -> ActionResult:
        with self.pool.connection() as conn:
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT employee_id, leave_type, start_date, end_date, business_days,
                               reason, expires_at, idempotency_key, request_id, audit_reference
                        FROM action_proposals
                        WHERE proposal_id = %s
                        FOR UPDATE
                        """,
                        (proposal_id,),
                    )
                    row = cur.fetchone()
                    if row is None or row[0] != employee_id:
                        raise KeyError(proposal_id)

                    expires_at = row[6]
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at < datetime.now(timezone.utc):
                        raise ConflictError("proposal expired")

                    existing_key, existing_request, existing_audit = row[7], row[8], row[9]
                    if existing_request is not None:
                        if existing_key == idempotency_key:
                            conn.commit()
                            return ActionResult(
                                request_id=existing_request,
                                status="pending_manager_review",
                                idempotent_replay=True,
                                audit_reference=existing_audit,
                            )
                        raise ConflictError("idempotency key conflict")

                    request_id = f"LR-{uuid.uuid4().hex[:12].upper()}"
                    audit_reference = f"AUD-{uuid.uuid4().hex[:10].upper()}"
                    created_at = datetime.now(timezone.utc)
                    cur.execute(
                        """
                        INSERT INTO leave_requests (
                            request_id, employee_id, leave_type, start_date, end_date,
                            business_days, status, created_at, reason
                        ) VALUES (%s, %s, %s, %s, %s, %s, 'pending_manager_review', %s, %s)
                        """,
                        (
                            request_id,
                            employee_id,
                            row[1],
                            row[2],
                            row[3],
                            row[4],
                            created_at,
                            row[5],
                        ),
                    )
                    cur.execute(
                        """
                        UPDATE action_proposals
                        SET idempotency_key = %s,
                            request_id = %s,
                            audit_reference = %s
                        WHERE proposal_id = %s
                        """,
                        (idempotency_key, request_id, audit_reference, proposal_id),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.autocommit = True

        return ActionResult(
            request_id=request_id,
            status="pending_manager_review",
            idempotent_replay=False,
            audit_reference=audit_reference,
        )

    def list_leave_requests(self, employee_id: str) -> list[LeaveRequestView]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT request_id, leave_type, start_date, end_date,
                           business_days, status, created_at
                    FROM leave_requests
                    WHERE employee_id = %s
                    ORDER BY created_at DESC
                    """,
                    (employee_id,),
                )
                rows = cur.fetchall()
        return [
            LeaveRequestView(
                request_id=row[0],
                leave_type=row[1],
                start_date=row[2],
                end_date=row[3],
                business_days=row[4],
                status=row[5],
                created_at=row[6],
            )
            for row in rows
        ]

    def create_ticket(self, employee_id: str, category: str, summary: str) -> str:
        ticket_id = f"TKT-{uuid.uuid4().hex[:10].upper()}"
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO hr_tickets (ticket_id, employee_id, category, summary)
                    VALUES (%s, %s, %s, %s)
                    """,
                    (ticket_id, employee_id, category, summary),
                )
        return ticket_id

    def save_trace(self, trace: dict[str, Any]) -> None:
        trace_id = trace.get("trace_id")
        employee_id = trace.get("employee_id")
        if not trace_id or not employee_id:
            raise ValueError("trace_id and employee_id are required")
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO traces (trace_id, employee_id, payload)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (trace_id) DO UPDATE
                    SET payload = EXCLUDED.payload, employee_id = EXCLUDED.employee_id
                    """,
                    (str(trace_id), str(employee_id), json.dumps(trace, default=str)),
                )

    def get_trace(self, trace_id: str) -> dict[str, Any] | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT payload FROM traces WHERE trace_id = %s",
                    (trace_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        payload = row[0]
        return dict(payload) if isinstance(payload, dict) else json.loads(payload)

    def monitoring_summary(self) -> dict[str, Any]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT payload FROM traces")
                payloads = [row[0] for row in cur.fetchall()]
        traces = [
            dict(item) if isinstance(item, dict) else json.loads(item) for item in payloads
        ]
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

