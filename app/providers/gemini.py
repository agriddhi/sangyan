"""Gemini REST client — standard library only.

Every function here is OPTIONAL and FAIL-SOFT: with no API key, no network, a
bad response or an unknown model it returns None, and the caller falls back to
rules + glossary only. Importing this module never fails and never touches the
network, so the test suite runs with no key.

Auth: x-goog-api-key header (the key never appears in a URL).
Endpoint: POST https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent
"""

from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

# Tried in order. The first that responds wins; a 404 moves to the next one.
# GEMINI_MODEL in .env is tried before these, so a model change needs no code edit.
DEFAULT_MODELS = ("gemini-3.8-flash", "gemini-2.5-flash", "gemini-3.5-flash-lite")
TIMEOUT_SECONDS = 40

_LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}

# Best-effort output guard for the SIMPLER intent. NOT a guarantee: it catches
# obvious phrasing only. The real protection is that the guide answers from
# text that is already on the card, and never composes a verdict.
_ADVICE_MARKERS = (
    "you should invest", "you must invest", "i recommend buying", "i recommend selling",
    "buy this", "sell this", "guaranteed return", "will definitely",
    "safe to invest", "invest in this", "definitely a fraud", "this is fraud",
    "this is genuine", "this is safe",
)

_MARKDOWN = re.compile(r"[*_`#>]+")
_SENTENCE_END = re.compile(r"[.!?।]")


class _UnknownModel(Exception):
    """Internal: the API said this model does not exist. Try the next one."""


_ENV_LOADED = False


def _load_env_file() -> None:
    """Read .env from the project root once, without any third-party package."""
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    path = Path(__file__).resolve().parent.parent.parent / ".env"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        value = value.strip().strip('"').strip("'")
        if name and name not in os.environ:
            os.environ[name] = value


def _api_key() -> str | None:
    _load_env_file()
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY", "")
    if not key:
        key = os.getenv("GOOGLE_API_KEY", "")
    key = (key or "").strip()
    return key or None


def is_configured() -> bool:
    """True when a key is present. The app works either way."""
    return _api_key() is not None


def _models() -> list[str]:
    models = []
    configured = (os.getenv("GEMINI_MODEL") or "").strip()
    if configured:
        models.append(configured)
    for model in DEFAULT_MODELS:
        if model not in models:
            models.append(model)
    return models


def _post(payload: dict, model: str) -> dict | None:
    key = _api_key()
    if key is None:
        return None
    request = urllib.request.Request(
        ENDPOINT.format(model=model),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            body = response.read().decode("utf-8", errors="replace")
        parsed = json.loads(body)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise _UnknownModel() from error
        return None
    except Exception:
        return None
    return parsed if isinstance(parsed, dict) else None


def _text_from_response(body: dict | None) -> str | None:
    if not isinstance(body, dict):
        return None
    for candidate in body.get("candidates") or []:
        content = candidate.get("content") or {}
        for part in content.get("parts") or []:
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _generate(parts: list[dict], system_prompt: str, json_mode: bool) -> str | None:
    generation = {"temperature": 0.2}
    if json_mode:
        generation["responseMimeType"] = "application/json"
    payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": generation,
    }
    for model in _models():
        try:
            body = _post(payload, model)
        except _UnknownModel:
            continue
        text = _text_from_response(body)
        if text:
            return text
    return None


