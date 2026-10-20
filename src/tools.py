"""Strict tool schemas and identity-bound execution."""
from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

from pydantic import ValidationError

from .config import Settings
from .contracts import (
    ActionProposal,
    AuthContext,
    ConfirmLeaveArgs,
    PrepareLeaveArgs,
    SearchPolicyArgs,
    TicketArgs,
)
from .domain import DomainError, validate_leave_request
from .repository import ConflictError, Repository
from .retrieval import RetrievalService


def _function_schema(
    name: str,
    description: str,
    properties: dict[str, Any],
    required: list[str],
) -> dict[str, Any]:
    return {
        "type": "function",
        "name": name,
        "description": description,
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": properties,
            "required": required,
            "additionalProperties": False,
        },
    }


TOOL_SCHEMAS: list[dict[str, Any]] = [
    _function_schema(
        name="search_hr_policy",
        description="Search HR policy documents and return grounded passages with metadata.",
        properties={
            "query": {"type": "string", "minLength": 2, "maxLength": 500},
            "top_k": {"type": "integer", "minimum": 1, "maximum": 5},
        },
        required=["query", "top_k"],
    ),
    _function_schema(
        name="get_my_leave_balance",
        description=(
            "Return leave balances for the authenticated employee only. "
            "Do not accept an employee_id argument."
        ),
        properties={},
        required=[],
    ),
    _function_schema(
        name="prepare_leave_request",
        description=(
            "Validate and prepare a leave request proposal. "
            "Does not create a leave request until the user confirms."
        ),
        properties={
            "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            "end_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
            "leave_type": {"type": "string", "enum": ["annual", "sick", "parental"]},
            "reason": {"type": ["string", "null"], "maxLength": 300},
        },
        required=["start_date", "end_date", "leave_type", "reason"],
    ),
    _function_schema(
        name="confirm_leave_request",
        description=(
            "Confirm a pending leave proposal after the user clearly agrees "
            "(for example confirm, yes, setuju, or ya). Creates a pending_manager_review "
            "request. Does not approve leave."
        ),
        properties={
            "proposal_id": {
                "type": ["string", "null"],
                "description": "Proposal id from the pending leave proposal, or null for the latest open one.",
            },
        },
        required=["proposal_id"],
    ),
    _function_schema(
        name="create_hr_ticket",
        description="Open an HR support ticket for escalation or exceptions.",
        properties={
            "category": {
                "type": "string",
                "enum": ["policy_question", "leave_exception", "technical_issue", "privacy"],
            },
            "summary": {"type": "string", "minLength": 5, "maxLength": 500},
        },
        required=["category", "summary"],
    ),
]


class ToolExecutor:
    def __init__(
        self,
        repository: Repository,
        retrieval: RetrievalService,
        settings: Settings,
        today_factory: Callable[[], date] | None = None,
    ) -> None:
        self.repository = repository
        self.retrieval = retrieval
        self.settings = settings
        self.today_factory = today_factory or date.today

    def execute(
        self, name: str, arguments: dict[str, Any], auth: AuthContext
    ) -> tuple[Any, ActionProposal | None]:
        """Run one tool. Private data always uses auth.employee_id from the bearer token."""
        if name == "search_hr_policy":
            args = SearchPolicyArgs.model_validate(arguments)
            chunks = self.retrieval.search(args.query, top_k=args.top_k)
            payload = [
                {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "title": chunk.title,
                    "section": chunk.section,
                    "version": chunk.version,
                    "effective_date": chunk.effective_date.isoformat(),
                    "content": chunk.content,
                    "score": chunk.score,
                }
                for chunk in chunks
            ]
            return payload, None

        if name == "get_my_leave_balance":
            # Ignore any attempted employee_id in arguments; identity is server-bound.
            balances = self.repository.get_balances(auth.employee_id)
            return [item.model_dump(mode="json") for item in balances], None

        if name == "prepare_leave_request":
            try:
                args = PrepareLeaveArgs.model_validate(arguments)
            except ValidationError as exc:
                raise DomainError(str(exc)) from exc
            balances = self.repository.get_balances(auth.employee_id)
            overlaps = self.repository.has_overlap(
                auth.employee_id, args.start_date, args.end_date
            )
            days, summary = validate_leave_request(
                args, balances, overlaps, self.today_factory()
            )
            proposal = ActionProposal(
                proposal_id=f"AP-{uuid.uuid4().hex[:12].upper()}",
                leave_type=args.leave_type,
                start_date=args.start_date,
                end_date=args.end_date,
                business_days=days,
                reason=args.reason,
                validation_summary=summary,
                expires_at=datetime.now(timezone.utc)
                + timedelta(minutes=self.settings.proposal_ttl_minutes),
            )
            self.repository.save_proposal(auth.employee_id, proposal)
            return proposal.model_dump(mode="json"), proposal

        if name == "confirm_leave_request":
            args = ConfirmLeaveArgs.model_validate(arguments)
            proposal_id = args.proposal_id
            if not proposal_id:
                latest = self.repository.latest_open_proposal(auth.employee_id)
                if latest is None:
                    raise DomainError("No pending leave proposal to confirm.")
                proposal_id = latest.proposal_id
            found = self.repository.get_proposal(proposal_id)
            if found is None or found[0] != auth.employee_id:
                raise DomainError("Pending leave proposal not found.")
            # Same stable key as the chat UI confirm button for this proposal.
            idempotency_key = f"confirm-{auth.employee_id}-{proposal_id}"
            try:
                result = self.repository.confirm_proposal(
                    auth.employee_id, proposal_id, idempotency_key
                )
            except KeyError as exc:
                raise DomainError("Pending leave proposal not found.") from exc
            except ConflictError as exc:
                raise DomainError(str(exc)) from exc
            return result.model_dump(mode="json"), None

        if name == "create_hr_ticket":
            from .security import redact

            args = TicketArgs.model_validate(arguments)
            ticket_id = self.repository.create_ticket(
                auth.employee_id, args.category, redact(args.summary)
            )
            return {"ticket_id": ticket_id, "status": "open"}, None

        raise DomainError(f"Unknown tool: {name}")
