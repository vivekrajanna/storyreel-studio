"""Gemini BYOK provider supporting BOTH Google AI Studio (AIza...) and Vertex AI Express (AQ....)."""

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from storyreel.config import build_image_prompt
from storyreel.providers.base import BaseProvider

AISTUDIO_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
VERTEX_BASE_URL = "https://aiplatform.googleapis.com/v1/publishers/google/models"


def detect_gemini_endpoint_mode(api_key: str, override: str = "auto") -> str:
    """Detect whether an API key targets Google AI Studio ('aistudio') or Vertex AI Express ('vertex')."""
    mode = (override or "auto").strip().lower()
    if mode in ("aistudio", "vertex"):
        return mode
    if api_key.startswith("AQ."):
        return "vertex"
    return "aistudio"


def build_generate_content_url(model: str, api_key: str, endpoint_mode: str) -> str:
    safe_model = urllib.parse.quote(model, safe="")
    if endpoint_mode == "vertex":
        return f"{VERTEX_BASE_URL}/{safe_model}:generateContent"
    return f"{AISTUDIO_BASE_URL}/{safe_model}:generateContent"


def http_post_json(url: str, api_key: str, payload: Dict[str, Any], timeout: int = 90) -> Dict[str, Any]:
    full_url = f"{url}?key={urllib.parse.quote(api_key)}"
    req = urllib.request.Request(
        full_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"HTTP {exc.code} calling {url}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error calling {url}: {exc.reason}") from exc


