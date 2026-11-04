"""Script generation via the Gemini API (primary text provider).

Returns a dict: {title, description, scenes: [{headline, narration}, ...]}
Stage 1: single provider. The fallback chain (Groq -> OpenRouter ->
Cloudflare) is added in Stage 4 behind this same interface.
"""
import json
import os

import requests

MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

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
    resp = requests.post(
        URL,
        headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]},
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
