"""Tests for the deterministic rule engine.

Every test encodes a product decision:
* real requests are flagged,
* look-alikes (postal PIN codes, safety warnings, plain mentions) are NOT,
* routes only fire on genuine complaint or loss context.
"""

from app.engine.rules import SEVERITY_ORDER, choose_route, evaluate

FORWARD_EN = (
    "Guaranteed 3% monthly returns. Send your PAN, Aadhaar and cancelled "
    "cheque on WhatsApp to activate your account."
)

FORWARD_HI = "आपका खाता बंद हो जाएगा। अपना ओटीपी और पिन भेजें।"

CLEAN_EN = (
    "Hi, your SIP of Rs 5,000 for October has been processed. "
    "You can see the details in the official app."
)

SAFETY_WARNING_EN = (
    "Reminder from your bank: never share your OTP, PIN or password with anyone."
)

PINCODE_EN = (
    "Please deliver the cheque book to my address: 12 MG Road, Pune 411001. "
    "This is my PIN code."
)


def ids(signals):
    return {s.rule_id for s in signals}


# --------------------------------------------------------------------------- #
# R01 -- credential requests
# --------------------------------------------------------------------------- #

def test_credential_request_en():
    signals = evaluate("Send me your OTP to verify your account.")
    assert "R01_CREDENTIAL_REQUEST" in ids(signals)
    signal = next(s for s in signals if s.rule_id == "R01_CREDENTIAL_REQUEST")
    assert signal.severity == "critical"
    assert "OTP" in signal.source_quote


def test_credential_request_hi():
    signals = evaluate(FORWARD_HI)
    assert "R01_CREDENTIAL_REQUEST" in ids(signals)


def test_safety_warning_not_flagged():
    signals = evaluate(SAFETY_WARNING_EN)
    assert "R01_CREDENTIAL_REQUEST" not in ids(signals)


def test_pin_code_not_flagged():
    signals = evaluate(PINCODE_EN)
    assert "R01_CREDENTIAL_REQUEST" not in ids(signals)


# --------------------------------------------------------------------------- #
# R02 / R10 -- return promises
# --------------------------------------------------------------------------- #

def test_guaranteed_return_flagged():
    signals = evaluate(FORWARD_EN)
    assert "R02_GUARANTEED_RETURN" in ids(signals)
    assert "R10_UNREGISTERED_RETURN_CLAIM" in ids(signals)


def test_registration_evidence_suppresses_r10():
    signals = evaluate(
        "SEBI registered portfolio manager offering fixed monthly returns."
    )
    assert "R02_GUARANTEED_RETURN" in ids(signals)
    assert "R10_UNREGISTERED_RETURN_CLAIM" not in ids(signals)


# --------------------------------------------------------------------------- #
# R03 / R04 -- pressure and authority
# --------------------------------------------------------------------------- #

def test_urgency_flagged():
    signals = evaluate("Act now! Your account will be blocked today.")
    assert "R03_URGENCY_OR_THREAT" in ids(signals)


def test_authority_claim_flagged():
    signals = evaluate("This is the cyber cell investigation team.")
    assert "R04_AUTHORITY_CLAIM" in ids(signals)


def test_authority_mention_without_context_not_flagged():
    signals = evaluate(
        "I read on the SEBI website that mutual funds carry market risk."
    )
    assert "R04_AUTHORITY_CLAIM" not in ids(signals)


# --------------------------------------------------------------------------- #
# R05 / R06 -- documents
# --------------------------------------------------------------------------- #

def test_document_request_flagged():
    signals = evaluate("Please send your Aadhaar and PAN card copy for KYC.")
    assert "R05_SENSITIVE_DOCUMENT" in ids(signals)


def test_informal_channel_document_request():
    signals = evaluate(FORWARD_EN)
    assert "R06_INFORMAL_DOCUMENT_CHANNEL" in ids(signals)


# --------------------------------------------------------------------------- #
# R07 / R08 / R09 -- device and payment patterns
# --------------------------------------------------------------------------- #

def test_app_install_flagged():
    signals = evaluate("Download this app to start investing: http://bit.ly/xyz")
    assert "R07_APP_INSTALL_REQUEST" in ids(signals)


def test_remote_access_flagged():
    signals = evaluate(
        "Please install AnyDesk and share your screen with our support team."
    )
    assert "R08_REMOTE_ACCESS_REQUEST" in ids(signals)


def test_qr_collect_flagged():
    signals = evaluate("Scan this QR code to receive your payment.")
    assert "R09_QR_OR_COLLECT_REQUEST" in ids(signals)


# --------------------------------------------------------------------------- #
# R11 -- deadlines
# --------------------------------------------------------------------------- #

def test_deadline_flagged():
    signals = evaluate("Submit your documents before 15/11/2026 to avoid penalty.")
    assert "R11_DEADLINE_PRESSURE" in ids(signals)


# --------------------------------------------------------------------------- #
# clean content
# --------------------------------------------------------------------------- #

def test_clean_message_has_no_signals():
    assert evaluate(CLEAN_EN) == []


# --------------------------------------------------------------------------- #
# routing
# --------------------------------------------------------------------------- #

def test_route_cybercrime_when_money_lost():
    text = (
        "Guaranteed 4% monthly profit. I paid Rs 1,00,000 and now my money is gone."
    )
    signals = evaluate(text)
    decision = choose_route(text, signals)
    assert decision.route_id == "cybercrime_1930"


def test_route_scores_for_broker_complaint():
    text = (
        "My broker is not refunding my money and is not responding to my complaint."
    )
    signals = evaluate(text)
    decision = choose_route(text, signals)
    assert decision.route_id == "scores"


def test_route_sachet_for_chit_fund():
    text = "Join our chit fund for guaranteed double returns."
    signals = evaluate(text)
    decision = choose_route(text, signals)
    assert decision.route_id == "sachet"


def test_route_none_for_clean():
    signals = evaluate(CLEAN_EN)
    decision = choose_route(CLEAN_EN, signals)
    assert decision.route_id == "none"


def test_routes_do_not_fire_on_plain_mentions():
    text = (
        "I paid my electricity bill online and the broker sent me a "
        "mutual fund statement."
    )
    signals = evaluate(text)
    decision = choose_route(text, signals)
    assert decision.route_id == "none"


# --------------------------------------------------------------------------- #
# shape guarantees
# --------------------------------------------------------------------------- #

def test_signals_sorted_by_severity():
    signals = evaluate(FORWARD_EN)
    severities = [SEVERITY_ORDER[s.severity] for s in signals]
    assert severities == sorted(severities, reverse=True)


def test_every_signal_carries_a_quote():
    signals = evaluate(FORWARD_EN)
    assert signals
    assert all(s.source_quote for s in signals)


def test_hindi_pressure_and_credential_flagged():
    signals = evaluate(FORWARD_HI)
    assert "R03_URGENCY_OR_THREAT" in ids(signals)
    assert "R01_CREDENTIAL_REQUEST" in ids(signals)
