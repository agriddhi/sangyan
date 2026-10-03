"""ask.py - questions about the document, answered from the document.

The reader asks about anything: a word, a sentence, "what happens if I pay
two months late?". The answer comes from their own document. When the
document genuinely does not cover the question, a clearly labelled general
explanation is given instead.

How it works:
1. Every line of the document is scored against the question's words; the
   best lines and their neighbours become an evidence block.
2. The model is given ONLY that block. It replies with JSON:
   {"found": true, "answer": "...", "quote": "...", "general": "..."}
3. A document answer is kept ONLY if the quote appears verbatim in the block.
   If nothing can be verified, the model is asked which words to search for,
   the document is searched again, and it answers one more time.

Trust rules:
* Nothing the document does not contain is presented as the document's view.
* Text that merely talks about the document is never shown as a general
  answer; it is shown as unverified.
* Advice questions ("which one should I take?") are declined, not answered.
* No verdicts, no recommendations, no predictions.

Run it directly:
    python -m app.engine.ask <file.txt> "your question" [en|hi|ta] [--focus "line"]
"""

from __future__ import annotations

import json
import re

ANSWER_MAX_CHARS = 700
GENERAL_MAX_CHARS = 400
QUOTE_MAX_CHARS = 260
BLOCK_MAX_LINES = 80
BLOCK_MAX_CHARS = 12_000
CONTEXT_LINES = 2
TOP_LINES = 20
MATCH_LINES = 4
PLANNER_MAX_TERMS = 6

# Text containing any of these is describing the document rather than
# explaining something in general. It is never shown as a general answer,
# because a general answer must not claim to come from the document.
_DOC_REFERENCE_WORDS = (
    "document",
    "lines above",
    "the provided",
    "this text",
    "provided lines",
    "these lines",
    "the agreement",
    "the clause",
    "the schedule",
)

DEFAULT_LANGUAGE = "en"

_LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}

_BANNED = (
    "you should",
    "we recommend",
    "i recommend",
    "is a scam",
    "is fraud",
    "is fraudulent",
    "guaranteed safe",
    "safe to invest",
    "buy this",
    "sell this",
    "definitely",
)

_ADVICE_PATTERNS = (
    r"\bshould i\b",
    r"\bshall i\b",
    r"\bwhich (one|should|is better)\b",
    r"\bwhat should i\b",
    r"\brecommend me\b",
    r"\bcan you advise\b",
    r"\bbest (option|choice|fund|loan|policy) for me\b",
    r"\bis it (safe|worth)\b",
    r"\bworth investing\b",
)

# Retrieval aids only: extra search words used when the question is about
# paying late. They are not financial facts and nothing is stored.
_LATE_QUESTION_WORDS = ("late", "delay", "delayed", "miss", "missed", "overdue", "skip", "default")
_LATE_SEARCH_WORDS = (
    "late", "overdue", "penalty", "charges", "default", "bounced", "bounce",
    "delinquen", "due date", "instalment", "installment", "repayment",
)

_STOP_WORDS = {
    "what", "does", "do", "did", "mean", "means", "meant", "meaning",
    "this", "that", "these", "those", "the", "and", "for", "from",
    "here", "you", "your", "are", "was", "were", "have", "has",
    "please", "explain", "tell", "about", "term", "word", "words",
    "document", "text", "matter", "kya", "hai", "ka", "ki", "ke",
    "mein", "se", "aur", "matlab", "iska", "is", "ko", "par",
    "इस", "का", "की", "के", "में", "है", "से", "और", "क्या",
    "मतलब", "इसे", "को", "पर", "हैं", "बताओ", "समझाओ",
    "इत", "என்றால்", "அது", "என்ன", "மூலம்", "ஆகும்",
    "இந்த", "அந்த", "எனக்கு", "வேண்டும்", "என்னை",
}

_SYSTEM_PROMPT = (
    "You answer questions about one document for a first-time reader in India. "
    "You report what the document states. You never advise, never recommend, "
    "and never predict outcomes. You reply with JSON only."
)

_SYSTEM_PLAN = (
    "You turn a reader's question into short search words for finding the "
    "matching lines inside their own document. You reply with JSON only."
)

