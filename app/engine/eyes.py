"""eyes.py - the two extra checks.

1) Clauses to review
   Deterministic patterns that mark clauses a first-time reader should read
   twice: auto-renewal, prepayment charges, rate changes, data sharing, lien
   and set-off, arbitration, and so on. A flag is a POINTER, never a verdict.
   It says "this clause exists, read it", not "this is bad".

2) Will this suit me?
   The reader answers 3 short questions. For each answer the app puts the
   reader's own words next to the document's own words, quoted exactly. If the
   document is silent, a general answer is given instead, clearly labelled as
   not coming from the document. It never says whether the product is
   suitable. The decision stays with the reader, and that is stated.

Both features obey one rule: nothing is shown as the document's view unless it
is copied word for word from the document the reader pasted.

Guardrails: no verdicts, no recommendations, no predictions, no ranking.

Run it directly:
    python -m app.engine.eyes <file.txt> [en|hi|ta]
"""

from __future__ import annotations

import inspect
import re

from app.engine.ask import answer_question

MAX_FLAGS = 12
EXPLAIN_MAX_CHARS = 500
MAX_LINE_CHARS = 260

DEFAULT_LANGUAGE = "en"
_LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "ta": "Tamil"}

# --------------------------------------------------------------- ai plumbing

# The factory that hands back model_call(system_prompt, user_prompt) -> str.
# Its name has changed once already, so: try the known names, then accept
# exactly ONE obvious zero-argument factory. If that is ambiguous we return
# None and the app runs without AI rather than calling the wrong thing.
_EXPLICIT_FACTORIES = (
    "get_model_call",
    "model_call",
    "make_model_call",
    "get_llm_call",
    "llm_call",
    "build_model_call",
    "default_model_call",
    "get_call",
)


def _required_params(func) -> int:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return 99
    return sum(
        1
        for param in signature.parameters.values()
        if param.default is inspect.Parameter.empty
        and param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD)
    )


def _try_factory(factory):
    try:
        produced = factory()
    except Exception:
        return None
    if callable(produced) and produced is not factory:
        return produced
    return None


def default_model_call():
    """Return the app's model_call, or None when the AI layer is unavailable."""
    try:
        from app.providers import llm
    except Exception:
        return None

    own = getattr(llm, "__name__", "")
    for name in _EXPLICIT_FACTORIES:
        factory = getattr(llm, name, None)
        if not inspect.isfunction(factory):
            continue
        if getattr(factory, "__module__", "") != own:
            continue
        produced = _try_factory(factory)
        if produced is not None:
            return produced

    candidates = []
    for name in dir(llm):
        if name.startswith("_"):
            continue
        obj = getattr(llm, name, None)
        if not inspect.isfunction(obj):
            continue
        if getattr(obj, "__module__", "") != own:
            continue
        lowered = name.lower()
        if "model_call" in lowered or ("llm" in lowered and "call" in lowered):
            if _required_params(obj) == 0:
                candidates.append(obj)

    if len(candidates) == 1:
        return _try_factory(candidates[0])
    return None


# --------------------------------------------------------------------- flags

