"""Open proposal: status, block/replace, remind, keep→Confirm, date hard-gate."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src.agent import (
    AgentService,
    is_cancel_open_proposal_intent,
    is_keep_open_proposal_intent,
    is_replace_open_intent,
    parse_leave_duration_days,
)
from src.data.cache import NullCache
from src.config import Settings
from src.domain.contracts import (
    ActionProposal,
    AuthContext,
    ChatRequest,
    LeaveBalance,
    ModelToolCall,
    ModelTurn,
)
from src.domain import OPEN_PROPOSAL_EXISTS_PREFIX, DomainError
from src.agent.providers import ModelProvider
from src.data.repository import ConflictError, MemoryRepository
from src.data.retrieval import RetrievalService
from src.agent.tools import ToolExecutor


def _proposal(
    proposal_id: str = "AP-OLD",
    *,
    start: date = date(2026, 11, 2),
    end: date = date(2026, 11, 3),
    days: int = 2,
) -> ActionProposal:
    return ActionProposal(
        proposal_id=proposal_id,
        leave_type="annual",
        start_date=start,
        end_date=end,
        business_days=days,
        validation_summary=["seed"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )


def _tools(repository: MemoryRepository, today: date = date(2026, 9, 23)) -> ToolExecutor:
    settings = Settings(model_mode="fake", proposal_ttl_minutes=15)
    retrieval = RetrievalService(repository, _NullProvider(), NullCache(), 0)
    return ToolExecutor(repository, retrieval, settings, today_factory=lambda: today)


def _agent(
    repository: MemoryRepository,
    provider: ModelProvider,
    today: date = date(2026, 9, 23),
) -> AgentService:
    settings = Settings(model_mode="fake", proposal_ttl_minutes=15)
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=lambda: today)
    return AgentService(
        repository, provider, tools, settings, today_factory=lambda: today
    )


class _NullProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: object) -> ModelTurn:
        return ModelTurn(response_id="noop", text="ok")


class _SilentProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: object) -> ModelTurn:
        return ModelTurn(response_id="silent", text="")


class _AskDurationProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: object) -> ModelTurn:
        return ModelTurn(
            response_id="ask",
            text="Cuti dapat dimulai pada 2026-10-29. Berapa hari kerja?",
        )


class _KeepExistingProvider:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: object) -> ModelTurn:
        return ModelTurn(response_id="keep", text="Baik, tetap dengan pengajuan yang ada.")


class _WrongDatesReplaceProvider:
    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: object) -> ModelTurn:
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="prep",
                tool_calls=[
                    ModelToolCall(
                        call_id="p1",
                        name="prepare_leave_request",
                        arguments={
                            "leave_type": "annual",
                            "start_date": "2026-10-29",
                            "end_date": "2026-10-31",
                            "reason": None,
                            "replace_open": True,
                        },
                    )
                ],
            )
        return ModelTurn(response_id="done", text="Pengajuan siap.")


def test_status_supersede_and_confirm(repository: MemoryRepository) -> None:
    repository.save_proposal("EMP-001", _proposal("AP-A"))
    assert repository.latest_open_proposal("EMP-001") is not None
    assert repository.supersede_open_proposals("EMP-001") == 1
    assert repository.proposal_status("AP-A") == "superseded"
    assert repository.latest_open_proposal("EMP-001") is None

    repository.save_proposal("EMP-001", _proposal("AP-B"))
    repository.confirm_proposal("EMP-001", "AP-B", "idem-1")
    assert repository.proposal_status("AP-B") == "confirmed"
    with pytest.raises(ConflictError, match="not open"):
        repository.confirm_proposal("EMP-001", "AP-A", "idem-2")


def test_prepare_block_and_replace(repository: MemoryRepository) -> None:
    repository.save_proposal("EMP-001", _proposal())
    tools = _tools(repository)
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    with pytest.raises(DomainError, match=OPEN_PROPOSAL_EXISTS_PREFIX):
        tools.execute(
            "prepare_leave_request",
            {
                "start_date": "2026-11-09",
                "end_date": "2026-11-10",
                "leave_type": "annual",
                "reason": None,
                "replace_open": False,
            },
            auth,
        )
    _, proposal = tools.execute(
        "prepare_leave_request",
        {
            "start_date": "2026-11-09",
            "end_date": "2026-11-10",
            "leave_type": "annual",
            "reason": None,
            "replace_open": True,
        },
        auth,
    )
    assert proposal is not None
    assert repository.proposal_status("AP-OLD") == "superseded"
    assert repository.proposal_status(proposal.proposal_id) == "open"


def test_confirm_revalidates_balance(repository: MemoryRepository) -> None:
    repository.save_proposal(
        "EMP-001",
        _proposal(start=date(2026, 11, 2), end=date(2026, 11, 13), days=10),
    )
    repository._balances["EMP-001"] = [
        LeaveBalance(leave_type="annual", available_days=1, as_of_date=date(2026, 1, 1)),
    ]
    with pytest.raises(DomainError, match="Saldo cuti tidak cukup"):
        _tools(repository).execute(
            "confirm_leave_request",
            {"proposal_id": "AP-OLD"},
            AuthContext(employee_id="EMP-001", display_name="Alya"),
        )


def test_intent_helpers() -> None:
    assert is_replace_open_intent("batalkan yang lama dan buat yang baru")
    assert not is_replace_open_intent("Siapkan cuti 3 hari")
    history = [
        {
            "role": "assistant",
            "content": "Anda masih punya pengajuan cuti yang belum dikonfirmasi.",
        }
    ]
    assert is_cancel_open_proposal_intent("batalkan", history)
    assert not is_cancel_open_proposal_intent("batalkan", [])
    assert is_keep_open_proposal_intent("tidak", history)
    assert is_keep_open_proposal_intent("jangan ganti", history)
    assert not is_keep_open_proposal_intent("tidak", [])
    assert parse_leave_duration_days(
        "batalkan dan buat baru",
        [{"role": "user", "content": "cuti tanggal 29 selama 3 hari"}],
    ) == 3


def test_leave_intake_reminds_before_duration_ask(repository: MemoryRepository) -> None:
    repository.save_proposal(
        "EMP-001",
        _proposal("AP-OLD", start=date(2026, 10, 29), end=date(2026, 11, 2), days=3),
    )
    response = _agent(repository, _AskDurationProvider(), date(2026, 10, 22)).run(
        ChatRequest(message="Saya mau cuti tahunan tanggal 29"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is None
    assert "berapa hari" not in response.answer.casefold()
    assert "belum dikonfirmasi" in response.answer.casefold()


def test_decline_replace_reattaches_confirm(repository: MemoryRepository) -> None:
    repository.save_proposal(
        "EMP-001",
        _proposal("AP-OLD", start=date(2026, 10, 29), end=date(2026, 11, 2), days=3),
    )
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(
        conversation_id,
        "assistant",
        "Anda masih punya pengajuan cuti yang belum dikonfirmasi. Buat yang baru?",
        outcome="answered",
    )
    response = _agent(repository, _KeepExistingProvider(), date(2026, 10, 22)).run(
        ChatRequest(message="tidak", conversation_id=conversation_id),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is not None
    assert response.action_proposal.proposal_id == "AP-OLD"
    assert response.outcome.value == "action_proposed"


def test_replace_hard_gates_business_days(repository: MemoryRepository) -> None:
    repository.save_proposal(
        "EMP-001",
        _proposal("AP-OLD", start=date(2026, 10, 29), end=date(2026, 10, 30), days=2),
    )
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(
        conversation_id,
        "user",
        "Saya mau cuti tahunan tanggal 29 selama 3 hari",
    )
    repository.append_message(
        conversation_id,
        "assistant",
        "Anda masih punya pengajuan cuti yang belum dikonfirmasi.",
        outcome="answered",
    )
    response = _agent(repository, _WrongDatesReplaceProvider(), date(2026, 10, 22)).run(
        ChatRequest(
            message="batalkan dan buat baru",
            conversation_id=conversation_id,
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is not None
    assert response.action_proposal.start_date == date(2026, 10, 29)
    assert response.action_proposal.end_date == date(2026, 11, 2)
    assert response.action_proposal.business_days == 3
    assert repository.proposal_status("AP-OLD") == "superseded"


def test_drip_feed_replace_creates_new(repository: MemoryRepository) -> None:
    repository.save_proposal("EMP-001", _proposal())
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(
        conversation_id, "user", "Saya mau cuti tahunan mulai 2026-11-09"
    )
    repository.append_message(
        conversation_id, "assistant", "Berapa hari kerja?", outcome="answered"
    )
    response = _agent(repository, _SilentProvider()).run(
        ChatRequest(
            message="2 hari, batalkan yang lama dan buat yang baru",
            conversation_id=conversation_id,
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is not None
    assert response.action_proposal.proposal_id != "AP-OLD"
    assert repository.proposal_status("AP-OLD") == "superseded"


def test_replace_cancels_overlapping_pending_leave_request(
    repository: MemoryRepository,
) -> None:
    """Confirmed pending leave_request must be cancelled when replace_open prepares over it."""
    old = _proposal(
        "AP-OLD",
        start=date(2026, 10, 29),
        end=date(2026, 10, 30),
        days=2,
    )
    repository.save_proposal("EMP-001", old)
    repository.confirm_proposal("EMP-001", "AP-OLD", "idem-overlap")
    assert repository.has_overlap("EMP-001", date(2026, 10, 29), date(2026, 10, 30))

    tools = _tools(repository, today=date(2026, 10, 22))
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    _, proposal = tools.execute(
        "prepare_leave_request",
        {
            "start_date": "2026-10-29",
            "end_date": "2026-10-30",
            "leave_type": "annual",
            "reason": None,
            "replace_open": True,
        },
        auth,
    )
    assert proposal is not None
    assert proposal.start_date == date(2026, 10, 29)
    requests = repository.list_leave_requests("EMP-001")
    assert any(r.status == "cancelled" for r in requests)
    assert repository.proposal_status(proposal.proposal_id) == "open"


def test_replace_balance_failure_keeps_old_open(repository: MemoryRepository) -> None:
    repository.save_proposal("EMP-001", _proposal("AP-OLD"))
    repository._balances["EMP-001"] = [
        LeaveBalance(leave_type="annual", available_days=1, as_of_date=date(2026, 1, 1)),
    ]
    tools = _tools(repository)
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    with pytest.raises(DomainError, match="Saldo cuti tidak cukup"):
        tools.execute(
            "prepare_leave_request",
            {
                "start_date": "2026-11-09",
                "end_date": "2026-11-12",
                "leave_type": "annual",
                "reason": None,
                "replace_open": True,
            },
            auth,
        )
    assert repository.proposal_status("AP-OLD") == "open"
    assert repository.latest_open_proposal("EMP-001") is not None


class _BalanceFailThenLookupProvider:
    """prepare fails on balance → get_my_leave_balance → explain with saldo."""

    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs: object) -> ModelTurn:
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="prep",
                tool_calls=[
                    ModelToolCall(
                        call_id="p1",
                        name="prepare_leave_request",
                        arguments={
                            "leave_type": "annual",
                            "start_date": "2026-11-09",
                            "end_date": "2026-11-13",
                            "reason": None,
                            "replace_open": False,
                        },
                    )
                ],
            )
        if self.turn == 2:
            return ModelTurn(
                response_id="bal",
                tool_calls=[
                    ModelToolCall(
                        call_id="b1",
                        name="get_my_leave_balance",
                        arguments={},
                    )
                ],
            )
        return ModelTurn(
            response_id="explain",
            text=(
                "Saldo cuti tahunan Anda saat ini hanya 1 hari. "
                "Untuk 5 hari kerja, saldo tidak cukup."
            ),
        )


def test_agent_keeps_balance_explanation_after_get_my_leave_balance(
    repository: MemoryRepository,
) -> None:
    repository._balances["EMP-001"] = [
        LeaveBalance(leave_type="annual", available_days=1, as_of_date=date(2026, 1, 1)),
    ]
    response = _agent(
        repository, _BalanceFailThenLookupProvider(), date(2026, 9, 23)
    ).run(
        ChatRequest(
            message="Siapkan cuti tahunan dari 2026-11-09 sampai 2026-11-13"
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.action_proposal is None
    assert any(
        item.name == "get_my_leave_balance" and item.status == "ok"
        for item in response.tool_calls
    )
    assert "hanya 1 hari" in response.answer
    assert "berapa hari" not in response.answer.casefold()
