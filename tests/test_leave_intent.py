from __future__ import annotations

from src.agent import is_leave_request_intent


def test_policy_question_is_not_leave_intake() -> None:
    assert not is_leave_request_intent(
        "How many annual leave days do permanent employees get?"
    )


def test_unrelated_follow_up_after_policy_is_not_leave_intake() -> None:
    history = [
        {
            "role": "user",
            "content": "How many annual leave days do permanent employees get?",
        },
        {
            "role": "assistant",
            "content": (
                "Permanent employees get 12 working days of annual leave [HR-LEAVE-001]. "
                "Pengajuan dilakukan paling lambat tiga hari kerja."
            ),
        },
    ]
    assert not is_leave_request_intent("What employee am I", history)


def test_leave_request_is_leave_intake() -> None:
    assert is_leave_request_intent("I want to take leave next week")


def test_drip_feed_details_keep_leave_intake_open() -> None:
    """Date corrections and type-only replies stay in intake until a proposal exists."""
    after_first = [
        {"role": "user", "content": "I want to take leave at 24 october"},
        {
            "role": "assistant",
            "content": "Got it. Which leave type, and confirm the date?",
        },
    ]
    assert is_leave_request_intent("No, maybe 22", after_first)

    after_second = [
        *after_first,
        {"role": "user", "content": "No, maybe 22"},
        {"role": "assistant", "content": "Okay, 22 October."},
    ]
    assert is_leave_request_intent("annual leave", after_second)


def test_leave_intake_closes_after_proposal() -> None:
    history = [
        {"role": "user", "content": "I want to take leave next week"},
        {
            "role": "assistant",
            "content": "Proposal ready. Confirm to submit.",
            "proposal_id": "PROP-1",
        },
    ]
    assert not is_leave_request_intent("annual leave", history)