FLAG_PATTERNS: tuple = (
    {
        "id": "auto_renewal",
        "pattern": r"auto[- ]?renew|renew(?:s|al|ed)?\s+automatically|"
                   r"shall\s+be\s+renewed|automatically\s+(?:be\s+)?extend",
    },
    {
        "id": "prepayment_penalty",
        "pattern": r"pre[- ]?payment\s+(?:charge|penalty|fee)|"
                   r"foreclosure\s+(?:charge|fee)|exit\s+load|prepayment\s+of\s+\d",
    },
    {
        "id": "rate_change",
        "pattern": r"revise\s+the\s+rate\s+of\s+interest|"
                   r"(?:change|revise|reset|alter)[a-z ]{0,20}rate\s+of\s+interest|"
                   r"rate\s+of\s+interest[^.]{0,80}(?:revise|reset|revision|change)",
    },
    {
        "id": "terms_change",
        "pattern": r"change\s+these\s+terms|revise\s+these\s+terms|"
                   r"modify\s+(?:these|the)\s+terms|"
                   r"updated\s+version[^.]{0,60}website|"
                   r"continued\s+use[^.]{0,60}acceptance",
    },
    {
        "id": "data_sharing",
        "pattern": r"(?:share|sharing|disclose|provide|furnish|transfer)[^.]{0,160}"
                   r"(?:information|details|data)[^.]{0,160}"
                   r"(?:partner|credit\s+bureau|third\s+part|affiliate|insurer)|"
                   r"(?:credit\s+bureau|third\s+part(?:y|ies)|affiliate)[^.]{0,160}"
                   r"(?:share|receive|obtain|provide)",
    },
    {
        "id": "lien_setoff",
        "pattern": r"(?:bank|lender)[^.]{0,160}(?:set[- ]?off|right\s+to\s+debit)|"
                   r"(?:set[- ]?off|right\s+to\s+debit)[^.]{0,160}"
                   r"(?:bank|lender|any\s+account)|"
                   r"bankers'?\s+lien|adjust[a-z]*\s+(?:your|the)\s+"
                   r"(?:credit\s+balance|any\s+account)",
    },
    {
        "id": "arbitration",
        "pattern": r"arbitrat(?:ion|or)|sole\s+arbitrator|arbitral",
    },
    {
        "id": "no_reminder",
        "pattern": r"no\s+notice,\s*reminder|will\s+not\s+(?:send|issue)\s+any\s+reminder|"
                   r"no\s+reminder[^.]{0,60}(?:reminder|reminders)",
    },
    {
        "id": "lock_in_exit",
        "pattern": r"lock[- ]?in|minimum\s+holding\s+period|minimum\s+tenure|"
                   r"exit\s+load|cooling[- ]?off\s+period",
    },
    {
        "id": "insurance_conditions",
        "pattern": r"pre[- ]?existing\s+disease|waiting\s+period|"
                   r"intimation[^.]{0,40}(?:24|forty[- ]eight)\s*hours|"
                   r"within\s+\d+\s+days[^.]{0,60}(?:claim|intimat)",
    },
    {
        "id": "nominee",
        "pattern": r"\bnominee\b",
    },
    {
        "id": "joint_liability",
        "pattern": r"jointly\s+and\s+severally|joint\s+and\s+several|"
                   r"jointly\s+and\s+jointly",
    },
    {
        "id": "late_penalty",
        "pattern": r"bounce\s+charge|late\s+(?:payment\s+)?(?:fee|charge|penalty)|"
                   r"penalty\s+of\s+\d|overdue[^.]{0,60}\d+\s*%|"
                   r"\d+\s*%\s*(?:p\.?a\.?|per\s+month|monthly)\s*(?:on\s+)?overdue",
    },
    {
        "id": "inspection_rights",
        "pattern": r"inspect(?:ion|or)?[^.]{0,120}(?:premises|books|accounts|records)|"
                   r"periodical\s+inspection",
    },
    {
        "id": "recall_without_notice",
        "pattern": r"without\s+(?:any\s+)?prior\s+(?:intimation|notice)|"
                   r"recall\s+the\s+entire\s+amount|without\s+notice\s+to\s+the\s+borrower",
    },
)

