"""routes_rights.py - the complaint directory, served as JSON.

GET /api/rights                  -> situations, urgent banner, checklist, links
GET /api/rights/{situation_id}   -> the escalation steps for one situation

Deterministic. No model is called, nothing is stored, nothing is collected.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.engine import rights

router = APIRouter()


def _lang(language: str) -> str:
    value = (language or "en").strip().lower()
    return value if value in rights.LANGUAGES else "en"


@router.get("/api/rights")
def api_rights(language: str = "en") -> dict:
    return rights.all_situations(_lang(language))


@router.get("/api/rights/{situation_id}")
def api_rights_situation(situation_id: str, language: str = "en") -> dict:
    return rights.ladder(situation_id, _lang(language))
