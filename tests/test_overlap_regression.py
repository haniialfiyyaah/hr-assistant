"""Regression: overlapping leave must be blocked before a new proposal is saved."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src.cache import NullCache
from src.config import Settings
from src.contracts import ActionProposal, AuthContext, PrepareLeaveArgs
from src.domain import DomainError, validate_leave_request
from src.providers import DeterministicProvider
from src.repository import MemoryRepository
from src.retrieval import RetrievalService
from src.tools import ToolExecutor


def test_domain_rejects_overlap_explicitly() -> None:
    args = PrepareLeaveArgs(
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 3),
        leave_type="annual",
        reason="trip",
    )
    from src.contracts import LeaveBalance

    balances = [LeaveBalance(leave_type="annual", available_days=10, as_of_date=date(2026, 1, 1))]
    with pytest.raises(DomainError, match="bertumpang tindih"):
        validate_leave_request(args, balances, overlaps=True, today=date(2026, 9, 23))


def test_prepare_leave_blocks_overlapping_active_request(repository: MemoryRepository) -> None:
    """After a pending request exists, preparing an overlapping range must fail."""
    existing = ActionProposal(
        proposal_id="AP-EXISTING",
        leave_type="annual",
        start_date=date(2026, 11, 2),
        end_date=date(2026, 11, 3),
        business_days=2,
        validation_summary=["seed"],
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
    )
    repository.save_proposal("EMP-001", existing)
    confirmed = repository.confirm_proposal("EMP-001", "AP-EXISTING", "idem-overlap-1")
    assert confirmed.status == "pending_manager_review"
    assert repository.has_overlap("EMP-001", date(2026, 11, 2), date(2026, 11, 3)) is True

    settings = Settings(model_mode="fake", proposal_ttl_minutes=15)
    retrieval = RetrievalService(repository, DeterministicProvider(), NullCache(), 0)
    tools = ToolExecutor(
        repository, retrieval, settings, today_factory=lambda: date(2026, 9, 23)
    )
    auth = AuthContext(employee_id="EMP-001", display_name="Alya")

    before = len(repository.list_leave_requests("EMP-001"))
    with pytest.raises(DomainError, match="bertumpang tindih"):
        tools.execute(
            "prepare_leave_request",
            {
                "start_date": "2026-11-02",
                "end_date": "2026-11-03",
                "leave_type": "annual",
                "reason": "overlap attempt",
            },
            auth,
        )
    assert len(repository.list_leave_requests("EMP-001")) == before