def _extract_json(text: str) -> dict | None:
    """Parse a JSON object out of the answer, tolerating code fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        if cleaned[:4].lower() == "json":
            cleaned = cleaned[4:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except ValueError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _strip_markdown(text: str) -> str:
    return _MARKDOWN.sub("", text).strip()


def _trim_to_sentence(text: str, limit: int = 600) -> str:
    """Cut long output at a sentence ending, never mid-word, never empty."""
    cleaned = text.strip()
    if len(cleaned) <= limit:
        return cleaned
    window = cleaned[:limit]
    best = -1
    for match in _SENTENCE_END.finditer(window):
        best = match.end()
    if best > 0:
        candidate = window[:best].strip()
        if candidate:
            return candidate
    candidate = window.strip()
    return candidate if candidate else cleaned[:limit].strip()


_DRAFT_SYSTEM = (
    "You help a first-time investor in India understand a message they received. "
    "You NEVER advise, judge or verify. You never say whether the sender, the "
    "offer or the message is genuine, safe, fraudulent or a scam. You never "
    "recommend buying, selling or holding anything. "
    "You return STRICT JSON only, with this shape: "
    '{"plain_summary": "<2-3 short sentences in {language}>", '
    '"claims": [{"text": "<one short claim in {language}>"}]}. '
    "Each claim must be something the message itself states, written in your own "
    "simple words. Use at most 5 claims. Write in {language} at the reading level "
    "of a first-time investor. Add no text outside the JSON."
)

_SIMPLIFY_SYSTEM = (
    "You explain one short piece of a financial message to a first-time investor "
    "in India. You NEVER advise, judge or verify, and you never say whether "
    "anything is genuine, safe, fraudulent or a scam. You never recommend buying, "
    "selling or holding. Explain only what the given text means, in {language}, "
    "in 2-3 short simple sentences. If the text asks for OTP, PIN or password, "
    "say plainly that a genuine institution never asks for these."
)

_MEDIA_SYSTEM = (
    "You transcribe text from images for a first-time investor in India. "
    "Return ONLY the text visible in the image, exactly as written, in its "
    "original language and script. Do not translate. Do not explain. Do not "
    "advise. If there is no readable text, return the single word NONE."
)


def draft_card(source_text: str, language: str = "en") -> dict | None:
    """Return {"plain_summary": str, "claims": [{"text": str}]} or None."""
    if not source_text or not source_text.strip():
        return None
    system = _DRAFT_SYSTEM.replace("{language}", _LANGUAGE_NAMES.get(language, "English"))
    prompt = 'Message to explain:\n"""\n' + source_text.strip() + '\n"""'
    raw = _generate([{"text": prompt}], system, json_mode=True)
    if raw is None:
        return None
    parsed = _extract_json(raw)
    if parsed is None:
        return None
    summary = parsed.get("plain_summary")
    if not isinstance(summary, str) or not summary.strip():
        return None
    claims = []
    for item in parsed.get("claims") or []:
        if not isinstance(item, dict):
            continue
        text = item.get("text")
        if isinstance(text, str) and text.strip():
            claims.append({"text": text.strip()})
    return {"plain_summary": summary.strip(), "claims": claims[:5]}


def simplify(text: str, language: str = "en") -> str | None:
    """Explain one card snippet in simpler words. None if unavailable or unsafe."""
    if not text or not text.strip():
        return None
    system = _SIMPLIFY_SYSTEM.replace("{language}", _LANGUAGE_NAMES.get(language, "English"))
    prompt = 'Text to explain:\n"""\n' + text.strip() + '\n"""'
    raw = _generate([{"text": prompt}], system, json_mode=False)
    if raw is None:
        return None
    cleaned = _strip_markdown(raw)
    if not cleaned:
        return None
    lowered = cleaned.lower()
    if any(marker in lowered for marker in _ADVICE_MARKERS):
        return None
    return _trim_to_sentence(cleaned)


def extract_text_from_media(data: bytes, mime_type: str, language: str = "en") -> str | None:
    """Transcribe text from an image (screenshot sent by the user). None on failure."""
    if not data:
        return None
    system = _MEDIA_SYSTEM.replace("{language}", _LANGUAGE_NAMES.get(language, "English"))
    encoded = base64.b64encode(data).decode("ascii")
    parts = [
        {"text": "Transcribe all visible text from this image exactly as written."},
        {"inlineData": {"mimeType": mime_type or "image/jpeg", "data": encoded}},
    ]
    raw = _generate(parts, system, json_mode=False)
    if raw is None or raw.strip().upper() == "NONE":
        return None
    return raw.strip()
