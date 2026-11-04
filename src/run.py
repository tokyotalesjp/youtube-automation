"""Pipeline entry point: process ONE queued row end to end.

queue row -> script (Gemini) -> narration (Kokoro) -> assemble (FFmpeg)
-> upload (YouTube API) -> write result back to the queue.
Any failure marks the row "error" with the reason, then re-raises so the
workflow run itself is visibly failed (Stage 2 adds auto-stop on repeats).
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_video
import script_gen
import sheets_queue
import tts_kokoro
import upload


def main() -> int:
    row = sheets_queue.next_queued()
    if row is None:
        print("No queued rows. Nothing to do.")
        return 0

    row_no = row["_row"]
    topic = row.get("topic", "").strip()
    language = (row.get("language") or "en").strip() or "en"
    privacy = os.environ.get("UPLOAD_PRIVACY", "unlisted")
    print(f"Processing row {row_no}: topic={topic!r} language={language} privacy={privacy}")
    sheets_queue.update_row(row_no, status="in_progress")

    try:
        script = script_gen.generate_script(topic, language)
        scenes = script["scenes"]

        with tempfile.TemporaryDirectory() as tmp:
            wav_dir = Path(tmp) / "wav"
            wav_dir.mkdir()
            for i, scene in enumerate(scenes, start=1):
                dur = tts_kokoro.synth_line(scene["narration"], str(wav_dir / f"line{i:02d}.wav"))
                scene["duration"] = dur
            out_path = str(Path(tmp) / "video.mp4")
            srt_path = build_video.build(scenes, str(wav_dir), str(Path(tmp) / "build"), out_path)

            video_id = upload.upload_video(
                out_path, script["title"], script["description"],
                privacy=privacy, language=language,
            )
            try:
                upload.upload_captions(video_id, srt_path, language=language)
            except Exception as cap_err:  # captions are best-effort in Stage 1
                print(f"Caption upload failed (continuing): {cap_err}")

        url = f"https://youtu.be/{video_id}"
        sheets_queue.update_row(
            row_no, status="done", title=script["title"], video_url=url,
            notes=f"privacy={privacy}",
        )
        print(f"Done: {url}")
        return 0
    except Exception:
        err = traceback.format_exc(limit=3)
        print(err)
        try:
            sheets_queue.update_row(row_no, status="error", notes=err[-400:])
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
