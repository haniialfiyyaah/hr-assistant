"""FastAPI application: auth, chat, confirm, traces, and monitoring."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .agent import AgentService
from .cache import NullCache, ResilientCache
from .calendar import today_in_jakarta
from .config import Settings, get_settings
from .contracts import (
    ActionProposal,
    ActionResult,
    AuthContext,
    ChatRequest,
    ChatResponse,
    ConfirmActionRequest,
    ConversationSummary,
    ConversationView,
    LeaveRequestView,
    ProblemDetail,
    ThreadMessageView,
    TicketProposal,
    TicketResult,
    TicketView,
)
from .providers import DeterministicProvider, OpenAIProvider
from .repository import (
    ConflictError,
    ConversationNotFound,
    MemoryRepository,
    PostgresRepository,
    Repository,
)
from .retrieval import RetrievalService
from .tools import ToolExecutor

ROOT = Path(__file__).resolve().parents[1]
MONITORING_RULES_PATH = ROOT / "data" / "monitoring_rules.json"


def build_runtime(settings: Settings) -> dict[str, Any]:
    """Wire repository, cache, provider, retrieval, tools, and agent for the active mode."""
    if settings.model_mode == "fake":
        repository: Repository = MemoryRepository()
        cache: ResilientCache = NullCache()
        provider: DeterministicProvider | OpenAIProvider = DeterministicProvider()
    else:
        if not settings.live_model_ready:
            raise RuntimeError(
                "Live mode requires OPENAI_API_KEY, AGENT_MODEL, and EMBEDDING_MODEL."
            )
        repository = PostgresRepository(settings.database_url, settings.embedding_dimensions)
        cache = ResilientCache(settings.redis_url) if settings.redis_url else NullCache()
        provider = OpenAIProvider(
            api_key=settings.openai_api_key or "",
            agent_model=settings.agent_model,
            embedding_model=settings.embedding_model,
            embedding_dimensions=settings.embedding_dimensions,
            base_url=settings.openai_base_url,
            timeout_seconds=settings.model_timeout_seconds,
        )

    retrieval = RetrievalService(repository, provider, cache, settings.retrieval_cache_ttl_seconds)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=today_in_jakarta)
    agent = AgentService(repository, provider, tools, settings, today_factory=today_in_jakarta)
    return {
        "repository": repository,
        "cache": cache,
        "agent": agent,
        "provider": provider,
    }


def create_app(
    *,
    settings: Settings | None = None,
    repository: Repository | None = None,
    cache: ResilientCache | None = None,
    agent: AgentService | None = None,
) -> FastAPI:
    """Build the documented API without changing endpoint or response contracts."""
    settings = settings or get_settings()
    if repository is None or cache is None or agent is None:
        runtime = build_runtime(settings)
        repository = repository or runtime["repository"]
        cache = cache or runtime["cache"]
        agent = agent or runtime["agent"]

    app = FastAPI(title=settings.app_name, version="1.0.0")
    app.state.settings = settings
    app.state.repository = repository
    app.state.cache = cache
    app.state.agent = agent

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        problem = ProblemDetail(
            title="Validation Error",
            status=422,
            detail="Request validation failed.",
        )
        return JSONResponse(status_code=422, content=problem.model_dump())

    @app.exception_handler(HTTPException)
    async def http_handler(request: Request, exc: HTTPException) -> JSONResponse:
        detail = exc.detail if isinstance(exc.detail, str) else "Request failed."
        problem = ProblemDetail(
            title="Request Error",
            status=exc.status_code,
            detail=detail,
        )
        return JSONResponse(
            status_code=exc.status_code, content={"detail": detail, **problem.model_dump()}
        )

    def require_auth(
        authorization: str | None = Header(default=None),
    ) -> AuthContext:
        if not authorization or not authorization.lower().startswith("bearer "):
            raise HTTPException(status_code=401, detail="Missing or invalid bearer token.")
        token = authorization.split(" ", 1)[1].strip()
        auth = repository.authenticate(token)
        if auth is None:
            raise HTTPException(status_code=401, detail="Invalid bearer token.")
        return auth

    @app.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> dict[str, Any]:
        db_ok = repository.health()
        cache_ok = cache.health()
        model_ok = settings.model_mode == "fake" or settings.live_model_ready
        if hasattr(repository, "index_ready"):
            index_ok = bool(repository.index_ready())
        else:
            chunks = getattr(repository, "chunks", None)
            index_ok = len(chunks) > 0 if isinstance(chunks, list) else True
        ready = db_ok and model_ok and index_ok
        return {
            "status": "ready" if ready else "not_ready",
            "database": "ok" if db_ok else "error",
            "cache": "ok" if cache_ok else "degraded",
            "model": "ok" if model_ok else "error",
            "index": "ok" if index_ok else "empty",
        }

    def visible_proposal(employee_id: str, proposal_id: str | None) -> ActionProposal | None:
        """Return a leave proposal the employee can still confirm."""
        if not proposal_id:
            return None
        if repository.proposal_request_id(proposal_id):
            return None
        found = repository.get_proposal(proposal_id)
        if found is None or found[0] != employee_id:
            return None
        proposal = found[1]
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None
        return proposal

    def visible_ticket_proposal(
        employee_id: str, proposal_id: str | None
    ) -> TicketProposal | None:
        """Return a ticket proposal the employee can still confirm."""
        if not proposal_id:
            return None
        if repository.ticket_proposal_ticket_id(proposal_id):
            return None
        found = repository.get_ticket_proposal(proposal_id)
        if found is None or found[0] != employee_id:
            return None
        proposal = found[1]
        expires_at = proposal.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            return None
        return proposal

    def conversation_view(employee_id: str, conversation_id: str | None) -> ConversationView:
        if conversation_id is None:
            return ConversationView()
        rows = repository.list_messages(conversation_id, limit=100)
        messages = [
            ThreadMessageView(
                message_id=str(row["message_id"]),
                role=row["role"],
                content=str(row["content"]),
                created_at=row["created_at"],
                outcome=row.get("outcome"),
                action_proposal=visible_proposal(employee_id, row.get("proposal_id")),
                ticket_proposal=visible_ticket_proposal(
                    employee_id, row.get("ticket_proposal_id")
                ),
                trace_id=str(row["trace_id"]) if row.get("trace_id") else None,
            )
            for row in rows
        ]
        return ConversationView(conversation_id=conversation_id, messages=messages)

    @app.get("/api/v1/conversations/current", response_model=ConversationView)
    def current_conversation(auth: AuthContext = Depends(require_auth)) -> ConversationView:
        conversation_id = repository.current_conversation_id(auth.employee_id)
        return conversation_view(auth.employee_id, conversation_id)

    @app.get("/api/v1/conversations", response_model=list[ConversationSummary])
    def list_conversations(auth: AuthContext = Depends(require_auth)) -> list[ConversationSummary]:
        rows = repository.list_conversations(auth.employee_id)
        return [
            ConversationSummary(
                conversation_id=str(row["conversation_id"]),
                title=str(row["title"]),
                updated_at=row["updated_at"],
            )
            for row in rows
        ]

    @app.get("/api/v1/conversations/{conversation_id}", response_model=ConversationView)
    def get_conversation(
        conversation_id: str, auth: AuthContext = Depends(require_auth)
    ) -> ConversationView:
        owner = repository.conversation_owner(conversation_id)
        if owner != auth.employee_id:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        return conversation_view(auth.employee_id, conversation_id)

    @app.post("/api/v1/conversations", response_model=ConversationView)
    def start_conversation(auth: AuthContext = Depends(require_auth)) -> ConversationView:
        conversation_id = repository.create_conversation(auth.employee_id)
        return ConversationView(conversation_id=conversation_id, messages=[])

    @app.post("/api/v1/chat", response_model=ChatResponse)
    def chat(body: ChatRequest, auth: AuthContext = Depends(require_auth)) -> ChatResponse:
        try:
            return agent.run(body, auth)
        except ConversationNotFound as exc:
            raise HTTPException(status_code=404, detail="Conversation not found.") from exc

    @app.post(
        "/api/v1/action-proposals/{proposal_id}/confirm",
        response_model=ActionResult,
    )
    def confirm_proposal(
        proposal_id: str,
        body: ConfirmActionRequest,
        auth: AuthContext = Depends(require_auth),
    ) -> ActionResult:
        try:
            return repository.confirm_proposal(auth.employee_id, proposal_id, body.idempotency_key)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Proposal not found.") from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.post(
        "/api/v1/ticket-proposals/{proposal_id}/confirm",
        response_model=TicketResult,
    )
    def confirm_ticket_proposal(
        proposal_id: str,
        body: ConfirmActionRequest,
        auth: AuthContext = Depends(require_auth),
    ) -> TicketResult:
        try:
            return repository.confirm_ticket_proposal(
                auth.employee_id, proposal_id, body.idempotency_key
            )
        except KeyError as exc:
            raise HTTPException(status_code=404, detail="Ticket proposal not found.") from exc
        except ConflictError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/api/v1/leave-requests/me", response_model=list[LeaveRequestView])
    def my_leave_requests(
        auth: AuthContext = Depends(require_auth),
    ) -> list[LeaveRequestView]:
        return repository.list_leave_requests(auth.employee_id)

    @app.get("/api/v1/hr-tickets/me", response_model=list[TicketView])
    def my_hr_tickets(auth: AuthContext = Depends(require_auth)) -> list[TicketView]:
        return repository.list_tickets(auth.employee_id)

    @app.get("/api/v1/traces/{trace_id}")
    def get_trace(trace_id: str, auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
        trace = repository.get_trace(trace_id)
        if trace is None:
            raise HTTPException(status_code=404, detail="Trace not found.")
        owner = trace.get("employee_id")
        if owner != auth.employee_id and auth.role != "monitoring_admin":
            raise HTTPException(status_code=403, detail="Trace access denied.")
        # Never expose raw user messages or chain-of-thought.
        safe = {key: value for key, value in trace.items() if key != "message"}
        return safe

    @app.get("/api/v1/monitoring/summary")
    def monitoring_summary(auth: AuthContext = Depends(require_auth)) -> dict[str, Any]:
        if auth.role != "monitoring_admin":
            raise HTTPException(status_code=403, detail="Monitoring access denied.")
        return repository.monitoring_summary()

    @app.get("/api/v1/monitoring/alerts")
    def monitoring_alerts(auth: AuthContext = Depends(require_auth)) -> list[dict[str, Any]]:
        if auth.role != "monitoring_admin":
            raise HTTPException(status_code=403, detail="Monitoring access denied.")
        summary = repository.monitoring_summary()
        rules = json.loads(MONITORING_RULES_PATH.read_text(encoding="utf-8"))
        alerts: list[dict[str, Any]] = []
        for rule in rules:
            metric = rule["metric"]
            value = float(summary.get(metric, 0) or 0)
            samples = int(summary.get("run_count", 0) or 0)
            if samples < int(rule.get("minimum_samples", 0)):
                continue
            operator = rule.get("operator", "gt")
            threshold = float(rule["threshold"])
            triggered = value > threshold if operator == "gt" else value < threshold
            if triggered:
                alerts.append(
                    {
                        "rule_id": rule["rule_id"],
                        "metric": metric,
                        "value": value,
                        "threshold": threshold,
                        "owner": rule.get("owner"),
                        "response": rule.get("response"),
                    }
                )
        return alerts

    return app