FLAG_TITLES: dict = {
    "auto_renewal": {
        "en": "The contract can continue on its own",
        "hi": "यह अनुबंध अपने आप जारी रह सकता है",
        "ta": "இந்த ஒப்பந்தம் தானாக தொடரலாம்",
    },
    "prepayment_penalty": {
        "en": "Paying early carries a charge",
        "hi": "जल्दी चुकाने पर शुल्क लगता है",
        "ta": "முன்கூடியாகச் செலுத்தினால் கட்டணம் உள்ளது",
    },
    "rate_change": {
        "en": "The interest rate can be changed",
        "hi": "ब्याज दर बदली जा सकती है",
        "ta": "வட்டி வீதத்தை மாற்றலாம்",
    },
    "terms_change": {
        "en": "The terms can be changed later",
        "hi": "शर्तें बाद में बदली जा सकती हैं",
        "ta": "விதிமுறைகளைப் பின்னர் மாற்றலாம்",
    },
    "data_sharing": {
        "en": "Your details can be passed to others",
        "hi": "आपकी जानकारी दूसरों को दी जा सकती है",
        "ta": "உங்கள் விவரங்கள் பிறருக்குப் பகிரப்படலாம்",
    },
    "lien_setoff": {
        "en": "The lender can take money from your other accounts",
        "hi": "ऋणदाता आपके दूसरे खातों से धन ले सकता है",
        "ta": "கடனளிப்பவர் உங்கள் மற்ற கணக்குகளிலிருந்து பணம் பெறலாம்",
    },
    "arbitration": {
        "en": "Disputes may go to a private arbitrator",
        "hi": "विवाद निजी मध्यस्थ के पास जा सकते हैं",
        "ta": "மோதனைகள் தனியார் நடுவரிடம் செல்லலாம்",
    },
    "no_reminder": {
        "en": "No payment reminders are sent",
        "hi": "भुगतान की कोई अनुस्मारक नहीं भेजा जाता",
        "ta": "கட்டண நினைவூட்டல்கள் வழங்கப்படுவதில்லை",
    },
    "lock_in_exit": {
        "en": "There is a minimum period or an exit charge",
        "hi": "न्यूनतम अवधि या निकास शुल्क है",
        "ta": "குறைந்தபடி காலம் அல்லது வெளியேற்றுக் கட்டணம் உள்ளது",
    },
    "insurance_conditions": {
        "en": "Claims depend on conditions and timelines",
        "hi": "दावे शर्तों और समय-सीमा पर निर्भर हैं",
        "ta": "கோரிக்கைகள் நிபந்தனை மற்றும் காலவரையைச் சார்ந்தவை",
    },
    "nominee": {
        "en": "A nominee is mentioned",
        "hi": "नामांकित व्यक्ति का उल्लेख है",
        "ta": "பெயரிடப்பட்ட நபர் குறிப்பிடப்படுகிறது",
    },
    "joint_liability": {
        "en": "Someone else is jointly responsible",
        "hi": "कोई अन्य व्यक्ति संयुक्त रूप से जिम्मेदार है",
        "ta": "மற்றொரு நபர் இணைந்த பொறுப்புடையவர்",
    },
    "late_penalty": {
        "en": "A penalty applies for late payment",
        "hi": "देरी से भुगतान पर जुर्माना लगता है",
        "ta": "தாமதமாகச் செலுத்தினால் அபராதம் பயன்படுத்தப்படும்",
    },
    "inspection_rights": {
        "en": "The lender can inspect your records or premises",
        "hi": "ऋणदाता आपके रिकॉर्ड या जगह देख सकता है",
        "ta": "கடனளிப்பவர் உங்கள் பதிவுகள் அல்லது இடத்தைப் பார்க்கலாம்",
    },
    "recall_without_notice": {
        "en": "The whole amount can be called back without notice",
        "hi": "बिना सूचना पूरी राशि वापस माँगी जा सकती है",
        "ta": "அறிவிப்பின்றி முழுத் தொகையைக் கோரலாம்",
    },
}

VERIFY_PROMPT = {
    "en": "Read the complete clause in the document above, then check the full terms on the organisation's official website.",
    "hi": "ऊपर दिए गए दस्तावेज़ में पूरी शर्त पढ़ें, फिर संस्था की आधिकारिक वेबसाइट पर पूरी शर्तें जाँचें।",
    "ta": "மேலே உள்ள ஆவணத்தில் முழுக் கூற்றையும் படிந்து, பின்னர் அமைப்பின் அதிகாரப்பூர்வ இணையதளத்தில் முழு விதிமுறைகளையும் சரிபார்க்கவும்.",
}

READ_IT_YOURSELF = {
    "en": "This clause was found in your document. Read it in full above, and ask about any part of it.",
    "hi": "यह शर्त आपके दस्तावेज़ में मिली है। ऊपर इसे पूरा पढ़ें, और किसी भी हिस्से के बारे में पूछ सकते हैं।",
    "ta": "இந்தக் கூற்று உங்கள் ஆவணத்தில் கிடைத்தது. மேலே முழுவதையும் படியுங்கள், எந்தப் பகுதியைப் பற்றியும் கேட்கலாம்.",
}

_FLAG_TITLES_SENTENCE = {
    "en": "Clauses in this document that are worth reading twice.",
    "hi": "इस दस्तावेज़ में वे शर्तें जिन्हें दो बार पढ़ना उचित है।",
    "ta": "இந்த ஆவணத்தில் இரண்டு தடவை படிக்கத் தகுந்த கூற்றுகள்.",
}

_FLAG_EXPLAIN_SYSTEM = (
    "You explain ONE clause from a financial document to a first-time reader "
    "in India. You describe only what that clause says, in simple language and "
    "in the chosen language. You never say whether the clause is good or bad, "
    "never call anything a scam or fraud, never advise, and never recommend. "
    "You reply with JSON only."
)

_FLAG_EXPLAIN_SHAPE = (
    '{"explanation": "2 to 3 simple sentences saying what this clause does in '
    'the document, in the chosen language"}'
)

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


