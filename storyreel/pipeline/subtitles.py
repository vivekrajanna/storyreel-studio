"""Synced multi-language SubRip (.srt) subtitle builder."""

from typing import Any, Dict, List, Optional


def fmt_srt_time(seconds: float) -> str:
    ms_total = max(0, int(round(seconds * 1000)))
    hours, rem = divmod(ms_total, 3600000)
    minutes, rem = divmod(rem, 60000)
    secs, ms = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def build_srt_content(
    scenes: List[Dict[str, Any]],
    lines_by_scene: Dict[Any, List[str]],
    speech_offset: float,
    scene_padding: float,
    lang_code: Optional[str] = None,
) -> str:
    """Build a valid .srt file synced to the shared master scene timeline."""
    blocks: List[str] = []
    cue_idx = 1
    cursor = 0.0

    for scene in scenes:
        lang_info = (scene.get("audio_by_lang") or {}).get(lang_code or "") if lang_code else None
        dur = float((lang_info or {}).get("durationSec") or scene["audioDurationSec"])
        slot_dur = float(scene.get("durationSec") or (float(scene["audioDurationSec"]) + scene_padding))
        key = scene.get("key", str(scene["id"]))
        lines = lines_by_scene.get(key) or lines_by_scene.get(scene["id"]) or [scene["vo"]]
        lines = [ln.strip() for ln in lines if ln.strip()]
        if not lines:
            cursor += slot_dur
            continue

        total_chars = sum(len(ln) for ln in lines) or 1
        t = cursor + speech_offset
        for idx, line in enumerate(lines):
            share = dur * (len(line) / total_chars)
            end_t = (cursor + speech_offset + dur) if idx == len(lines) - 1 else (t + share)
            blocks.append(f"{cue_idx}\n{fmt_srt_time(t)} --> {fmt_srt_time(end_t)}\n{line}\n")
            cue_idx += 1
            t = end_t
        cursor += slot_dur

    return "\n".join(blocks)
