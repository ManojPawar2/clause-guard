"""Dual-provider LLM client: Groq (screening) + Gemini (explanations/generation).

Design rules (from the build plan):
- Disk cache from day one, keyed on sha256(provider|model|temp|prompt).
  The demo video is recorded against a warm cache, so a live API failure can
  never ruin a recording. Cache entries are one JSON file each (parallel-safe).
- Retry with exponential backoff on 429/5xx; cross-provider fallback helper.
- Plain requests, no SDKs (nothing extra to install).
"""
import hashlib
import json
import os
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = ROOT / "cache" / "llm"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

def _load_env():
    """Minimal .env loader (no python-dotenv dependency)."""
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


_load_env()  # must run BEFORE the model constants read os.environ

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
# LLM_MODE=ollama routes EVERY call to a local Ollama server (testing without
# API keys); delete the line from .env to switch back to Gemini/Groq. The disk
# cache keys on provider+model, so ollama-era cache never pollutes cloud runs.
LLM_MODE = os.environ.get("LLM_MODE", "cloud").lower()
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "llama3.1")
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")


class LLMError(RuntimeError):
    pass


def _cache_key(provider, model, temperature, prompt):
    h = hashlib.sha256(f"{provider}|{model}|{temperature}|{prompt}".encode()).hexdigest()
    return CACHE_DIR / f"{h[:24]}.json"


def _cached(provider, model, temperature, prompt):
    p = _cache_key(provider, model, temperature, prompt)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))["text"]
        except Exception:
            p.unlink(missing_ok=True)
    return None


def _store(provider, model, temperature, prompt, text):
    p = _cache_key(provider, model, temperature, prompt)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(
        json.dumps({"provider": provider, "model": model, "text": text}, ensure_ascii=False),
        encoding="utf-8",
    )
    tmp.replace(p)


def _post_with_retry(url, headers, payload, tries=4):
    delay = 5.0
    last = None
    for _ in range(tries):
        try:
            r = requests.post(url, headers=headers, json=payload, timeout=120)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}: {r.text[:300]}"
            if r.status_code in (400, 401, 403, 404):
                break  # non-retryable
            ra = r.headers.get("retry-after")
            if ra:
                try:
                    delay = max(delay, float(ra) + 1)
                except ValueError:
                    pass
        except requests.RequestException as e:
            last = f"{type(e).__name__}: {e}"
        time.sleep(delay)
        delay *= 2.5
    raise LLMError(last or "unknown error")


def _gemini(prompt, temperature, max_tokens, json_mode):
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise LLMError("GEMINI_API_KEY not set (.env)")
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{GEMINI_MODEL}:generateContent?key={key}"
    )
    gc = {"temperature": temperature, "maxOutputTokens": max_tokens}
    if json_mode:
        gc["responseMimeType"] = "application/json"
        # Gemini 3 spends output budget on internal thinking; on hard inputs it
        # can exhaust max_tokens before emitting any text. Structured-output
        # calls don't benefit from thinking — turn it off.
        gc["thinkingConfig"] = {"thinkingBudget": 0}
    data = _post_with_retry(url, {"Content-Type": "application/json"},
                            {"contents": [{"parts": [{"text": prompt}]}],
                             "generationConfig": gc})
    try:
        return data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError):
        raise LLMError(f"gemini: unexpected response shape: {str(data)[:300]}")


def _groq(prompt, temperature, max_tokens, json_mode):
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise LLMError("GROQ_API_KEY not set (.env)")
    payload = {
        "model": GROQ_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}
    data = _post_with_retry(
        "https://api.groq.com/openai/v1/chat/completions",
        {"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        payload,
    )
    try:
        return data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        raise LLMError(f"groq: unexpected response shape: {str(data)[:300]}")


def _ollama(prompt, temperature, max_tokens, json_mode):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
        "options": {"temperature": temperature, "num_predict": max_tokens},
    }
    if json_mode:
        payload["format"] = "json"
    try:
        r = requests.post(f"{OLLAMA_URL}/api/chat", json=payload, timeout=600)
        if r.status_code != 200:
            raise LLMError(f"ollama HTTP {r.status_code}: {r.text[:200]}")
        return r.json()["message"]["content"]
    except requests.RequestException as e:
        raise LLMError(f"ollama: {type(e).__name__}: {e}")


def llm(prompt, provider="groq", temperature=0.2, max_tokens=2048,
        json_mode=False, use_cache=True):
    if LLM_MODE == "ollama":
        provider, model = "ollama", OLLAMA_MODEL
    else:
        model = GROQ_MODEL if provider == "groq" else GEMINI_MODEL
    if use_cache:
        hit = _cached(provider, model, temperature, prompt)
        if hit is not None:
            return hit
    fn = {"ollama": _ollama, "groq": _groq, "gemini": _gemini}[provider]
    text = fn(prompt, temperature, max_tokens, json_mode)
    if use_cache:
        _store(provider, model, temperature, prompt, text)
    return text


def llm_with_fallback(prompt, preferred="groq", **kw):
    """Try preferred provider; on failure, silently try the other one.
    In ollama mode there is no second provider — the single call is the ball game."""
    if LLM_MODE == "ollama":
        return llm(prompt, **kw)
    other = "gemini" if preferred == "groq" else "groq"
    try:
        return llm(prompt, provider=preferred, **kw)
    except LLMError:
        return llm(prompt, provider=other, **kw)


if __name__ == "__main__":
    # M0 gate: one live round-trip per active provider.
    provs = ["ollama"] if LLM_MODE == "ollama" else ["groq", "gemini"]
    for prov in provs:
        try:
            out = llm("Reply with exactly: OK", provider=prov, use_cache=False, max_tokens=1024)
            print(f"{prov}: {out.strip()[:40]!r}")
        except LLMError as e:
            print(f"{prov}: FAILED — {e}")
