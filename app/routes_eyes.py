"""routes_eyes.py - the two extra checks, exposed over HTTP.

POST /api/flags   -> the document's clauses that are worth reading twice
POST /api/fit     -> the reader's answers next to the document's own words

Both accept the same body as the rest of the app: {"text", "language",
"use_model"}. With use_model false the checks still work using exact matches
only, which is also what happens if the model is rate limited.
"""

from __future__ import annotations

from typing import Any, Dict

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.engine.eyes import default_model_call, find_flags, run_fit_check

router = APIRouter()

LANGUAGES = ("en", "hi", "ta")
MAX_TEXT = 120_000

_NOT_READY = {
    "en": "The AI layer is busy (rate limit). The exact lines are still shown "
          "below. Wait about a minute and press the button again for the "
          "plain-language explanation.",
    "hi": "AI लेयर व्यस्त है (रट लिमिट)। सही लाइनें नीचे दिखाई जा रही हैं। "
          "लगभग एक मिनट बाद दोबारा दबाएँ।",
    "ta": "AI அடுக்கு தற்காலிகமாகப் ப占மாக உள்ளது (ரேட் லிமிட்). சரியான "
          "வரிகள் கீழே காட்டப்படுகின்றன. சுமார் ஒரு நிமிடம் கழித்து மீண்டும் "
          "அழுத்துங்கள்.",
}


class FlagsRequest(BaseModel):
    text: str = ""
    language: str = "en"
    use_model: bool = True


class FitRequest(BaseModel):
    text: str = ""
    language: str = "en"
    answers: Dict[str, Any] = Field(default_factory=dict)
    use_model: bool = True


def _lang(value: str) -> str:
    value = (value or "en").strip().lower()
    return value if value in LANGUAGES else "en"


@router.post("/api/flags")
def api_flags(request: FlagsRequest) -> dict:
    language = _lang(request.language)
    text = (request.text or "").strip()[:MAX_TEXT]
    if not text:
        return {"language": language, "intro": "", "read_it_yourself": "", "items": [], "checked": 0}

    model_call = default_model_call() if request.use_model else None
    result = find_flags(text, language, model_call)

    if model_call is None and result.get("items"):
        result["notice"] = _NOT_READY[language]
    return result


@router.post("/api/fit")
def api_fit(request: FitRequest) -> dict:
    language = _lang(request.language)
    text = (request.text or "").strip()[:MAX_TEXT]
    if not text:
        return {"language": language, "intro": "", "comparisons": [], "disclaimer": ""}

    model_call = default_model_call() if request.use_model else None
    return run_fit_check(text, request.answers or {}, language, model_call)
