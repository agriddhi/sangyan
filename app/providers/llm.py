"""llm.py - the single place this app talks to a language model.

Everything else stays model-agnostic: the explainer receives a
`model_call(system_prompt, user_prompt) -> str` and does not care who answers.

Contract (important):
* model_call NEVER raises. On any failure - no key, no SDK, network down,
  quota hit, model unavailable - it returns "" and the explainer falls back to
  showing the document's own lines. The quote check in explainer.py stays the
  final gate: an explanation that cannot be traced to the source text is
  discarded, no matter who wrote it.

Free-tier behaviour:
* Requests are throttled to 12 per minute (our own throttle, not a promise).
* Model chain: GEMINI_MODEL from .env (if set) is tried first, then the
  defaults below. A model that is unavailable for this key is skipped; a model
  that is busy (503 / high demand) is skipped too, and the next model in the
  chain is tried. The first model that answers is remembered and tried first
  next time.
* The SDK's own silent retry loop is disabled (attempts=1) so a busy model is
  skipped quickly instead of leaving the terminal looking frozen. Every model
  attempt prints one line so progress is always visible.

SDKs:
* google-genai (current) is preferred; google-generativeai (deprecated) is
  kept only as a fallback so an older install still works.

Test it:  python -m app.providers.llm
"""

from __future__ import annotations

import hashlib
import os
import sys
import threading
import time
from pathlib import Path

DEFAULT_MODELS = ("gemini-3.5-flash-lite", "gemini-3.8-flash", "gemini-2.5-flash")
ENV_KEY_NAMES = ("GEMINI_API_KEY", "GOOGLE_API_KEY")
ENV_MODEL_NAME = "GEMINI_MODEL"

HTTP_TIMEOUT_MS = 45_000
TEMPERATURE = 0.2          # low drift: we want faithful rewriting, not creativity
MAX_OUTPUT_TOKENS = 1600
RATE_LIMIT = 12            # requests
RATE_WINDOW = 60.0         # seconds
RETRY_SLEEP = 5.0          # one retry after a quota/rate-limit error
BUSY_SLEEP = 1.5           # pause before hopping to the next model
MAX_CACHE = 200

_MODEL_MISSING_HINTS = (
    "not found",
    "404",
    "not supported",
    "does not exist",
    "no such model",
    "invalid model",
    "unsupported model",
)
_JSON_MODE_HINTS = ("mime", "response_mime", "json mode")
_RETRY_HINTS = (
    "429",
    "quota",
    "rate limit",
    "rate_limit",
    "resource_exhausted",
    "resource exhausted",
    "503",
    "unavailable",
    "overloaded",
    "high demand",
)

_lock = threading.Lock()
_rate_lock = threading.Lock()
_cache_lock = threading.Lock()

_state = {
    "init_done": False,
    "client": None,
    "backend": "",
    "working_model": "",
    "last_error": "",
}

_rate_times: list[float] = []
_cache: dict[str, str] = {}
_warned: set[str] = set()
_env_loaded = False


# ---------------------------------------------------------------- environment

def _load_env_file() -> None:
    """Read the project-root .env once. Does not overwrite real env vars."""
    global _env_loaded
    if _env_loaded:
        return
    _env_loaded = True

    root = Path(__file__).resolve().parent.parent.parent
    path = root / ".env"
    if not path.is_file():
        return
    try:
        raw = path.read_text(encoding="utf-8-sig")
    except OSError:
        return

    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, _, value = line.partition("=")
        name = name.strip()
        if name.lower().startswith("export "):
            name = name[7:].strip()
        value = value.strip()
        if " #" in value:
            value = value.split(" #")[0].strip()
        value = value.strip().strip("'\"")
        if name and value and not os.environ.get(name):
            os.environ[name] = value


def _api_key() -> str:
    _load_env_file()
    for name in ENV_KEY_NAMES:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def _model_chain() -> list[str]:
    """Working model first, then GEMINI_MODEL override, then the defaults."""
    _load_env_file()
    override = os.environ.get(ENV_MODEL_NAME, "").strip()
    chain: list[str] = []
    working = _state.get("working_model") or ""
    if working:
        chain.append(working)
    if override and override not in chain:
        chain.append(override)
    for name in DEFAULT_MODELS:
        if name not in chain:
            chain.append(name)
    return chain


def _remember_error(message: str) -> None:
    short = " ".join(str(message or "unknown error").split())[:300]
    _state["last_error"] = short
    with _lock:
        first = short not in _warned
        if first:
            _warned.add(short)
    if first:
        print(f"[llm] {short}", file=sys.stderr)


# ------------------------------------------------------------------ client

