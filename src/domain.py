"""Deterministic leave-domain rules; this module must never call the model."""

from __future__ import annotations

from datetime import date, timedelta

from typing import Literal, cast

from .contracts import ActionProposal, LeaveBalance, PrepareLeaveArgs


class DomainError(ValueError):
    pass


# Prefix so the agent can detect a blocked prepare and remind without a Confirm card.
OPEN_PROPOSAL_EXISTS_PREFIX = "OPEN_PROPOSAL_EXISTS|"


# HR-LEAVE-001: submit at least this many business days before the start date.
ANNUAL_LEAVE_NOTICE_BUSINESS_DAYS = 3
# HR-LEAVE-002: consecutive sick leave above this many business days needs docs via HR system.
SICK_LEAVE_DOCS_THRESHOLD_BUSINESS_DAYS = 2


def business_days(start: date, end: date) -> int:
    """Count inclusive weekdays between start and end (Saturday/Sunday excluded)."""
    if end < start:
        raise DomainError("Tanggal akhir tidak boleh sebelum tanggal mulai.")
    days = 0
    current = start
    while current <= end:
        if current.weekday() < 5:
            days += 1
        current += timedelta(days=1)
    if days == 0:
        raise DomainError("Rentang tanggal tidak mengandung hari kerja.")
    return days


def add_business_days(day: date, count: int) -> date:
    """Return the date that is `count` weekdays after `day` (not counting `day`)."""
    if count < 0:
        raise DomainError("Business-day offset must be non-negative.")
    current = day
    seen = 0
    while seen < count:
        current += timedelta(days=1)
        if current.weekday() < 5:
            seen += 1
    return current


def validate_leave_request(
    args: PrepareLeaveArgs,
    balances: list[LeaveBalance],
    overlaps: bool,
    today: date,
) -> tuple[int, list[str]]:
    """Validate a leave proposal and return business days plus a human summary."""
    if args.start_date < today:
        raise DomainError("Tanggal mulai tidak boleh di masa lalu.")
    if args.end_date < args.start_date:
        raise DomainError("Tanggal akhir tidak boleh sebelum tanggal mulai.")
    if overlaps:
        raise DomainError("Permintaan cuti bertumpang tindih dengan permintaan aktif.")

    if args.leave_type == "annual":
        earliest = add_business_days(today, ANNUAL_LEAVE_NOTICE_BUSINESS_DAYS)
        if args.start_date < earliest:
            raise DomainError(
                "Pengajuan cuti tahunan harus paling lambat tiga hari kerja "
                "sebelum tanggal mulai."
            )

    days = business_days(args.start_date, args.end_date)

    available = next(
        (item.available_days for item in balances if item.leave_type == args.leave_type),
        0,
    )
    if days > available:
        raise DomainError("Saldo cuti tidak cukup untuk rentang tanggal ini.")

    summary = [
        f"leave_type={args.leave_type}",
        f"business_days={days}",
        f"available_days={available}",
        "overlap=false",
    ]
    if args.leave_type == "annual":
        summary.append(f"notice_business_days>={ANNUAL_LEAVE_NOTICE_BUSINESS_DAYS}")
    # HR-LEAVE-002: prepare is allowed; supporting docs go via HR system (not chat).
    if args.leave_type == "sick":
        if days > SICK_LEAVE_DOCS_THRESHOLD_BUSINESS_DAYS:
            summary.append("sick_docs_via_hr=required")
        else:
            summary.append("sick_docs_via_hr=not_required")
    return days, summary


def open_proposal_exists_error(proposal: ActionProposal) -> DomainError:
    """Structured domain error when prepare is blocked by an open proposal."""
    return DomainError(
        f"{OPEN_PROPOSAL_EXISTS_PREFIX}"
        f"{proposal.proposal_id}|{proposal.leave_type}|"
        f"{proposal.start_date.isoformat()}|{proposal.end_date.isoformat()}|"
        f"{proposal.business_days}"
    )


def parse_open_proposal_exists_error(message: str) -> ActionProposal | None:
    """Parse OPEN_PROPOSAL_EXISTS payload; returns a minimal proposal or None."""
    text = (message or "").strip()
    if not text.startswith(OPEN_PROPOSAL_EXISTS_PREFIX):
        return None
    parts = text[len(OPEN_PROPOSAL_EXISTS_PREFIX) :].split("|")
    if len(parts) != 5:
        return None
    proposal_id, leave_type, start_s, end_s, days_s = parts
    try:
        from datetime import datetime, timezone

        return ActionProposal(
            proposal_id=proposal_id,
            leave_type=leave_type,
            start_date=date.fromisoformat(start_s),
            end_date=date.fromisoformat(end_s),
            business_days=int(days_s),
            reason=None,
            validation_summary=["open"],
            expires_at=datetime.now(timezone.utc),
        )
    except ValueError:
        return None


def validate_action_proposal(
    proposal: ActionProposal,
    balances: list[LeaveBalance],
    overlaps: bool,
    today: date,
) -> tuple[int, list[str]]:
    """Re-run leave domain gates for confirm / create."""
    leave_type = proposal.leave_type
    if leave_type not in ("annual", "sick", "parental"):
        raise DomainError("Jenis cuti tidak valid.")
    args = PrepareLeaveArgs(
        start_date=proposal.start_date,
        end_date=proposal.end_date,
        leave_type=cast(Literal["annual", "sick", "parental"], leave_type),
        reason=proposal.reason,
    )
    return validate_leave_request(args, balances, overlaps, today)


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    input_rate: float | None,
    output_rate: float | None,
) -> float | None:
    """Estimate USD cost from per-1M token rates; None when rates are not configured."""
    if input_rate is None or output_rate is None:
        return None
    return (input_tokens * input_rate + output_tokens * output_rate) / 1_000_000.0