class GeminiProvider(BaseProvider):
    """Zero-dependency Gemini provider using urllib and user-supplied API keys."""

    name = "gemini"

    def __init__(self, api_key: str, endpoint_mode: str = "auto") -> None:
        self.api_key = api_key.strip()
        self.endpoint_mode = detect_gemini_endpoint_mode(self.api_key, endpoint_mode)

    def _call_model(self, model: str, payload: Dict[str, Any], timeout: int = 90) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. Add your key to `.env` or run with `--provider mock`."
            )
        url = build_generate_content_url(model, self.api_key, self.endpoint_mode)
        return http_post_json(url, self.api_key, payload, timeout=timeout)

    def translate_lines(
        self,
        lines: List[str],
        source_language_name: str,
        target_language_name: str,
        config: Dict[str, Any],
    ) -> List[str]:
        model = (config.get("models") or {}).get("text", "gemini-2.5-flash")
        char_names = ", ".join(
            c.get("name", "") for c in (config.get("characters") or []) if isinstance(c, dict) and c.get("name")
        )
        char_note = f" Keep character names consistent ({char_names})." if char_names else ""
        prompt = (
            f"Translate each {source_language_name} narration line below into natural, "
            f"warm, expressive {target_language_name}.{char_note} Keep the exact same number of lines ({len(lines)}). "
            f"Return ONLY a JSON array of {len(lines)} plain strings.\n\n"
            f"{json.dumps(lines, ensure_ascii=False, indent=2)}"
        )
        last_err: Optional[Exception] = None
        for _attempt in range(2):
            try:
                resp = self._call_model(
                    model,
                    {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json"},
                    },
                    timeout=60,
                )
                parts = (resp.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
                parsed = json.loads(cleaned)
                if not isinstance(parsed, list) or len(parsed) != len(lines):
                    raise RuntimeError(f"Expected {len(lines)} lines, got {type(parsed).__name__}")
                return [str(item).strip() for item in parsed]
            except Exception as exc:
                last_err = exc
        raise RuntimeError(f"Translation to {target_language_name} failed: {last_err}")

    def generate_localized_seo(
        self,
        story: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        model = (config.get("models") or {}).get("text", "gemini-2.5-flash")
        meta = story["meta"]
        handle = config["handle"]
        audio_langs = config["audio_languages"]
        lang_codes = [cfg["code"] for cfg in audio_langs]
        chapters = [s["label"] for s in story["scenes"]]
        takeaways = []
        for scene in story["scenes"]:
            for r in scene.get("rules") or []:
                takeaways.append(f"{r['icon']} {r['title']} — {r['desc']}")

        source_payload = {
            "episode_number": meta.get("episode_number", ""),
            "title": meta.get("title") or meta.get("title_en") or story["slug"],
            "description_md": (story.get("description_md") or "").strip(),
            "source_credit": meta.get("source_credit") or meta.get("source_book", ""),
            "tags": meta.get("tags", ""),
            "chapters": chapters,
            "takeaways": takeaways,
            "channel_handle": handle,
        }
        lang_spec = ", ".join(f"{cfg['code']} ({cfg['name']})" for cfg in audio_langs)
        prompt = (
            f"You are a video SEO copywriter for the channel {handle}. "
            f"Using the story details below, generate localized YouTube Title, Intro Description, "
            f"Chapter Titles, Key Takeaways, and Tags in ALL of these languages: {lang_spec}.\n\n"
            f"Rules:\n"
            f"- Return ONLY a valid JSON object whose top-level keys are exactly: {json.dumps(lang_codes)}.\n"
            f"- Each language object MUST contain: \"title\" (<= 95 chars, ending with \"| {handle}\"), "
            f"\"intro\" (2-3 engaging sentences in that language), "
            f"\"chapters\" (array of exactly {len(chapters)} localized chapter titles), "
            f"\"takeaways\" (array of exactly {len(takeaways)} localized bullets keeping leading emojis), "
            f"and \"tags\" (comma-separated string of 8-12 search tags).\n\n"
            f"Story source data:\n{json.dumps(source_payload, ensure_ascii=False, indent=2)}"
        )

        last_err: Optional[Exception] = None
        for _attempt in range(2):
            try:
                resp = self._call_model(
                    model,
                    {
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                        "generationConfig": {"responseMimeType": "application/json"},
                    },
                    timeout=60,
                )
                parts = (resp.get("candidates") or [{}])[0].get("content", {}).get("parts") or []
                text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
                cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
                parsed = json.loads(cleaned)
                if not isinstance(parsed, dict):
                    raise RuntimeError("SEO output was not a JSON object")
                result: Dict[str, Dict[str, Any]] = {}
                for code in lang_codes:
                    entry = parsed.get(code)
                    if not isinstance(entry, dict) or not str(entry.get("title", "")).strip():
                        raise RuntimeError(f"Missing localized SEO fields for '{code}'")
                    result[code] = {
                        "title": str(entry.get("title", "")).strip(),
                        "intro": str(entry.get("intro", "")).strip(),
                        "chapters": [str(c).strip() for c in (entry.get("chapters") or [])],
                        "takeaways": [str(t).strip() for t in (entry.get("takeaways") or [])],
                        "tags": str(entry.get("tags", "")).strip(),
                    }
                return result
            except Exception as exc:
                last_err = exc
        raise RuntimeError(f"Localized SEO generation failed: {last_err}")

    def synthesize_speech(
        self,
        text: str,
        voice_name: str,
        style_prompt: str,
        config: Dict[str, Any],
    ) -> Tuple[bytes, str]:
        model = (config.get("models") or {}).get("tts", "gemini-2.5-flash-preview-tts")
        payload: Dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {"voiceName": voice_name}
                    }
                },
            },
        }
        if style_prompt:
            payload["systemInstruction"] = {"parts": [{"text": style_prompt}]}

        resp = self._call_model(model, payload, timeout=120)
        for cand in resp.get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                inline = part.get("inlineData") or {}
                if inline.get("data"):
                    return base64.b64decode(inline["data"]), inline.get("mimeType", "audio/L16;rate=24000")
        raise RuntimeError(f"Gemini TTS ({model}) returned no audio data.")

    def generate_image(
        self,
        prompt: str,
        out_path: Path,
        config: Dict[str, Any],
    ) -> str:
        full_prompt = build_image_prompt(prompt, config)
        models = (config.get("models") or {}).get("images") or ["gemini-2.5-flash-image"]
        last_err: Optional[Exception] = None
        for model in models:
            try:
                resp = self._call_model(
                    model,
                    {
                        "contents": [{"role": "user", "parts": [{"text": full_prompt}]}],
                        "generationConfig": {"responseModalities": ["IMAGE"]},
                    },
                    timeout=120,
                )
                for cand in resp.get("candidates") or []:
                    for part in (cand.get("content") or {}).get("parts") or []:
                        inline = part.get("inlineData") or {}
                        if inline.get("data"):
                            out_path.parent.mkdir(parents=True, exist_ok=True)
                            out_path.write_bytes(base64.b64decode(inline["data"]))
                            return model
            except Exception as exc:
                last_err = exc
        raise RuntimeError(f"All image models failed ({models}). Last error: {last_err}")
