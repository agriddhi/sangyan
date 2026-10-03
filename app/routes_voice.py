"""routes_voice.py - one endpoint: turn recorded audio into text.

POST /api/transcribe  (multipart: file, language)

The audio is read into memory, transcribed, and discarded. Nothing is stored.
"""

from __future__ import annotations

from fastapi import APIRouter, File, Form, UploadFile

from app.providers import stt

router = APIRouter()

MAX_BYTES = 6_000_000

_NO_KEY = {
    "en": "Voice input is not set up on this server yet. "
          "You can still press Win + H and speak, or type your question.",
    "hi": "इस सर्वर पर वॉइस इनपुट सेट नहीं है। आप Win + H दबाकर बोल सकते हैं।",
    "ta": "இந்த சர்வரில் குரல் உள்ளிடல் அமைக்கப்படவில்லை. "
          "நீங்கள் Win + H அழுத்தி பேசலாம்.",
}


@router.post("/api/transcribe")
async def transcribe(
    file: UploadFile = File(...),
    language: str = Form("en"),
) -> dict:
    lang = (language or "en").lower()
    if lang not in ("en", "hi", "ta"):
        lang = "en"

    if not stt.available():
        return {"text": "", "ok": False, "notice": _NO_KEY[lang]}

    audio = await file.read()
    if not audio or len(audio) > MAX_BYTES:
        return {"text": "", "ok": False, "notice": "No audio was received."}

    text = stt.transcribe(audio, lang)
    return {"text": text, "ok": bool(text), "language": lang}
