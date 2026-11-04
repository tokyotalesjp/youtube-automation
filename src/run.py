"""Pipeline entry point: process ONE queued row end to end.

queue row -> script (Gemini) -> narration (Kokoro) -> assemble (FFmpeg)
-> upload (YouTube API) -> write result back to the queue.
Any failure marks the row "error" with the reason, then re-raises so the
workflow run itself is visibly failed (Stage 2 adds auto-stop on repeats).
"""
import os
import sys
import tempfile
import time
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import build_video
import script_gen
import sheets_queue
import tts_kokoro
import upload


def _control_value(control: dict, key: str, default: str = "") -> str:
    return str(control.get(key, (0, default))[1]).strip()


def main() -> int:
    # --- Safety devices (Stage 2): emergency stop + consecutive-failure auto-stop.
    # Both live in the spreadsheet's "control" tab so the owner can flip them
    # from any browser/phone without touching code.
    try:
        control = sheets_queue.read_control()
    except Exception as ctl_err:
        print(f"Control tab unreadable, continuing without safety flags: {ctl_err}")
        control = {}
    if _control_value(control, "emergency_stop", "0").lower() in ("1", "true", "stop", "yes"):
        print("EMERGENCY STOP is set in the control tab. Exiting without processing.")
        return 0
    try:
        fail_limit = int(_control_value(control, "consecutive_failure_limit", "3") or 3)
        fail_count = int(_control_value(control, "consecutive_failures", "0") or 0)
    except ValueError:
        fail_limit, fail_count = 3, 0
    if fail_count >= fail_limit:
        print(
            f"AUTO-STOP: {fail_count} consecutive failures reached the limit of "
            f"{fail_limit}. Reset 'consecutive_failures' in the control tab to resume."
        )
        return 0

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
            srt_path = build_video.build(
                scenes, str(wav_dir), str(Path(tmp) / "build"), out_path,
                verdict=script.get("verdict", "HALF HYPE"),
            )

            video_id = upload.upload_video(
                out_path, script["title"], script["description"],
                privacy=privacy, language=language,
            )
            # Captions are best-effort but retried: a transient 503 killed
            # them in the Stage 1 proof run.
            for attempt, wait in enumerate((0, 5, 15, 45), start=1):
                if wait:
                    time.sleep(wait)
                try:
                    upload.upload_captions(video_id, srt_path, language=language)
                    print(f"Captions uploaded (attempt {attempt}).")
                    break
                except Exception as cap_err:
                    print(f"Caption upload attempt {attempt} failed: {cap_err}")
            else:
                print("Caption upload gave up after all retries (continuing).")

        url = f"https://youtu.be/{video_id}"
        sheets_queue.update_row(
            row_no, status="done", title=script["title"], video_url=url,
            notes=f"privacy={privacy}",
        )
        if fail_count:
            try:
                sheets_queue.write_control("consecutive_failures", "0")
            except Exception:
                pass
        print(f"Done: {url}")
        return 0
    except Exception:
        err = traceback.format_exc(limit=3)
        print(err)
        try:
            sheets_queue.update_row(row_no, status="error", notes=err[-400:])
        except Exception:
            pass
        try:
            sheets_queue.write_control("consecutive_failures", str(fail_count + 1))
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
