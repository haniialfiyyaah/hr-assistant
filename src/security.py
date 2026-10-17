"""Security helpers for token hashing and telemetry redaction."""
from __future__ import annotations

import hashlib
import re


def token_hash(token: str) -> str:
    """Deterministic SHA-256 hex digest; never store the raw bearer token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def stable_safety_id(employee_id: str) -> str:
    """Stable, non-identifying hash for the provider safety_identifier field."""
    material = f"hr-assistant:safety:{employee_id}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()


_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")
_PHONE_RE = re.compile(r"(?:\+62|62|0)8\d{8,12}\b")
_TOKEN_RE = re.compile(r"\btoken[-_][A-Za-z0-9_-]+\b", re.IGNORECASE)
# Common medical detail / diagnosis cues for synthetic demo traces.
_MEDICAL_RE = re.compile(
    r"\b(?:diabetes|diagnosis|diagnosa|penyakit|medical|medis)\b[:\s]*[A-Za-z0-9_-]*",
    re.IGNORECASE,
)


def redact(value: str) -> str:
    """Redact email, Indonesian phone numbers, token-like values, and medical detail."""
    redacted = _EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    redacted = _PHONE_RE.sub("[REDACTED_PHONE]", redacted)
    redacted = _TOKEN_RE.sub("[REDACTED_TOKEN]", redacted)
    redacted = _MEDICAL_RE.sub("[REDACTED_MEDICAL]", redacted)
    return redacted
