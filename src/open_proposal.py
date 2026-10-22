"""Open leave proposal: replace/cancel/keep intents and prepare-failure shaping."""

from __future__ import annotations

import re
from typing import Any

from .contracts import ActionProposal, Citation, Outcome, ToolCallSummary
from .domain import parse_open_proposal_exists_error
from .leave_intake import prefers_indonesian
from .security import redact

_BARE_CANCEL_OPEN = frozenset(
    {
        "batalkan",
        "batal",
        "batalin",
        "cancel",
        "cancel it",
        "cancel proposal",
        "batalkan saja",
        "batal saja",
    }
)
_KEEP_PHRASES = (
    "tetap yang",
    "yang lama",
    "jangan ganti",
    "keep the",
    "don't replace",
    "do not replace",
    "no replace",
    "no change",
    "tetap pakai",
)
_BARE_KEEP = frozenset(
    {
        "tidak",
        "no",
        "nope",
        "jangan",
        "ga",
        "gak",
        "nggak",
        "enggak",
        "tidak usah",
        "ga usah",
        "no thanks",
    }
)
_REMIND_CUES = (
    "belum dikonfirmasi",
    "open leave proposal",
    "pending proposal",
    "buat yang baru",
    "create a new",
    "batalkan yang lama",
    "cancel the old",
    "cancel it and create",
    "atau batalkan",
)
_HARD_PREPARE_CUES = (
    "saldo cuti tidak cukup",
    "tidak cukup untuk rentang",
    "masa lalu",
    "paling lambat tiga",
    "tiga hari kerja sebelum",
    "three business day",
)
_DEFAULT_PREPARE_FAIL = (
    "I cannot prepare that leave request because it failed validation."
)


def is_confirm_intent(message: str) -> bool:
    """Clear confirmation phrases. Bare 'yes' is left to the model with the pending block."""
    text = message.strip().casefold()
    if text in {"confirm", "setuju", "ok confirm", "yes confirm", "ya confirm"}:
        return True
    if re.search(r"\bconfirm\b", text):
        return True
    if re.search(r"(?<![a-zà-ÿ])setuju(?![a-zà-ÿ])", text):
        return True
    return False


def is_replace_open_intent(message: str) -> bool:
    """True when the user consents to cancel the open proposal and create a new one."""
    lower = (message or "").casefold()
    if any(c in lower for c in ("replace", "supersede", "ganti saja", "ya ganti", "iya ganti")):
        return True
    if ("ganti" in lower) and ("baru" in lower or "proposal" in lower):
        return True
    cancel = "cancel" in lower or "batal" in lower
    create_new = any(w in lower for w in ("new", "baru", "create", "buat"))
    return cancel and create_new


def latest_assistant_text(history: list[dict[str, Any]] | None) -> str:
    for item in reversed(history or []):
        if item.get("role") == "assistant":
            return str(item.get("content", ""))
    return ""


def looks_like_open_proposal_remind(answer: str) -> bool:
    """True when text is already a keep-vs-replace remind about an open proposal."""
    lower = (answer or "").casefold()
    return any(c in lower for c in _REMIND_CUES)


def is_cancel_open_proposal_intent(
    message: str, history: list[dict[str, Any]] | None = None
) -> bool:
    """True when the user cancels the open proposal (bare 'batalkan' after a remind, or replace)."""
    if is_replace_open_intent(message):
        return True
    lower = (message or "").casefold().strip()
    if lower not in _BARE_CANCEL_OPEN:
        return False
    return looks_like_open_proposal_remind(latest_assistant_text(history))


def replace_open_authorized(
    message: str, history: list[dict[str, Any]] | None = None
) -> bool:
    """True when this turn or a post-remind cancel still authorizes replace_open.

    Does not supersede by itself — prepare validates first, then supersedes on success.
    """
    if is_cancel_open_proposal_intent(message, history):
        return True
    items = list(history or [])
    remind_idx = next(
        (
            idx
            for idx in range(len(items) - 1, -1, -1)
            if items[idx].get("role") == "assistant"
            and looks_like_open_proposal_remind(str(items[idx].get("content", "")))
        ),
        None,
    )
    if remind_idx is None:
        return False
    for idx in range(remind_idx + 1, len(items)):
        item = items[idx]
        if item.get("role") != "user":
            continue
        if not is_cancel_open_proposal_intent(str(item.get("content", "")), items[:idx]):
            continue
        # Consent spent once a replacement proposal was created after that cancel.
        if any(
            later.get("role") == "assistant" and later.get("proposal_id")
            for later in items[idx + 1 :]
        ):
            return False
        return True
    return False


def is_keep_open_proposal_intent(
    message: str, history: list[dict[str, Any]] | None = None
) -> bool:
    """True when the user declines replacing and wants to keep the open proposal."""
    if (
        is_replace_open_intent(message)
        or is_cancel_open_proposal_intent(message, history)
        or is_confirm_intent(message)
    ):
        return False
    lower = (message or "").casefold().strip()
    if any(c in lower for c in _KEEP_PHRASES):
        return True
    if lower not in _BARE_KEEP:
        return False
    return looks_like_open_proposal_remind(latest_assistant_text(history))


def remind_open_proposal_answer(message: str, proposal: ActionProposal) -> str:
    """Server fallback remind when the model did not produce one."""
    detail = (
        f"{proposal.leave_type} {proposal.start_date.isoformat()}–"
        f"{proposal.end_date.isoformat()} ({proposal.business_days} business days)"
    )
    if prefers_indonesian(message):
        return (
            f"Anda masih punya pengajuan cuti yang belum dikonfirmasi: {detail}. "
            "Konfirmasi yang lama, atau batalkan yang lama dan buat yang baru?"
        )
    return (
        f"You still have an open leave proposal: {detail}. "
        "Confirm the existing one, or cancel it and create a new one?"
    )


def is_hard_prepare_domain_error(message: str) -> bool:
    """True for balance / notice / past-date refusals that must not be softened."""
    lower = (message or "").casefold()
    return any(cue in lower for cue in _HARD_PREPARE_CUES)


def shape_prepare_failure(
    *,
    answer: str,
    prepare_error_message: str | None,
    tool_summaries: list[ToolCallSummary],
    message: str,
) -> tuple[str, Outcome, list[Citation], bool]:
    """Map a failed prepare into answer/outcome; returns kept_open_proposal_remind."""
    blocked = parse_open_proposal_exists_error(prepare_error_message or "")
    domain_error = redact(prepare_error_message or "").strip()
    looked_up_balance = any(
        item.name == "get_my_leave_balance" and item.status == "ok"
        for item in tool_summaries
    )
    if blocked is not None:
        text = answer.strip() or remind_open_proposal_answer(message, blocked)
        return text, Outcome.answered, [], True
    if is_hard_prepare_domain_error(domain_error):
        if looked_up_balance and answer.strip():
            return answer, Outcome.abstained, [], False
        return domain_error or _DEFAULT_PREPARE_FAIL, Outcome.abstained, [], False
    if answer.strip():
        # e.g. overlap with an active leave_request — keep the model explanation.
        return answer, Outcome.answered, [], False
    return domain_error or _DEFAULT_PREPARE_FAIL, Outcome.abstained, [], False
