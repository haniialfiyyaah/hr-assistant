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
    TicketProposal,
    TicketResult,
    TicketView,
)
from .security import token_hash

ROOT = Path(__file__).resolve().parents[1]
EMPLOYEES_PATH = ROOT / "data" / "employees.json"


class Repository(Protocol):
    def health(self) -> bool: ...
    def authenticate(self, token: str) -> AuthContext | None: ...
    def list_profiles(self) -> list[AuthContext]: ...
    def lexical_search(self, query: str, limit: int) -> list[PolicyChunk]: ...
    def vector_search(self, embedding: list[float], limit: int) -> list[PolicyChunk]: ...
    def get_balances(self, employee_id: str) -> list[LeaveBalance]: ...
    def has_overlap(self, employee_id: str, start: date, end: date) -> bool: ...
    def save_proposal(self, employee_id: str, proposal: ActionProposal) -> None: ...
    def get_proposal(self, proposal_id: str) -> tuple[str, ActionProposal] | None: ...
    def proposal_request_id(self, proposal_id: str) -> str | None: ...
    def latest_open_proposal(self, employee_id: str) -> ActionProposal | None: ...
    def confirm_proposal(self, employee_id: str, proposal_id: str, idempotency_key: str) -> ActionResult: ...
    def list_leave_requests(self, employee_id: str) -> list[LeaveRequestView]: ...
    def save_ticket_proposal(self, employee_id: str, proposal: TicketProposal) -> None: ...
    def get_ticket_proposal(self, proposal_id: str) -> tuple[str, TicketProposal] | None: ...
    def ticket_proposal_ticket_id(self, proposal_id: str) -> str | None: ...
    def latest_open_ticket_proposal(self, employee_id: str) -> TicketProposal | None: ...
    def confirm_ticket_proposal(
        self, employee_id: str, proposal_id: str, idempotency_key: str
    ) -> TicketResult: ...
    def list_tickets(self, employee_id: str) -> list[TicketView]: ...
    def create_ticket(self, employee_id: str, category: str, summary: str) -> str: ...
    def save_trace(self, trace: dict[str, Any]) -> None: ...
    def get_trace(self, trace_id: str) -> dict[str, Any] | None: ...
    def monitoring_summary(self) -> dict[str, Any]: ...
    def create_conversation(self, employee_id: str) -> str: ...
    def conversation_owner(self, conversation_id: str) -> str | None: ...
    def current_conversation_id(self, employee_id: str) -> str | None: ...
    def list_conversations(self, employee_id: str, limit: int = 30) -> list[dict[str, Any]]: ...
    def list_messages(self, conversation_id: str, limit: int) -> list[dict[str, Any]]: ...
    def append_message(
        self,
        conversation_id: str,
        role: Literal["user", "assistant"],
        content: str,
        outcome: str | None = None,
        proposal_id: str | None = None,
        ticket_proposal_id: str | None = None,
        trace_id: str | None = None,
    ) -> str: ...


class ConflictError(RuntimeError):
    pass


class ConversationNotFound(LookupError):
    """Missing conversation, or one owned by a different employee."""


