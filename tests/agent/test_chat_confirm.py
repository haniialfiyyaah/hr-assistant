from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from fastapi.testclient import TestClient

from src.agent import AgentService, is_confirm_intent
from src.api import create_app
from src.data.cache import NullCache
from src.domain.contracts import ActionProposal, ModelToolCall, ModelTurn
from src.data.repository import MemoryRepository
from src.data.retrieval import RetrievalService
from src.agent.tools import ToolExecutor


def test_disetujui_is_not_confirm_intent() -> None:
    assert not is_confirm_intent(
        "Saldo cuti orang tua saya 60 hari. Berarti durasi saya sudah disetujui?"
    )
    assert not is_confirm_intent("Apakah cuti saya sudah disetujui?")
    assert is_confirm_intent("confirm")
    assert is_confirm_intent("setuju")
    assert is_confirm_intent("ya, saya setuju")
    assert is_confirm_intent("please confirm the proposal")

ALYA = {"Authorization": "Bearer token-alya"}


class ConfirmToolProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: Any) -> ModelTurn:
        blob = kwargs.get("input_data")
        text = blob if isinstance(blob, str) else str(blob)
        if "function_call_output" in text or "request_id" in text:
            return ModelTurn(
                response_id="done",
                text="Your leave request is now pending manager review.",
                input_tokens=1,
                output_tokens=1,
            )
        return ModelTurn(
            response_id="confirm-tool",
            tool_calls=[
                ModelToolCall(
                    call_id="confirm-1",
                    name="confirm_leave_request",
                    arguments={"proposal_id": None},
                )
            ],
            input_tokens=1,
            output_tokens=1,
        )


class SilentConfirmProvider:
    """Does not call the confirm tool; the server fallback should still confirm."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: Any) -> ModelTurn:
        return ModelTurn(response_id="silent", text="Okay.", input_tokens=1, output_tokens=1)


def _seed_proposal(repository: MemoryRepository) -> ActionProposal:
    proposal = ActionProposal(
        proposal_id="AP-CHATCONFIRM",
        leave_type="annual",
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 3),
        business_days=2,
        reason="family",
        validation_summary=["ok"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    repository.save_proposal("EMP-001", proposal)
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(conversation_id, "user", "Prepare leave")
    repository.append_message(
        conversation_id,
        "assistant",
        "Proposal ready.",
        outcome="action_proposed",
        proposal_id=proposal.proposal_id,
    )
    return proposal


def test_chat_confirm_tool_creates_pending_request(
    repository: MemoryRepository, settings
) -> None:
    proposal = _seed_proposal(repository)
    conversation_id = repository.current_conversation_id("EMP-001")
    provider = ConfirmToolProvider()
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings)
    agent = AgentService(repository, provider, tools, settings)
    client = TestClient(
        create_app(settings=settings, repository=repository, cache=NullCache(), agent=agent)
    )

    response = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "confirm", "conversation_id": conversation_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "answered"
    assert "pending" in body["answer"].lower()
    assert any(item["name"] == "confirm_leave_request" for item in body["tool_calls"])
    requests = repository.list_leave_requests("EMP-001")
    assert len(requests) == 1
    assert requests[0].status == "pending_manager_review"
    assert repository.proposal_request_id(proposal.proposal_id)


def test_chat_confirm_fallback_without_tool_call(
    repository: MemoryRepository, settings
) -> None:
    _seed_proposal(repository)
    conversation_id = repository.current_conversation_id("EMP-001")
    provider = SilentConfirmProvider()
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings)
    agent = AgentService(repository, provider, tools, settings)
    client = TestClient(
        create_app(settings=settings, repository=repository, cache=NullCache(), agent=agent)
    )

    response = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={"message": "confirm", "conversation_id": conversation_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["outcome"] == "answered"
    assert "LR-" in body["answer"] or "pending_manager_review" in body["answer"]
    assert repository.list_leave_requests("EMP-001")


def test_disetujui_question_does_not_auto_confirm_pending_proposal(
    repository: MemoryRepository, settings
) -> None:
    _seed_proposal(repository)
    conversation_id = repository.current_conversation_id("EMP-001")
    provider = SilentConfirmProvider()
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings)
    agent = AgentService(repository, provider, tools, settings)
    client = TestClient(
        create_app(settings=settings, repository=repository, cache=NullCache(), agent=agent)
    )

    response = client.post(
        "/api/v1/chat",
        headers=ALYA,
        json={
            "message": (
                "Saldo cuti orang tua saya 60 hari. Berarti durasi saya sudah disetujui?"
            ),
            "conversation_id": conversation_id,
        },
    )
    assert response.status_code == 200
    assert not repository.list_leave_requests("EMP-001")
    assert "pending_manager_review" not in response.json()["answer"]
