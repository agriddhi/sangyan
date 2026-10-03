"""explainer.py - the document reader.

Takes any document text and returns:
* a short overall summary,
* the document split into named subtopics,
* for every subtopic: a heading, a plain-language explanation, the difficult
  words it contains (each explained simply), and the document's own lines.

Works with NO API key. If a model_call is provided (app/providers/llm.py),
each part is rewritten in plain language and in the chosen language; without
it, the part shows the document's own words, marked as extracted text.

The model_call signature is:  model_call(system_prompt: str, user_prompt: str) -> str
It must return JSON like:
    {"explanation": "...", "quote": "...",
     "hard_words": [{"word": "...", "meaning": "..."}]}

Trust rules that never change:
* An explanation is used ONLY if the model quotes a line that literally exists
  in that section. No quote, no explanation.
* A hard word is listed ONLY if that word literally appears in the section.
* No advice, no verdicts, no recommendations. This file only organizes and
  restates what the document says.

Run it directly:  python -m app.engine.explainer <file.txt> [en|hi|ta] [--no-ai]
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass

# ------------------------------------------------------------------ settings

MAX_SECTIONS = 30
CHUNK_TARGET = 1100
GIST_MAX_CHARS = 900
QUOTE_MAX_CHARS = 240
SUMMARY_MAX_CHARS = 700
SUMMARY_PER_SECTION = 160
HEADING_MAX_CHARS = 90
TITLE_MAX_CHARS = 120
MODEL_SECTION_CHARS = 4000
REPEAT_HEADING_LIMIT = 3
HARD_WORD_LIMIT = 4
QUOTE_MIN_CHARS = 12
QUOTE_SENTENCE_MIN_CHARS = 25

DEFAULT_LANGUAGE = "en"

_SENTENCE_END = re.compile(r"(?<=[.!?\u0964\u0965])\s+")

_NUM_HEADING = re.compile(r"^\d{1,2}[.)]\s+\S.{0,80}$")
_WORD_HEADING = re.compile(
    r"^(article|section|clause|part|schedule|annexure)\s+[\divxlcdm]+[.):]?\b.{0,80}$",
    re.IGNORECASE,
)
_ROMAN_HEADING = re.compile(r"^[IVXLC]{1,6}[.)]\s+\S.{0,80}$")
_CAPS_HEADING = re.compile(r"^[A-Z][A-Z0-9 &/()\-',.]{4,80}$")
_LABEL_HEADING = re.compile(r"^([A-Z][A-Za-z0-9 /&()'\-]{1,40}?):\s+(\S.*)$")

_LANGUAGE_NAMES = {
    "en": "English",
    "hi": "Hindi, written in the Devanagari script",
    "ta": "Tamil",
}

_HARD_WORD_LABELS = {
    "en": "Hard words in this part:",
    "hi": "इस हिस्से के कठिन शब्द:",
    "ta": "இந்தப் பகுதியின் கடினமான சொற்கள்:",
}

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

_SYSTEM_PROMPT = (
    "You explain financial documents to first-time readers in India. "
    "You never advise, never recommend, and never predict outcomes. "
    "You only restate what the document itself says, in simple language. "
    "You reply with JSON only."
)

_JSON_SHAPE = (
    '{"explanation": "simple explanation in the chosen language", '
    '"quote": "the exact sentence(s) from the section text that your '
    'explanation is based on - copied word for word in its original '
    'language, never translated", '
    '"hard_words": [{"word": "a difficult word or phrase that appears '
    'exactly in the section text", "meaning": "its meaning explained '
    'simply in the chosen language"}]}'
)

_STRICT_QUOTE_RULE = (
    "Copy the quote from the section text character for character. "
    "Do not translate it, do not fix its grammar, do not change its "
    "punctuation, and do not merge sentences that are apart in the text."
)


# ---------------------------------------------------------------- data shapes

@dataclass
class Subtopic:
    index: int
    heading: str
    gist: str
    source_quote: str = ""
    explained_by: str = "extract"


@dataclass
class DocumentExplanation:
    language: str
    title: str
    summary: str
    subtopics: list
    word_count: int
    note: str = ""


# ------------------------------------------------------------- small helpers

def _collapse(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _clean_line(text: str) -> str:
    return re.sub(r"[ \t]+", " ", str(text or "")).strip()


def _clean_multiline(text: str) -> str:
    lines = [_clean_line(line) for line in str(text or "").splitlines()]
    return "\n".join(line for line in lines if line).strip()


def _cut(text: str, limit: int) -> str:
    """Trim to `limit` characters, cutting on a word boundary."""
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


def _normalize_for_match(text: str) -> str:
    """Fold the harmless differences a model can introduce.

    Smart quotes, en/em dashes, non-breaking spaces and unicode variants are
    all the same character to a human reader. This makes verification tolerant
    of those and nothing else: the words must still be the document's words.
    """
    text = unicodedata.normalize("NFKC", str(text or ""))
    replacements = {
        "\u2018": "'", "\u2019": "'", "\u201a": "'", "\u201b": "'",
        "\u201c": '"', "\u201d": '"', "\u201e": '"', "\u201f": '"',
        "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-",
        "\u2014": "-", "\u2015": "-", "\u2212": "-",
        "\u00a0": " ", "\u2007": " ", "\u202f": " ", "\u2009": " ",
        "\u200b": "", "\ufeff": "", "\u200c": "", "\u200d": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return _collapse(text)


def _quote_is_real(quote: str, source: str) -> bool:
    """True only when the model's quote really appears in the source text.

    The whole quote must match. If the model joined or split sentences, a
    single sentence of it is enough - but that sentence must still be present
    in the document word for word.
    """
    needle = _normalize_for_match(quote)
    haystack = _normalize_for_match(source)
    if len(needle) >= QUOTE_MIN_CHARS and needle in haystack:
        return True

    for sentence in re.split(r"(?<=[.!?])\s+", needle):
        piece = sentence.strip()
        if len(piece) >= QUOTE_SENTENCE_MIN_CHARS and piece in haystack:
            return True
    return False


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


def _looks_like_caps_heading(text: str) -> bool:
    letters = [char for char in text if char.isalpha()]
    if len(letters) < 3:
        return False
    upper = sum(1 for char in letters if char.isupper())
    return upper / len(letters) >= 0.8


def _detect_heading(line: str):
    """Return (heading, inline_text) if the line looks like a heading."""
    text = _clean_line(line)
    if not text or len(text) > HEADING_MAX_CHARS:
        return None
    label = _LABEL_HEADING.match(text)
    if label:
        return label.group(1).strip(), label.group(2).strip()
    for pattern in (_WORD_HEADING, _NUM_HEADING, _ROMAN_HEADING):
        if pattern.match(text):
            return text, ""
    if _CAPS_HEADING.match(text) and _looks_like_caps_heading(text):
        return text, ""
    return None


# ----------------------------------------------------------------- splitting

def _fallback_chunks(text: str) -> list:
    """No headings found: cut the text into even chunks on blank lines."""
    text = (text or "").strip()
    if not text:
        return [("Document", "")]
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        paragraphs = [text]
    chunks = []
    current = []
    size = 0
    for paragraph in paragraphs:
        current.append(paragraph)
        size += len(paragraph)
        if size >= CHUNK_TARGET:
            chunks.append(" ".join(current))
            current = []
            size = 0
    if current:
        chunks.append(" ".join(current))
    if not chunks:
        chunks = [text]
    return [("Part %d" % (index + 1), chunk) for index, chunk in enumerate(chunks)]


def _split_sections(text: str):
    """Return (title, [(heading, body), ...]).

    A standalone heading that repeats many times is a running page header or
    footer (a form code, a repeated document label), not a real section. Those
    lines are dropped before sections are built, and the title skips them.
    """
    lines = [_clean_line(line) for line in (text or "").splitlines()]

    counts = {}
    for line in lines:
        if not line:
            continue
        detected = _detect_heading(line)
        if detected and not detected[1]:
            key = _collapse(detected[0]).lower()
            if len(key) <= 60:
                counts[key] = counts.get(key, 0) + 1

    def _is_repeat_heading(line: str) -> bool:
        detected = _detect_heading(line)
        if not detected or detected[1]:
            return False
        key = _collapse(detected[0]).lower()
        return counts.get(key, 0) >= REPEAT_HEADING_LIMIT

    title = ""
    for line in lines:
        if not line or sum(char.isalpha() for char in line) < 3:
            continue
        if _is_repeat_heading(line):
            continue
        title = line[:TITLE_MAX_CHARS].strip()
        break

    blocks = []
    current = None
    kept = []

    for line in lines:
        if not line:
            continue
        if _is_repeat_heading(line):
            continue
        kept.append(line)
        detected = _detect_heading(line)
        if detected:
            current = [detected[0], [detected[1]] if detected[1] else []]
            blocks.append(current)
        elif current is not None:
            current[1].append(line)

    if not blocks:
        return (title or "Document"), _fallback_chunks("\n".join(kept))

    sections = [(heading, "\n".join(body).strip()) for heading, body in blocks]
    sections = [(heading, body) for heading, body in sections if body]
    if not sections:
        return (title or "Document"), _fallback_chunks("\n".join(kept))
    return (title or "Document"), sections


def _chunk_body(body: str) -> list:
    """Split one body into pieces of about CHUNK_TARGET characters."""
    sentences = [s.strip() for s in _SENTENCE_END.split(body) if s.strip()]
    if not sentences:
        sentences = [body]
    pieces = []
    current = []
    size = 0
    for sentence in sentences:
        current.append(sentence)
        size += len(sentence) + 1
        if size >= CHUNK_TARGET:
            pieces.append(" ".join(current))
            current = []
            size = 0
    if current:
        pieces.append(" ".join(current))
    return pieces or [body]


def _split_long_sections(sections: list) -> list:
    """A very long body is cut into smaller parts so nothing is skipped."""
    output = []
    for heading, body in sections:
        if len(body) <= CHUNK_TARGET * 2:
            output.append((heading, body))
            continue
        for piece in _chunk_body(body):
            output.append((heading, piece))
    return output


def _merge_smallest_pair(sections: list):
    """Fold the two shortest neighbouring sections into one."""
    best_index = -1
    best_size = None
    for index in range(len(sections) - 1):
        size = len(sections[index][1]) + len(sections[index + 1][1])
        if best_size is None or size < best_size:
            best_size = size
            best_index = index
    if best_index < 0:
        return None
    heading_a, body_a = sections[best_index]
    heading_b, body_b = sections[best_index + 1]
    merged = (heading_a, _clean_multiline(body_a + "\n" + body_b))
    return sections[:best_index] + [merged] + sections[best_index + 2:]


def _merge_to_limit(sections: list, limit: int) -> list:
    """Fold neighbouring sections together until the count fits `limit`."""
    work = list(sections)
    while len(work) > limit:
        merged = _merge_smallest_pair(work)
        if merged is None:
            break
        work = merged
    return work


def _build_summary(title: str, sections: list) -> str:
    """A short overall summary built from the section explanations."""
    parts = []
    used = 0
    for heading, body in sections:
        label = _cut(heading, 60)
        parts.append("%s: %s" % (label, _cut(body, SUMMARY_PER_SECTION)))
        used += len(label) + SUMMARY_PER_SECTION
        if used >= SUMMARY_MAX_CHARS:
            break
    if not parts:
        return ""
    return _cut(" ".join(parts), SUMMARY_MAX_CHARS)


# -------------------------------------------------------------- hard words

def _is_word_char(char: str) -> bool:
    """Letters, digits, and combining marks such as Hindi matras."""
    if char.isalnum():
        return True
    return unicodedata.category(char).startswith("M")


def _word_in_body(word: str, body: str) -> bool:
    """True when the word appears in the body on clean word boundaries."""
    pattern = re.compile(re.escape(word), re.IGNORECASE)
    for match in pattern.finditer(body):
        before = body[match.start() - 1] if match.start() > 0 else " "
        after = body[match.end()] if match.end() < len(body) else " "
        if not _is_word_char(before) and not _is_word_char(after):
            return True
    return False


def _clean_hard_words(raw_items, body: str) -> list:
    """Keep only hard words that literally appear in this section's text."""
    cleaned = []
    seen = set()
    for item in raw_items or []:
        if not isinstance(item, dict):
            continue
        word = _clean_line(item.get("word"))
        meaning = _clean_line(item.get("meaning"))
        if not word or len(meaning) < 5:
            continue
        key = word.lower()
        if key in seen or not _word_in_body(word, body):
            continue
        if _has_banned(meaning):
            continue
        seen.add(key)
        cleaned.append((word, meaning))
        if len(cleaned) >= HARD_WORD_LIMIT:
            break
    return cleaned


