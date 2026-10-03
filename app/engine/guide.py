"""The grounded guide: answers questions about the card on screen.

Design rules:
* The guide never judges whether a message is genuine, and never advises.
* Six of seven intents are answered straight from the card: deterministic,
  instant, and unable to invent facts.
* Only the SIMPLER intent calls the model. Its output is rejected if it
  contains a banned verdict/advice phrase, or if it introduces any link,
  number, percentage or contact detail that is not already in the card.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.engine import glossary
from app.schemas import LearningActionCard

MAX_ANSWER = 600

_TOKEN = re.compile(r"[A-Za-z\u0900-\u097F\u0B80-\u0BFF]{2,}")

_BANNED_MARKERS = (
    "is a scam",
    "is fraud",
    "is fraudulent",
    "guaranteed safe",
    "safe to invest",
    "you should buy",
    "you should sell",
    "we recommend",
    "i recommend",
    "guaranteed return",
    "guaranteed profit",
    "assured return",
)

_SIMPLER_WORDS = (
    "simpler", "simple", "easier", "easy words", "easy language",
    "short version", "summar", "आसान", "सरल", "साधारण", "छोटा",
    "எளிய", "எளித", "சுருக்",
)

_VERIFY_WORDS = (
    "genuine", "real", "scam", "fraud", "fake", "safe", "trust", "true", "legit",
    "असली", "नकली", "सच", "धोखा", "भरोसा", "உண்மை", "மோசடி", "போலி", "நம்ப",
)

_NEXT_WORDS = (
    "what should i do", "what do i do", "what now", "next step", "what next",
    "should i do", "what to do", "wait", "pause",
    "रुक", "करना चाहिए", "क्या करूँ", "क्या करूं", "आगे",
    "என்ன செய்ய", "அடுத்து", "காத்திரு",
)

_RISK_WORDS = (
    "why", "risky", "risk", "danger", "problem", "flag", "wrong", "alert",
    "warning", "खतरा", "जोखिम", "गड़बड़", "चेतावनी", "क्यों",
    "ஆபத்த", "ஏன்", "எச்சரிக்க",
)

_REQUEST_WORDS = (
    "asking", "ask me", "want from me", "wants from me", "asking me",
    "what does it want", "मांग", "क्या चाह", "चाहता",
    "என்ன கேட்க", "கேட்கிற",
)

_FACT_PATTERNS = (
    re.compile(r"https?://\S+|www\.\S+", re.IGNORECASE),
    re.compile(r"\b[a-z0-9-]+\.(?:com|net|org|in|co|io|ly|gov|info)\b\S*", re.IGNORECASE),
    re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+"),
    re.compile(r"(?:\+?91[\s-]?)?\b\d{5}[\s-]?\d{5}\b"),
    re.compile(r"[₹$]\s?[\d,]+(?:\.\d+)?"),
    re.compile(r"\bRs\.?\s?[\d,]+(?:\.\d+)?", re.IGNORECASE),
    re.compile(r"\b\d{1,3}(?:,\d{2,3})+\b"),
    re.compile(r"\b\d+(?:\.\d+)?\s?%"),
)

_COMPARE_STRIP = re.compile(r"[\s,]")


@dataclass
class GuideAnswer:
    intent: str
    text: str
    ai_used: bool = False


def answer_question(question: str, card: LearningActionCard, language: str = "en") -> GuideAnswer:
    """Answer from the card only. Unknown questions get a helpful fallback."""
    q = (question or "").strip().lower()

    if _has(q, _SIMPLER_WORDS):
        return _answer_simpler(card, language)
    if _has(q, _VERIFY_WORDS):
        return _answer_verify(card)
    if _has(q, _NEXT_WORDS):
        return _answer_next(card)

    named = _named_from_question(question, card, language)
    if named is not None:
        kind, _, text = named
        return GuideAnswer(kind, _trim(text), False)

    if _has(q, _RISK_WORDS):
        return _answer_risk(card)
    if _has(q, _REQUEST_WORDS):
        return _answer_request(card)
    return _answer_unknown(card)


def _has(text: str, words) -> bool:
    return any(word in text for word in words)


def _matches_name(lowered_question: str, name: str) -> bool:
    """True if the question mentions this term/document by its head word."""
    if not name:
        return False
    q_tokens = set(_TOKEN.findall(lowered_question))
    tokens = _TOKEN.findall(name)
    if tokens and tokens[0].lower() in q_tokens:
        return True
    for token in tokens:
        if token.isupper() and len(token) >= 2 and token.lower() in q_tokens:
            return True
    phrase = name.strip().lower()
    return len(phrase) >= 4 and phrase in lowered_question


def _document_text(display: str, purpose: str, note: str) -> str:
    text = f"{display}: {purpose}".strip().rstrip(": ")
    if note:
        text = f"{text} {note}".strip()
    return text


def _named_from_question(question: str, card: LearningActionCard, language: str):
    """Find the term or document the question is about, from the card or the glossary."""
    lowered = question.lower()
    for doc in card.documents:
        if _matches_name(lowered, doc.document):
            return ("document", doc.document, _document_text(doc.document, doc.common_purpose, doc.context_note))
    for term in card.terms:
        if _matches_name(lowered, term.term):
            return ("term", term.term, f"{term.term}: {term.simple_meaning}")

    found = glossary.find_terms(question, language)
    if found:
        t = found[0]
        return ("term", t.term, f"{t.term}: {t.simple_meaning}")
    found = glossary.find_documents(question, language)
    if found:
        d = found[0]
        return ("document", d.document, _document_text(d.document, d.common_purpose, d.context_note))
    return None


def _answer_verify(card: LearningActionCard) -> GuideAnswer:
    text = card.uncertainty.strip() or (
        "I cannot confirm who sent this or whether it is genuine. "
        "Verify through an official channel you find yourself — never through contact details in the message."
    )
    return GuideAnswer("verify", _trim(text), False)


def _answer_request(card: LearningActionCard) -> GuideAnswer:
    text = card.comprehension_check.correct_learning_point.strip() or card.plain_summary.strip()
    if not text:
        text = "Read the card again and name, in your own words, what the message asks you to do before acting."
    return GuideAnswer("request", _trim(text), False)


def _answer_risk(card: LearningActionCard) -> GuideAnswer:
    if not card.signals:
        text = (
            "Nothing in this message matched a known warning pattern. That is not a clearance — "
            "it only means no pattern fired. Check who sent it and why before acting."
        )
    else:
        parts = [f"{s.title}: {s.explanation}" for s in card.signals[:3] if s.title or s.explanation]
        text = " ".join(parts)
        if len(card.signals) > 3:
            text += f" ({len(card.signals) - 3} more patterns are listed on the card.)"
    return GuideAnswer("risk", _trim(text), False)


def _answer_next(card: LearningActionCard) -> GuideAnswer:
    parts = []
    if card.route.action_text.strip():
        parts.append(card.route.action_text.strip())
    if card.pause_checklist:
        parts.append(card.pause_checklist[0])
    text = " ".join(parts) or (
        "Follow the pause checklist on the card: wait, verify through an official channel, "
        "and tell someone you trust."
    )
    return GuideAnswer("next_step", _trim(text), False)


def _card_digest(card: LearningActionCard) -> str:
    """Everything the card knows, as one text for the model to simplify."""
    parts = []
    if card.plain_summary.strip():
        parts.append(card.plain_summary.strip())
    if card.signals:
        titles = [s.title.strip() for s in card.signals[:4] if s.title.strip()]
        if titles:
            parts.append("Warning patterns: " + "; ".join(titles))
    if card.terms:
        names = [t.term.strip() for t in card.terms[:4] if t.term.strip()]
        if names:
            parts.append("Terms: " + ", ".join(names))
    if card.documents:
        names = [d.document.strip() for d in card.documents[:4] if d.document.strip()]
        if names:
            parts.append("Documents asked for: " + ", ".join(names))
    if card.pause_checklist:
        parts.append("Pause steps: " + " ".join(card.pause_checklist[:2]))
    if card.route.action_text.strip():
        parts.append("Next step: " + card.route.action_text.strip())
    return "\n".join(parts)


def _answer_simpler(card: LearningActionCard, language: str) -> GuideAnswer:
    fallback = card.plain_summary.strip() or (
        "This card is a reading aid: it shows what the message claims, what it asks for, and safe next steps."
    )
    digest = _card_digest(card)
    if digest:
        result = _ai_simplify(digest, language)
        if result:
            return GuideAnswer("simpler", _trim(result), True)
    return GuideAnswer("simpler", _trim(fallback), False)


def _ai_simplify(text: str, language: str):
    """Ask the model to simplify the card digest. None if unavailable, unsafe, or it adds facts."""
    try:
        from app.providers import gemini
    except Exception:
        return None
    simplify = getattr(gemini, "simplify", None)
    if simplify is None:
        return None
    try:
        result = simplify(text, language)
    except Exception:
        return None
    if not isinstance(result, str):
        return None
    cleaned = _strip_markdown(result)
    if not cleaned or _has_banned(cleaned):
        return None
    if _introduces_new_facts(cleaned, text):
        return None
    return cleaned


def _strip_markdown(text: str) -> str:
    cleaned = text.replace("**", "").replace("__", "")
    cleaned = re.sub(r"^[#>\-\*\s]+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"`+", "", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def _has_banned(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _BANNED_MARKERS)


def _normalise_for_compare(text: str) -> str:
    return _COMPARE_STRIP.sub("", (text or "").lower())


def _introduces_new_facts(candidate: str, source: str) -> bool:
    """True if the candidate mentions any link, contact or figure that is not in the source."""
    haystack = _normalise_for_compare(source)
    for pattern in _FACT_PATTERNS:
        for match in pattern.finditer(candidate):
            if _normalise_for_compare(match.group(0)) not in haystack:
                return True
    return False


def _trim(text: str, limit: int = MAX_ANSWER) -> str:
    """Spoken answers must stay short: cut at a sentence boundary, never mid-word."""
    text = re.sub(r"\s+", " ", text or "").strip()
    if len(text) <= limit:
        return text
    cut = text[:limit]
    for boundary in (". ", "! ", "? ", "। "):
        position = cut.rfind(boundary)
        if position > limit // 2:
            return cut[: position + 1].strip()
    return cut.rsplit(" ", 1)[0].strip()


def _answer_unknown(card: LearningActionCard) -> GuideAnswer:
    options = [
        "what is this message asking me to do",
        "why was this flagged",
        "what should I do now",
    ]
    if card.terms:
        options.insert(0, f"what does {card.terms[0].term.split('(')[0].strip()} mean")
    text = "I can only answer from this card. Try asking: " + "; ".join(options) + "."
    return GuideAnswer("unknown", _trim(text), False)
