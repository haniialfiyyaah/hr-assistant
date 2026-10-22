from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from src.agent import AgentService
from src.data.cache import NullCache
from src.config import Settings
from src.domain.contracts import (
    ActionProposal,
    AuthContext,
    ChatRequest,
    ModelToolCall,
    ModelTurn,
)
from src.data.repository import MemoryRepository
from src.data.retrieval import RetrievalService
from src.setup_lab import ROOT, chunk_policy
from src.agent.tools import ToolExecutor


class FailingProvider:
    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        raise TimeoutError("provider timeout for secret-token_ABCDEF123")


class BadCitationProvider:
    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="one",
                tool_calls=[
                    ModelToolCall(
                        call_id="search", name="search_hr_policy", arguments={"query": "cuti tahunan", "top_k": 3}
                    )
                ],
            )
        return ModelTurn(response_id="two", text="Jawaban tanpa bukti [HR-FAKE-999].")


def service(repository: MemoryRepository, provider) -> AgentService:
    settings = Settings(model_mode="fake")
    retrieval = RetrievalService(repository, provider, NullCache(), 0)
    tools = ToolExecutor(repository, retrieval, settings, today_factory=lambda: date(2026, 9, 23))
    return AgentService(repository, provider, tools, settings)


def test_provider_failure_is_side_effect_free_and_redacted(repository: MemoryRepository) -> None:
    response = service(repository, FailingProvider()).run(
        ChatRequest(message="Tolong jawab"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert not repository.list_leave_requests("EMP-001")
    trace = repository.get_trace(response.trace_id)
    assert "ABCDEF123" not in trace["error"]


def test_invalid_citation_forces_abstention(repository: MemoryRepository) -> None:
    response = service(repository, BadCitationProvider()).run(
        ChatRequest(message="Berapa cuti tahunan?"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert response.citations == []


class UngroundedProvider:
    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        return ModelTurn(
            response_id="freeform",
            text="Subsidi perjalanan ke Mars adalah 1 juta kredit.",
        )


class FailedPrepareProvider:
    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="prepare",
                tool_calls=[
                    ModelToolCall(
                        call_id="prep-1",
                        name="prepare_leave_request",
                        arguments={
                            "leave_type": "annual",
                            "start_date": "2025-01-02",
                            "end_date": "2025-01-02",
                            "reason": None,
                        },
                    )
                ],
            )
        return ModelTurn(
            response_id="after-fail",
            text="Saya sudah ajukan cuti untuk tanggal itu.",
        )


class MedicalEchoProvider:
    def __init__(self) -> None:
        self.turn = 0

    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        self.turn += 1
        if self.turn == 1:
            return ModelTurn(
                response_id="ticket",
                tool_calls=[
                    ModelToolCall(
                        call_id="ticket-1",
                        name="create_hr_ticket",
                        arguments={
                            "category": "privacy",
                            "summary": "Diagnosis: diabetes. Simpan ke trace.",
                        },
                    )
                ],
            )
        return ModelTurn(
            response_id="echo",
            text="Tiket dibuat untuk kasus diagnosis diabetes.",
        )


def test_ungrounded_answer_is_abstained(repository: MemoryRepository) -> None:
    response = service(repository, UngroundedProvider()).run(
        ChatRequest(message="Berapa subsidi perjalanan ke Mars?"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    # Off-topic free-form must not leak the model answer into chat.
    assert "Mars" not in response.answer
    assert "kebijakan HR" in response.answer or "HR policy" in response.answer
    assert response.citations == []


def test_offtopic_math_is_refused(repository: MemoryRepository) -> None:
    class MathProvider:
        def embed(self, texts):
            return [[0.0] * 8 for _ in texts]

        def respond(self, **kwargs):
            return ModelTurn(response_id="math", text="2 + 2 = 4")

    response = service(repository, MathProvider()).run(
        ChatRequest(message="What is 2 + 2?"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert "2 + 2 = 4" not in response.answer
    assert "HR policy" in response.answer
    assert response.citations == []


def test_offtopic_keeps_model_refusal_wording(repository: MemoryRepository) -> None:
    class ModelRefuseProvider:
        def embed(self, texts):
            return [[0.0] * 8 for _ in texts]

        def respond(self, **kwargs):
            return ModelTurn(
                response_id="refuse",
                text=(
                    "I only help with HR topics here — I cannot help with coding questions."
                ),
            )

    response = service(repository, ModelRefuseProvider()).run(
        ChatRequest(message="Write a Python sort function"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert "cannot help with coding" in response.answer
    assert "Python sort" not in response.answer


class LeaveClarifyProvider:
    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        return ModelTurn(
            response_id="clarify",
            text="Which leave type do you need, and how many business days next week?",
        )


class LeaveSilentProvider:
    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        return ModelTurn(response_id="silent", text="Leave approved for everyone.")


def test_incomplete_leave_request_keeps_clarifying_question(
    repository: MemoryRepository,
) -> None:
    response = service(repository, LeaveClarifyProvider()).run(
        ChatRequest(message="I want to take leave next week"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "answered"
    assert "how many" in response.answer.lower()
    assert response.action_proposal is None


def test_incomplete_leave_request_gets_default_clarify_when_model_invents(
    repository: MemoryRepository,
) -> None:
    response = service(repository, LeaveSilentProvider()).run(
        ChatRequest(message="I want to take leave next week"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "answered"
    assert "Which type do you need" in response.answer
    assert "approved" not in response.answer.lower()


class PendingProposalTalkProvider:
    def embed(self, texts):
        return [[0.0] * 8 for _ in texts]

    def respond(self, **kwargs):
        return ModelTurn(
            response_id="pending-talk",
            text=(
                "I see that there is already a pending proposal for your annual leave "
                "from October 26 to October 28, 2026. Please confirm if you would like "
                "me to proceed with it."
            ),
        )


def test_pending_proposal_reply_is_not_replaced_by_leave_clarify(
    repository: MemoryRepository,
) -> None:
    proposal = ActionProposal(
        proposal_id="AP-PENDINGTALK",
        leave_type="annual",
        start_date=date(2026, 10, 26),
        end_date=date(2026, 10, 28),
        business_days=3,
        reason=None,
        validation_summary=["ok"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=15),
    )
    repository.save_proposal("EMP-001", proposal)
    conversation_id = repository.create_conversation("EMP-001")
    repository.append_message(conversation_id, "user", "I want annual leave")
    repository.append_message(
        conversation_id,
        "assistant",
        "Proposal ready.",
        outcome="action_proposed",
        proposal_id=proposal.proposal_id,
    )

    response = service(repository, PendingProposalTalkProvider()).run(
        ChatRequest(
            message="Saya mau cuti tahunan, tolong langsung ajukan.",
            conversation_id=conversation_id,
        ),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert "pending proposal" in response.answer.lower()
    assert "Which type do you need" not in response.answer
    assert response.action_proposal is None


def test_short_leave_follow_up_keeps_thread_context(
    repository: MemoryRepository,
) -> None:
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    agent = service(repository, LeaveClarifyProvider())
    first = agent.run(ChatRequest(message="I want to take leave next week"), auth)
    second = agent.run(
        ChatRequest(message="2 days", conversation_id=first.conversation_id),
        auth,
    )
    assert second.outcome == "answered"
    assert "I do not have enough policy evidence" not in second.answer


def test_policy_then_identity_does_not_force_leave_clarify(
    repository: MemoryRepository,
) -> None:
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    agent = service(repository, LeaveSilentProvider())
    first = agent.run(
        ChatRequest(message="How many annual leave days do permanent employees get?"),
        auth,
    )
    second = agent.run(
        ChatRequest(
            message="What employee am I",
            conversation_id=first.conversation_id,
        ),
        auth,
    )
    assert "Which type do you need" not in second.answer


def test_drip_feed_leave_details_stay_in_intake(
    repository: MemoryRepository,
) -> None:
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")
    agent = service(repository, LeaveSilentProvider())
    first = agent.run(
        ChatRequest(message="I want to take leave at 24 october"),
        auth,
    )
    second = agent.run(
        ChatRequest(message="No, maybe 22", conversation_id=first.conversation_id),
        auth,
    )
    third = agent.run(
        ChatRequest(message="annual leave", conversation_id=first.conversation_id),
        auth,
    )
    assert "I do not have enough policy evidence" not in third.answer
    assert second.outcome == "answered"
    assert third.outcome == "answered"


def test_failed_prepare_forces_abstention(repository: MemoryRepository) -> None:
    response = service(repository, FailedPrepareProvider()).run(
        ChatRequest(message="Ajukan cuti tahunan 2025-01-02"),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    assert response.outcome == "abstained"
    assert response.action_proposal is None


def test_medical_detail_is_redacted_from_answer(repository: MemoryRepository) -> None:
    response = service(repository, MedicalEchoProvider()).run(
        ChatRequest(message="Diagnosis: diabetes. Simpan ke trace."),
        AuthContext(employee_id="EMP-001", display_name="Alya"),
    )
    # Ticket is proposed first; diagnosis stays redacted until/after confirm.
    assert response.outcome == "action_proposed"
    assert response.ticket_proposal is not None
    assert "diabetes" not in response.answer.lower()
    assert "diabetes" not in response.ticket_proposal.summary.lower()
    assert repository.list_tickets("EMP-001") == []


def test_policy_chunk_ids_and_metadata_are_stable() -> None:
    path = ROOT / "data" / "policies" / "annual-leave.md"
    first = chunk_policy(path)
    second = chunk_policy(path)
    assert first == second
    assert first[0]["document_id"] == "HR-LEAVE-001"
    assert first[0]["version"] == "2.1"
    assert first[0]["effective_date"] == "2026-01-01"

