"""Assemble one video (Method A): headline plates with the channel's host
character + Kokoro narration + zoompan drift -> loudnorm master + SRT.

Production design (2026-11-04):
- Every plate features the channel's fixed fictional host character on the
  right side; the pose follows the scene's role (hype opener, talking,
  shocked, and the verdict pose on the final scene).
- A stamp with the script's verdict (REAL HYPE / FAKE HYPE / HALF HYPE)
  slams onto the final scene while the host shouts "HYPE CHECK!".
- On some scenes a brief, clearly VISIBLE badge (SUBSCRIBE / HIT LIKE,
  alternating) flashes for ~0.7 s. (Perceptible on purpose — no subliminal
  frames.)
"""
import subprocess
import wave
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1920, 1080
FPS = 30
BG = (13, 20, 36)
FG = (235, 240, 248)
ACCENT = (255, 209, 26)
CORAL = (255, 99, 88)
PANEL_W = 700
CHAR_DIR = Path(__file__).resolve().parent.parent / "assets" / "character"
VERDICT_POSE = {"REAL HYPE": "yes", "FAKE HYPE": "no", "HALF HYPE": "talk"}
VERDICT_COLOR = {
    "REAL HYPE": (64, 210, 120),
    "FAKE HYPE": (255, 84, 84),
    "HALF HYPE": (255, 170, 40),
}
FONT_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
]


def _font(size: int) -> ImageFont.FreeTypeFont:
    for p in FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, max_w: int) -> list[str]:
    words, lines, cur = text.split(), [], ""
    for w_ in words:
        trial = (cur + " " + w_).strip()
        if draw.textlength(trial, font=font) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = w_
    if cur:
        lines.append(cur)
    return lines


