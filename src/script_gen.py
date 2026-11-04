"""Script generation via the Gemini API (primary text provider).

Returns a dict: {title, description, scenes: [{headline, narration}, ...]}
Stage 1: single provider. The fallback chain (Groq -> OpenRouter ->
Cloudflare) is added in Stage 4 behind this same interface.

Model selection: a model can appear in the key's model list yet still
404 on generateContent (observed 2026-11-04 with gemini-2.5-flash at
v1beta). So instead of trusting the list, try candidate models across
API versions (v1beta, then v1) and use the first combination that
actually answers. Every failed attempt's status + response body is
logged so the reason is visible in the workflow log.
"""
import json
import os

import requests

BASE = "https://generativelanguage.googleapis.com"
PREFERENCE = [
    "gemini-2.5-flash",
    "gemini-flash-latest",
    "gemini-3.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-3.6-flash",
    "gemini-3.7-flash",
    "gemini-3.8-flash",
]
EXCLUDE_SUBSTRINGS = (
    "tts", "image", "robotics", "computer-use", "deep-research",
    "lyria", "gemma", "antigravity", "nano-banana", "omni",
    "transcribe", "customtools", "preview",
)

PROMPT = """You are the scriptwriter for a YouTube explainer channel that covers
one trending topic per video, respectfully and factually.

Topic: {topic}
Language for narration and metadata: {language}

Rules:
- Explain what happened and why it matters. Never sensationalise disasters,
  deaths, or unverified breaking claims. If a fact is uncertain, leave it out.
- Narration must be original writing, about 900-1100 words in total, split
  into 10-14 scenes. Each scene: a short on-screen headline (max 8 words) and
  60-100 words of calm, clear narration.
- No first-person claims of personal experience.

Return ONLY valid JSON with this shape:
{{"title": "...", "description": "...", "scenes": [{{"headline": "...", "narration": "..."}}]}}
The description: 2-3 short paragraphs plus 3 hashtags at the end.
"""


def _headers() -> dict:
    return {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}


def _available_models() -> list[str]:
    resp = requests.get(f"{BASE}/v1beta/models", headers=_headers(), timeout=30)
    resp.raise_for_status()
    available = []
    for m in resp.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            available.append(m["name"].removeprefix("models/"))
    return available


def _candidates(available: list[str]) -> list[str]:
    picked = [p for p in PREFERENCE if p in available]
    for name in available:
        if name in picked or "flash" not in name:
            continue
        if any(x in name for x in EXCLUDE_SUBSTRINGS):
            continue
        picked.append(name)
    return picked


def generate_script(topic: str, language: str = "en") -> dict:
    payload = {
        "contents": [{"parts": [{"text": PROMPT.format(topic=topic, language=language)}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
    }
    forced = os.environ.get("GEMINI_MODEL")
    if forced:
        candidates = [forced]
        versions = [os.environ.get("GEMINI_API_VERSION", "v1beta")]
    else:
        available = _available_models()
        print(f"Gemini models available to this key: {available}")
        candidates = _candidates(available)
        versions = ["v1beta", "v1"]

    attempts = []
    for model in candidates:
        for version in versions:
            url = f"{BASE}/{version}/models/{model}:generateContent"
            resp = requests.post(url, headers=_headers(), json=payload, timeout=120)
            if resp.ok:
                print(f"Using Gemini model: {model} (API {version})")
                text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
                data = json.loads(text)
                assert data["title"] and data["scenes"], "script JSON missing fields"
                return data
            note = f"{version}/{model} -> HTTP {resp.status_code}: {resp.text[:200]}"
            attempts.append(note)
            print(f"Gemini attempt failed: {note}")
    raise RuntimeError("All Gemini attempts failed:\n" + "\n".join(attempts))
