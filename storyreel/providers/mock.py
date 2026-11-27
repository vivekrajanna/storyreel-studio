"""Deterministic offline MockProvider for dry-runs, demos, and CI tests (zero API cost)."""

import math
import struct
from pathlib import Path
from typing import Any, Dict, List, Tuple

from storyreel.providers.base import BaseProvider


class MockProvider(BaseProvider):
    """Generates clean local tone WAVs, SVG scene cards, and deterministic translations offline."""

    name = "mock"

    def translate_lines(
        self,
        lines: List[str],
        source_language_name: str,
        target_language_name: str,
        config: Dict[str, Any],
    ) -> List[str]:
        return [f"[{target_language_name}] {ln}" for ln in lines]

    def generate_localized_seo(
        self,
        story: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        meta = story["meta"]
        handle = config["handle"]
        base_title = meta.get("title") or meta.get("title_en") or story["slug"]
        base_intro = (story.get("description_md") or f"Animated story: {base_title}").strip()
        chapters = [s["label"] for s in story["scenes"]]
        takeaways = [
            f"{r['icon']} {r['title']} — {r['desc']}"
            for s in story["scenes"]
            for r in (s.get("rules") or [])
        ]
        tags = meta.get("tags", "animated story, storytelling, storyreel studio")

        out: Dict[str, Dict[str, Any]] = {}
        for cfg in config["audio_languages"]:
            code = cfg["code"]
            suffix = "" if code == config.get("primary_language", "en") else f" ({cfg['name']})"
            out[code] = {
                "title": f"{base_title}{suffix} | {handle}"[:95],
                "intro": base_intro,
                "chapters": list(chapters),
                "takeaways": list(takeaways),
                "tags": tags,
            }
        return out

    def synthesize_speech(
        self,
        text: str,
        voice_name: str,
        style_prompt: str,
        config: Dict[str, Any],
    ) -> Tuple[bytes, str]:
        # Generate a gentle 2.5s pleasant chime + soft silence so playback works in browser offline
        sample_rate = 24000
        dur_sec = max(2.2, min(5.0, len(text) / 45.0))
        n_frames = int(sample_rate * dur_sec)
        samples = bytearray()
        for i in range(n_frames):
            t = i / float(sample_rate)
            env = math.exp(-t * 3.5) if t < 0.8 else 0.0
            val = int(4200 * env * math.sin(2 * math.pi * 440.0 * t))
            samples.extend(struct.pack("<h", val))
        return bytes(samples), "audio/L16;rate=24000"

    def generate_image(
        self,
        prompt: str,
        out_path: Path,
        config: Dict[str, Any],
    ) -> str:
        # Write a clean colorful SVG card (browsers render SVG cleanly in <img> & <canvas>)
        accent1 = (config.get("brand") or {}).get("accent_primary", "#fde047")
        accent2 = (config.get("brand") or {}).get("accent_secondary", "#38bdf8")
        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720">'
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1">'
            f'<stop offset="0%" stop-color="#0f172a"/><stop offset="55%" stop-color="#1e1b4b"/><stop offset="100%" stop-color="#0c4a6e"/>'
            '</linearGradient></defs>'
            '<rect width="1280" height="720" fill="url(#g)"/>'
            f'<circle cx="960" cy="230" r="150" fill="{accent1}" opacity="0.22"/>'
            f'<circle cx="320" cy="520" r="190" fill="{accent2}" opacity="0.2"/>'
            f'<rect x="110" y="120" width="1060" height="480" rx="36" fill="rgba(15,23,42,0.55)" stroke="{accent2}" stroke-width="5"/>'
            f'<circle cx="640" cy="360" r="88" fill="{accent1}" opacity="0.9"/>'
            '<polygon points="616,316 694,360 616,404" fill="#0f172a"/>'
            '</svg>'
        )
        target = out_path.with_suffix(".svg")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(svg, encoding="utf-8")
        return "mock-svg"
