"""Assemble the final Learning & Action Card.

This is the one place where model output and deterministic rules meet.

Contract:
* Rules produce the signals and the route. The model NEVER chooses either.
* Raw engine signals are passed back to the engine untouched.
* Every model-supplied claim must carry a quote that literally exists in the
  source text, or the claim is dropped entirely.
* If the model is unavailable, the card is still built from rules + glossary alone.
"""

from __future__ import annotations

import inspect
import re
import uuid

from app.engine import glossary
from app.engine.rules import choose_route, evaluate
from app.schemas import (
    ClaimEvidence,
    ComprehensionCheck,
    LearningActionCard,
    RouteAction,
    RuleSignal,
)


def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def _quote_is_real(quote: str, source: str) -> bool:
    """A quote counts only if it appears verbatim in the source (whitespace-insensitive)."""
    needle = _collapse(quote)
    return len(needle) >= 3 and needle in _collapse(source)


def _arity(func) -> int:
    """Count positional parameters, or -1 if the signature cannot be read.

    Used ONLY to decide how many arguments to pass. Argument ORDER is fixed:
    evaluate(text[, language]) and choose_route(text, signals).
    """
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return -1
    kinds = (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    return sum(1 for param in signature.parameters.values() if param.kind in kinds)


def _run_engine(source_text: str, language: str):
    """Call the Drop 1 engine and hand its RAW signals straight back to it."""
    raw_signals = evaluate(source_text) if _arity(evaluate) == 1 else evaluate(source_text, language)

    if _arity(choose_route) == 1:
        decision = choose_route(raw_signals)
    else:
        decision = choose_route(source_text, raw_signals)

    return raw_signals, decision


def _to_signals(raw_signals) -> list[RuleSignal]:
    """Convert the engine's results into the card's Pydantic signals.

    Duck-typed on purpose so this layer does not depend on engine class names.
    """
    signals: list[RuleSignal] = []
    for item in raw_signals:
        severity = getattr(item, "severity", "info")
        if severity not in ("info", "caution", "high", "critical"):
            severity = "info"
        signals.append(RuleSignal(
            rule_id=str(getattr(item, "rule_id", "UNKNOWN")),
            severity=severity,
            title=str(getattr(item, "title", "")),
            explanation=str(getattr(item, "explanation", "")),
            source_quote=str(getattr(item, "source_quote", "")),
        ))
    return signals


def _claims_from_model(draft: dict | None, source_text: str) -> list[ClaimEvidence]:
    """Build claim/evidence pairs.

    A claim is kept ONLY if its source_quote appears verbatim in the input.
    An invented quote means the claim itself is discarded, not just the quote.
    """
    claims: list[ClaimEvidence] = []
    for item in (draft or {}).get("claims_and_evidence", []) or []:
        claim = (item.get("claim") or "").strip()
        if not claim:
            continue
        quote = (item.get("source_quote") or "").strip()
        if not quote or not _quote_is_real(quote, source_text):
            continue

        evidence = (item.get("evidence_quote") or "").strip()
        status = item.get("evidence_status") or "unclear"
        if status not in ("shown_in_input", "not_shown_in_input", "unclear"):
            status = "unclear"
        if evidence and not _quote_is_real(evidence, source_text):
            evidence = ""
        if status == "shown_in_input" and not evidence:
            status = "not_shown_in_input"

        claims.append(ClaimEvidence(
            claim=claim,
            source_quote=quote,
            evidence_quote=evidence,
            evidence_status=status,
        ))
    return claims


def _pause_list(locale: dict, signals: list[RuleSignal]) -> list[str]:
    items = list(locale.get("pause", []))
    per_rule = locale.get("pause_by_rule", {})
    for signal in signals:
        extra = per_rule.get(signal.rule_id)
        if extra and extra not in items:
            items.append(extra)
    return items


def _comprehension(locale: dict, documents) -> ComprehensionCheck:
    base = locale.get("comprehension", {})
    question = base.get("question", "What is this message asking you to do?")
    choices = list(base.get("choices", []))
    point = base.get("learning_point", "")
    if documents:
        names = ", ".join(doc.document for doc in documents[:3])
        choices = [f"Send {names}", "Only read some information", "I am not sure yet"]
        point = (
            f"The message asks for {names}. Naming the request is the point — if a message "
            f"asks for documents, check the channel before sending anything."
        )
    return ComprehensionCheck(question=question, choices=choices, correct_learning_point=point)


def _route_action(locale: dict, decision) -> RouteAction:
    """Map the engine's route decision onto the card. Fails loudly if the shape is wrong."""
    if not hasattr(decision, "route_id"):
        raise TypeError(
            "choose_route returned an unexpected value "
            f"({type(decision).__name__}). Expected an object with a .route_id attribute."
        )
    route_id = str(decision.route_id)
    if route_id not in ("scores", "sachet", "cybercrime_1930", "none"):
        route_id = "none"
    meta = locale.get("routes", {}).get(route_id, {})
    return RouteAction(
        route_id=route_id,
        reason=str(getattr(decision, "reason", "")),
        action_text=meta.get("action_text", ""),
        official_url=meta.get("official_url", ""),
    )


def build_card(source_text: str, language: str = "en", use_model: bool = True) -> LearningActionCard:
    """Build the card. Works with or without the model available."""
    source_text = (source_text or "").strip()
    locale = glossary.load_locale(language)

    raw_signals, decision = _run_engine(source_text, language)
    signals = _to_signals(raw_signals)
    documents = glossary.find_documents(source_text, language)
    terms = glossary.find_terms(source_text, language)

    draft = None
    if use_model:
        from app.providers import gemini

        draft = gemini.draft_card(source_text, language)

    summary = ((draft or {}).get("plain_summary") or "").strip()
    if not summary:
        summary = locale.get("fallback_summary", "")

    return LearningActionCard(
        card_id=str(uuid.uuid4()),
        language=language,
        plain_summary=summary,
        claims_and_evidence=_claims_from_model(draft, source_text),
        terms=terms,
        documents=documents,
        signals=signals,
        comprehension_check=_comprehension(locale, documents),
        pause_checklist=_pause_list(locale, signals),
        route=_route_action(locale, decision),
        uncertainty=locale.get("uncertainty", ""),
        progress_action=locale.get("progress_action", ""),
    )
