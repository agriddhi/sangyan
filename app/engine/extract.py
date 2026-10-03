"""Deterministic extraction of concrete entities from a message.

Pure regex + standard library. Every function returns a list (possibly empty)
and never raises.

These are display facts: the exact numbers, links and handles that appear in
the message. They are produced by rules, not by a model, so they can be shown
back to the user verbatim with full confidence.
"""

from __future__ import annotations

import re

MAX_ITEMS = 10

_AMOUNT = re.compile(
    r"(?<![\w₹])"
    r"(?:"
    r"(?:₹|rs\.?|inr)\s*\d[\d,]*(?:\.\d+)?"
    r"|"
    r"\d{1,3}(?:,\d{2,3})+(?:\.\d+)?"
    r"|"
    r"\d[\d,]*(?:\.\d+)?\s*(?:crores?|lakhs?|lacs?|cr|k)\b"
    r")"
    r"(?!\d)",
    re.IGNORECASE,
)

_PERCENT = re.compile(
    r"(?<!\d)\d+(?:\.\d+)?\s*(?:%|per\s*cent\b|percent\b|प्रतिशत|சதவீதம்)",
    re.IGNORECASE,
)

_PHONE = re.compile(
    r"(?<![\w])"
    r"(?:"
    r"(?:(?:\+91|91)[\s-]?)?[6-9]\d{4}[\s-]?\d{5}"
    r"|"
    r"(?:1800|1860)[\s-]?\d{3}[\s-]?\d{3,4}"
    r")"
    r"(?![\w])"
)

_SCHEME_URL = re.compile(
    r"(?:https?://|www\.)[^\s<>\"'()\[\]{}]+",
    re.IGNORECASE,
)

_BARE_DOMAIN = re.compile(
    r"(?<![\w@.-])"
    r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+"
    r"(?:com|in|org|net|co|io|ly|me|info|online|site|app|xyz|club|top|live|shop|dev|link|cc|gov|edu)"
    r"(?![\w-])"
    r"(?:/[^\s<>\"'()\[\]{}]*)?",
    re.IGNORECASE,
)

_UPI = re.compile(
    r"(?<![\w.@])"
    r"[a-z0-9][a-z0-9._-]{1,40}"
    r"@"
    r"(?:upi|ok[a-z]+|ybl|paytm|apl|axl|ibl)"
    r"(?![\w.])",
    re.IGNORECASE,
)

_TRAILING = ".,;:!?)]}'\"»"


def _dedupe(items, limit: int = MAX_ITEMS) -> list[str]:
    seen = set()
    out = []
    for item in items:
        cleaned = str(item).strip()
        if not cleaned:
            continue
        lowered = cleaned.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        out.append(cleaned)
        if len(out) >= limit:
            break
    return out


def extract_amounts(text: str) -> list[str]:
    """Money amounts, including Indian grouping like 1,00,000 and units like 50k."""
    if not text:
        return []
    return _dedupe(match.group(0) for match in _AMOUNT.finditer(text))


def extract_percentages(text: str) -> list[str]:
    """Percentages written as %, 'per cent', or in Hindi/Tamil."""
    if not text:
        return []
    return _dedupe(match.group(0) for match in _PERCENT.finditer(text))


def extract_phone_numbers(text: str) -> list[str]:
    """Indian mobile numbers and 1800/1860 helpline numbers."""
    if not text:
        return []
    return _dedupe(match.group(0) for match in _PHONE.finditer(text))


def extract_urls(text: str) -> list[str]:
    """Full URLs and bare domains. Trailing punctuation is trimmed."""
    if not text:
        return []
    found = []
    spans = []
    for match in _SCHEME_URL.finditer(text):
        spans.append((match.start(), match.end()))
        found.append(match.group(0))
    for match in _BARE_DOMAIN.finditer(text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        found.append(match.group(0))
    return _dedupe(item.rstrip(_TRAILING) for item in found)


def extract_upi_ids(text: str) -> list[str]:
    """UPI handles such as name@ybl, name@okhdfcbank, name@paytm."""
    if not text:
        return []
    return _dedupe(match.group(0) for match in _UPI.finditer(text))


def extract_all(text: str) -> dict[str, list[str]]:
    """Everything at once, keyed for the card."""
    return {
        "amounts": extract_amounts(text),
        "percentages": extract_percentages(text),
        "phone_numbers": extract_phone_numbers(text),
        "urls": extract_urls(text),
        "upi_ids": extract_upi_ids(text),
    }
