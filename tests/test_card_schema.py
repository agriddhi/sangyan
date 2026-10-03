"""Tests for the Learning & Action Card schema."""

import pytest
from pydantic import ValidationError

from app.schemas import (
    ClaimEvidence,
    ComprehensionCheck,
    LearningActionCard,
    RouteAction,
    RuleSignal,
)


def _card(**overrides):
    data = dict(
        card_id="card_test_001",
        language="en",
        plain_summary=(
            "This message promises a fixed monthly return and asks for documents."
        ),
        claims_and_evidence=[
            ClaimEvidence(
                claim="3% monthly returns are guaranteed",
                source_quote="Guaranteed 3% monthly returns.",
                evidence_status="not_shown_in_input",
            )
        ],
        terms=[],
        documents=[],
        signals=[
            RuleSignal(
                rule_id="R02_GUARANTEED_RETURN",
                severity="high",
                title="A guaranteed return is being promised",
                explanation="Market returns cannot be guaranteed.",
                source_quote="Guaranteed 3% monthly returns.",
            )
        ],
        comprehension_check=ComprehensionCheck(
            question="In your own words, what is this message promising?",
            choices=["A fixed monthly return", "A bank interest rate"],
            correct_learning_point=(
                "The message promises a return; nothing in it proves the return."
            ),
        ),
        pause_checklist=["Do not send documents in this chat."],
        route=RouteAction(
            route_id="sachet",
            reason="A scheme with an unregistered return claim is described.",
            action_text="You can read about unregistered schemes on SEBI Sachet.",
            official_url="https://sachet.sebi.gov.in",
        ),
        uncertainty="This tool explains the message. It cannot confirm who sent it.",
        progress_action="You reviewed a message before acting.",
    )
    data.update(overrides)
    return LearningActionCard(**data)


def test_card_round_trips():
    card = _card()
    dumped = card.model_dump()
    again = LearningActionCard(**dumped)
    assert again == card


def test_card_defaults_are_empty_lists():
    card = _card()
    assert card.terms == []
    assert card.documents == []


def test_card_rejects_unknown_language():
    with pytest.raises(ValidationError):
        _card(language="fr")