_JSON_SHAPE = (
    '{"found": true or false, '
    '"answer": "how the document lines above treat this, 1 to 3 simple '
    'sentences, or an empty string", '
    '"quote": "the single most relevant sentence copied word for word from '
    'the document lines above, in the original language, or an empty string", '
    '"general": "a plain general explanation when the lines above do not '
    'address the question, or the everyday meaning of a word, or an empty '
    'string"}'
)

_JSON_TERMS = '{"terms": ["word or short phrase", ...]}'

_NOT_FOUND = {
    "en": "This document does not state that, and there is nothing general to add. Rather than guess, here are the closest lines it does contain:",
    "hi": "इस दस्तावेज़ में यह बात नहीं लिखी है, और सामान्य रूप से कुछ जोड़ने को नहीं है। अंदाज़ा लगाने के बजाय, यहाँ वे करीबी पंक्तियाँ हैं जो इसमें हैं:",
    "ta": "இந்த ஆவணத்தில் இது குறிப்பிடப்படவில்லை, பொதுவாகவும் ஏதும் சேர்க்க இல்லை. ஊகித்து சொல்வதற்குப் பதிலாக, இதில் உள்ள மிக நெருக்கமான வரிகள் இவை:",
}

_NO_QUESTION = {
    "en": "Please type the word, sentence or line you want explained.",
    "hi": "कृपया वह शब्द, वाक्य या पंक्ति लिखें जिसे समझाना है।",
    "ta": "விளக்க வேண்டிய சொல், வாக்கியம் அல்லது வரியைத் தட்டச்சு செய்யவும்.",
}

_NO_DOCUMENT = {
    "en": "Paste the document first, so I can find that part in it.",
    "hi": "पहले दस्तावेज़ पेस्ट करें, ताकि मैं उसमें वह हिस्सा ढूँढ सकूँ।",
    "ta": "முதலில் ஆவணத்தை ஒட்டவும், அப்போதுதான் அதில் அந்தப் பகுதியைக் கண்டுபிடிக்க முடியும்.",
}

_DECLINED = {
    "en": "I only explain what this document says. Which option to choose, or what to do, is not something a document can answer.",
    "hi": "मैं केवल यह बताता हूँ कि दस्तावेज़ में क्या लिखा है। कौन सा चुनना है या क्या करना है, यह दस्तावेज़ नहीं बता सकता।",
    "ta": "ஆவணத்தில் என்ன எழுதப்பட்டுள்ளது என்பதை மட்டுமே நான் விளக்குகிறேன். எதைத் தேர்ந்தெடுக்க வேண்டும் என்பது இந்த ஆவணம் சொல்லாது.",
}

_NOTICE = {
    "document_answer": {
        "en": "From your document:",
        "hi": "आपके दस्तावेज़ के अनुसार:",
        "ta": "உங்கள் ஆவணத்தின்படி:",
    },
    "general_answer": {
        "en": "General explanation - not stated in your document; may not apply.",
        "hi": "सामान्य जानकारी - यह आपके दस्तावेज़ में नहीं लिखा है; शायद आप पर लागू न हो।",
        "ta": "பொதுவான விளக்கம் - இது உங்கள் ஆவணத்தில் இல்லை; உங்களுக்கு பொருந்தாமல் இருக்கலாம்.",
    },
    "unverified": {
        "en": "This could not be confirmed against the document's exact words.",
        "hi": "इसे दस्तावेज़ के शब्दों से पुष्टि नहीं किया जा सका।",
        "ta": "ஆவணத்தின் சொற்களால் இதை உறுதிப்படுத்த முடியவில்லை.",
    },
    "not_found": {
        "en": "Not found in this document.",
        "hi": "इस दस्तावेज़ में नहीं मिला।",
        "ta": "இந்த ஆவணத்தில் கிடைக்கவில்லை.",
    },
    "declined": {
        "en": "Not answered by design.",
        "hi": "जानबूझकर उत्तर नहीं दिया गया।",
        "ta": "உத்தேசமாக பதில் அளிக்கப்படவில்லை.",
    },
}


# ------------------------------------------------------------- text helpers

def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _cut(text: str, limit: int) -> str:
    text = str(text or "").strip()
    if limit <= 0 or len(text) <= limit:
        return text
    cut = text[:limit]
    space = cut.rfind(" ")
    if space > limit // 2:
        cut = cut[:space]
    return cut.rstrip(" ,;:.-") + "..."


