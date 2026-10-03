"""Glossary, document and locale lookup for the Samjho engine.

Loads the per-language JSON files in app/data:

* glossary.<lang>.json -> financial terms and documents
* locales.<lang>.json  -> the card's own copy (pause list, routes, ...)

Design rules:
* The requested language is tried first. Any FIELD missing there falls back to
  the English value, field by field, so a partial translation never renders a
  blank panel. Alias lists are merged (requested language first, then English).
* Matching is boundary-checked with Unicode-aware logic (unicodedata), because
  \\w in Python's re does not treat Devanagari/Tamil combining marks as word
  characters, which would let an alias match inside a longer Hindi/Tamil word.
* One result per glossary key, sorted by where it first appears in the text.
* find_terms / find_documents return the schema objects the card expects.
"""

from __future__ import annotations

import json
import re
import unicodedata
from functools import lru_cache
from pathlib import Path

from app.schemas import DocumentExplanation, TermExplanation

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

DEFAULT_LANGUAGE = "en"
MAX_TERMS = 8
MAX_DOCUMENTS = 6
MAX_QUOTE = 240

_LANGUAGE_FILES = {
    "en": "glossary.en.json",
    "hi": "glossary.hi.json",
    "ta": "glossary.ta.json",
}

_LOCALE_FILES = {
    "en": "locales.en.json",
    "hi": "locales.hi.json",
    "ta": "locales.ta.json",
}

_SENTENCE_BOUNDARIES = ".!?।\n"


