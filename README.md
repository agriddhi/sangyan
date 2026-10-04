# SANGYAN

**Understand any financial document before you sign it.**

A first-time investor in India is handed a 20-40 page policy wording, key information memorandum or loan annexure written in English legal prose. Nobody is lying to them. They simply cannot read it - so they sign it.

Sangyan is the explanation they were never given.

---

## What it does

1. **Plain-language reader** - splits any document into named subtopics and rewrites each one in simple language, in English, Hindi or Tamil.
2. **Ask anything** - type or speak a question about any word, sentence or consequence. The answer is grounded in the document, with the exact line quoted.
3. **Voice-first** - reads the whole thing aloud, part by part, in the reader's chosen language. Users who prefer reading can switch off audio in one click.
4. **Voice input** - press the mic, speak one question, it transcribes and sends itself.
5. **Clauses to review** - a deterministic scanner flags the clauses worth reading twice (auto-renewal, rate changes, set-off, arbitration, late fees) and quotes the document's own line for each.
6. **Will this suit me?** - puts the reader's own situation beside what the document actually says. It never decides; it shows the two side by side.
7. **Rights and grievance navigator** - a static, dated directory of official Indian complaint channels (SEBI SCORES, SMART ODR, RBI CMS, IRDAI Bima Bharosa, cybercrime.gov.in / 1930, NCH 1915) with the order of escalation and the published deadlines. Zero model calls.

---

## The core rule

> **An explanation the model cannot prove is never shown.**

Every AI-generated claim must carry a sentence copied **verbatim** from the source document. Code verifies that quote against the source text - not the prompt, the code. If the quote is not there, the claim is **dropped** and the document's own lines are shown instead.

This runs on every explanation, every hard-word definition, every Q&A answer and every flagged clause. It is the reason the tool can be trusted with a financial document: it is structurally incapable of stating something the document did not say.

---

## Architecture

    Browser (vanilla JS, no framework)
       |  paste / upload document, voice input, read-aloud
       v
    FastAPI  -  app/server.py
       |
       |-- /api/explain     -> app/engine/explainer.py   chunk, rewrite, verify quotes
       |-- /api/ask         -> app/engine/ask.py         retrieve-then-answer
       |-- /api/flags       -> app/engine/eyes.py        deterministic clause scanner
       |-- /api/fit         -> app/engine/eyes.py        situation vs document
       |-- /api/rights      -> app/engine/rights.py      static complaint directory
       |-- /api/transcribe  -> app/routes_voice.py       Groq Whisper STT
       |
       v
    LLM layer  -  app/providers/llm.py + gemini.py
       Gemini (google-genai) for rewriting, translation and Q&A
       Groq Whisper for speech-to-text
       |
       v
    Data  -  app/data/*.json   glossary + locale strings (en / hi / ta)

**Stack:** Python, FastAPI, Pydantic, google-genai, vanilla JS.
**No database. No accounts. No tracking. No training data required.**

---

## Running it locally

    pip install -r requirements.txt

    # PowerShell
    $env:GEMINI_API_KEY="your key"
    $env:GROQ_API_KEY="your key"

    uvicorn app.server:app

Open http://127.0.0.1:8000

`GROQ_API_KEY` is optional - without it the reader still works and voice input says so instead of failing silently.

### Tests

    python -m pytest -q

---

## Guardrails

This is an investor-protection tool. By design it:

- gives **no** stock tips, buy/sell/hold calls or price predictions
- promotes **no** broker, product, scheme or investment
- takes **no** commission and has **no** monetisation
- never asks for an OTP, PAN, Aadhaar, account number or password
- collects **no** personal data - no database, no logs of document content
- states uncertainty explicitly, and says "not stated in your document" rather than guessing
- records audio only on an explicit click, holds it in memory for a few seconds, and discards it - there is no storage of any kind

Audio read-aloud uses the browser's own speech engine. Speech-to-text runs on Groq. Both keys are environment variables; neither is ever written to a file.

---

## Accessibility (Bharat-first)

- Three languages from day one - English, Hindi, Tamil
- Voice-first: the entire explanation can be spoken, including spoken guidance through the flow for users who cannot read
- Users who prefer reading can disable audio entirely
- Large type, high contrast, one-action navigation, keyboard-visible focus
- Print-friendly, so a reader can take a paper copy
- Runs on a low-end Android browser over a slow connection

---

## Impact and scalability

Every language added is an access win and costs **no new training data** - the model handles the language, the reviewed glossary handles the finance terms. The rights navigator is deterministic, so it works offline and burns no AI quota.

The pattern generalises beyond investments: any long-form document a citizen is expected to sign - a loan annexure, an insurance policy, a bank tariff sheet, a school admission form - goes through the same reader.

---

## Licence

Built for the SANGYAN hackathon. Provided for public-good use.
