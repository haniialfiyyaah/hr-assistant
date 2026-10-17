"""Deterministic leave-domain rules; this module must never call the model."""
from __future__ import annotations

from datetime import date, timedelta

from .contracts import LeaveBalance, PrepareLeaveArgs


class DomainError(ValueError):
    pass


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
    return days, summary


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
