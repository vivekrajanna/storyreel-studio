"""Configuration and .env loader for StoryReel Studio."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional


DEFAULT_CONFIG_NAME = "studio.config.json"


def find_project_root(start: Optional[Path] = None) -> Path:
    """Resolve the project root containing studio.config.json or templates/."""
    base = (start or Path.cwd()).resolve()
    for candidate in [base] + list(base.parents):
        if (candidate / DEFAULT_CONFIG_NAME).is_file() or (candidate / "templates").is_dir():
            return candidate
    return Path(__file__).resolve().parent.parent


def load_dotenv(env_path: Path) -> Dict[str, str]:
    """Parse a simple .env file into os.environ (without overwriting existing vars)."""
    loaded: Dict[str, str] = {}
    if not env_path.is_file():
        return loaded
    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        loaded[key] = val
        if key and key not in os.environ:
            os.environ[key] = val
    return loaded


def validate_config(cfg: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable validation errors (empty if valid)."""
    errors: List[str] = []
    if not isinstance(cfg, dict):
        return ["Configuration must be a JSON object."]
    if not str(cfg.get("handle", "")).strip():
        errors.append("Missing required field: 'handle' (e.g. '@YourChannel').")
    audio_langs = cfg.get("audio_languages")
    if not isinstance(audio_langs, list) or not audio_langs:
        errors.append("'audio_languages' must be a non-empty list of {code, name, label} objects.")
    else:
        for idx, item in enumerate(audio_langs):
            if not isinstance(item, dict) or not item.get("code") or not item.get("name"):
                errors.append(f"audio_languages[{idx}] must include 'code' and 'name'.")
    primary = cfg.get("primary_language")
    if audio_langs and isinstance(audio_langs, list):
        codes = [item.get("code") for item in audio_langs if isinstance(item, dict)]
        if primary and primary not in codes:
            errors.append(f"primary_language '{primary}' must be listed in audio_languages ({codes}).")
    return errors


def load_config(project_root: Optional[Path] = None, config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load studio.config.json (falling back to studio.config.example.json) with defaults."""
    root = project_root or find_project_root()
    load_dotenv(root / ".env")

    cfg_file = config_path or (root / DEFAULT_CONFIG_NAME)
    if not cfg_file.is_file():
        fallback = root / "studio.config.example.json"
        if fallback.is_file():
            cfg_file = fallback
        else:
            raise FileNotFoundError(
                f"No {DEFAULT_CONFIG_NAME} found in {root}. Run `python3 -m storyreel init` first."
            )

    cfg = json.loads(cfg_file.read_text(encoding="utf-8"))
    errors = validate_config(cfg)
    if errors:
        raise ValueError("Invalid studio configuration:\n- " + "\n- ".join(errors))

    cfg.setdefault("channel_name", cfg.get("handle", "StoryReel Studio").lstrip("@"))
    cfg.setdefault("primary_language", cfg["audio_languages"][0]["code"])
    cfg.setdefault("subtitle_languages", list(cfg["audio_languages"]))
    cfg.setdefault("models", {})
    cfg["models"].setdefault("text", "gemini-2.5-flash")
    cfg["models"].setdefault("tts", "gemini-2.5-flash-preview-tts")
    cfg["models"].setdefault("images", ["gemini-2.5-flash-image"])
    cfg.setdefault("voice", {})
    cfg["voice"].setdefault("default", "Achird")
    cfg["voice"].setdefault("by_language", {})
    cfg["voice"].setdefault(
        "style",
        "Speak as a warm, engaging, clear storyteller with lively expressive delivery.",
    )
    cfg.setdefault("characters", [])
    cfg.setdefault("visual_style", {})
    cfg["visual_style"].setdefault(
        "prefix",
        "Full-bleed seamless edge-to-edge 16:9 2D storybook vector illustration, vibrant colors, strictly zero text anywhere in the image.",
    )
    cfg.setdefault("timing", {})
    cfg["timing"].setdefault("scene_padding_sec", 0.8)
    cfg["timing"].setdefault("speech_offset_sec", 0.15)
    cfg["timing"].setdefault("default_scene_duration_sec", 14)
    cfg.setdefault("brand", {})
    cfg["brand"].setdefault("fallback_image", "brand/placeholder.svg")
    cfg["brand"].setdefault("accent_primary", "#fde047")
    cfg["brand"].setdefault("accent_secondary", "#38bdf8")
    cfg["brand"].setdefault(
        "fonts_url",
        "https://fonts.googleapis.com/css2?family=Fredoka:wght@600;700&family=Plus+Jakarta+Sans:wght@500;700;800&display=swap",
    )
    cfg["brand"].setdefault(
        "font_family",
        '"Plus Jakarta Sans", "Fredoka", -apple-system, BlinkMacSystemFont, sans-serif',
    )
    cfg.setdefault("ui_copy", {})
    cfg["ui_copy"].setdefault("outro_big", "What Do You Think?")
    cfg["ui_copy"].setdefault("outro_sub", "Share your thoughts in the comments! 👇")
    cfg["ui_copy"].setdefault("cta_like", "👍 Like")
    cfg["ui_copy"].setdefault("cta_comment", "💬 Comment")
    cfg["ui_copy"].setdefault("cta_subscribe", "🔔 Subscribe")
    cfg["ui_copy"].setdefault("hashtags", "#Storytelling #AnimatedVideo #StoryReelStudio")
    return cfg


def build_image_prompt(scene_prompt: str, config: Dict[str, Any]) -> str:
    """Combine configured visual style + recurring character sheet + scene prompt."""
    parts: List[str] = []
    prefix = str((config.get("visual_style") or {}).get("prefix", "")).strip()
    if prefix:
        parts.append(prefix)
    chars = config.get("characters") or []
    if chars:
        cast_desc = "; ".join(
            f"{c.get('name', 'Character')}: {c.get('description', '').strip()}"
            for c in chars
            if isinstance(c, dict) and c.get("name") and c.get("description")
        )
        if cast_desc:
            parts.append(f"Recurring characters (keep appearance consistent): {cast_desc}.")
    parts.append(f"Scene: {scene_prompt.strip()}")
    return " ".join(parts)