def _hard_words_block(pairs: list, language: str) -> str:
    """A small bullet block for the difficult words in one section."""
    if not pairs:
        return ""
    label = _HARD_WORD_LABELS.get(language, _HARD_WORD_LABELS["en"])
    lines = [label]
    for word, meaning in pairs:
        lines.append("- " + word + ": " + meaning)
    return "\n".join(lines)


# --------------------------------------------------------------- the model

def _pack_gist(data: dict, body: str, language: str) -> str:
    """Turn a verified model reply into the text shown for one part.

    Returns '' when the reply fails any trust rule, which makes the caller
    fall back to the document's own lines.
    """
    if not data:
        return ""
    explanation = _clean_multiline(str(data.get("explanation") or ""))
    quote = _collapse(str(data.get("quote") or ""))
    if len(explanation) < 10:
        return ""
    if _has_banned(explanation):
        return ""
    if not _quote_is_real(quote, body):
        return ""

    pairs = _clean_hard_words(data.get("hard_words"), body)
    block = _hard_words_block(pairs, language)
    budget = GIST_MAX_CHARS - (len(block) + 2 if block else 0)
    if budget < 200:
        budget = 200
    gist = _cut(explanation, budget)
    if block:
        gist = gist + "\n\n" + block
    return gist


def _model_gist(model_call, heading: str, body: str, language: str) -> str:
    """Ask the model to explain one section. Returns '' when unusable.

    Two attempts are made. The second one repeats the request with a stricter
    instruction about copying the quote, because the usual reason a reply is
    rejected is that the model re-typed the quote instead of copying it.
    """
    language_name = _LANGUAGE_NAMES.get(language, "English")
    snippet = body[:MODEL_SECTION_CHARS]

    system_prompt = (
        _SYSTEM_PROMPT
        + f"\nWrite the explanation and every hard-word meaning in "
        f"{language_name}."
        + f"\nThe document text itself is in English. Never translate it."
    )

    user_prompt = (
        f"Document section heading: {heading}\n"
        f'Document section text:\n"""\n{snippet}\n"""\n\n'
        f"Task: Explain what this section says, in simple {language_name}, "
        f"for a first-time reader who is not comfortable with financial or "
        f"legal language.\n"
        f"Also list up to {HARD_WORD_LIMIT} difficult words or phrases that "
        f"appear in the section text, each with a simple meaning in "
        f"{language_name}, explained only as it is used in this section.\n"
        f"Rules:\n"
        f"- Use ONLY the section text above. Do not add outside information.\n"
        f"- Do not advise, recommend, warn about fraud, or predict anything.\n"
        f"- The explanation is 3 to 6 short sentences.\n"
        f"- Every hard word must be copied exactly as it appears in the "
        f"section text.\n"
        f"- The quote must stay in the original language of the document, "
        f"even though your explanation is in {language_name}.\n"
        f"- Reply with JSON only, in this exact shape:\n"
        + _JSON_SHAPE
        + "\n"
    )

    for attempt in range(2):
        prompt = user_prompt
        if attempt == 1:
            prompt = _STRICT_QUOTE_RULE + "\n\n" + user_prompt
        try:
            raw = model_call(system_prompt, prompt)
        except Exception:
            return ""
        gist = _pack_gist(_parse_json_object(raw), body, language)
        if gist:
            return gist
    return ""