def _char_panel(pose: str) -> Image.Image | None:
    path = CHAR_DIR / f"char-{pose}.jpg"
    if not path.exists():
        return None
    im = Image.open(path).convert("RGB")
    # Crop to fill the panel (PANEL_W x H) around the upper-center (the face).
    tw, th = PANEL_W, H
    scale = max(tw / im.width, th / im.height)
    im = im.resize((round(im.width * scale), round(im.height * scale)), Image.LANCZOS)
    x = max(0, (im.width - tw) // 2)
    y = 0
    return im.crop((x, y, x + tw, y + th))


def make_plate(headline: str, out_path: str, pose: str | None = None) -> None:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    panel = _char_panel(pose) if pose else None
    text_right = W - 90
    if panel is not None:
        img.paste(panel, (W - PANEL_W, 0))
        draw = ImageDraw.Draw(img)
        draw.rectangle([W - PANEL_W - 5, 0, W - PANEL_W, H], fill=CORAL)
        text_right = W - PANEL_W - 70
    font = _font(80)
    text_x = 90
    max_w = text_right - text_x
    lines = _wrap(draw, headline, font, max_w)
    line_h = 102
    y = (H - line_h * len(lines)) // 2 - 20
    for ln in lines:
        draw.text((text_x, y), ln, font=font, fill=FG)
        y += line_h
    draw.rectangle([text_x + 4, y + 26, text_x + 300, y + 40], fill=ACCENT)
    img.save(out_path)


def make_badge(text: str, out_path: str) -> None:
    font = _font(54)
    probe = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    tw = int(probe.textlength(text, font=font))
    w_, h_ = tw + 72, 104
    img = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([2, 2, w_ - 2, h_ - 2], radius=52, fill=CORAL + (255,))
    draw.text((36, 22), text, font=font, fill=(255, 255, 255, 255))
    img.save(out_path)


def make_stamp(verdict: str, out_path: str) -> None:
    color = VERDICT_COLOR.get(verdict, VERDICT_COLOR["HALF HYPE"])
    font = _font(150)
    probe = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    tw = int(probe.textlength(verdict, font=font))
    w_, h_ = tw + 110, 250
    img = Image.new("RGBA", (w_, h_), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle([8, 8, w_ - 8, h_ - 8], radius=28, outline=color + (255,), width=16)
    draw.text((55, 38), verdict, font=font, fill=color + (255,))
    img = img.rotate(-10, expand=True, resample=Image.BICUBIC)
    img.save(out_path)


def wav_duration(path: str) -> float:
    with wave.open(path, "rb") as w:
        return w.getnframes() / float(w.getframerate())


def fmt_ts(sec: float) -> str:
    ms = int(round(sec * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def pose_for(i: int, total: int, verdict: str) -> str | None:
    if total > 1 and i == total:
        return VERDICT_POSE.get(verdict, "talk")
    if i == 1:
        return "hype"
    return "talk" if i % 2 == 0 else "shock"


def build(scenes: list[dict], wav_dir: str, workdir: str, out_path: str,
          verdict: str = "HALF HYPE") -> str:
    wd = Path(workdir)
    wd.mkdir(parents=True, exist_ok=True)
    badge_a = str(wd / "badge-subscribe.png")
    badge_b = str(wd / "badge-like.png")
    make_badge("SUBSCRIBE", badge_a)
    make_badge("HIT LIKE", badge_b)
    stamp_path = str(wd / "stamp.png")
    make_stamp(verdict, stamp_path)
    total = len(scenes)
    durations: list[float] = []
    segments: list[str] = []
    for i, scene in enumerate(scenes, start=1):
        wav = str(Path(wav_dir) / f"line{i:02d}.wav")
        dur = wav_duration(wav) + 0.6
        durations.append(dur)
        plate = str(wd / f"plate{i:02d}.png")
        make_plate(scene["headline"], plate, pose=pose_for(i, total, verdict))
        seg = str(wd / f"seg{i:02d}.mp4")
        zoom = (
            "zoompan=z='min(zoom+0.0008,1.12)':x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':d={int(dur * FPS)}:s={W}x{H}:fps={FPS}"
        )
        inputs = ["-loop", "1", "-i", plate, "-i", wav]
        chain = f"[0:v]{zoom},format=yuv420p[v0]"
        cur = "[v0]"
        next_idx = 2  # inputs 0 (plate) and 1 (wav) are taken
        # Brief visible CTA badge flash (~0.7 s) on every third scene.
        if i % 3 == 2:
            inputs += ["-loop", "1", "-i", badge_a if (i // 3) % 2 == 0 else badge_b]
            chain += (
                f";{cur}[{next_idx}:v]overlay=W-w-48:48:"
                f"enable='between(t,1.0,1.7)'[vb]"
            )
            cur = "[vb]"
            next_idx += 1
        # The verdict stamp slams in on the final scene and stays.
        if total > 1 and i == total:
            inputs += ["-loop", "1", "-i", stamp_path]
            chain += (
                f";{cur}[{next_idx}:v]overlay=(W-w)/2:(H-h)/2:"
                f"enable='gte(t,0.8)'[vs]"
            )
            cur = "[vs]"
            next_idx += 1
        subprocess.run(
            ["ffmpeg", "-y", *inputs, "-filter_complex", chain,
             "-map", cur, "-map", "1:a",
             "-t", str(dur), "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
             "-c:a", "aac", "-b:a", "160k", "-ar", "48000", seg],
            check=True, capture_output=True,
        )
        segments.append(seg)

    concat_list = wd / "concat.txt"
    concat_list.write_text(
        "".join(f"file '{Path(s).resolve()}'\n" for s in segments), encoding="utf-8"
    )
    joined = str(wd / "joined.mp4")
    subprocess.run(
        ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
         "-c", "copy", joined],
        check=True, capture_output=True,
    )
    subprocess.run(
        ["ffmpeg", "-y", "-i", joined,
         "-af", "loudnorm=I=-14:TP=-2.0:LRA=11",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", out_path],
        check=True, capture_output=True,
    )

    srt_path = str(Path(out_path).with_suffix(".srt"))
    t = 0.0
    cues = []
    for idx, (scene, dur) in enumerate(zip(scenes, durations), start=1):
        cues.append(f"{idx}\n{fmt_ts(t)} --> {fmt_ts(t + dur)}\n{scene['narration']}\n")
        t += dur
    Path(srt_path).write_text("\n".join(cues), encoding="utf-8")
    return srt_path