def _has_banned(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(phrase in lowered for phrase in _BANNED)


def _is_advice_request(question: str) -> bool:
    lowered = str(question or "").lower()
    return any(re.search(pattern, lowered) for pattern in _ADVICE_PATTERNS)


def _quote_is_real(quote: str, source: str) -> bool:
    needle = _collapse(quote)
    return len(needle) >= 12 and needle in _collapse(source)


def _parse_json_object(raw: str) -> dict:
    """Pull the first JSON object out of a model reply."""
    if not raw:
        return {}
    text = str(raw).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```\s*$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end <= start:
        return {}
    try:
        data = json.loads(text[start:end + 1])
    except (ValueError, TypeError):
        return {}
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------- retrieval

def _content_words(question: str, limit: int = 10) -> list:
    """The meaningful words of a question, safe for Hindi and Tamil."""
    words = re.findall(r"[^\W\d_]{3,}", str(question or "").lower())
    result = []
    seen = set()
    for word in words:
        if word in _STOP_WORDS or word in seen:
            continue
        seen.add(word)
        result.append(word)
        if len(result) >= limit:
            break
    return result


def _search_words(question: str) -> list:
    """Question words, plus a few search words when it is about paying late."""
    words = _content_words(question, limit=20)
    lowered = str(question or "").lower()
    if any(word in lowered for word in _LATE_QUESTION_WORDS):
        for extra in _LATE_SEARCH_WORDS:
            if extra not in words:
                words.append(extra)
    return words


def _document_lines(document: str) -> list:
    cleaned = (_collapse(raw) for raw in (document or "").splitlines())
    return [line for line in cleaned if line]


def _score_line(line: str, words: list) -> int:
    """How well one line matches. Longer matched words count more."""
    lowered = line.lower()
    return sum(len(word) for word in words if word in lowered)


def _evidence(document: str, question: str, focus: str = ""):
    """Return (evidence_block, matching_lines) for one question."""
    lines = _document_lines(document)
    if not lines:
        return "", []

    words = _search_words(question)

    focus_index = -1
    focus_text = _collapse(focus)
    if focus_text:
        focus_words = _content_words(focus_text)
        if focus_words:
            best = max(range(len(lines)), key=lambda index: _score_line(lines[index], focus_words))
            if _score_line(lines[best], focus_words) > 0:
                focus_index = best

    ranked = sorted(
        ((_score_line(line, words), index) for index, line in enumerate(lines)),
        key=lambda pair: (-pair[0], pair[1]),
    )
    top = [index for score, index in ranked[:TOP_LINES] if score > 0]

    if not top and focus_index < 0:
        return "\n".join(lines[:10])[:BLOCK_MAX_CHARS], []

    picked = [focus_index] if focus_index >= 0 else []
    picked.extend(index for index in top if index != focus_index)

    window = []
    for index in picked:
        low = max(0, index - CONTEXT_LINES)
        high = min(len(lines), index + CONTEXT_LINES + 1)
        window.extend(range(low, high))
    ordered = [index for index in window if index not in picked]
    ordered = picked + ordered

    block = "\n".join(lines[index] for index in ordered[:BLOCK_MAX_LINES])
    matches = [lines[index] for index in picked[:MATCH_LINES]]
    return block[:BLOCK_MAX_CHARS], matches


# ---------------------------------------------------------------- the model

def _model_answer(model_call, block: str, question: str, language: str) -> dict:
    """Ask the model about one block of the reader's document."""
    if model_call is None or not block:
        return {}
    language_name = _LANGUAGE_NAMES.get(language, "English")
    user_prompt = (
        f"Document lines:\n\"\"\"\n{block}\n\"\"\"\n\n"
        f"Question from the reader: {question}\n\n"
        f"Answer in simple {language_name} for a first-time reader.\n"
        f"Rules:\n"
        f"- Use ONLY the lines above for the answer and the quote.\n"
        f"- The quote must be ONE sentence copied word for word from the "
        f"lines above, in the original language, never translated.\n"
        f"- If the lines address the question even partly, set found to true. "
        f"Answer what the lines do say, and you may say what they do not "
        f"specify. Quote the most relevant sentence.\n"
        f"- Set found to false ONLY when the lines have nothing to do with "
        f"the question. Then answer and quote must be empty strings.\n"
        f"- general is for what the document does NOT cover: the everyday "
        f"meaning of a word, or a plain general explanation. It must never "
        f"mention the document, the lines, the agreement or the clause.\n"
        f"- Never say buy, sell, hold, safe, fraud, or recommend anything.\n"
        f"- Reply with JSON only, in this exact shape:\n"
        + _JSON_SHAPE
        + "\n"
    )
    try:
        raw = model_call(_SYSTEM_PROMPT, user_prompt)
    except Exception:
        return {}
    return _parse_json_object(raw)


def _plan_terms(model_call, question: str) -> list:
    """Ask which words to search for. One short call, no document shown.

    Used only when the first attempt could not be verified, so an ordinary
    question still costs a single model call.
    """
    if model_call is None:
        return []
    user_prompt = (
        f"Question: {question}\n\n"
        f"List 3 to {PLANNER_MAX_TERMS} short words or short phrases that are "
        f"most likely to appear in the document lines that answer this "
        f"question. Use the everyday wording a bank, insurer or employer "
        f"would write, not the reader's wording. No explanation.\n"
        f"Reply with JSON only, in this exact shape:\n"
        f"{_JSON_TERMS}\n"
    )
    try:
        raw = model_call(_SYSTEM_PLAN, user_prompt)
    except Exception:
        return []
    data = _parse_json_object(raw)
    terms = data.get("terms") or []
    result = []
    for term in terms:
        if isinstance(term, str):
            value = _collapse(term)
            if 2 < len(value) <= 40 and value not in result:
                result.append(value)
        if len(result) >= PLANNER_MAX_TERMS:
            break
    return result


# ------------------------------------------------------------------ the API

def _result(status: str, message: str, language: str, lines: list,
            quote: str = "", general: str = "") -> dict:
    """One flat shape, whatever happened."""
    notices = _NOTICE.get(status, {})
    return {
        "status": status,
        "answer": _cut(message, ANSWER_MAX_CHARS),
        "quote": _cut(quote, QUOTE_MAX_CHARS),
        "general": _cut(general, GENERAL_MAX_CHARS),
        "lines": list(lines or [])[:MATCH_LINES],
        "notice": notices.get(language, ""),
        "language": language,
    }


def _extract(data: dict, block: str):
    """Pull (found, answer, quote, general) out of one model reply.

    The quote is verified against the evidence block. No real quote means no
    document answer.
    """
    found = bool(data.get("found"))
    answer = _collapse(str(data.get("answer") or ""))
    quote = _collapse(str(data.get("quote") or ""))
    general = _collapse(str(data.get("general") or ""))

    if not _quote_is_real(quote, block):
        found = False
        answer = ""
        quote = ""
    if _has_banned(answer) or _has_banned(general):
        found = False
        answer = ""
        general = ""
    if not found:
        answer = ""
        quote = ""
    return found, answer, quote, general


def _mentions_document(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(word in lowered for word in _DOC_REFERENCE_WORDS)

_GENERAL_SYSTEM = (
    "You explain financial words, short phrases and situations for a "
    "first-time reader in India. You give a plain, educational explanation "
    "only. You never advise, never recommend a product, never predict a "
    "price or return, and never call anything a scam or fraud. You reply "
    "with JSON only."
)

_GENERAL_SHAPE = (
    '{"explanation": "a plain explanation in 1 to 3 simple sentences, in the '
    'chosen language, "not_in_document": "one short sentence telling the '
    'reader this is general knowledge and may not apply to their document"}'
)


def _dedupe_lines(lines, limit: int = MATCH_LINES) -> list:
    """Same line twice is noise. Keep the first occurrence, keep order."""
    seen = set()
    out = []
    for line in lines or []:
        text = str(line or "").strip()
        key = re.sub(r"\s+", " ", text).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(text)
        if len(out) >= limit:
            break
    return out


def _general_explanation(model_call, question: str, language: str) -> str:
    """Explain a word, phrase or question in general, when the document is silent.

    The document is deliberately NOT shown here. A general explanation must
    never borrow the document's authority, so it is answered from general
    knowledge and always shown with the 'not stated in your document' notice.
    """
    if model_call is None or not str(question or "").strip():
        return ""
    language_name = _LANGUAGE_NAMES.get(language, "English")
    user_prompt = (
        f"A first-time reader in India asks: {question}\n\n"
        f"Answer in simple {language_name}, 1 to 3 sentences.\n"
        f"Rules:\n"
        f"- If they ask what a word or short phrase means, give its plain meaning.\n"
        f"- If they ask about a situation, for example what usually happens if a "
        f"payment is late, explain how it generally works in Indian banking and "
        f"say clearly it may not apply to their document.\n"
        f"- Never advise, never recommend a product, never predict a return, and "
        f"never call anything a scam or fraud.\n"
        f"- Reply with JSON only: {_GENERAL_SHAPE}"
    )
    try:
        raw = model_call(_GENERAL_SYSTEM, user_prompt)
        data = _parse_json_object(raw)
    except Exception:
        return ""
    if not isinstance(data, dict):
        return ""
    text = str(data.get("explanation") or "").strip()
    if not text:
        return ""
    if _has_banned(text):          # same guard used everywhere else
        return ""
    return _cut(text, GENERAL_MAX_CHARS)


def answer_question(document: str, question: str, language: str = DEFAULT_LANGUAGE,
                    model_call=None, focus: str = "") -> dict:
    """Answer one question about one document. Never raises."""
    document = document or ""
    question = _collapse(question)
    language = language if language in _LANGUAGE_NAMES else DEFAULT_LANGUAGE

    if not question:
        return _result("not_found", _NO_QUESTION[language], language, [])
    if not document.strip():
        return _result("not_found", _NO_DOCUMENT[language], language, [])
    if _is_advice_request(question):
        return _result("declined", _DECLINED[language], language, [])

    # Pass 1 - search with the reader's own words.
    block, matches = _evidence(document, question, focus)
    data = _model_answer(model_call, block, question, language)
    found, answer, quote, general = _extract(data, block)

    # Pass 2 - only when nothing could be verified. The model suggests the
    # words worth searching for, we search again, and it answers once more.
    if not found and model_call is not None:
        extra = _plan_terms(model_call, question)
        if extra:
            retry_block, retry_matches = _evidence(
                document, question + " " + " ".join(extra), focus
            )
            if retry_block and retry_block != block:
                retry_data = _model_answer(model_call, retry_block, question, language)
                retry_found, retry_answer, retry_quote, retry_general = _extract(
                    retry_data, retry_block
                )
                if retry_found or retry_general:
                    block, matches = retry_block, retry_matches
                    found, answer, quote, general = (
                        retry_found, retry_answer, retry_quote, retry_general
                    )

    if found and answer:
        return _result("document_answer", answer, language, matches, quote, general)

    matches = _dedupe_lines(matches)
    general = _general_explanation(model_call, (focus or question), language)
    if general:
        result = _result("general_answer", general, language, matches)
        result["general"] = general
        return result
    return _result("not_found", _NOT_FOUND[language], language, matches)

  




# ------------------------------------------------------------- command line

def main() -> None:
    import sys
    from pathlib import Path

    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        return

    path = Path(args[0])
    if not path.is_file():
        print("File not found: " + str(path))
        return

    language = DEFAULT_LANGUAGE
    focus = ""
    question_words = []
    skip = False
    for index, value in enumerate(args[1:], start=1):
        if skip:
            skip = False
            continue
        if value == "--focus":
            if index + 1 < len(args):
                focus = args[index + 1]
                skip = True
            continue
        if value in _LANGUAGE_NAMES:
            language = value
            continue
        question_words.append(value)

    model_call = None
    if "--no-ai" not in args:
        try:
            from app.providers import llm
            model_call = llm.model_call
            print("AI layer: enabled")
        except Exception:
            model_call = None
    if model_call is None:
        print("AI layer: off (keyword matches only)")

    raw = path.read_text(encoding="utf-8", errors="replace")
    result = answer_question(
        raw,
        " ".join(question_words),
        language=language,
        model_call=model_call,
        focus=focus,
    )

    print("")
    print("status : " + result["status"])
    if result["notice"]:
        print("notice : " + result["notice"])
    print("answer : " + result["answer"])
    if result["general"]:
        print("general: " + result["general"])
    if result["quote"]:
        print("quote  : " + result["quote"])
    for line in result["lines"]:
        print("match  : " + line)


if __name__ == "__main__":
    main()
