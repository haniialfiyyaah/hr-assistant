"""Leave intake: date/duration parsing and request-intent detection."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any

_LEAVE_WORDS = (
    "leave",
    "cuti",
    "annual",
    "sick",
    "parental",
    "tahunan",
    "sakit",
)
_LEAVE_REQUEST_CUES = (
    "want",
    "take",
    "prepare",
    "request",
    "book",
    "ajukan",
    "siapkan",
    "ambil",
    "mau",
)
_RELATIVE_DATE_WORDS = (
    "next week",
    "this week",
    "minggu depan",
    "minggu ini",
    "tomorrow",
    "besok",
    "today",
    "hari ini",
)
_DATE_EVIDENCE_WORDS = _RELATIVE_DATE_WORDS + (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "senin",
    "selasa",
    "rabu",
    "kamis",
    "jumat",
    "jum'at",
    "this friday",
    "next friday",
    "jumat ini",
    "jumat depan",
)
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_LOOSE_DATE_RE = re.compile(
    r"\b\d{1,2}[/\-.]\d{1,2}(?:[/\-.]\d{2,4})?\b"
    r"|\b\d{1,2}\s+"
    r"(jan|feb|mar|apr|mei|may|jun|jul|agu|aug|sep|okt|oct|nov|des|dec)[a-z]*\b"
    r"|\b(jan|feb|mar|apr|mei|may|jun|jul|agu|aug|sep|okt|oct|nov|des|dec)[a-z]*"
    r"\s+\d{1,2}\b",
    re.IGNORECASE,
)
_DURATION_RE = re.compile(
    r"^\s*(\d{1,2})\s*(?:hari(?:\s+kerja)?|days?(?:\s+business)?|business\s+days?)\s*$",
    re.IGNORECASE,
)
_DURATION_EMBEDDED_RE = re.compile(
    r"(?:for|selama)\s+(\d{1,2})\s*(?:hari(?:\s+kerja)?|days?(?:\s+business)?|business\s+days?)"
    r"|(\d{1,2})\s*(?:hari(?:\s+kerja)?|days?(?:\s+business)?|business\s+days?)",
    re.IGNORECASE,
)
_DAY_OF_MONTH_RE = re.compile(
    r"(?:tanggal|tgl\.?)\s+(\d{1,2})\b"
    r"|\bin\s+(\d{1,2})\b"
    r"|\bon\s+(?:the\s+)?(\d{1,2})\b",
    re.IGNORECASE,
)
BARE_NUMBER_RE = re.compile(r"^\s*(\d{1,2})\s*$")
_NOTICE_FAILURE_CUES = (
    "tiga hari kerja",
    "three business day",
    "tidak memenuhi",
    "does not meet",
    "paling lambat tiga",
)
_REASON_EVIDENCE_WORDS = (
    "holiday",
    "liburan",
    "family",
    "keluarga",
    "urusan",
    "wedding",
    "pernikahan",
    "travel",
    "trip",
    "alasan",
    "because",
    "untuk ",
    "for ",
)
_ID_LANGUAGE_HINTS = (
    "berapa",
    "saya",
    "anda",
    "yang",
    "untuk",
    "tidak",
    "boleh",
    "bagaimana",
    "apakah",
    "tolong",
    "cuti",
    "saldo",
    "kirim",
    "sudah",
    "bantu",
)


def prefers_indonesian(message: str) -> bool:
    """Heuristic: Indonesian phrasing in the latest user message."""
    lower = (message or "").casefold()
    return any(word in lower for word in _ID_LANGUAGE_HINTS)


def _day_of_month_from_text(text: str) -> int | None:
    match = _DAY_OF_MONTH_RE.search(text or "")
    if not match:
        return None
    for group in match.groups():
        if group is not None:
            day = int(group)
            return day if 1 <= day <= 31 else None
    return None


def _duration_days_from_text(text: str) -> int | None:
    stripped = (text or "").strip()
    if not stripped:
        return None
    match = _DURATION_RE.match(stripped)
    if match:
        days = int(match.group(1))
        return days if days >= 1 else None
    embedded = _DURATION_EMBEDDED_RE.search(stripped)
    if embedded:
        raw = embedded.group(1) or embedded.group(2)
        days = int(raw)
        return days if days >= 1 else None
    return None


def _user_message_texts(
    message: str, history: list[dict[str, Any]] | None = None
) -> list[str]:
    texts = [message]
    for item in history or []:
        if item.get("role") == "user":
            texts.append(str(item.get("content", "")))
    return texts


def message_is_leave_request(message: str) -> bool:
    """True when this single user turn is asking to prepare/book leave."""
    text = message.casefold()
    if not any(word in text for word in _LEAVE_WORDS):
        return False
    has_request = any(word in text for word in _LEAVE_REQUEST_CUES)
    has_relative = any(word in text for word in _RELATIVE_DATE_WORDS)
    return has_request or has_relative


def leave_intake_still_open(history: list[dict[str, Any]]) -> bool:
    """True after a leave request until a leave proposal is saved."""
    last_leave_at: int | None = None
    for index, item in enumerate(history):
        if item.get("role") != "user":
            continue
        if message_is_leave_request(str(item.get("content", ""))):
            last_leave_at = index
    if last_leave_at is None:
        return False
    for item in history[last_leave_at + 1 :]:
        if item.get("role") == "assistant" and item.get("proposal_id"):
            return False
    return True


def is_leave_request_intent(
    message: str, history: list[dict[str, Any]] | None = None
) -> bool:
    """True for a leave request, or while an unfinished leave request is open."""
    if message_is_leave_request(message):
        return True
    return leave_intake_still_open(history or [])


def conversation_has_leave_dates(
    message: str, history: list[dict[str, Any]] | None = None
) -> bool:
    """True when the user stated dates or a resolvable relative date phrase."""
    for text in _user_message_texts(message, history):
        if _ISO_DATE_RE.search(text) or _LOOSE_DATE_RE.search(text):
            return True
        if _day_of_month_from_text(text) is not None:
            return True
        lower = text.casefold()
        if any(word in lower for word in _DATE_EVIDENCE_WORDS):
            return True
    if re.fullmatch(r"\d{1,2}", (message or "").strip()) and leave_intake_still_open(
        history or []
    ):
        return True
    return False


def conversation_has_leave_reason(
    message: str, history: list[dict[str, Any]] | None = None
) -> bool:
    """True when the user stated a leave reason (not invented by the model)."""
    for text in _user_message_texts(message, history):
        lower = text.casefold()
        if any(word in lower for word in _REASON_EVIDENCE_WORDS):
            return True
    return False


def resolve_day_of_month(day_num: int, today: date) -> date | None:
    """Map a bare day number to this month or next month on/after today."""
    if day_num < 1 or day_num > 31:
        return None
    for month_offset in (0, 1):
        year = today.year + ((today.month - 1 + month_offset) // 12)
        month = (today.month - 1 + month_offset) % 12 + 1
        try:
            candidate = date(year, month, day_num)
        except ValueError:
            continue
        if candidate >= today:
            return candidate
    return None


def resolve_leave_start_date_excluding_message(
    history: list[dict[str, Any]] | None,
    today: date,
) -> date | None:
    """Start date from earlier user turns only (for bare duration replies like '4')."""
    return resolve_leave_start_date("", history, today)


def _text_has_non_bare_start_clue(text: str) -> bool:
    """True for ISO / 'tanggal N' / relative dates — not a bare digit duration."""
    stripped = (text or "").strip()
    if not stripped or re.fullmatch(r"\d{1,2}", stripped):
        return False
    if _ISO_DATE_RE.search(stripped) or _day_of_month_from_text(stripped):
        return True
    lower = stripped.casefold()
    return (
        "besok" in lower
        or "tomorrow" in lower
        or "hari ini" in lower
        or bool(re.search(r"\btoday\b", lower))
    )


def resolve_leave_start_date(
    message: str,
    history: list[dict[str, Any]] | None,
    today: date,
    *,
    skip_bare_numbers: bool = False,
) -> date | None:
    """Newest user date clue wins (ISO, day number, besok/tomorrow, today)."""
    texts: list[str] = []
    if (message or "").strip():
        texts.append(message)
    for item in reversed(history or []):
        if item.get("role") == "user":
            texts.append(str(item.get("content", "")))
    prior_start = None
    if (message or "").strip() and history:
        prior_start = resolve_leave_start_date_excluding_message(history, today)
    for index, text in enumerate(texts):
        stripped = text.strip()
        if not stripped:
            continue
        iso_hits = _ISO_DATE_RE.findall(stripped)
        if iso_hits:
            return date.fromisoformat(iso_hits[-1])
        day_num = _day_of_month_from_text(stripped)
        if day_num is not None:
            resolved = resolve_day_of_month(day_num, today)
            if resolved is not None:
                return resolved
        if re.fullmatch(r"\d{1,2}", stripped):
            if skip_bare_numbers:
                continue
            # Current bare number after a known start is duration ("4"), not a new day.
            if index == 0 and prior_start is not None and (message or "").strip():
                continue
            # Older bare turns ("4") are duration retries when a real start exists
            # earlier (tanggal 29). Still allow bare "29" as the original start.
            if index > 0 or not (message or "").strip():
                if any(_text_has_non_bare_start_clue(t) for t in texts[index + 1 :]):
                    continue
            return resolve_day_of_month(int(stripped), today)
        lower = stripped.casefold()
        if "besok" in lower or "tomorrow" in lower:
            return today + timedelta(days=1)
        if "hari ini" in lower or re.search(r"\btoday\b", lower):
            return today
    return None


def parse_leave_duration_days(
    message: str,
    history: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> int | None:
    """Parse duration like '4 hari', 'for 2 days', or bare '4' after a start date exists."""
    from_text = _duration_days_from_text(message or "")
    if from_text is not None:
        return from_text
    bare = BARE_NUMBER_RE.match((message or "").strip())
    if bare and today is not None and leave_intake_still_open(history or []):
        prior_start = resolve_leave_start_date_excluding_message(history, today)
        if prior_start is not None:
            days = int(bare.group(1))
            return days if days >= 1 else None
    for item in reversed(history or []):
        if item.get("role") != "user":
            continue
        prior = _duration_days_from_text(str(item.get("content", "")))
        if prior is not None:
            return prior
    return None


def conversation_has_leave_duration(
    message: str,
    history: list[dict[str, Any]] | None = None,
    today: date | None = None,
) -> bool:
    """True when the user stated duration or an explicit start–end range."""
    if parse_leave_duration_days(message, history, today) is not None:
        return True
    for text in _user_message_texts(message, history):
        if text.strip() == (message or "").strip():
            continue
        if _duration_days_from_text(text) is not None:
            return True
        if len(_ISO_DATE_RE.findall(text)) >= 2:
            return True
    if len(_ISO_DATE_RE.findall(message or "")) >= 2:
        return True
    return False


def resolve_leave_type_from_texts(
    message: str, history: list[dict[str, Any]] | None = None
) -> str | None:
    """Infer leave_type from user wording in this turn or earlier turns."""
    for text in _user_message_texts(message, history):
        lower = text.casefold()
        if "tahunan" in lower or "annual" in lower:
            return "annual"
        if "sakit" in lower or "sick" in lower:
            return "sick"
        if "orang tua" in lower or "parental" in lower:
            return "parental"
    return None


def claims_annual_notice_failure(answer: str) -> bool:
    """True when the model claims annual notice failure in free text."""
    lower = answer.casefold()
    return any(cue in lower for cue in _NOTICE_FAILURE_CUES)


def message_provides_start_clue(message: str) -> bool:
    """True when this turn itself states a date (not only duration)."""
    stripped = (message or "").strip()
    if not stripped:
        return False
    if _ISO_DATE_RE.search(stripped) or _LOOSE_DATE_RE.search(stripped):
        return True
    if _day_of_month_from_text(stripped) is not None:
        return True
    if re.fullmatch(r"\d{1,2}", stripped):
        return True
    lower = stripped.casefold()
    return any(word in lower for word in _DATE_EVIDENCE_WORDS)
