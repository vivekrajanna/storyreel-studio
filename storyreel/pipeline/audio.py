"""Pure-Python WAV audio writing, duration inspection, and frame-aligned stitching."""

import re
import wave
from pathlib import Path
from typing import Any, Dict, List, Optional


def write_wav_bytes(audio_bytes: bytes, mime_type: str, out_path: Path) -> float:
    """Write raw PCM or WAV audio bytes to out_path and return duration in seconds."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if audio_bytes[:4] == b"RIFF" and audio_bytes[8:12] == b"WAVE":
        out_path.write_bytes(audio_bytes)
    else:
        rate_match = re.search(r"rate=(\d+)", mime_type or "")
        sample_rate = int(rate_match.group(1)) if rate_match else 24000
        with wave.open(str(out_path), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(audio_bytes)
    return wav_duration_sec(out_path)


def wav_duration_sec(wav_path: Path) -> float:
    """Return exact duration of a WAV file in seconds."""
    with wave.open(str(wav_path), "rb") as wf:
        return round(wf.getnframes() / float(wf.getframerate()), 2)


def stitch_full_wav(
    scenes: List[Dict[str, Any]],
    lang_code: str,
    out_dir: Path,
    speech_offset: float,
    out_wav_path: Path,
) -> Optional[float]:
    """Stitch per-scene WAVs into one full-episode WAV aligned to the master scene timeline."""
    sample_rate = 24000
    nchannels = 1
    sampwidth = 2
    found_any = False

    for scene in scenes:
        info = (scene.get("audio_by_lang") or {}).get(lang_code) or {}
        rel = info.get("file") or ""
        if rel and (out_dir / rel).is_file():
            with wave.open(str(out_dir / rel), "rb") as wf:
                sample_rate = wf.getframerate()
                nchannels = wf.getnchannels()
                sampwidth = wf.getsampwidth()
            found_any = True
            break
    if not found_any:
        return None

    frame_bytes = nchannels * sampwidth
    total_frames = 0
    out_wav_path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_wav_path), "wb") as out_wf:
        out_wf.setnchannels(nchannels)
        out_wf.setsampwidth(sampwidth)
        out_wf.setframerate(sample_rate)

        for scene in scenes:
            slot_frames = int(round(float(scene["durationSec"]) * sample_rate))
            lead_frames = min(slot_frames, int(round(speech_offset * sample_rate)))
            written = 0

            if lead_frames > 0:
                out_wf.writeframes(b"\x00" * (lead_frames * frame_bytes))
                written += lead_frames

            info = (scene.get("audio_by_lang") or {}).get(lang_code) or {}
            rel = info.get("file") or ""
            scene_path = (out_dir / rel) if rel else None
            if scene_path and scene_path.is_file():
                with wave.open(str(scene_path), "rb") as in_wf:
                    raw_frames = in_wf.readframes(in_wf.getnframes())
                    n_read = len(raw_frames) // frame_bytes
                    max_allowed = max(0, slot_frames - written)
                    if n_read > max_allowed:
                        raw_frames = raw_frames[: max_allowed * frame_bytes]
                        n_read = max_allowed
                    if raw_frames:
                        out_wf.writeframes(raw_frames)
                        written += n_read

            tail_frames = max(0, slot_frames - written)
            if tail_frames > 0:
                out_wf.writeframes(b"\x00" * (tail_frames * frame_bytes))
                written += tail_frames
            total_frames += written

    return round(total_frames / float(sample_rate), 2)
