from __future__ import annotations

from datetime import date

from src.agent import (
    AgentService,
    conversation_has_leave_dates,
    conversation_has_leave_reason,
)
from src.cache import NullCache
from src.config import Settings
from src.contracts import AuthContext, ChatRequest, ModelToolCall, ModelTurn
from src.repository import MemoryRepository
from src.retrieval import RetrievalService
from src.tools import ToolExecutor


def test_langsung_ajukan_without_dates_has_no_date_evidence() -> None:
    assert not conversation_has_leave_dates(
        "Saya mau cuti tahunan, tolong langsung ajukan."
    )
    assert conversation_has_leave_dates("Saya mau cuti tahunan besok")
    assert conversation_has_leave_dates("Siapkan cuti 2026-11-02 sampai 2026-11-03")
    assert conversation_has_leave_dates("I want leave next week")


def test_reason_evidence_requires_user_phrase() -> None:
    assert not conversation_has_leave_reason(
        "Saya mau cuti tahunan, tolong langsung ajukan."
    )
    assert conversation_has_leave_reason("Cuti tahunan untuk liburan")


def _service(repository: MemoryRepository, provider) -> AgentService:
    settings = Settings(model_mode="fake")
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=lambda: date(2026, 9, 23))
    return AgentService(repository, provider, tools, settings)


class InventDatesPrepareProvider:
    """Ignores missing dates and tries to prepare with invented ISO dates."""

    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="prep",
                tool_calls=[
                    ModelToolCall(
                        call_id="prep-1",
                        name="prepare_leave_request",
                        arguments={
                            "leave_type": "annual",
                            "start_date": "2026-09-28",
                            "end_date": "2026-09-29",
                            "reason": "keperluan pribadi",
                        },
                    )
                ],
            )
        return ModelTurn(
            response_id="after",
            text="Proposal cuti tahunan sudah siap untuk dikonfirmasi.",
        )


def test_prepare_without_user_dates_is_blocked(repository: MemoryRepository) -> None:
    response = _service(repository, InventDatesPrepareProvider()).run(
        ChatRequest(message="Saya mau cuti tahunan, tolong langsung ajukan."),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is None
    assert not any(
        item.name == "prepare_leave_request" and item.status == "ok"
        for item in response.tool_calls
    )
    assert any(
        item.name == "prepare_leave_request" and item.status == "error"
        for item in response.tool_calls
    )


class DatedPrepareProvider:
    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="search",
                tool_calls=[
                    ModelToolCall(
                        call_id="search-1",
                        name="search_hr_policy",
                        arguments={"query": "pengajuan cuti tahunan", "top_k": 3},
                    )
                ],
            )
        if self.turn == 2:
            return ModelTurn(
                response_id="prep",
                tool_calls=[
                    ModelToolCall(
                        call_id="prep-1",
                        name="prepare_leave_request",
                        arguments={
                            "leave_type": "annual",
                            "start_date": "2026-11-02",
                            "end_date": "2026-11-03",
                            "reason": None,
                        },
                    )
                ],
            )
        return ModelTurn(
            response_id="done",
            text="Proposal ready for 2026-11-02 to 2026-11-03.",
        )


def test_prepare_with_user_dates_is_allowed(repository: MemoryRepository) -> None:
    response = _service(repository, DatedPrepareProvider()).run(
        ChatRequest(
            message="Siapkan cuti tahunan dari 2026-11-02 sampai 2026-11-03"
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is not None
    assert response.action_proposal.reason is None
