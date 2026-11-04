"""Script generation via the Gemini API (primary text provider).

Returns a dict: {title, description, scenes: [{headline, narration}, ...]}
Stage 1: single provider. The fallback chain (Groq -> OpenRouter ->
Cloudflare) is added in Stage 4 behind this same interface.
"""
import json
import os

import requests

MODELS_URL = "https://generativelanguage.googleapis.com/v1beta/models"
PREFERENCE = [
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-flash",
    "gemini-1.5-flash-8b",
]


def _headers() -> dict:
    return {"x-goog-api-key": os.environ["GEMINI_API_KEY"]}


def choose_model() -> str:
    """Pick a generateContent-capable model that THIS API key can actually
    see. A hard-coded name 404s when the key's project has a different
    catalogue, so list first and prefer in PREFERENCE order."""
    forced = os.environ.get("GEMINI_MODEL")
    if forced:
        return forced
    resp = requests.get(MODELS_URL, headers=_headers(), timeout=30)
    resp.raise_for_status()
    available = []
    for m in resp.json().get("models", []):
        if "generateContent" in m.get("supportedGenerationMethods", []):
            available.append(m["name"].removeprefix("models/"))
    print(f"Gemini models available to this key: {available}")
    for pref in PREFERENCE:
        if pref in available:
            print(f"Using Gemini model: {pref}")
            return pref
    for name in available:
        if "flash" in name:
            print(f"Using Gemini model (fallback): {name}")
            return name
    raise RuntimeError(f"No usable Gemini model found. Available: {available}")

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


def generate_script(topic: str, language: str = "en") -> dict:
    model = choose_model()
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    resp = requests.post(
        url,
        headers=_headers(),
        json={
            "contents": [{"parts": [{"text": PROMPT.format(topic=topic, language=language)}]}],
            "generationConfig": {"responseMimeType": "application/json", "temperature": 0.7},
        },
        timeout=120,
    )
    resp.raise_for_status()
    text = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
    data = json.loads(text)
    assert data["title"] and data["scenes"], "script JSON missing fields"
    return data
