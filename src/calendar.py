"""Fixed Asia/Jakarta calendar facts for the agent. This module never calls the model."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

JAKARTA = ZoneInfo("Asia/Jakarta")


def today_in_jakarta() -> date:
    """Current calendar date in Asia/Jakarta, independent of the server's UTC date."""
    return datetime.now(JAKARTA).date()


def business_week(day: date) -> tuple[date, date]:
    """Monday and Friday of the week that contains `day`."""
    monday = day - timedelta(days=day.weekday())
    friday = monday + timedelta(days=4)
    return monday, friday


def next_business_week(day: date) -> tuple[date, date]:
    """Monday and Friday of the following week."""
    monday, _friday = business_week(day)
    return business_week(monday + timedelta(days=7))


def first_business_days(start: date, count: int) -> tuple[date, date]:
    """First and last date covering `count` weekdays beginning at `start`.

    Saturday and Sunday are skipped. Public holidays are not.
    """
    if count < 1:
        raise ValueError("count must be positive")
    current = start
    while current.weekday() >= 5:
        current += timedelta(days=1)
    first = current
    remaining = count - 1
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return first, current


def calendar_brief(today: date) -> str:
    """Trusted date block inserted into the system prompt for one run."""
    tomorrow = today + timedelta(days=1)
    this_monday, this_friday = business_week(today)
    next_monday, next_friday = next_business_week(today)
    two_start, two_end = first_business_days(next_monday, 2)
    return "\n".join(
        [
            "Trusted calendar (Asia/Jakarta). Weekends are Saturday and Sunday.",
            "Public holidays are not excluded.",
            f"Today is {today.isoformat()} ({today.strftime('%A')}).",
            f"Tomorrow is {tomorrow.isoformat()} ({tomorrow.strftime('%A')}).",
            f"This week Monday-Friday is {this_monday.isoformat()} to {this_friday.isoformat()}.",
            f"Next week Monday-Friday is {next_monday.isoformat()} to {next_friday.isoformat()}.",
            (
                "The first two business days of next week are "
                f"{two_start.isoformat()} to {two_end.isoformat()}."
            ),
        ]
    )
