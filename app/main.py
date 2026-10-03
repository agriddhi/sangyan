"""Samjho API server.

Endpoints:
  GET  /          -> the app page (once static/index.html exists)
  GET  /health    -> server status, model key presence, cards held
  POST /api/card  -> builds a Learning & Action Card from pasted text
  POST /api/ask   -> the grounded guide, answering about a card held on the server

Cards are kept in a small in-memory store and referenced by card_id, so the
guide always answers from a card this server actually built. Nothing is written
to disk and no user text leaves the process except the optional model call.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.engine.card_builder import build_card
from app.engine.guide import answer_question
from app.schemas import Language, LearningActionCard

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="Samjho", version="0.2.0")

# Local development convenience: lets the page work if opened through another
# dev server. Tighten or remove for any public deployment.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_CARDS: dict[str, LearningActionCard] = {}
_CARD_LIMIT = 50


class CardRequest(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    language: Language = "en"
    use_model: bool = True


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    card_id: str = Field(min_length=1, max_length=64)
    language: Language | None = None


class AskResponse(BaseModel):
    intent: str
    text: str
    ai_used: bool = False


def _model_key_present() -> bool:
    if os.environ.get("GEMINI_API_KEY"):
        return True
    env_file = BASE_DIR / ".env"
    try:
        content = env_file.read_text(encoding="utf-8")
    except OSError:
        return False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("GEMINI_API_KEY=") and len(stripped) > len("GEMINI_API_KEY="):
            return True
    return False


def _remember(card: LearningActionCard) -> None:
    """Keep the most recent cards so /api/ask can answer from a server-built card."""
    _CARDS[card.card_id] = card
    while len(_CARDS) > _CARD_LIMIT:
        _CARDS.pop(next(iter(_CARDS)), None)


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "model_key_present": _model_key_present(),
        "cards_held": len(_CARDS),
    }


@app.post("/api/card", response_model=LearningActionCard)
def make_card(request: CardRequest) -> LearningActionCard:
    try:
        card = build_card(request.text, request.language, use_model=request.use_model)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Card build failed: {exc}") from exc
    _remember(card)
    return card


@app.post("/api/ask", response_model=AskResponse)
def ask(request: AskRequest) -> AskResponse:
    card = _CARDS.get(request.card_id)
    if card is None:
        raise HTTPException(
            status_code=404,
            detail="That card is no longer available. Build the card again, then ask.",
        )
    language = request.language or card.language
    answer = answer_question(request.question, card, language)
    return AskResponse(intent=answer.intent, text=answer.text, ai_used=answer.ai_used)


if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def index():
    page = STATIC_DIR / "index.html"
    if page.exists():
        return FileResponse(page)
    return {
        "message": "Samjho API is running. The page (static/index.html) is not created yet.",
        "endpoints": ["/health", "/api/card", "/api/ask"],
    }
