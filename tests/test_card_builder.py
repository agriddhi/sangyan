"""Card builder tests. These run WITHOUT an API key on purpose."""

import os

os.environ.pop("GEMINI_API_KEY", None)

from app.engine.card_builder import _claims_from_model, build_card  # noqa: E402
from app.schemas import LearningActionCard  # noqa: E402

FORWARD = (
    "Guaranteed 3% monthly returns. Send your PAN, Aadhaar and cancelled "
    "cheque on WhatsApp to activate your account."
)

JARGON = "Your SIP folio NAV is updated. Check your demat account."


def test_card_is_valid_without_model():
    card = build_card(FORWARD, "en", use_model=False)
    assert isinstance(card, LearningActionCard)
    assert card.plain_summary
    assert card.uncertainty
    assert card.comprehension_check.question


def test_never_uses_verdict_language():
    card = build_card(FORWARD, "en", use_model=False)
    blob = card.model_dump_json().lower()
    for banned in ("is a scam", "is fraud", "is fraudulent", "guaranteed safe",
                   "safe to invest", "you should buy", "you should sell", "we recommend"):
        assert banned not in blob


def test_document_panel_contains_pan():
    card = build_card(FORWARD, "en", use_model=False)
    names = {doc.document for doc in card.documents}
    assert any("PAN" in name for name in names)


def test_document_panel_explains_purpose_and_context():
    card = build_card(FORWARD, "en", use_model=False)
    assert card.documents
    for doc in card.documents:
        assert doc.common_purpose
        assert doc.context_note
        assert doc.source_quote


def test_glossary_terms_are_attached():
    card = build_card(JARGON, "en", use_model=False)
    names = {term.term for term in card.terms}
    assert any("NAV" in name for name in names)
    assert any("Folio" in name for name in names)
    assert any("Demat" in name for name in names)


def test_terms_never_include_unreviewed_invention():
    card = build_card("Buy this amazing new thing called FINTECH5000 now.", "en", use_model=False)
    assert card.terms == []


def test_comprehension_check_names_the_documents():
    card = build_card(FORWARD, "en", use_model=False)
    joined = " ".join(card.comprehension_check.choices)
    assert "PAN" in joined


def test_pause_checklist_includes_credential_rule_when_otp_asked():
    card = build_card("Send me your OTP and PIN now.", "en", use_model=False)
    joined = " ".join(card.pause_checklist).lower()
    assert "otp" in joined


def test_plain_message_has_no_signals():
    card = build_card("Good morning, hope you are well. See you at lunch.", "en", use_model=False)
    assert card.signals == []
    assert card.route.route_id == "none"


def test_hindi_card_is_built():
    card = build_card("आपका खाता बंद हो जाएगा। अपना ओटीपी भेजें।", "hi", use_model=False)
    assert card.language == "hi"
    assert card.uncertainty
    assert any("\u0900" <= ch <= "\u097f" for ch in card.uncertainty)


def test_model_claims_without_real_quotes_are_dropped():
    draft = {"claims_and_evidence": [
        {"claim": "A real claim", "source_quote": "Guaranteed 3% monthly returns",
         "evidence_status": "not_shown_in_input"},
        {"claim": "An invented claim", "source_quote": "The sender is SEBI registered",
         "evidence_status": "shown_in_input", "evidence_quote": "reg no 12345"},
    ]}
    claims = _claims_from_model(draft, FORWARD)
    assert len(claims) == 1
    assert claims[0].source_quote == "Guaranteed 3% monthly returns"


def test_fake_evidence_quote_is_cleared():
    draft = {"claims_and_evidence": [
        {"claim": "A claim", "source_quote": "Guaranteed 3% monthly returns",
         "evidence_status": "shown_in_input", "evidence_quote": "SEBI registration number 999"},
    ]}
    claims = _claims_from_model(draft, FORWARD)
    assert claims[0].evidence_quote == ""
    assert claims[0].evidence_status == "not_shown_in_input"
