"""stt.py - speech to text, done on our side.

The browser's own recogniser sends audio to Google and is blocked on many
networks, including this one. So the microphone is recorded here, in the page,
and the audio is sent to this function instead.

Privacy: audio is held in memory only, is never written to disk, and is never
stored or logged. The user presses a button before any of this happens, and
the microphone can be switched off completely.
"""

from __future__ import annotations

import os

try:
    import requests
except ImportError:  # pragma: no cover
    requests = None

GROQ_URL = "https://api.groq.com/openai/v1/audio/transcriptions"
MODEL = "whisper-large-v3"
MAX_SECONDS = 15

# Only sent when the user has already chosen that language, so a Hindi
# recording is not forced through an English model.
LANG_HINTS = {"en": "en", "hi": "hi", "ta": "ta"}


def available() -> bool:
    return bool(os.getenv("GROQ_API_KEY", "").strip()) and requests is not None


def transcribe(audio: bytes, language: str = "en") -> str:
    """Return the spoken words as text. Returns '' on any failure."""
    key = os.getenv("GROQ_API_KEY", "").strip()
    if not key or not audio or requests is None:
        return ""

    files = {"file": ("clip.webm", audio, "audio/webm")}
    data = {"model": MODEL, "temperature": "0"}
    hint = LANG_HINTS.get((language or "en").lower())
    if hint:
        data["language"] = hint

    try:
        response = requests.post(
            GROQ_URL,
            headers={"Authorization": f"Bearer {key}"},
            files=files,
            data=data,
            timeout=60,
        )
        if response.status_code != 200:
            return ""
        payload = response.json()
    except Exception:
        return ""

    if isinstance(payload, dict):
        return str(payload.get("text") or "").strip()
    return ""


if __name__ == "__main__":
    print("stt available:", available())