# ------------------------------------------------------------------- helpers

def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _cut(text: str, limit: int) -> str:
    text = _collapse(text)
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _has_banned(text: str) -> bool:
    lowered = str(text or "").lower()
    return any(phrase in lowered for phrase in _BANNED)


def _lines(document: str) -> list:
    out = []
    for raw in str(document or "").splitlines():
        line = _collapse(raw)
        if len(line) >= 25:
            out.append(line)
    return out


def _window(line: str, lines: list, index: int) -> str:
    """The matched line plus a little context, still copied from the document."""
    start = max(0, index - 1)
    end = min(len(lines), index + 2)
    return _cut(" ".join(lines[start:end]), MAX_LINE_CHARS)


def _parse_json_object(raw: str) -> dict:
    import json

    text = str(raw or "").strip()
    if not text:
        return {}
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\s*", "", text)
        text = re.sub(r"```$", "", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return {}
    try:
        loaded = json.loads(text[start : end + 1])
    except ValueError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


# --------------------------------------------------------------------- flags

def find_flags(document: str, language: str = DEFAULT_LANGUAGE, model_call=None) -> dict:
    """Clauses worth reading twice. Each one is the document's own line."""
    if model_call is None:
        model_call = default_model_call()

    lines = _lines(document)
    items = []
    seen_quotes = set()

    for rule in FLAG_PATTERNS:
        if len(items) >= MAX_FLAGS:
            break
        pattern = re.compile(rule["pattern"], re.IGNORECASE)
        found = None
        for index, line in enumerate(lines):
            if pattern.search(line):
                quote = _window(line, lines, index)
                key = re.sub(r"\W+", "", quote.lower())[:120]
                if key in seen_quotes:
                    quote = ""
                else:
                    seen_quotes.add(key)
                found = {"quote": quote, "line": line, "line_index": index}
                break
        if not found:
            continue

        explanation = _explain_clause(model_call, found["line"], language)
        items.append({
            "id": rule["id"],
            "title": FLAG_TITLES.get(rule["id"], {}).get(language)
                     or FLAG_TITLES.get(rule["id"], {}).get("en", rule["id"]),
            "quote": found["quote"] or _cut(found["line"], MAX_LINE_CHARS),
            "matched_text": _cut(found["line"], MAX_LINE_CHARS),
            "explanation": explanation,
            "explanation_source": "model" if explanation else "read_it_yourself",
            "verify_prompt": VERIFY_PROMPT.get(language, VERIFY_PROMPT["en"]),
        })

    return {
        "language": language,
        "intro": _FLAG_TITLES_SENTENCE.get(language, _FLAG_TITLES_SENTENCE["en"]),
        "read_it_yourself": READ_IT_YOURSELF.get(language, READ_IT_YOURSELF["en"]),
        "items": items,
        "checked": len(FLAG_PATTERNS),
    }


def _explain_clause(model_call, line: str, language: str) -> str:
    """Plain-language description of one clause. Never an opinion about it."""
    if model_call is None or not line:
        return ""
    language_name = _LANGUAGE_NAMES.get(language, "English")
    prompt = (
        f"This is one clause copied from a financial document:\n\"\"\"\n{line}\n\"\"\"\n\n"
        f"Explain in simple {language_name}, in 2 to 3 sentences, what this clause "
        f"does for the person signing it.\n"
        f"Rules:\n"
        f"- Describe only what this clause does. Do not say it is good or bad, "
        f"fair or unfair.\n"
        f"- Do not advise, recommend, or predict anything.\n"
        f"- Reply with JSON only: {_FLAG_EXPLAIN_SHAPE}"
    )
    try:
        data = _parse_json_object(model_call(_FLAG_EXPLAIN_SYSTEM, prompt))
    except Exception:
        return ""
    text = _cut(data.get("explanation") or "", EXPLAIN_MAX_CHARS)
    if not text or _has_banned(text):
        return ""
    return text


# ----------------------------------------------------------------- fit check

FIT_QUESTIONS: tuple = (
    {
        "id": "money_soon",
        "ask": "what does this document say about how long the money stays "
               "committed, any lock-in period, and charges for closing early?",
    },
    {
        "id": "miss_payment",
        "ask": "what does this document say happens if a payment is missed or "
               "paid late, including any penalty or extra charge?",
    },
    {
        "id": "emergency_money",
        "ask": "what does this document say about withdrawing, surrendering or "
               "closing the account or policy, and any charge for that?",
    },
    {
        "id": "other_commitments",
        "ask": "what does this document say about other loans, other EMIs or "
               "obligations the borrower already has?",
    },
)

FIT_LABELS = {
    "intro": {
        "en": "Three or four honest answers, next to the document's own words.",
        "hi": "तीन या चार सच्चे उत्तर, दस्तावेज़ के अपने शब्दों के साथ।",
        "ta": "மூன்று அல்லது நான்கு நேர்மையான பதில்கள், ஆவணத்தின் சொற்களுடன்.",
    },
    "question": {
        "money_soon": {
            "en": "Might you need this money within the next 1 to 2 years?",
            "hi": "क्या आपको अगले 1 से 2 वर्षों में यह पैसा चाहिए पड़ सकता है?",
            "ta": "அடுத்த 1 முதல் 2 ஆண்டுகளில் இந்தப் பணம் தேவைப்படலாமா?",
        },
        "miss_payment": {
            "en": "If a payment is missed for a couple of months, could you manage?",
            "hi": "क्या आप एक-दो महीने भुगतान छूटने की स्थिति संभाल सकते हैं?",
            "ta": "ஒரு சில மாதங்கள் கட்டணம் தவறினால் அதைச் சமாள முடியுமா?",
        },
        "emergency_money": {
            "en": "Is this the money you would need in an emergency?",
            "hi": "क्या यह वह पैसा है जो आपको आपातकाल में चाहिए?",
            "ta": "இது அவசரத்தில் தேவையான பணமா?",
        },
        "other_commitments": {
            "en": "Do you already repay another loan, EMI or card bill?",
            "hi": "क्या आप पहले से कोई और ऋण, EMI या कार्ड बिल चुकाते हैं?",
            "ta": "ஏற்கனவே வேறு கடன், EMI அல்லது அட்டைக் கட்டணம் செலுத்துகிறீர்களா?",
        },
    },
    "you_said": {
        "en": "You said",
        "hi": "आपने कहा",
        "ta": "நீங்கள் கூறியது",
    },
    "doc_says": {
        "en": "The document says",
        "hi": "दस्तावेज़ कहता है",
        "ta": "ஆவணம் கூறுவது",
    },
    "in_general": {
        "en": "In general - this is not stated in your document, so it may not apply",
        "hi": "सामान्य रूप से - यह आपके दस्तावेज़ में नहीं लिखा है, इसलिए शायद लागू न हो",
        "ta": "பொதுவாக - இது உங்கள் ஆவணத்தில் குறிப்பிடப்படவில்லை, எனவே பொருந்தாமல் இருக்கலாம்",
    },
    "yes": {"en": "Yes", "hi": "हाँ", "ta": "ஆம்"},
    "no": {"en": "No", "hi": "नहीं", "ta": "இல்லை"},
    "not_found": {
        "en": "I could not find a clause about this in the text you provided. "
              "That does not mean the condition is absent. Check the complete "
              "document, or ask the organisation directly.",
        "hi": "आपके दिए गए पाठ में इस बारे में कोई शर्त नहीं मिली। इसका मतलब यह नहीं कि शर्त नहीं है। पूरा दस्तावेज़ देखें, या संस्था से सीधे पूछें।",
        "ta": "நீங்கள் வழங்கிய உரையில் இதற்கான கூற்று கிடைக்கவில்லை. இது அந்த நிபந்தனை இல்லை என்பதைக் குறிக்காது. முழு ஆவணத்தைப் பாருங்கள், அல்லது அமைப்பிடம் நேரடியாகக் கேளுங்கள்.",
    },
    "disclaimer": {
        "en": "This comparison does not decide whether the product suits you. "
              "It only shows what the document itself says next to what you "
              "said. The decision is yours, and reading the complete official "
              "terms is always the safe step.",
        "hi": "यह तुलना यह तय नहीं करती कि यह उत्पाद आपके लिए उपयुक्त है या नहीं। यह केवल यह दिखाती है कि दस्तावेज़ खुद क्या कहता है, आपकी बात के साथ। निर्णय आपका है, और पूरी आधिकारिक शर्तें पढ़ना हमेशा सुरक्षित कदम है।",
        "ta": "இந்த ஒப்பீடு இந்தத் திட்டம் உங்களுக்கு ஏற்றதா என்பதை முடிவு செய்யாது. ஆவணம் என்ன கூறுகிறது என்பதையே உங்கள் பதிலுடன் காட்டுகிறது. முடிவு உங்களுடையது, முழு அதிகாரப்பூர்வ விதிமுறைகளைப் படிப்பது பாதுகாப்பான செயலாகும்.",
    },
}


def _t(bucket: str, language: str, key: str = "") -> str:
    block = FIT_LABELS.get(bucket, {})
    if key:
        block = block.get(key, {}) if isinstance(block, dict) else {}
    if not isinstance(block, dict):
        return ""
    return block.get(language) or block.get("en") or ""


def run_fit_check(
    document: str,
    answers: dict,
    language: str = DEFAULT_LANGUAGE,
    model_call=None,
) -> dict:
    """Put the reader's own answers next to the document's own words.

    Never answers "does this suit me". It answers only "what does the
    document say about the thing you just told us". When the document is
    silent, a general answer is shown and labelled as not the document's.
    """
    if model_call is None:
        model_call = default_model_call()

    answers = answers if isinstance(answers, dict) else {}
    comparisons = []

    for question in FIT_QUESTIONS:
        raw = str(answers.get(question["id"]) or "").strip().lower()
        if raw not in ("yes", "no"):
            continue
        you_said = _t("yes" if raw == "yes" else "no", language)

        result = answer_question(
            document,
            question["ask"],
            language=language,
            model_call=model_call,
        )
        status = str(result.get("status") or "not_found")
        quote = _cut(result.get("quote") or "", MAX_LINE_CHARS)
        answer = _cut(result.get("answer") or "", EXPLAIN_MAX_CHARS)

        general_text = ""
        if status in ("document_answer", "unverified") and quote and not _has_banned(answer):
            matched = True
        elif status == "general_answer" and answer and not _has_banned(answer):
            matched = False
            general_text = answer          # a real answer, but not the document's
        else:
            matched = False

        comparisons.append({
            "id": question["id"],
            "question": _t("question", language, question["id"]),
            "you_said": you_said,
            "status": "matched" if matched else ("general" if general_text else "not_found"),
            "quote": quote,
            "document_says": answer if matched else "",
            "general_note": general_text,
            "not_found_note": "" if (matched or general_text) else _t("not_found", language),
            "ask_hint": question["ask"],
        })

    return {
        "language": language,
        "intro": _t("intro", language),
        "you_said_label": _t("you_said", language),
        "doc_says_label": _t("doc_says", language),
        "in_general_label": _t("in_general", language),
        "comparisons": comparisons,
        "disclaimer": _t("disclaimer", language),
    }


# ----------------------------------------------------------------------- cli

def main() -> None:
    import sys

    if len(sys.argv) < 2:
        print("usage: python -m app.engine.eyes <file.txt> [en|hi|ta]")
        return

    path = sys.argv[1]
    language = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_LANGUAGE
    if language not in _LANGUAGE_NAMES:
        language = DEFAULT_LANGUAGE

    with open(path, "r", encoding="utf-8") as handle:
        document = handle.read()

    model_call = default_model_call()
    print("AI layer: " + ("enabled" if model_call else "disabled"))
    if not model_call:
        print("  Note: no AI layer found. Clauses stay unexpanded and questions")
        print("  are answered only from exact matches in the document.")

    print("\n" + "=" * 72)
    print("CLAUSES TO REVIEW")
    print("=" * 72)
    result = find_flags(document, language, model_call)
    print(result["intro"])
    if not result["items"]:
        print("No clause from the review list was found in this text.")
    for index, item in enumerate(result["items"], 1):
        print(f"\n  {index}. {item['title']}  [{item['id']}]")
        print(f"     line    : {item['quote']}")
        print(f"     meaning : {item['explanation'] or result['read_it_yourself']}")
        print(f"     check   : {item['verify_prompt']}")

    print("\n" + "=" * 72)
    print("WILL THIS SUIT ME?")
    print("=" * 72)
    fit = run_fit_check(
        document,
        {"money_soon": "yes", "miss_payment": "no"},
        language,
        model_call,
    )
    for item in fit["comparisons"]:
        print(f"\n  Q: {item['question']}")
        print(f"     {fit['you_said_label']}: {item['you_said']}")
        if item["status"] == "matched":
            print(f"     {fit['doc_says_label']}: {item['document_says']}")
            print(f"     line: {item['quote']}")
        elif item["status"] == "general":
            print(f"     {fit['in_general_label']}: {item['general_note']}")
        else:
            print(f"     {item['not_found_note']}")
    print(f"\n  {fit['disclaimer']}")


if __name__ == "__main__":
    main()