def _build_note(model_call, fallback_count: int) -> str:
    """Plain words about why a part shows the document's own lines."""
    if model_call is None:
        return (
            "AI rewriting was off for this run, so every part shows the "
            "document's own words."
        )
    if fallback_count == 0:
        return ""
    word = "part" if fallback_count == 1 else "parts"
    return (
        "%d %s could not be verified against the document text, so those "
        "show the document's own lines instead of an explanation."
        % (fallback_count, word)
    )


# ------------------------------------------------------------------- the API

def explain_document(text: str, language: str = DEFAULT_LANGUAGE, model_call=None):
    """Read a document and return its summary plus explained subtopics."""
    text = text or ""
    language = language if language in _LANGUAGE_NAMES else DEFAULT_LANGUAGE

    title, sections = _split_sections(text)
    sections = _split_long_sections(sections)
    sections = _merge_to_limit(sections, MAX_SECTIONS)

    results = []
    fallback_count = 0

    for index, (heading, body) in enumerate(sections, start=1):
        gist = ""
        explained_by = "extract"
        if model_call is not None:
            gist = _model_gist(model_call, heading, body, language)
        if gist:
            explained_by = "model"
        else:
            fallback_count += 1
            gist = _cut(_clean_multiline(body), GIST_MAX_CHARS)
        results.append(Subtopic(
            index=index,
            heading=heading,
            gist=gist,
            source_quote=_cut(body, QUOTE_MAX_CHARS),
            explained_by=explained_by,
        ))

    summary = _build_summary(title, [(item.heading, item.gist) for item in results])
    if not summary:
        summary = _cut(_clean_multiline(text), SUMMARY_MAX_CHARS)

    return DocumentExplanation(
        language=language,
        title=title,
        summary=summary,
        subtopics=results,
        word_count=len(text.split()),
        note=_build_note(model_call, fallback_count),
    )


# ---------------------------------------------------------------- command line

def _print_report(result) -> None:
    print("title  : " + result.title)
    print("words  : %d | parts: %d" % (result.word_count, len(result.subtopics)))
    print("summary: " + result.summary)
    print("")
    for item in result.subtopics:
        print("  %d. %s  [%s]" % (item.index, item.heading, item.explained_by))
        for line in item.gist.splitlines() or [""]:
            print("     " + line)
        print("     source: " + item.source_quote)
        print("")
    if result.note:
        print("note   : " + result.note)


def main() -> None:
    import sys
    from pathlib import Path

    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return

    path = Path(args[0])
    if not path.is_file():
        print("File not found: " + str(path))
        return

    language = DEFAULT_LANGUAGE
    for value in args[1:]:
        if value in _LANGUAGE_NAMES:
            language = value

    model_call = None
    if "--no-ai" not in args:
        try:
            from app.providers import llm
            model_call = llm.model_call
            print("AI layer: enabled")
        except Exception:
            model_call = None
    if model_call is None:
        print("AI layer: off (showing the document's own words)")

    raw = path.read_text(encoding="utf-8", errors="replace")
    _print_report(explain_document(raw, language=language, model_call=model_call))


if __name__ == "__main__":
    main()