def _is_empty(value) -> bool:
    """True for None, blank strings, and empty collections."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return False


def _is_word_char(char: str) -> bool:
    """True for letters/digits and for combining marks (matras, viramas)."""
    return char.isalnum() or unicodedata.category(char).startswith("M")


def _has_clean_boundaries(text: str, start: int, end: int) -> bool:
    if start > 0 and _is_word_char(text[start - 1]):
        return False
    if end < len(text) and _is_word_char(text[end]):
        return False
    return True


def _merge_entry(target: dict, fallback: dict) -> dict:
    """Fill any empty field in `target` from `fallback`, and merge aliases."""
    merged = dict(target)
    for field, value in fallback.items():
        if field == "aliases":
            continue
        if _is_empty(merged.get(field)) and not _is_empty(value):
            merged[field] = value

    aliases = []
    seen = set()
    for source in (target.get("aliases"), fallback.get("aliases")):
        if not isinstance(source, list):
            continue
        for alias in source:
            text = str(alias).strip()
            lowered = text.lower()
            if not text or lowered in seen:
                continue
            seen.add(lowered)
            aliases.append(text)
    merged["aliases"] = aliases
    return merged


def _merge_locale(base: dict, override: dict) -> dict:
    """Merge two locale dicts. Non-empty values in `override` win; nested
    dicts (comprehension, routes, pause_by_rule) merge key by key."""
    merged = {}
    for key in set(base) | set(override):
        left = base.get(key)
        right = override.get(key)
        if isinstance(left, dict) and isinstance(right, dict):
            merged[key] = _merge_locale(left, right)
        elif _is_empty(right):
            merged[key] = left
        else:
            merged[key] = right
    return merged


def _read_file(filename: str) -> dict | None:
    try:
        with (DATA_DIR / filename).open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
    except (OSError, ValueError):
        return None
    return loaded if isinstance(loaded, dict) else None


@lru_cache(maxsize=None)
def _load(language: str) -> dict:
    """Glossary: requested language first, then English as field-level fallback."""
    payload = {"terms": {}, "documents": {}}
    languages = [language] if language == DEFAULT_LANGUAGE else [language, DEFAULT_LANGUAGE]
    for lang in languages:
        filename = _LANGUAGE_FILES.get(lang)
        if not filename:
            continue
        raw = _read_file(filename)
        if raw is None:
            continue
        for section in ("terms", "documents"):
            entries = raw.get(section)
            if not isinstance(entries, dict):
                continue
            for key, entry in entries.items():
                if not isinstance(entry, dict):
                    continue
                existing = payload[section].get(key)
                if existing is None:
                    payload[section][key] = _merge_entry(entry, {})
                else:
                    payload[section][key] = _merge_entry(existing, entry)
    return payload


@lru_cache(maxsize=None)
def load_locale(language: str = DEFAULT_LANGUAGE) -> dict:
    """The card's own copy: pause list, comprehension, routes, disclaimers.

    Unknown languages fall back to English here; the Pydantic schema is what
    rejects them at card-construction time.
    """
    base = _read_file(_LOCALE_FILES[DEFAULT_LANGUAGE]) or {}
    filename = _LOCALE_FILES.get(language)
    if not filename or language == DEFAULT_LANGUAGE:
        return dict(base)
    override = _read_file(filename) or {}
    return _merge_locale(base, override)


def _alias_pattern(aliases) -> re.Pattern | None:
    parts = []
    for alias in aliases or []:
        text = str(alias).strip()
        if not text:
            continue
        parts.append(r"\s+".join(re.escape(piece) for piece in text.split()))
    if not parts:
        return None
    # Longest alias first, so "net asset value" is preferred over "nav".
    parts.sort(key=len, reverse=True)
    return re.compile("|".join(parts), re.IGNORECASE)


def _find(text: str, section: str, language: str, limit: int):
    """First clean match per key, sorted by position in the text."""
    if not text:
        return []
    entries = _load(language).get(section, {})
    results = []
    for key, entry in entries.items():
        pattern = _alias_pattern(entry.get("aliases"))
        if pattern is None:
            continue
        for match in pattern.finditer(text):
            if _has_clean_boundaries(text, match.start(), match.end()):
                results.append((match.start(), key, entry, match.group(0)))
                break
    results.sort(key=lambda item: item[0])
    return results[:limit]


def _sentence_around(text: str, start: int, end: int) -> str:
    """The sentence containing the match, capped so one long line cannot flood the card."""
    left = start
    while left > 0 and text[left - 1] not in _SENTENCE_BOUNDARIES:
        left -= 1
    right = end
    while right < len(text) and text[right] not in _SENTENCE_BOUNDARIES:
        right += 1
    if right < len(text):
        right += 1
    quote = text[left:right].strip()
    if len(quote) > MAX_QUOTE:
        quote = text[max(0, start - 60): min(len(text), end + 60)].strip()
    return quote or text[start:end].strip()


def find_terms(text: str, language: str = DEFAULT_LANGUAGE) -> list[TermExplanation]:
    """Financial terms mentioned in the text, explained from the reviewed glossary."""
    found = _find(text, "terms", language, MAX_TERMS)
    terms: list[TermExplanation] = []
    for position, key, entry, matched in found:
        meaning = entry.get("meaning")
        if _is_empty(meaning):
            continue
        terms.append(TermExplanation(
            term=str(entry.get("display") or key),
            simple_meaning=str(meaning),
            source_quote=_sentence_around(text, position, position + len(matched)),
        ))
    return terms


def find_documents(text: str, language: str = DEFAULT_LANGUAGE) -> list[DocumentExplanation]:
    """Identity/bank documents the message asks about."""
    found = _find(text, "documents", language, MAX_DOCUMENTS)
    documents: list[DocumentExplanation] = []
    for position, key, entry, matched in found:
        documents.append(DocumentExplanation(
            document=str(entry.get("display") or key),
            common_purpose=str(entry.get("purpose") or ""),
            context_note=str(entry.get("context_note") or ""),
            source_quote=_sentence_around(text, position, position + len(matched)),
        ))
    return documents


def lookup(key: str, language: str = DEFAULT_LANGUAGE) -> dict | None:
    """One entry by key, from terms or documents. English fallback applies."""
    if not key:
        return None
    data = _load(language)
    entry = data["terms"].get(key)
    if entry is None:
        entry = data["documents"].get(key)
    if not isinstance(entry, dict):
        return None
    result = dict(entry)
    if _is_empty(result.get("display")):
        result["display"] = key
    return result
