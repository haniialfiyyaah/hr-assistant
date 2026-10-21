from __future__ import annotations

from datetime import date

from src.agent import (
    AgentService,
    conversation_has_leave_dates,
    conversation_has_leave_reason,
    parse_leave_duration_days,
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


def test_day_number_counts_as_dates_during_open_leave_intake() -> None:
    history = [
        {"role": "user", "content": "Saya mau cuti tahunan, tolong langsung ajukan."},
        {"role": "assistant", "content": "Tanggal mulai dan akhirnya kapan?"},
        {"role": "user", "content": "besok"},
        {"role": "assistant", "content": "Besok terlalu dekat untuk cuti tahunan."},
    ]
    assert conversation_has_leave_dates("28", history)


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


class FalseNoticeAfterDurationProvider:
    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        return ModelTurn(
            response_id="false-notice",
            text=(
                "Berdasarkan kebijakan pengajuan cuti tahunan, pengajuan harus dilakukan "
                "paling lambat tiga hari kerja sebelum tanggal mulai cuti. Karena besok "
                "adalah 22 Oktober 2026, pengajuan cuti pada tanggal 28 Oktober tidak "
                "memenuhi syarat kebijakan ini [HR-LEAVE-001:pengajuan]."
            ),
        )


def test_bare_day_number_is_not_a_duration_without_prior_start() -> None:
    assert parse_leave_duration_days("28") is None
    assert parse_leave_duration_days("4 hari") == 4
    assert parse_leave_duration_days("4 days") == 4


def test_bare_number_is_duration_after_start_date() -> None:
    history = [
        {"role": "user", "content": "Saya mau cuti tahunan, tolong langsung ajukan."},
        {"role": "assistant", "content": "Tanggal mulai?"},
        {"role": "user", "content": "29"},
        {"role": "assistant", "content": "Berapa hari kerja?"},
    ]
    assert (
        parse_leave_duration_days("4", history, today=date(2026, 10, 21)) == 4
    )
    assert parse_leave_duration_days("29", history=[], today=date(2026, 10, 21)) is None


class OneDayAssumeProvider:
    """Treats bare day-of-month as a one-day leave prepare."""

    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="prep-1day",
                tool_calls=[
                    ModelToolCall(
                        call_id="prep-1",
                        name="prepare_leave_request",
                        arguments={
                            "leave_type": "annual",
                            "start_date": "2026-10-29",
                            "end_date": "2026-10-29",
                            "reason": None,
                        },
                    )
                ],
            )
        return ModelTurn(
            response_id="done",
            text="Proposal 1 hari pada 29 Oktober siap.",
        )


def test_bare_day_does_not_prepare_one_day_leave(
    repository: MemoryRepository,
) -> None:
    settings = Settings(model_mode="fake")
    provider = OneDayAssumeProvider()
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(
        repository, retrieval, settings, today_factory=lambda: date(2026, 10, 21)
    )
    agent = AgentService(
        repository, provider, tools, settings, today_factory=lambda: date(2026, 10, 21)
    )
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(
        conversation_id, "user", "Saya mau cuti tahunan, tolong langsung ajukan."
    )
    repository.append_message(
        conversation_id, "assistant", "Tanggal mulai cutinya kapan?"
    )

    response = agent.run(
        ChatRequest(message="29", conversation_id=conversation_id),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is None
    assert "hari kerja" in response.answer.lower()
    assert any(
        item.name == "prepare_leave_request" and item.status == "error"
        for item in response.tool_calls
    )


def test_valid_start_day_asks_for_business_days(
    repository: MemoryRepository,
) -> None:
    settings = Settings(model_mode="fake")

    class SilentProvider:
        def embed(self, texts):
            return [[0.0] * 8 for _ in texts]

        def respond(self, **kwargs):
            return ModelTurn(response_id="silent", text="Okay.")

    provider = SilentProvider()
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(
        repository, retrieval, settings, today_factory=lambda: date(2026, 10, 21)
    )
    agent = AgentService(
        repository, provider, tools, settings, today_factory=lambda: date(2026, 10, 21)
    )
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(
        conversation_id, "user", "Saya mau cuti tahunan, tolong langsung ajukan."
    )
    repository.append_message(
        conversation_id, "assistant", "Tanggal mulai cutinya kapan?"
    )

    response = agent.run(
        ChatRequest(message="28", conversation_id=conversation_id),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "answered"
    assert response.action_proposal is None
    assert "hari kerja" in response.answer.lower()
    assert "2026-10-28" in response.answer


def test_besok_refuses_annual_notice_immediately(
    repository: MemoryRepository,
) -> None:
    """Prefer refuse on 'besok' right away — do not ask how many days first."""
    settings = Settings(model_mode="fake")

    class AskDurationProvider:
        def embed(self, texts):
            return [[0.0] * 8 for _ in texts]

        def respond(self, **kwargs):
            return ModelTurn(
                response_id="ask",
                text="Cuti mulai besok. Berapa lama Anda berencana untuk mengambil cuti?",
            )

    provider = AskDurationProvider()
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(
        repository, retrieval, settings, today_factory=lambda: date(2026, 10, 21)
    )
    agent = AgentService(
        repository, provider, tools, settings, today_factory=lambda: date(2026, 10, 21)
    )
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(
        conversation_id, "user", "Saya mau cuti tahunan, tolong langsung ajukan."
    )
    repository.append_message(
        conversation_id, "assistant", "Tanggal mulai cutinya kapan?"
    )

    response = agent.run(
        ChatRequest(message="besok", conversation_id=conversation_id),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert "tiga hari kerja" in response.answer.lower()
    assert "berapa lama" not in response.answer.lower()
    assert response.action_proposal is None


def test_duration_reply_prepares_valid_october_28_range(
    repository: MemoryRepository,
) -> None:
    """After accepting the 28th, '4' or '4 hari' must prepare — not invent a notice failure."""
    settings = Settings(model_mode="fake")
    retrieval = RetrievalService(
        repository, FalseNoticeAfterDurationProvider(), NullCache(), 0
    )
    tools = ToolExecutor(
        repository,
        retrieval,
        settings,
        today_factory=lambda: date(2026, 10, 21),
    )
    agent = AgentService(
        repository,
        FalseNoticeAfterDurationProvider(),
        tools,
        settings,
        today_factory=lambda: date(2026, 10, 21),
    )
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(
        conversation_id, "user", "Saya mau cuti tahunan, tolong langsung ajukan."
    )
    repository.append_message(
        conversation_id, "assistant", "Tanggal mulai cutinya kapan?"
    )
    repository.append_message(conversation_id, "user", "28")
    repository.append_message(
        conversation_id,
        "assistant",
        "Cuti tahunan akan dimulai pada tanggal 28 Oktober 2026. Berapa lama?",
    )

    response = agent.run(
        ChatRequest(message="4", conversation_id=conversation_id),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "action_proposed"
    assert response.action_proposal is not None
    assert response.action_proposal.start_date == date(2026, 10, 28)
    assert response.action_proposal.business_days == 4
    assert "tidak memenuhi" not in response.answer.lower()
