
"""Deterministic investor-safety rule engine (Drop 1).

Contract
--------
* Rules decide SIGNALS and ROUTES. The LLM never does.
* A signal means "this pattern is present in the content" -- NOT "this is fraud".
* Severity is how urgently the user should pause, not the probability of fraud.
* A MENTION is not a REQUEST: a trigger fires only when request or context
  language appears in the SAME sentence.
* Every signal carries the exact source quote so the user can verify it.
* Rules never assert account ownership, registry status, or legal validity.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

Severity = Literal["info", "caution", "high", "critical"]
RouteId = Literal["scores", "sachet", "cybercrime_1930", "none"]

SEVERITY_ORDER: dict[str, int] = {
    "info": 0,
    "caution": 1,
    "high": 2,
    "critical": 3,
}

_FLAGS = re.IGNORECASE | re.UNICODE


@dataclass(frozen=True)
class DetectedSignal:
    """One pattern found in the content. Not a verdict."""

    rule_id: str
    severity: Severity
    title: str
    explanation: str
    source_quote: str = ""


@dataclass(frozen=True)
class RouteDecision:
    """Where the user can go next. Chosen by rules, never by the model."""

    route_id: RouteId
    reason: str


ROUTE_INFO: dict[str, dict[str, str]] = {
    "scores": {"name": "SEBI SCORES", "url": "https://scores.sebi.gov.in"},
    "sachet": {"name": "SEBI Sachet", "url": "https://sachet.sebi.gov.in"},
    "cybercrime_1930": {
        "name": "Cyber Crime Helpline 1930",
        "url": "https://cybercrime.gov.in",
    },
    "none": {"name": "", "url": ""},
}


# --------------------------------------------------------------------------- #
# text helpers
# --------------------------------------------------------------------------- #

def _normalize(text: str) -> str:
    """NFC-normalise, collapse horizontal whitespace, trim."""
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u00a0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?\u0964])\s+|\n+")


def _sentences(text: str) -> list[str]:
    """Split into sentences so a MENTION can never be mistaken for a REQUEST."""
    parts = _SENTENCE_SPLIT.split(text)
    return [p.strip() for p in parts if p and p.strip()]


# --------------------------------------------------------------------------- #
# R01 -- secrets: OTP / PIN / password
# --------------------------------------------------------------------------- #

_CREDENTIAL = re.compile(
    r"\b(?:"
    r"otp|one[\s-]?time[\s-]?password|mpin|upi[\s-]?pin|atm[\s-]?pin|cvv"
    r"|card[\s-]?pin|password|passcode|verification code|security code"
    r"|pin(?!\s*[-:\u2013]?\s*\d{6}(?!\d))(?!\s*(?:code|number|no\b))"
    r")\b"
    r"|(?:ओटीपी|पिन|पासवर्ड|सीवीवी)",
    _FLAGS,
)

_REQUEST_VERB = re.compile(
    r"\b(?:share|send|give|provide|enter|type|submit|forward|confirm|verify"
    r"|reply|fill|update|upload|attach)\b"
    r"|(?:भेज|साझा|बताएं|बताइए|डालें|दर्ज करें|जमा करें)",
    _FLAGS,
)

# A safety warning is not a request. Hindi patterns are whitespace-anchored so
# "पिन भेजें" (send the PIN -- a REQUEST) can never match "न भेजें" (do not send).
_NEGATED_REQUEST = re.compile(
    r"\b(?:never|do not|don't|dont|avoid)\s+(?:\w+\s+){0,2}"
    r"(?:share|send|give|provide|enter|tell|reveal|disclose|forward)\b"
    r"|(?:साझा\s+न\s+करें|भेज\s+न\s+करें|\sन\s+बताएं|\sन\s+बताइए"
    r"|\sन\s+भेजें|\sन\s+साझा)",
    _FLAGS,
)

# --------------------------------------------------------------------------- #
# R02 / R10 -- return promises
# --------------------------------------------------------------------------- #

_RETURN_CLAIM = re.compile(
    r"\b(?:guaranteed|guarantee|assured|risk[\s-]?free|fixed(?!\s+deposit)|confirmed)\b"
    r"|(?:गारंटी|गारंटीड|पक्का)",
    _FLAGS,
)

_RETURN_WORDS = re.compile(
    r"\b(?:returns?|profits?|income|gains?|interest|monthly|daily|weekly"
    r"|doubl\w*|tripl\w*)\b"
    r"|(?:मुनाफ़ा|मुनाफा|रिटर्न|ब्याज|डबल|लाभ)",
    _FLAGS,
)

_REGISTRATION_EVIDENCE = re.compile(
    r"\b(?:sebi|rbi|irdai|amfi)\b[^.\n]{0,30}\b(?:registered|registration|regulated|licen[cs]ed)\b"
    r"|\b(?:cin|registration no|registration number|licen[cs]e no)\b"
    r"|(?:पंजीकृत|रजिस्टर्ड)",
    _FLAGS,
)

# --------------------------------------------------------------------------- #
# R03 -- urgency and threats
# --------------------------------------------------------------------------- #

_URGENCY = re.compile(
    r"\b(?:act (?:now|fast|immediately|today)|urgent|urgently|limited time"
    r"|limited offer|last chance|today only|only (?:for )?today"
    r"|expires? (?:today|soon|in \d)|offer ends (?:today|soon)"
    r"|within \d+ (?:hours?|minutes?|hrs?)|only \d+ (?:seats|slots|spots) left"
    r"|account (?:will be |may be |has been )?(?:frozen|blocked|suspended|closed|deactivated)"
    r"|legal action|penalt(?:y|ies)|arrest)\b"
    r"|(?:तुरंत|आज ही|जल्दी करें|सीमित समय|खाता बंद|कानूनी कार्रवाई)",
    _FLAGS,
)

# --------------------------------------------------------------------------- #
# R04 -- authority claims
# --------------------------------------------------------------------------- #

_AUTHORITY_TERM = re.compile(
    r"\b(?:sebi|rbi|reserve bank|nse|bse|irdai|amfi|income tax|cbi|customs"
    r"|cyber ?cell|police|government|govt|ministry of finance)\b"
    r"|(?:सेबी|आरबीआई|पुलिस|सरकार)",
    _FLAGS,
)

_AUTHORITY_CONTEXT = re.compile(
    r"\b(?:registered|registration|approved|authoris|authoriz|certified"
    r"|verified|officer|official|department|notice|team|case|investigation"
    r"|action|representative|executive)\b"
    r"|(?:अधिकारी|विभाग|नोटिस)",
    _FLAGS,
)

# --------------------------------------------------------------------------- #
# R05 / R06 -- documents and the channel they are requested on
# --------------------------------------------------------------------------- #

_DOCUMENT = re.compile(
    r"\b(?:pan(?: card)?|aadhaar|aadhar|adhar|bank statement|account statement"
    r"|cancelled cheque|canceled cheque|cancelled check|cheque book|passport"
    r"|voter id|driving licen[cs]e|signature|date of birth|dob)\b"
    r"|(?:आधार|पैन|बैंक स्टेटमेंट|पासबुक|हस्ताक्षर|जन्म तिथि)",
    _FLAGS,
)

_INFORMAL_CHANNEL = re.compile(
    r"\b(?:whatsapp|whats app|telegram|dm|direct message|personal (?:chat|number|email|id)"
    r"|gmail|yahoo|instagram|facebook|signal app)\b"
    r"|(?:व्हाट्सएप|व्हाट्सऐप|वाट्सएप|वॉट्सऐप|टेलीग्राम)",
    _FLAGS,
)

# --------------------------------------------------------------------------- #
# R07 / R08 / R09 -- device, screen and payment-request patterns
# --------------------------------------------------------------------------- #

_APP_INSTALL = re.compile(
    r"\b(?:apk|install (?:this|the|our) app|download (?:this|the|our) app"
    r"|install (?:this|the) application|click (?:this|the) link to (?:install|download))\b"
    r"|(?:यह ऐप इंस्टॉल|ऐप डाउनलोड|लिंक पर क्लिक)",
    _FLAGS,
)

_REMOTE_ACCESS = re.compile(
    r"\b(?:screen shar\w*|share (?:your )?screen|any ?desk|team ?viewer"
    r"|quick ?support|remote (?:access|desktop)|screen mirroring)\b",
    _FLAGS,
)

_QR_COLLECT = re.compile(
    r"\b(?:scan (?:this|the|below) qr|scan (?:this|the) code"
    r"|approve (?:the |this )?(?:collect )?request"
    r"|accept (?:the |this )?(?:collect )?request|collect request)\b"
    r"|(?:क्यूआर कोड स्कैन|स्कैन करें)",
    _FLAGS,
)

# --------------------------------------------------------------------------- #
# R11 -- deadlines
# --------------------------------------------------------------------------- #

_DEADLINE_WORD = re.compile(
    r"\b(?:deadline|last date|due date|expires?|expiry|last day"
    r"|valid (?:till|until)|before)\b",
    _FLAGS,
)

_DATE = re.compile(
    r"\b\d{1,2}[-/.]\d{1,2}[-/.]\d{2,4}\b"
    r"|\b\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b",
    _FLAGS,
)

_TODAY_WORD = re.compile(r"\b(?:today|tomorrow|tonight)\b|(?:आज|कल)", _FLAGS)

_ACTION_VERB = re.compile(
    r"\b(?:pay|paid|payment|submit|complete|reply|respond|confirm|update|upload|provide)\b",
    _FLAGS,
)

# --------------------------------------------------------------------------- #
# routing context
# --------------------------------------------------------------------------- #

_LOSS_CONTEXT = re.compile(
    r"\b(?:i|we)\s+(?:have\s+|had\s+)?(?:paid|transferred|sent)\b"
    r"|\bmoney\s+(?:was\s+|has\s+been\s+)?(?:debited|deducted|gone|lost|taken)\b"
    r"|\b(?:amount|money)\s+(?:was\s+)?(?:debited|deducted)\b"
    r"|\blost\s+(?:my\s+)?money\b"
    r"|\b(?:got|been)\s+(?:scammed|cheated|defrauded)\b"
    r"|(?:पैसे\s+(?:गए|कट गए|निकल गए)|धोखा)",
    _FLAGS,
)

_INTERMEDIARY = re.compile(
    r"\b(?:broker|sub[\s-]?broker|trading account|demat|depository participant"
    r"|mutual fund|portfolio manager|investment advis(?:er|or)|research analyst"
    r"|stock exchange)\b"
    r"|(?:ब्रोकर|डीमैट|म्यूचुअल फंड)",
    _FLAGS,
)

_COMPLAINT_CONTEXT = re.compile(
    r"\b(?:complain\w*|grievance|dispute|cheated|misled"
    r"|not (?:returning|refunding|responding)|refus\w* to|cannot withdraw"
    r"|unable to withdraw|withheld)\b"
    r"|(?:शिकायत|धोखा|पैसे वापस नहीं)",
    _FLAGS,
)

_SCHEME_TERMS = re.compile(
    r"\b(?:chit fund|chit scheme|ponzi|money circulation|pyramid scheme|mlm"
    r"|multi[\s-]?level marketing|unregistered (?:scheme|investment)"
    r"|collective investment scheme|deposit scheme|daily deposit|monthly deposit)\b"
    r"|(?:चिट फंड|पोंजी|धन वसूली)",
    _FLAGS,
)


def _deadline_hit(sentence: str) -> bool:
    if _DEADLINE_WORD.search(sentence) and (
        _DATE.search(sentence) or _TODAY_WORD.search(sentence)
    ):
        return True
    if _DATE.search(sentence) and _ACTION_VERB.search(sentence):
        return True
    return False


# --------------------------------------------------------------------------- #
# the engine
# --------------------------------------------------------------------------- #

def evaluate(text: str) -> list[DetectedSignal]:
    """Return every signal present in the text, most urgent first.

    A signal is a pattern, not a verdict. This function never decides whether
    anything is safe or fraudulent.
    """
    normalized = _normalize(text)
    sentences = _sentences(normalized)
    signals: list[DetectedSignal] = []
    seen: set[str] = set()

    def add(
        rule_id: str,
        severity: Severity,
        title: str,
        explanation: str,
        quote: str,
    ) -> None:
        if rule_id in seen:
            return
        seen.add(rule_id)
        signals.append(
            DetectedSignal(
                rule_id=rule_id,
                severity=severity,
                title=title,
                explanation=explanation,
                source_quote=quote,
            )
        )

    for sentence in sentences:
        credential_request = (
            bool(_CREDENTIAL.search(sentence))
            and bool(_REQUEST_VERB.search(sentence))
            and not _NEGATED_REQUEST.search(sentence)
        )
        if credential_request:
            add(
                "R01_CREDENTIAL_REQUEST",
                "critical",
                "A secret code or password is being requested",
                "The content asks you to share or enter an OTP, PIN, password or "
                "similar secret. No genuine bank, broker or government office asks "
                "for these. Do not share it.",
                sentence,
            )

        if _RETURN_CLAIM.search(sentence) and _RETURN_WORDS.search(sentence):
            add(
                "R02_GUARANTEED_RETURN",
                "high",
                "A guaranteed or fixed return is being promised",
                "The content promises a guaranteed, assured or fixed return. This "
                "tool cannot check whether that promise is true. Market returns "
                "cannot be guaranteed.",
                sentence,
            )
            if not _REGISTRATION_EVIDENCE.search(sentence):
                add(
                    "R10_UNREGISTERED_RETURN_CLAIM",
                    "high",
                    "Return promise with no registration details shown",
                    "The promise of returns is not accompanied by any registration "
                    "or licence details in the same sentence. You can verify any "
                    "claim of SEBI registration on the official SEBI website.",
                    sentence,
                )

        if _URGENCY.search(sentence):
            add(
                "R03_URGENCY_OR_THREAT",
                "high",
                "Urgency or a threat is being used",
                "The content pushes you to act immediately or warns of a penalty, "
                "freeze or legal action. Pressure to act fast is a common fraud "
                "pattern; slow down before paying or sharing anything.",
                sentence,
            )

        if _AUTHORITY_TERM.search(sentence) and _AUTHORITY_CONTEXT.search(sentence):
            add(
                "R04_AUTHORITY_CLAIM",
                "high",
                "An authority or regulator is being named",
                "The content mentions a regulator, department or authority. This "
                "tool cannot verify who sent it or whether any registration is "
                "real. Verify using contact details you find yourself.",
                sentence,
            )

        document_request = (
            bool(_DOCUMENT.search(sentence))
            and bool(_REQUEST_VERB.search(sentence))
            and not _NEGATED_REQUEST.search(sentence)
        )
        if document_request:
            add(
                "R05_SENSITIVE_DOCUMENT",
                "caution",
                "Identity or bank documents are being requested",
                "Documents such as PAN, Aadhaar or bank statements are commonly "
                "needed for genuine account opening and KYC. This signal does not "
                "mean anything is wrong here -- it means you should confirm who "
                "is asking and through which channel.",
                sentence,
            )
            if _INFORMAL_CHANNEL.search(sentence):
                add(
                    "R06_INFORMAL_DOCUMENT_CHANNEL",
                    "high",
                    "Sensitive documents requested over an informal channel",
                    "The request asks for identity or bank documents through a chat "
                    "or personal channel. Genuine KYC is done through an official "
                    "app, portal or branch, not a personal chat.",
                    sentence,
                )

        if _APP_INSTALL.search(sentence):
            add(
                "R07_APP_INSTALL_REQUEST",
                "high",
                "An app install or download is being requested",
                "The content asks you to install or download an app, often from a "
                "link. Apps installed from links or APK files outside official app "
                "stores can read your messages and your screen.",
                sentence,
            )

        if _REMOTE_ACCESS.search(sentence):
            add(
                "R08_REMOTE_ACCESS_REQUEST",
                "high",
                "Screen sharing or remote access is being requested",
                "The content asks you to share your screen or install remote-access "
                "software. Anyone who can see your screen can also see your OTPs "
                "and banking details.",
                sentence,
            )

        if _QR_COLLECT.search(sentence):
            add(
                "R09_QR_OR_COLLECT_REQUEST",
                "high",
                "A QR scan or collect request is being asked for",
                "The content asks you to scan a QR code or approve a request, "
                "usually promising to send money. In UPI, scanning a QR code or "
                "approving a collect request SENDS money from your account.",
                sentence,
            )

        if _deadline_hit(sentence):
            add(
                "R11_DEADLINE_PRESSURE",
                "caution",
                "A deadline or cut-off date is mentioned",
                "The content mentions a date or deadline. Check the date against "
                "the original document and never act only because a message says "
                "time is running out.",
                sentence,
            )

    signals.sort(key=lambda s: (-SEVERITY_ORDER[s.severity], s.rule_id))
    return signals


def choose_route(text: str, signals: list[DetectedSignal]) -> RouteDecision:
    """Pick the official next step. Deterministic, fixed priority.

    Priority: cybercrime (money already lost) > SCORES (intermediary complaint)
    > Sachet (unregistered scheme). Never chosen by the model.
    """
    sentences = _sentences(_normalize(text))
    has_high = any(SEVERITY_ORDER[s.severity] >= SEVERITY_ORDER["high"] for s in signals)
    unregistered_claim = any(
        s.rule_id == "R10_UNREGISTERED_RETURN_CLAIM" for s in signals
    )

    if has_high and any(_LOSS_CONTEXT.search(s) for s in sentences):
        return RouteDecision(
            route_id="cybercrime_1930",
            reason=(
                "Money already paid or lost is mentioned together with "
                "high-urgency signals."
            ),
        )

    if any(
        _INTERMEDIARY.search(s) and _COMPLAINT_CONTEXT.search(s) for s in sentences
    ):
        return RouteDecision(
            route_id="scores",
            reason=(
                "A complaint involving a broker or regulated intermediary "
                "is described."
            ),
        )

    if (
        any(_SCHEME_TERMS.search(s) for s in sentences) or unregistered_claim
    ) and (has_high or any(_COMPLAINT_CONTEXT.search(s) for s in sentences)):
        return RouteDecision(
            route_id="sachet",
            reason="A deposit, chit-style or unregistered scheme is described.",
        )

    return RouteDecision(
        route_id="none",
        reason="No complaint, loss or scheme context was detected.",
    )