def _init_client() -> None:
    """Create the client once. Prefers google-genai, falls back to the old SDK."""
    with _lock:
        if _state["init_done"]:
            return
        _state["init_done"] = True

        key = _api_key()
        if not key:
            _state["last_error"] = (
                "No API key found. Add GEMINI_API_KEY=... to a .env file in the "
                "project root."
            )
            return

        errors: list[str] = []

        try:
            from google import genai as new_genai
            from google.genai import types as new_types
        except Exception:
            new_genai = None
            new_types = None

        if new_genai is not None:
            http_options = None
            try:
                # attempts=1 disables the SDK's own retry loop. Without this a
                # busy model silently retries for a long time and the terminal
                # looks frozen.
                http_options = new_types.HttpOptions(
                    timeout=HTTP_TIMEOUT_MS,
                    retry_options=new_types.HttpRetryOptions(attempts=1),
                )
            except Exception:
                print(
                    "[llm] note: could not disable the SDK's internal retries on "
                    "this google-genai version - requests may take longer before "
                    "switching models.",
                    file=sys.stderr,
                )

            try:
                if http_options is not None:
                    client = new_genai.Client(api_key=key, http_options=http_options)
                else:
                    client = new_genai.Client(
                        api_key=key,
                        http_options=new_types.HttpOptions(timeout=HTTP_TIMEOUT_MS),
                    )
                _state["client"] = client
                _state["backend"] = "google-genai"
                return
            except Exception as exc:
                errors.append(f"google-genai init failed: {exc}")

        try:
            import google.generativeai as old_genai
        except Exception:
            old_genai = None

        if old_genai is not None:
            try:
                old_genai.configure(api_key=key)
                _state["client"] = old_genai
                _state["backend"] = "google-generativeai"
                return
            except Exception as exc:
                errors.append(f"google-generativeai init failed: {exc}")

        _state["last_error"] = " | ".join(errors) or (
            "No Gemini SDK installed. Run: pip install google-genai"
        )


def available() -> bool:
    """True when a client could be created. Does NOT prove the key is valid."""
    _init_client()
    return _state["client"] is not None and bool(_state["backend"])


def status() -> str:
    """Human-readable state for the terminal. Never prints the key itself."""
    _init_client()
    lines = [
        f"SDK      : {_state['backend'] or 'not installed'}",
        f"API key  : {'found' if _api_key() else 'missing'}",
        f"Models   : {', '.join(_model_chain())}",
    ]
    if _state["working_model"]:
        lines.append(f"Working  : {_state['working_model']}")
    if _state["last_error"]:
        lines.append(f"Last err : {' '.join(_state['last_error'].split())}")
    return "\n".join(lines)


# ------------------------------------------------------------- rate limiting

def _rate_limit_wait() -> None:
    """Own throttle: at most RATE_LIMIT calls per RATE_WINDOW seconds."""
    while True:
        with _rate_lock:
            now = time.monotonic()
            _rate_times[:] = [t for t in _rate_times if now - t < RATE_WINDOW]
            if len(_rate_times) < RATE_LIMIT:
                _rate_times.append(now)
                return
            wait = RATE_WINDOW - (now - _rate_times[0])
        time.sleep(max(0.5, min(wait, 5.0)))


# ------------------------------------------------------------------- calls

def _response_text(response) -> str:
    """Read text from a response, tolerating blocked/empty responses."""
    try:
        text = response.text
        if text:
            return str(text)
    except Exception:
        pass
    try:
        pieces: list[str] = []
        for candidate in getattr(response, "candidates", None) or []:
            content = getattr(candidate, "content", None)
            for part in getattr(content, "parts", None) or []:
                value = getattr(part, "text", None)
                if value:
                    pieces.append(str(value))
        return "".join(pieces)
    except Exception:
        return ""


def _generate_once(
    model_name: str,
    system_prompt: str,
    user_prompt: str,
    json_mode: bool = True,
) -> str:
    """One attempt against one model. Every attempt passes the rate limiter."""
    _rate_limit_wait()

    backend = _state["backend"]
    client = _state["client"]

    print(f"[llm] asking {model_name} ...", file=sys.stderr)
    started = time.monotonic()

    if backend == "google-genai":
        from google.genai import types as new_types

        config_kwargs = {
            "system_instruction": system_prompt,
            "temperature": TEMPERATURE,
            "max_output_tokens": MAX_OUTPUT_TOKENS,
        }
        if json_mode:
            config_kwargs["response_mime_type"] = "application/json"
        response = client.models.generate_content(
            model=model_name,
            contents=user_prompt,
            config=new_types.GenerateContentConfig(**config_kwargs),
        )
        text = _response_text(response)
        print(
            f"[llm] {model_name} answered in {time.monotonic() - started:.1f}s",
            file=sys.stderr,
        )
        return text

    if backend == "google-generativeai":
        import google.generativeai as old_genai

        # json_mode is ignored here: the prompt already demands JSON and the
        # explainer's parser tolerates code fences.
        model = old_genai.GenerativeModel(
            model_name=model_name,
            system_instruction=system_prompt,
        )
        response = model.generate_content(
            user_prompt,
            generation_config=old_genai.GenerationConfig(
                temperature=TEMPERATURE,
                max_output_tokens=MAX_OUTPUT_TOKENS,
            ),
        )
        text = _response_text(response)
        print(
            f"[llm] {model_name} answered in {time.monotonic() - started:.1f}s",
            file=sys.stderr,
        )
        return text

    raise RuntimeError(_state["last_error"] or "No AI client is available.")


