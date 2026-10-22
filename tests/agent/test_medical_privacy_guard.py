from __future__ import annotations

from datetime import date

from src.agent import AgentService, requires_medical_privacy_search
from src.data.cache import NullCache
from src.config import Settings
from src.domain.contracts import AuthContext, ChatRequest, ModelToolCall, ModelTurn
from src.data.repository import MemoryRepository
from src.data.retrieval import RetrievalService
from src.agent.tools import ToolExecutor


def test_diagnosis_in_chat_question_requires_search() -> None:
    assert requires_medical_privacy_search(
        "Saya sakit tiga hari. Boleh saya kirim diagnosis di chat ini?"
    )
    assert requires_medical_privacy_search(
        "Can I send my diagnosis in this chat?"
    )
    assert not requires_medical_privacy_search("Saya sakit tiga hari")
    assert not requires_medical_privacy_search("Berapa jatah cuti tahunan?")


def _service(repository: MemoryRepository, provider) -> AgentService:
    settings = Settings(model_mode="fake")
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=lambda: date(2026, 9, 23))
    return AgentService(repository, provider, tools, settings)


class UngroundedMedicalPrivacyProvider:
    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        return ModelTurn(
            response_id="ungrounded",
            text=(
                "Saya tidak dapat menerima informasi mengenai diagnosis. "
                "Jika cuti sakit lebih dari dua hari, buat tiket HR."
            ),
        )


class GroundedMedicalPrivacyProvider:
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
                        arguments={"query": "diagnosis cuti sakit privasi chat", "top_k": 3},
                    )
                ],
            )
        return ModelTurn(
            response_id="grounded",
            text=(
                "Tidak. Asisten tidak boleh menerima atau menyimpan diagnosis di chat; "
                "kirim melalui kanal HR yang disetujui [HR-LEAVE-002]."
            ),
        )


def test_ungrounded_diagnosis_chat_answer_is_abstained(
    repository: MemoryRepository,
) -> None:
    response = _service(repository, UngroundedMedicalPrivacyProvider()).run(
        ChatRequest(
            message="Saya sakit tiga hari. Boleh saya kirim diagnosis di chat ini?"
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert response.citations == []
    assert "grounded policy evidence" in response.answer.lower()


class SearchedMedicalPrivacyWithoutCitationProvider:
    """Search succeeds; model answers correctly but omits [DOCUMENT_ID] markers."""

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
                        arguments={"query": "kirim diagnosis di chat privasi", "top_k": 3},
                    )
                ],
            )
        return ModelTurn(
            response_id="no-cite",
            text=(
                "Tidak. Anda tidak boleh mengirim diagnosis di chat ini. "
                "Informasi medis harus melalui kanal HR yang disetujui."
            ),
        )


def test_grounded_diagnosis_chat_answer_is_accepted(
    repository: MemoryRepository,
) -> None:
    response = _service(repository, GroundedMedicalPrivacyProvider()).run(
        ChatRequest(
            message="Saya sakit tiga hari. Boleh saya kirim diagnosis di chat ini?"
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "answered"
    assert any(item.document_id == "HR-LEAVE-002" for item in response.citations)
    assert "diagnosis" in response.answer.lower()
    assert "[REDACTED_MEDICAL]" not in response.answer


def test_searched_diagnosis_answer_backfills_citation(
    repository: MemoryRepository,
) -> None:
    response = _service(
        repository, SearchedMedicalPrivacyWithoutCitationProvider()
    ).run(
        ChatRequest(
            message="Saya sakit tiga hari. Boleh saya kirim diagnosis di chat ini?"
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "answered"
    assert any(item.document_id == "HR-LEAVE-002" for item in response.citations)
    assert "[HR-LEAVE-002]" in response.answer
    assert "tidak boleh" in response.answer.lower()
