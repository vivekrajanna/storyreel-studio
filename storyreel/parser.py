"""Markdown Story parser for StoryReel Studio."""

import re
from pathlib import Path
from typing import Any, Dict, List


def detect_source_language(scenes: List[Dict[str, Any]], default_lang: str = "en") -> str:
    """Detect script source language from Unicode script ranges; defaults to configured primary."""
    sample = " ".join(s.get("vo", "") for s in scenes)
    if any("\u0c80" <= ch <= "\u0cff" for ch in sample):
        return "kn"
    if any("\u0900" <= ch <= "\u097f" for ch in sample):
        return "hi"
    if any("\u0c00" <= ch <= "\u0c7f" for ch in sample):
        return "te"
    if any("\u0b80" <= ch <= "\u0bff" for ch in sample):
        return "ta"
    return default_lang


def parse_story_md(md_path: Path) -> Dict[str, Any]:
    """Parse a story Markdown file into structured metadata, description, and scenes."""
    text = md_path.read_text(encoding="utf-8")
    meta: Dict[str, str] = {}
    body = text

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", text, flags=re.S)
    if fm_match:
        fm_raw, body = fm_match.group(1), fm_match.group(2)
        for line in fm_raw.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")

    # Optional ## Description section before first ## Scene
    description_md = ""
    desc_match = re.search(
        r"^##\s+Description\s*\n(.*?)(?=^##\s+Scene\s+\d+|\Z)",
        body,
        flags=re.M | re.S | re.I,
    )
    if desc_match:
        description_md = desc_match.group(1).strip()

    scene_blocks = re.split(r"^##\s+Scene\s+(\d+)\s*:\s*(.+)$", body, flags=re.M)
    scenes: List[Dict[str, Any]] = []

    for i in range(1, len(scene_blocks), 3):
        scene_id = int(scene_blocks[i].strip())
        scene_label = scene_blocks[i + 1].strip()
        block = scene_blocks[i + 2].strip()

        kv: Dict[str, str] = {}
        rules: List[Dict[str, str]] = []
        vo_lines: List[str] = []
        mode = "kv"

        for raw_line in block.splitlines():
            stripped = raw_line.strip()
            if re.match(r"^###\s+VO\b", stripped, flags=re.I):
                mode = "vo"
                continue
            if re.match(r"^###\s+Rules\b", stripped, flags=re.I):
                mode = "rules"
                continue
            if not stripped:
                continue

            if mode == "kv":
                if ":" in stripped:
                    k, v = stripped.split(":", 1)
                    kv[k.strip().lower()] = v.strip()
            elif mode == "rules":
                cleaned = re.sub(r"^[-*]\s*", "", stripped)
                parts = [p.strip() for p in cleaned.split("|")]
                if len(parts) >= 3:
                    rules.append({"icon": parts[0], "title": parts[1], "desc": parts[2]})
                elif len(parts) == 2:
                    rules.append({"icon": "⭐", "title": parts[0], "desc": parts[1]})
            elif mode == "vo":
                vo_lines.append(stripped)

        particles = [p for p in kv.get("particles", "").split() if p]
        badge_left = (
            {"text": kv["badge_left"], "color": kv.get("badge_left_color", "gold")}
            if kv.get("badge_left")
            else None
        )
        badge_right = (
            {"text": kv["badge_right"], "color": kv.get("badge_right_color", "blue")}
            if kv.get("badge_right")
            else None
        )
        hero = (
            {"big": kv["hero_big"], "sub": kv.get("hero_sub", "")}
            if kv.get("hero_big")
            else None
        )

        scenes.append(
            {
                "id": scene_id,
                "key": str(scene_id),
                "label": scene_label,
                "title": f"Scene {scene_id} — {scene_label}",
                "image_ref": kv.get("image", ""),
                "image_prompt": kv.get("image_prompt", ""),
                "anim": kv.get("anim", "zoom-in"),
                "sfx": kv.get("sfx", "pop"),
                "particles": particles,
                "badgeLeft": badge_left,
                "badgeRight": badge_right,
                "hero": hero,
                "rules": rules or None,
                "outro": kv.get("outro", "").lower() in ("true", "yes", "1"),
                "outroBig": kv.get("outro_big", ""),
                "outroSub": kv.get("outro_sub", ""),
                "vo_lines": vo_lines,
                "vo": " ".join(vo_lines),
            }
        )

    if not scenes:
        raise ValueError(
            f"No scenes found in {md_path.name}. Add at least one `## Scene 1: Hook` heading."
        )

    return {
        "slug": md_path.stem,
        "source_md": md_path.name,
        "meta": meta,
        "description_md": description_md,
        "scenes": scenes,
    }
