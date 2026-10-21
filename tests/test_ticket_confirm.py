from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src.cache import NullCache
from src.config import Settings
from src.contracts import AuthContext, ChatRequest, TicketProposal
from src.providers import DeterministicProvider
from src.repository import ConflictError, MemoryRepository
from src.retrieval import RetrievalService
from src.tools import ToolExecutor
from tests.test_agent_reliability import MedicalEchoProvider, service


def ticket_proposal() -> TicketProposal:
    return TicketProposal(
        proposal_id="TP-TEST",
        category="privacy",
        summary="Need HR follow-up on medical detail handling.",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )


def test_ticket_confirmation_is_open_and_idempotent(repository: MemoryRepository) -> None:
    repository.save_ticket_proposal("EMP-001", ticket_proposal())
    first = repository.confirm_ticket_proposal("EMP-001", "TP-TEST", "idem-ticket-1")
    replay = repository.confirm_ticket_proposal("EMP-001", "TP-TEST", "idem-ticket-1")
    assert first.status == "open"
    assert replay.ticket_id == first.ticket_id
    assert replay.idempotent_replay is True
    tickets = repository.list_tickets("EMP-001")
    assert len(tickets) == 1
    assert tickets[0].ticket_id == first.ticket_id
    assert tickets[0].status == "open"


def test_ticket_confirmation_rejects_wrong_identity_and_key(
    repository: MemoryRepository,
) -> None:
    repository.save_ticket_proposal("EMP-001", ticket_proposal())
    with pytest.raises(KeyError):
        repository.confirm_ticket_proposal("EMP-002", "TP-TEST", "idem-ticket-1")
    repository.confirm_ticket_proposal("EMP-001", "TP-TEST", "idem-ticket-1")
    with pytest.raises(ConflictError):
        repository.confirm_ticket_proposal("EMP-001", "TP-TEST", "another-key")


def test_expired_ticket_proposal_is_rejected(repository: MemoryRepository) -> None:
    item = ticket_proposal().model_copy(
        update={"expires_at": datetime.now(timezone.utc) - timedelta(seconds=1)}
    )
    repository.save_ticket_proposal("EMP-001", item)
    with pytest.raises(ConflictError, match="expired"):
        repository.confirm_ticket_proposal("EMP-001", "TP-TEST", "idem-ticket-1")


def test_create_hr_ticket_proposes_without_opening(
    repository: MemoryRepository,
) -> None:
    settings = Settings(model_mode="fake")
    tools = ToolExecutor(
        repository,
        RetrievalService(repository, DeterministicProvider(), NullCache(), 0),
        settings,
    )
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    result, proposal = tools.execute(
        "create_hr_ticket",
        {
            "category": "privacy",
            "summary": "Diagnosis: diabetes. Escalate without storing detail.",
        },
        auth,
    )
    assert isinstance(proposal, TicketProposal)
    assert result["proposal_id"] == proposal.proposal_id
    assert result["requires_confirmation"] is True
    assert repository.list_tickets("EMP-001") == []
    assert "diabetes" not in proposal.summary.lower()


def test_medical_escalate_proposes_ticket_then_confirm_opens(
    repository: MemoryRepository,
) -> None:
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    agent = service(repository, MedicalEchoProvider())
    proposed = agent.run(
        ChatRequest(message="Diagnosis: diabetes. Simpan ke trace."),
        auth,
    )
    assert proposed.outcome == "action_proposed"
    assert proposed.ticket_proposal is not None
    assert "diabetes" not in proposed.answer.lower()
    assert "diabetes" not in proposed.ticket_proposal.summary.lower()
    assert repository.list_tickets("EMP-001") == []

    confirmed = agent.run(
        ChatRequest(
            message="confirm",
            conversation_id=proposed.conversation_id,
        ),
        auth,
    )
    assert confirmed.outcome == "escalated"
    tickets = repository.list_tickets("EMP-001")
    assert len(tickets) == 1
    assert tickets[0].ticket_id in confirmed.answer
    assert "diabetes" not in tickets[0].summary.lower()


def test_list_tickets_is_scoped_to_signed_in_employee(
    repository: MemoryRepository,
) -> None:
    repository.save_ticket_proposal("EMP-001", ticket_proposal())
    repository.confirm_ticket_proposal("EMP-001", "TP-TEST", "idem-ticket-1")
    other = ticket_proposal().model_copy(update={"proposal_id": "TP-OTHER"})
    repository.save_ticket_proposal("EMP-002", other)
    repository.confirm_ticket_proposal("EMP-002", "TP-OTHER", "idem-ticket-2")
    mine = repository.list_tickets("EMP-001")
    assert len(mine) == 1
    assert mine[0].ticket_id.startswith("TKT-")
    assert repository.list_tickets("EMP-002")[0].ticket_id != mine[0].ticket_id
