"""server.py - the browser front door for the document explainer.

Routes:
* GET  /              -> serves static/explainer.html
* POST /api/explain   -> {text, language, use_model} -> DocumentExplanation JSON
* POST /api/ask       -> {text, question, focus, language, use_model} -> answer JSON
* GET  /api/health    -> tiny health + AI layer status
* /static/*           -> static assets
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.engine.ask import answer_question
from app.engine.explainer import explain_document
from app.providers import llm

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "static"
MAX_INPUT_CHARS = 200_000
SUPPORTED_LANGUAGES = ("en", "hi", "ta")

app = FastAPI(title="SANGYAN document explainer", version="0.4.0")
from app.routes_eyes import router as _eyes_router  # noqa: E402
app.include_router(_eyes_router)


class ExplainRequest(BaseModel):
    text: str = Field(default="", max_length=MAX_INPUT_CHARS)
    language: str = "en"
    use_model: bool = True


class AskRequest(BaseModel):
    text: str = Field(default="", max_length=MAX_INPUT_CHARS)
    question: str = Field(default="", max_length=1000)
    focus: str = Field(default="", max_length=1200)
    language: str = "en"
    use_model: bool = True


def _checked_language(raw: str) -> str:
    language = (raw or "en").strip().lower()
    if language not in SUPPORTED_LANGUAGES:
        raise HTTPException(
            status_code=400,
            detail="language must be one of: " + ", ".join(SUPPORTED_LANGUAGES),
        )
    return language


@app.get("/")
def index() -> FileResponse:
    page = STATIC_DIR / "explainer.html"
    if not page.is_file():
        raise HTTPException(status_code=500, detail="static/explainer.html is missing.")
    return FileResponse(page)


@app.post("/api/explain")
def api_explain(request: ExplainRequest) -> dict:
    """Split a document into parts and explain each part in plain language."""
    text = (request.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="No document text was provided.")
    language = _checked_language(request.language)
    model_call = llm.model_call if request.use_model else None
    try:
        result = explain_document(text, language=language, model_call=model_call)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not read this document: " + str(exc),
        ) from exc
    return asdict(result)


@app.post("/api/ask")
def api_ask(request: AskRequest) -> dict:
    """Answer one question about one document, from that document."""
    text = (request.text or "").strip()
    question = (request.question or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="No question was provided.")
    if not text:
        raise HTTPException(status_code=400, detail="No document text was provided.")
    language = _checked_language(request.language)
    model_call = llm.model_call if request.use_model else None
    try:
        return answer_question(
            text,
            question,
            language=language,
            model_call=model_call,
            focus=(request.focus or "").strip(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Could not answer that: " + str(exc),
        ) from exc


@app.get("/api/health")
def api_health() -> dict:
    info: dict = {"ok": True}
    status_fn = getattr(llm, "status", None)
    if callable(status_fn):
        try:
            extra = status_fn()
            if isinstance(extra, dict):
                info.update(extra)
        except Exception:
            pass
    return info


if not STATIC_DIR.exists():
    STATIC_DIR.mkdir(parents=True, exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# --- extra panels: clauses to review, fit check, and voice transcription ---
from app.routes_eyes import router as _eyes_router  # noqa: E402
from app.routes_voice import router as _voice_router  # noqa: E402
app.include_router(_eyes_router)
app.include_router(_voice_router)

from app.routes_rights import router as _rights_router  # noqa: E402
app.include_router(_rights_router)