class MemoryRepository:
    """In-memory store for deterministic tests. Identity is bound via hashed demo tokens."""

    def __init__(self, employees_path: Path | None = None) -> None:
        self.chunks: list[PolicyChunk] = []
        self._token_to_auth: dict[str, AuthContext] = {}
        self._balances: dict[str, list[LeaveBalance]] = {}
        self._proposals: dict[str, dict[str, Any]] = {}
        self._requests: list[dict[str, Any]] = []
        self._ticket_proposals: dict[str, dict[str, Any]] = {}
        self._tickets: list[dict[str, Any]] = []
        self._traces: dict[str, dict[str, Any]] = {}
        self._conversations: dict[str, dict[str, Any]] = {}
        self._message_seq = 0
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

    def list_profiles(self) -> list[AuthContext]:
        profiles: dict[str, AuthContext] = {}
        for auth in self._token_to_auth.values():
            profiles[auth.employee_id] = auth
        return list(profiles.values())

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

    def proposal_request_id(self, proposal_id: str) -> str | None:
        row = self._proposals.get(proposal_id)
        if row is None:
            return None
        request_id = row.get("request_id")
        return str(request_id) if request_id else None

    def latest_open_proposal(self, employee_id: str) -> ActionProposal | None:
        now = datetime.now(timezone.utc)
        open_items: list[ActionProposal] = []
        for row in self._proposals.values():
            if row["employee_id"] != employee_id or row.get("request_id"):
                continue
            proposal: ActionProposal = row["proposal"]
            expires_at = proposal.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                continue
            open_items.append(proposal)
        if not open_items:
            return None
        open_items.sort(key=lambda item: item.expires_at, reverse=True)
        return open_items[0]

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

    def save_ticket_proposal(self, employee_id: str, proposal: TicketProposal) -> None:
        self._ticket_proposals[proposal.proposal_id] = {
            "employee_id": employee_id,
            "proposal": proposal,
            "ticket_id": None,
            "idempotency_key": None,
            "audit_reference": None,
        }

    def get_ticket_proposal(self, proposal_id: str) -> tuple[str, TicketProposal] | None:
        row = self._ticket_proposals.get(proposal_id)
        if row is None:
            return None
        return row["employee_id"], row["proposal"]

    def ticket_proposal_ticket_id(self, proposal_id: str) -> str | None:
        row = self._ticket_proposals.get(proposal_id)
        if row is None:
            return None
        ticket_id = row.get("ticket_id")
        return str(ticket_id) if ticket_id else None

    def latest_open_ticket_proposal(self, employee_id: str) -> TicketProposal | None:
        now = datetime.now(timezone.utc)
        open_items: list[TicketProposal] = []
        for row in self._ticket_proposals.values():
            if row["employee_id"] != employee_id or row.get("ticket_id"):
                continue
            proposal: TicketProposal = row["proposal"]
            expires_at = proposal.expires_at
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                continue
            open_items.append(proposal)
        if not open_items:
            return None
        open_items.sort(key=lambda item: item.expires_at, reverse=True)
        return open_items[0]

    def confirm_ticket_proposal(
        self, employee_id: str, proposal_id: str, idempotency_key: str
    ) -> TicketResult:
        row = self._ticket_proposals.get(proposal_id)
        if row is None or row["employee_id"] != employee_id:
            raise KeyError(proposal_id)

        proposal: TicketProposal = row["proposal"]
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise ConflictError("ticket proposal expired")

        if row["ticket_id"] is not None:
            if row["idempotency_key"] == idempotency_key:
                return TicketResult(
                    ticket_id=row["ticket_id"],
                    status="open",
                    idempotent_replay=True,
                    audit_reference=row["audit_reference"],
                )
            raise ConflictError("idempotency key conflict")

        ticket_id = self.create_ticket(employee_id, proposal.category, proposal.summary)
        audit_reference = f"AUD-{uuid.uuid4().hex[:10].upper()}"
        row["ticket_id"] = ticket_id
        row["idempotency_key"] = idempotency_key
        row["audit_reference"] = audit_reference
        return TicketResult(
            ticket_id=ticket_id,
            status="open",
            idempotent_replay=False,
            audit_reference=audit_reference,
        )

    def list_tickets(self, employee_id: str) -> list[TicketView]:
        return [
            TicketView(
                ticket_id=row["ticket_id"],
                category=row["category"],
                summary=row["summary"],
                status=row.get("status") or "open",
                created_at=row["created_at"],
            )
            for row in self._tickets
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
                "status": "open",
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

    def create_conversation(self, employee_id: str) -> str:
        conversation_id = f"CV-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)
        self._conversations[conversation_id] = {
            "conversation_id": conversation_id,
            "employee_id": employee_id,
            "created_at": now,
            "updated_at": now,
            "messages": [],
        }
        return conversation_id

    def conversation_owner(self, conversation_id: str) -> str | None:
        row = self._conversations.get(conversation_id)
        if row is None:
            return None
        return str(row["employee_id"])

    def current_conversation_id(self, employee_id: str) -> str | None:
        owned = [
            row
            for row in self._conversations.values()
            if row["employee_id"] == employee_id
        ]
        if not owned:
            return None
        owned.sort(key=lambda row: row["updated_at"], reverse=True)
        return str(owned[0]["conversation_id"])

    def list_conversations(self, employee_id: str, limit: int = 30) -> list[dict[str, Any]]:
        """Return recent threads that already have a user message (skip empty drafts)."""
        safe_limit = max(1, min(int(limit), 100))
        owned = [
            row
            for row in self._conversations.values()
            if row["employee_id"] == employee_id
        ]
        owned.sort(key=lambda row: row["updated_at"], reverse=True)
        summaries: list[dict[str, Any]] = []
        for row in owned:
            if len(summaries) >= safe_limit:
                break
            title: str | None = None
            for message in row["messages"]:
                if message.get("role") == "user" and str(message.get("content") or "").strip():
                    title = str(message["content"]).strip()
                    break
            if title is None:
                continue
            if len(title) > 72:
                title = f"{title[:69].rstrip()}..."
            summaries.append(
                {
                    "conversation_id": row["conversation_id"],
                    "title": title,
                    "updated_at": row["updated_at"],
                }
            )
        return summaries

    def list_messages(self, conversation_id: str, limit: int) -> list[dict[str, Any]]:
        row = self._conversations.get(conversation_id)
        if row is None:
            return []
        safe_limit = max(1, min(int(limit), 200))
        messages = list(row["messages"])[-safe_limit:]
        return [dict(item) for item in messages]

    def append_message(
        self,
        conversation_id: str,
        role: Literal["user", "assistant"],
        content: str,
        outcome: str | None = None,
        proposal_id: str | None = None,
        ticket_proposal_id: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        row = self._conversations.get(conversation_id)
        if row is None:
            raise ConversationNotFound(conversation_id)
        self._message_seq += 1
        message_id = f"MSG-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)
        row["messages"].append(
            {
                "message_id": message_id,
                "role": role,
                "content": content,
                "outcome": outcome,
                "proposal_id": proposal_id,
                "ticket_proposal_id": ticket_proposal_id,
                "trace_id": trace_id,
                "created_at": now,
                "seq": self._message_seq,
            }
        )
        row["updated_at"] = now
        return message_id


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

    def list_profiles(self) -> list[AuthContext]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT employee_id, display_name, role FROM employees")
                rows = cur.fetchall()
        return [
            AuthContext(employee_id=row[0], display_name=row[1], role=row[2])
            for row in rows
        ]

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

    def proposal_request_id(self, proposal_id: str) -> str | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT request_id FROM action_proposals WHERE proposal_id = %s",
                    (proposal_id,),
                )
                row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return str(row[0])

    def latest_open_proposal(self, employee_id: str) -> ActionProposal | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT proposal_id, leave_type, start_date, end_date, business_days,
                           reason, validation_summary, expires_at
                    FROM action_proposals
                    WHERE employee_id = %s
                      AND request_id IS NULL
                      AND expires_at > NOW()
                    ORDER BY created_at DESC
                    LIMIT 1
                    """,
                    (employee_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return ActionProposal(
            proposal_id=row[0],
            leave_type=row[1],
            start_date=row[2],
            end_date=row[3],
            business_days=row[4],
            reason=row[5],
            validation_summary=list(row[6] or []),
            expires_at=row[7],
        )

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

    def save_ticket_proposal(self, employee_id: str, proposal: TicketProposal) -> None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ticket_proposals (
                        proposal_id, employee_id, category, summary, expires_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (proposal_id) DO UPDATE SET
                        employee_id = EXCLUDED.employee_id,
                        category = EXCLUDED.category,
                        summary = EXCLUDED.summary,
                        expires_at = EXCLUDED.expires_at
                    """,
                    (
                        proposal.proposal_id,
                        employee_id,
                        proposal.category,
                        proposal.summary,
                        proposal.expires_at,
                    ),
                )

    def get_ticket_proposal(self, proposal_id: str) -> tuple[str, TicketProposal] | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT employee_id, proposal_id, category, summary, expires_at
                    FROM ticket_proposals
                    WHERE proposal_id = %s
                    """,
                    (proposal_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return row[0], TicketProposal(
            proposal_id=row[1],
            category=row[2],
            summary=row[3],
            expires_at=row[4],
        )

    def ticket_proposal_ticket_id(self, proposal_id: str) -> str | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ticket_id FROM ticket_proposals WHERE proposal_id = %s",
                    (proposal_id,),
                )
                row = cur.fetchone()
        if row is None or row[0] is None:
            return None
        return str(row[0])

    def latest_open_ticket_proposal(self, employee_id: str) -> TicketProposal | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT proposal_id, category, summary, expires_at
                    FROM ticket_proposals
                    WHERE employee_id = %s
                      AND ticket_id IS NULL
                      AND expires_at > NOW()
                    ORDER BY expires_at DESC
                    LIMIT 1
                    """,
                    (employee_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return TicketProposal(
            proposal_id=row[0],
            category=row[1],
            summary=row[2],
            expires_at=row[3],
        )

    def confirm_ticket_proposal(
        self, employee_id: str, proposal_id: str, idempotency_key: str
    ) -> TicketResult:
        with self.pool.connection() as conn:
            conn.autocommit = False
            try:
                with conn.cursor() as cur:
                    cur.execute(
                        """
                        SELECT employee_id, category, summary, expires_at,
                               idempotency_key, ticket_id, audit_reference
                        FROM ticket_proposals
                        WHERE proposal_id = %s
                        FOR UPDATE
                        """,
                        (proposal_id,),
                    )
                    row = cur.fetchone()
                    if row is None or row[0] != employee_id:
                        raise KeyError(proposal_id)

                    expires_at = row[3]
                    if expires_at.tzinfo is None:
                        expires_at = expires_at.replace(tzinfo=timezone.utc)
                    if expires_at < datetime.now(timezone.utc):
                        raise ConflictError("ticket proposal expired")

                    existing_key, existing_ticket, existing_audit = row[4], row[5], row[6]
                    if existing_ticket is not None:
                        if existing_key == idempotency_key:
                            conn.commit()
                            return TicketResult(
                                ticket_id=existing_ticket,
                                status="open",
                                idempotent_replay=True,
                                audit_reference=existing_audit,
                            )
                        raise ConflictError("idempotency key conflict")

                    ticket_id = f"TKT-{uuid.uuid4().hex[:10].upper()}"
                    audit_reference = f"AUD-{uuid.uuid4().hex[:10].upper()}"
                    cur.execute(
                        """
                        INSERT INTO hr_tickets (ticket_id, employee_id, category, summary)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (ticket_id, employee_id, row[1], row[2]),
                    )
                    cur.execute(
                        """
                        UPDATE ticket_proposals
                        SET idempotency_key = %s,
                            ticket_id = %s,
                            audit_reference = %s
                        WHERE proposal_id = %s
                        """,
                        (idempotency_key, ticket_id, audit_reference, proposal_id),
                    )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                conn.autocommit = True

        return TicketResult(
            ticket_id=ticket_id,
            status="open",
            idempotent_replay=False,
            audit_reference=audit_reference,
        )

    def list_tickets(self, employee_id: str) -> list[TicketView]:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT ticket_id, category, summary, created_at
                    FROM hr_tickets
                    WHERE employee_id = %s
                    ORDER BY created_at DESC
                    """,
                    (employee_id,),
                )
                rows = cur.fetchall()
        return [
            TicketView(
                ticket_id=row[0],
                category=row[1],
                summary=row[2],
                status="open",
                created_at=row[3],
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

    def create_conversation(self, employee_id: str) -> str:
        conversation_id = f"CV-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO conversations (
                        conversation_id, employee_id, created_at, updated_at
                    )
                    VALUES (%s, %s, %s, %s)
                    """,
                    (conversation_id, employee_id, now, now),
                )
        return conversation_id

    def conversation_owner(self, conversation_id: str) -> str | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT employee_id FROM conversations WHERE conversation_id = %s",
                    (conversation_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return str(row[0])

    def current_conversation_id(self, employee_id: str) -> str | None:
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT conversation_id
                    FROM conversations
                    WHERE employee_id = %s
                    ORDER BY updated_at DESC
                    LIMIT 1
                    """,
                    (employee_id,),
                )
                row = cur.fetchone()
        if row is None:
            return None
        return str(row[0])

    def list_conversations(self, employee_id: str, limit: int = 30) -> list[dict[str, Any]]:
        """Return recent threads that already have a user message (skip empty drafts)."""
        safe_limit = max(1, min(int(limit), 100))
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        c.conversation_id,
                        c.updated_at,
                        first_msg.content AS first_user_message
                    FROM conversations c
                    INNER JOIN LATERAL (
                        SELECT m.content
                        FROM conversation_messages m
                        WHERE m.conversation_id = c.conversation_id
                          AND m.role = 'user'
                          AND btrim(m.content) <> ''
                        ORDER BY m.seq ASC
                        LIMIT 1
                    ) first_msg ON true
                    WHERE c.employee_id = %s
                    ORDER BY c.updated_at DESC
                    LIMIT %s
                    """,
                    (employee_id, safe_limit),
                )
                rows = cur.fetchall()
        summaries: list[dict[str, Any]] = []
        for row in rows:
            title = str(row[2]).strip()
            if len(title) > 72:
                title = f"{title[:69].rstrip()}..."
            summaries.append(
                {
                    "conversation_id": row[0],
                    "title": title,
                    "updated_at": row[1],
                }
            )
        return summaries

    def list_messages(self, conversation_id: str, limit: int) -> list[dict[str, Any]]:
        safe_limit = max(1, min(int(limit), 200))
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT message_id, role, content, outcome, proposal_id,
                           ticket_proposal_id, trace_id, created_at
                    FROM (
                        SELECT message_id, role, content, outcome, proposal_id,
                               ticket_proposal_id, trace_id, created_at, seq
                        FROM conversation_messages
                        WHERE conversation_id = %s
                        ORDER BY seq DESC
                        LIMIT %s
                    ) recent
                    ORDER BY seq ASC
                    """,
                    (conversation_id, safe_limit),
                )
                rows = cur.fetchall()
        return [
            {
                "message_id": row[0],
                "role": row[1],
                "content": row[2],
                "outcome": row[3],
                "proposal_id": row[4],
                "ticket_proposal_id": row[5],
                "trace_id": row[6],
                "created_at": row[7],
            }
            for row in rows
        ]

    def append_message(
        self,
        conversation_id: str,
        role: Literal["user", "assistant"],
        content: str,
        outcome: str | None = None,
        proposal_id: str | None = None,
        ticket_proposal_id: str | None = None,
        trace_id: str | None = None,
    ) -> str:
        message_id = f"MSG-{uuid.uuid4().hex[:12].upper()}"
        now = datetime.now(timezone.utc)
        with self.pool.connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT 1 FROM conversations WHERE conversation_id = %s",
                    (conversation_id,),
                )
                if cur.fetchone() is None:
                    raise ConversationNotFound(conversation_id)
                cur.execute(
                    """
                    INSERT INTO conversation_messages (
                        message_id, conversation_id, role, content, outcome,
                        proposal_id, ticket_proposal_id, trace_id, created_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        message_id,
                        conversation_id,
                        role,
                        content,
                        outcome,
                        proposal_id,
                        ticket_proposal_id,
                        trace_id,
                        now,
                    ),
                )
                cur.execute(
                    """
                    UPDATE conversations
                    SET updated_at = %s
                    WHERE conversation_id = %s
                    """,
                    (now, conversation_id),
                )
        return message_id

