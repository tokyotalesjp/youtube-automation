"""Assemble a Method-A style video from scenes + narration WAVs.

Stage 1 visuals: generated plates (dark background + headline text) with a
slow zoom. Real photo/illustration sourcing arrives with Method C/A assets
in Stage 4; the assembly contract (scenes -> segments -> concat -> master)
stays the same.
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
BG = (13, 20, 36)
FG = (235, 238, 245)
ACCENT = (199, 139, 68)
LINE_PAUSE = 0.7
SCENE_TAIL = 1.6


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def make_plate(headline: str, out_path: str) -> None:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im)
    font = _font(84)
    # simple word wrap
    words, lines, cur = headline.split(), [], ""
    for w in words:
        trial = f"{cur} {w}".strip()
        if d.textlength(trial, font=font) <= W - 240:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    y = H // 2 - (len(lines) * 104) // 2
    for line in lines:
        tw = d.textlength(line, font=font)
        d.text(((W - tw) / 2, y), line, font=font, fill=FG)
        y += 104
    d.rectangle([W // 2 - 90, y + 12, W // 2 + 90, y + 20], fill=ACCENT)
    im.save(out_path)


def _run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True, capture_output=True, text=True)


def build(scenes: list[dict], wav_dir: str, workdir: str, out_path: str) -> str:
    """scenes: [{headline, narration, duration}] — duration from TTS.
    Returns the path of the generated SRT file."""
    work = Path(workdir)
    work.mkdir(parents=True, exist_ok=True)
    wav_dir = Path(wav_dir)

    segments = []
    srt_entries = []
    t = 0.0
    for i, scene in enumerate(scenes, start=1):
        plate = work / f"plate{i:02d}.png"
        make_plate(scene["headline"], str(plate))
        seg = work / f"seg{i:02d}.mp4"
        dur = scene["duration"] + LINE_PAUSE + SCENE_TAIL
        _run([
            "ffmpeg", "-y", "-v", "error",
            "-loop", "1", "-i", str(plate),
            "-i", str(wav_dir / f"line{i:02d}.wav"),
            "-filter_complex",
            f"[0:v]zoompan=z='1+0.08*on/{max(int(dur*25),1)}':d={int(dur*25)}:s={W}x{H}:fps=25[v]",
            "-map", "[v]", "-map", "1:a",
            "-t", f"{dur:.2f}",
            "-af", f"apad=pad_dur={dur:.2f}",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "160k", "-ar", "48000",
            str(seg),
        ])
        segments.append(seg)
        start = t
        end = t + scene["duration"]
        srt_entries.append((len(srt_entries) + 1, start, end, scene["narration"]))
        t += dur

    list_file = work / "concat.txt"
    list_file.write_text("".join(f"file '{s.resolve()}'\n" for s in segments))
    joined = work / "joined.mp4"
    _run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0",
          "-i", str(list_file), "-c", "copy", str(joined)])
    _run(["ffmpeg", "-y", "-v", "error", "-i", str(joined),
          "-c:v", "copy", "-af", "loudnorm=I=-14:TP=-2.0:LRA=11",
          "-c:a", "aac", "-b:a", "160k", "-ar", "48000", out_path])

    def ts(sec: float) -> str:
        ms = int(round(sec * 1000))
        h, ms = divmod(ms, 3600000)
        m, ms = divmod(ms, 60000)
        s, ms = divmod(ms, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    srt_path = str(Path(out_path).with_suffix(".srt"))
    with open(srt_path, "w", encoding="utf-8") as f:
        for n, start, end, text in srt_entries:
            f.write(f"{n}\n{ts(start)} --> {ts(end)}\n{text}\n\n")
    return srt_path
