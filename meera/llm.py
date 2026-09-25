"""Model calls. Gemini Flash does the cheap mechanical work (scoring, keywords,
transcription); drafting goes to Gemini or Claude depending on DRAFT_PROVIDER."""

import base64
import json
import re
import time

from . import http
from .config import env

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Tried in order; a 404 (model retired / not enabled for this key) falls through.
GEMINI_FALLBACKS = ["gemini-3.8-flash", "gemini-3.5-flash", "gemini-flash-latest"]

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _gemini_models():
    preferred = env("GEMINI_MODEL")
    models = [preferred] if preferred else []
    return models + [m for m in GEMINI_FALLBACKS if m != preferred]


def gemini(prompt, *, system=None, json_mode=False, audio=None, temperature=0.7):
    """Returns (text, model_used)."""
    key = env("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY is not set")

    parts = [{"text": prompt}]
    if audio:
        data, mime = audio
        parts.append({"inline_data": {"mime_type": mime, "data": base64.b64encode(data).decode()}})
    body = {
        "contents": [{"role": "user", "parts": parts}],
        "generationConfig": {"temperature": temperature},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}
    if json_mode:
        body["generationConfig"]["responseMimeType"] = "application/json"

    last_error = None
    # Two passes over the model list: 404 = model not available to this key,
    # 429/5xx = overloaded right now (common on Flash), so try the next one.
    attempts = [(m, i) for i in range(2) for m in _gemini_models()]
    for model, attempt in attempts:
        if attempt and last_error:
            time.sleep(2)
        try:
            resp = http.request(
                "POST", GEMINI_URL.format(model=model),
                headers={"x-goog-api-key": key}, body=body, timeout=90,
            )
        except http.HTTPError as e:
            if e.status in (404, 429, 500, 503):
                last_error = e
                continue
            raise
        candidate = (resp.get("candidates") or [{}])[0]
        text = "".join(
            p.get("text", "") for p in candidate.get("content", {}).get("parts", [])
            if not p.get("thought")
        ).strip()
        if not text:
            raise RuntimeError(f"Gemini returned no text (finishReason={candidate.get('finishReason')})")
        return text, model
    raise RuntimeError(f"Gemini unavailable (tried {', '.join(_gemini_models())}): {last_error}")


def gemini_json(prompt, *, system=None):
    text, _ = gemini(prompt, system=system, json_mode=True, temperature=0.2)
    return parse_json(text)


def claude(prompt, *, system=None, temperature=0.7):
    """Returns (text, model_used)."""
    key = env("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("DRAFT_PROVIDER=claude but ANTHROPIC_API_KEY is not set")
    model = env("CLAUDE_MODEL", "claude-sonnet-5")
    body = {
        "model": model,
        "max_tokens": 2000,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    resp = http.request(
        "POST", ANTHROPIC_URL,
        headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
        body=body, timeout=90,
    )
    text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
    return text.strip(), resp.get("model", model)


def draft_model(prompt, *, system):
    """Returns (text, provider, model)."""
    provider = env("DRAFT_PROVIDER", "gemini").lower()
    if provider == "claude":
        text, model = claude(prompt, system=system)
    else:
        provider = "gemini"
        text, model = gemini(prompt, system=system)
    return text, provider, model


def parse_json(text):
    """Parse a JSON object, tolerating ```json fences or stray prose around it."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))
