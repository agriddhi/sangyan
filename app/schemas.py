"""The single object every entry point produces: the Learning & Action Card.

This module is pure data shape. No logic, no AI, no rules live here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Language = Literal["en", "hi", "ta"]
Severity = Literal["info", "caution", "high", "critical"]
RouteId = Literal["scores", "sachet", "cybercrime_1930", "none"]


class ClaimEvidence(BaseModel):
    """One claim in the content, paired with whatever evidence the content shows."""

    claim: str
    source_quote: str = ""
    evidence_quote: str = ""
    evidence_status: Literal["shown_in_input", "not_shown_in_input", "unclear"]


class TermExplanation(BaseModel):
    """A jargon term found in the content, explained from the reviewed glossary."""

    term: str
    simple_meaning: str
    source_quote: str = ""


class DocumentExplanation(BaseModel):
    """A document requested in the content, with its normal purpose and context."""

    document: str
    common_purpose: str
    context_note: str
    source_quote: str = ""


class RuleSignal(BaseModel):
    """A pattern the deterministic engine found. Not a verdict."""

    rule_id: str
    severity: Severity
    title: str
    explanation: str
    source_quote: str = ""


class ComprehensionCheck(BaseModel):
    """The Ruko step: make the user restate what they understood."""

    question: str
    choices: list[str] = Field(default_factory=list)
    correct_learning_point: str


class RouteAction(BaseModel):
    """Where the user can go next. Chosen by rules, never by the model."""

    route_id: RouteId
    reason: str
    action_text: str
    official_url: str = ""


class LearningActionCard(BaseModel):
    """The single object every entry point produces."""

    card_id: str
    language: Language
    plain_summary: str
    claims_and_evidence: list[ClaimEvidence] = Field(default_factory=list)
    terms: list[TermExplanation] = Field(default_factory=list)
    documents: list[DocumentExplanation] = Field(default_factory=list)
    signals: list[RuleSignal] = Field(default_factory=list)
    comprehension_check: ComprehensionCheck
    pause_checklist: list[str] = Field(default_factory=list)
    route: RouteAction
    uncertainty: str
    progress_action: str
