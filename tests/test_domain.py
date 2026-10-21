from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from src.contracts import LeaveBalance, PrepareLeaveArgs
from src.domain import (
    DomainError,
    add_business_days,
    business_days,
    validate_leave_request,
)


def test_business_days_excludes_weekend() -> None:
    assert business_days(date(2026, 9, 25), date(2026, 9, 28)) == 2


def test_add_business_days_skips_weekend() -> None:
    # Wednesday + 3 business days → Monday next week
    assert add_business_days(date(2026, 9, 23), 3) == date(2026, 9, 28)


@pytest.mark.parametrize(
    "start,end,message",
    [
        (date(2026, 9, 22), date(2026, 9, 24), "masa lalu"),
        (date(2026, 9, 25), date(2026, 9, 24), "sebelum"),
        # Wednesday today; Friday is only 2 business days ahead → notice too short
        (date(2026, 9, 25), date(2026, 9, 25), "tiga hari kerja"),
    ],
)
def test_invalid_dates_are_blocked(start: date, end: date, message: str) -> None:
    args = PrepareLeaveArgs(start_date=start, end_date=end, leave_type="annual", reason=None)
    with pytest.raises(DomainError, match=message):
        validate_leave_request(
            args,
            [LeaveBalance(leave_type="annual", available_days=8, as_of_date=date(2026, 1, 1))],
            False,
            date(2026, 9, 23),
        )


def test_annual_leave_allows_start_on_third_business_day() -> None:
    # Wednesday + 3 BD = Monday 28 Sep
    args = PrepareLeaveArgs(
        start_date=date(2026, 9, 28),
        end_date=date(2026, 9, 28),
        leave_type="annual",
        reason="holiday",
    )
    days, summary = validate_leave_request(
        args,
        [LeaveBalance(leave_type="annual", available_days=8, as_of_date=date(2026, 1, 1))],
        False,
        date(2026, 9, 23),
    )
    assert days == 1
    assert "notice_business_days>=3" in summary


def test_sick_leave_up_to_two_business_days_is_allowed() -> None:
    # Mon–Tue = 2 BD → under docs threshold
    args = PrepareLeaveArgs(
        start_date=date(2026, 9, 28),
        end_date=date(2026, 9, 29),
        leave_type="sick",
        reason=None,
    )
    days, summary = validate_leave_request(
        args,
        [LeaveBalance(leave_type="sick", available_days=10, as_of_date=date(2026, 1, 1))],
        False,
        date(2026, 9, 23),
    )
    assert days == 2
    assert "sick_docs_threshold_business_days<=2" in summary


def test_sick_leave_over_two_business_days_is_blocked() -> None:
    # Mon–Wed = 3 BD → docs must go through HR system
    args = PrepareLeaveArgs(
        start_date=date(2026, 9, 28),
        end_date=date(2026, 9, 30),
        leave_type="sick",
        reason=None,
    )
    with pytest.raises(DomainError, match="dokumen pendukung"):
        validate_leave_request(
            args,
            [LeaveBalance(leave_type="sick", available_days=10, as_of_date=date(2026, 1, 1))],
            False,
            date(2026, 9, 23),
        )


def test_insufficient_balance_and_overlap_are_blocked() -> None:
    args = PrepareLeaveArgs(
        start_date=date(2026, 10, 1), end_date=date(2026, 10, 9), leave_type="annual", reason=None
    )
    balance = [LeaveBalance(leave_type="annual", available_days=2, as_of_date=date(2026, 1, 1))]
    with pytest.raises(DomainError, match="tidak cukup"):
        validate_leave_request(args, balance, False, date(2026, 9, 23))
    with pytest.raises(DomainError, match="bertumpang tindih"):
        validate_leave_request(args, balance, True, date(2026, 9, 23))


def test_unsupported_leave_type_is_rejected_by_contract() -> None:
    with pytest.raises(ValidationError):
        PrepareLeaveArgs(
            start_date=date(2026, 10, 1),
            end_date=date(2026, 10, 2),
            leave_type="study",
            reason=None,
        )