def _is_model_missing(message: str) -> bool:
    return any(hint in message for hint in _MODEL_MISSING_HINTS)


def _call_model(system_prompt: str, user_prompt: str) -> str:
    """Try each model in the chain. Skips missing models, hops past busy ones."""
    _init_client()
    if _state["client"] is None or not _state["backend"]:
        raise RuntimeError(_state["last_error"] or "No AI client is available.")

    last_missing: list[str] = []
    last_busy: list[str] = []

    for model_name in _model_chain():
        try:
            text = _generate_once(model_name, system_prompt, user_prompt, json_mode=True)
        except Exception as exc:
            message = str(exc).lower()
            if _is_model_missing(message):
                last_missing.append(model_name)
                continue
            if any(hint in message for hint in _RETRY_HINTS):
                last_busy.append(model_name)
                print(
                    f"[llm] {model_name} is busy right now, trying the next model",
                    file=sys.stderr,
                )
                time.sleep(BUSY_SLEEP)
                continue
            if any(hint in message for hint in _JSON_MODE_HINTS):
                try:
                    text = _generate_once(
                        model_name, system_prompt, user_prompt, json_mode=False
                    )
                except Exception as inner:
                    inner_message = str(inner).lower()
                    if _is_model_missing(inner_message):
                        last_missing.append(model_name)
                        continue
                    if any(hint in inner_message for hint in _RETRY_HINTS):
                        last_busy.append(model_name)
                        print(
                            f"[llm] {model_name} is busy right now, trying the "
                            f"next model",
                            file=sys.stderr,
                        )
                        time.sleep(BUSY_SLEEP)
                        continue
                    raise
            else:
                raise

        if text:
            _state["working_model"] = model_name
        return text

    if last_busy:
        raise RuntimeError(
            "The models were temporarily busy (high demand). Tried: "
            + ", ".join(last_busy)
            + ". Please run the same command again in a minute."
        )

    raise RuntimeError(
        "No configured model was available for this key (tried: "
        + ", ".join(last_missing or _model_chain())
        + "). Set GEMINI_MODEL in .env to a model your key can use."
    )


def _cache_key(system_prompt: str, user_prompt: str) -> str:
    blob = system_prompt + "\x00" + user_prompt
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def model_call(system_prompt: str, user_prompt: str) -> str:
    """Answer as a string, or "" on any failure. Never raises.

    Used by app.engine.explainer as its model_call slot.
    """
    system_prompt = str(system_prompt or "")
    user_prompt = str(user_prompt or "")
    if not user_prompt.strip():
        return ""

    key = _cache_key(system_prompt, user_prompt)
    with _cache_lock:
        cached = _cache.get(key)
    if cached:
        return cached

    for attempt in range(2):
        try:
            text = _call_model(system_prompt, user_prompt)
        except Exception as exc:
            _remember_error(str(exc))
            message = str(exc).lower()
            if attempt == 0 and any(hint in message for hint in _RETRY_HINTS):
                time.sleep(RETRY_SLEEP)
                continue
            return ""

        if not text:
            _remember_error("The model returned no usable text.")
            return ""

        with _cache_lock:
            if len(_cache) >= MAX_CACHE:
                _cache.clear()
            _cache[key] = text
        return text

    return ""


if __name__ == "__main__":
    print(status())

    if not available():
        print(
            "\nNo AI layer yet. Two things:\n"
            "  1. Create a .env file in the project root containing:\n"
            "         GEMINI_API_KEY=your-key-from-aistudio.google.com\n"
            "  2. Install the SDK:\n"
            "         .\\.venv\\Scripts\\python.exe -m pip install google-genai"
        )
        raise SystemExit(1)

    print("\nSending one tiny test call ...")
    reply = model_call(
        "You reply with JSON only.",
        'Reply with exactly {"ok": true} and nothing else.',
    )
    if reply:
        print(f"Reply: {reply}")
        print("AI layer is working.")
    else:
        print("The test call failed. See the [llm] line above for the reason.")
        raise SystemExit(1)
