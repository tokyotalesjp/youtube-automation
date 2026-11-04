"""Narration synthesis with Kokoro ONNX on CPU (GitHub Actions runner)."""
import os

import soundfile as sf
from kokoro_onnx import Kokoro

VOICE = os.environ.get("TTS_VOICE", "af_nova")
SPEED = float(os.environ.get("TTS_SPEED", "1.0"))
LANG = os.environ.get("TTS_LANG", "en-us")

_kokoro = None


def _engine() -> Kokoro:
    global _kokoro
    if _kokoro is None:
        _kokoro = Kokoro("models/kokoro-v1.0.onnx", "models/voices-v1.0.bin")
    return _kokoro


def synth_line(text: str, out_path: str) -> float:
    """Synthesise one line; returns duration in seconds."""
    samples, sr = _engine().create(text, voice=VOICE, speed=SPEED, lang=LANG)
    sf.write(out_path, samples, sr)
    return len(samples) / sr
