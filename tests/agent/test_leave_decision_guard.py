from __future__ import annotations

from datetime import date

from src.agent import (
    AgentService,
    requires_leave_decision_policy_search,
)
from src.data.cache import NullCache
from src.config import Settings
from src.domain.contracts import AuthContext, ChatRequest, ModelToolCall, ModelTurn
from src.data.repository import MemoryRepository
from src.data.retrieval import RetrievalService
from src.agent.tools import ToolExecutor


def test_parental_duration_question_requires_policy_search() -> None:
    assert requires_leave_decision_policy_search(
        "Saldo cuti orang tua saya 60 hari. Berarti durasi saya sudah disetujui?"
    )
    assert not requires_leave_decision_policy_search("Berapa saldo cuti saya?")


def _service(repository: MemoryRepository, provider) -> AgentService:
    settings = Settings(model_mode="fake")
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=lambda: date(2026, 9, 23))
    return AgentService(repository, provider, tools, settings)


class WrongCrossEmployeeProvider:
    """Misreads 'orang tua' as another employee and answers without tools."""

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        return ModelTurn(
            response_id="wrong",
            text=(
                "Saya tidak dapat memberikan informasi tentang saldo cuti orang lain. "
                "Saya hanya dapat melaporkan saldo cuti untuk karyawan yang sedang masuk."
            ),
        )


class GroundedParentalDecisionProvider:
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
                        arguments={
                            "query": "cuti orang tua durasi disetujui HR",
                            "top_k": 3,
                        },
                    )
                ],
            )
        return ModelTurn(
            response_id="grounded",
            text=(
                "Tidak. Saldo 60 hari bukan berarti durasi sudah disetujui. "
                "Keputusan kelayakan dan durasi akhir ditentukan oleh tim HR "
                "[HR-LEAVE-003]."
            ),
        )


def test_ungrounded_parental_approval_question_is_abstained(
    repository: MemoryRepository,
) -> None:
    response = _service(repository, WrongCrossEmployeeProvider()).run(
        ChatRequest(
            message=(
                "Saldo cuti orang tua saya 60 hari. Berarti durasi saya sudah disetujui?"
            )
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert "already approved" in response.answer.lower() or "duration" in response.answer.lower()
    assert "orang lain" not in response.answer.lower()


def test_grounded_parental_approval_answer_is_accepted(
    repository: MemoryRepository,
) -> None:
    response = _service(repository, GroundedParentalDecisionProvider()).run(
        ChatRequest(
            message=(
                "Saldo cuti orang tua saya 60 hari. Berarti durasi saya sudah disetujui?"
            )
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "answered"
    assert any(item.document_id == "HR-LEAVE-003" for item in response.citations)
    assert "hr" in response.answer.lower() or "tidak" in response.answer.lower()
