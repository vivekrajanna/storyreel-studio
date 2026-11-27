"""Main story build orchestrator with --dry-run cost preview and multi-format rendering."""

import html
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from storyreel.parser import detect_source_language, parse_story_md
from storyreel.pipeline.assets import _find_existing_asset, resolve_scene_image
from storyreel.pipeline.audio import stitch_full_wav, wav_duration_sec, write_wav_bytes
from storyreel.pipeline.seo import build_seo_data, build_seo_md, fmt_chapter_time
from storyreel.pipeline.subtitles import build_srt_content
from storyreel.providers.base import BaseProvider


def plan_build(
    md_path: Path,
    config: Dict[str, Any],
    project_root: Path,
    skip_images: bool = False,
    skip_audio: bool = False,
    skip_subtitles: bool = False,
    force_images: bool = False,
    force_audio: bool = False,
    force_subtitles: bool = False,
) -> Dict[str, Any]:
    """Inspect cache state and calculate exact API calls required BEFORE spending budget."""
    story = parse_story_md(md_path)
    slug = story["slug"]
    out_dir = project_root / "output" / slug
    assets_dir = project_root / "assets" / slug

    audio_langs = config["audio_languages"]
    sub_langs = config.get("subtitle_languages") or audio_langs
    src_lang = detect_source_language(story["scenes"], default_lang=config.get("primary_language", "en"))

    images_to_gen = 0
    if not skip_images:
        for scene in story["scenes"]:
            ref = scene["image_ref"]
            if ref and not ref.startswith("brand/") and scene.get("image_prompt"):
                existing = _find_existing_asset(assets_dir / ref)
                if force_images or not existing.is_file():
                    images_to_gen += 1
        thumb_ref = story["meta"].get("thumbnail_image") or ""
        if thumb_ref and not thumb_ref.startswith("brand/") and story["meta"].get("thumbnail_prompt"):
            existing_thumb = _find_existing_asset(assets_dir / thumb_ref)
            if force_images or not existing_thumb.is_file():
                images_to_gen += 1

    all_lang_codes = sorted({cfg["code"] for cfg in audio_langs + sub_langs})
    trans_cache = {}
    if (out_dir / "translations.json").is_file() and not force_subtitles:
        try:
            trans_cache = json.loads((out_dir / "translations.json").read_text(encoding="utf-8"))
        except ValueError:
            trans_cache = {}
    translations_to_gen = (
        0
        if (skip_audio and skip_subtitles)
        else sum(1 for c in all_lang_codes if c != src_lang and c not in trans_cache)
    )

    tts_to_gen = 0
    if not skip_audio:
        for cfg in audio_langs:
            code = cfg["code"]
            for scene in story["scenes"]:
                wav = out_dir / "audio" / code / f"scene_{scene['id']}.wav"
                if force_audio or not wav.is_file():
                    tts_to_gen += 1

    seo_cache = {}
    if (out_dir / "seo_translations.json").is_file() and not force_subtitles:
        try:
            seo_cache = json.loads((out_dir / "seo_translations.json").read_text(encoding="utf-8"))
        except ValueError:
            seo_cache = {}
    seo_calls = 0 if skip_subtitles else (1 if any(cfg["code"] not in seo_cache for cfg in audio_langs) else 0)

    return {
        "slug": slug,
        "scenes": len(story["scenes"]),
        "source_language": src_lang,
        "audio_languages": [cfg["code"] for cfg in audio_langs],
        "subtitle_languages": [cfg["code"] for cfg in sub_langs],
        "api_calls": {
            "images": images_to_gen,
            "translations": translations_to_gen,
            "tts_clips": tts_to_gen,
            "seo_pack": seo_calls,
        },
    }


def render_dashboard(config: Dict[str, Any], project_root: Path) -> None:
    """Render output/index.html with cards for every built story."""
    output_dir = project_root / "output"
    templates_dir = project_root / "templates"
    output_dir.mkdir(parents=True, exist_ok=True)

    stories_data: List[Dict[str, Any]] = []
    for ep_json in sorted(output_dir.glob("*/episode.json")):
        try:
            stories_data.append(json.loads(ep_json.read_text(encoding="utf-8")))
        except ValueError:
            continue

    cards_html = []
    for ep in stories_data:
        slug = ep["slug"]
        meta = ep.get("meta", {})
        ep_num = html.escape(meta.get("episode_number", slug))
        title_main = html.escape(meta.get("title") or meta.get("title_en") or slug)
        title_sub = html.escape(meta.get("subtitle") or "")
        thumb = html.escape(f"{slug}/{ep.get('thumbnail', {}).get('image', '')}")
        scene_count = len(ep.get("scenes", []))
        total_sec = sum(float(s.get("durationSec", 0)) for s in ep.get("scenes", []))
        dur_str = fmt_chapter_time(total_sec)
        sub_links = " ".join(
            f'<a class="pill" href="{slug}/subtitles/{html.escape(s)}" download>{html.escape(s)}</a>'
            for s in ep.get("subtitle_files", [])
        )
        audio_links = " ".join(
            f'<a class="pill" href="{slug}/audio/{html.escape(a)}" download>🎧 {html.escape(a)}</a>'
            for a in ep.get("full_audio_files", [])
        )
        sub_line = f'<p class="sub">{title_sub}</p>' if title_sub else ""
        cards_html.append(
            f"""
            <article class="card">
              <img class="thumb" src="{thumb}" alt="{title_main}" />
              <div class="body">
                <div class="kicker">{ep_num} • {scene_count} scenes • ~{dur_str}</div>
                <h2>{title_main}</h2>
                {sub_line}
                <div class="actions">
                  <a class="btn primary" href="{slug}/player.html">▶ 16:9 YouTube Player</a>
                  <a class="btn ig" href="{slug}/reel.html">📱 9:16 Insta Reel</a>
                  <a class="btn" href="{slug}/thumbnail.html">🎨 Thumbnail</a>
                  <a class="btn" href="{slug}/seo.md">📝 SEO Pack</a>
                </div>
                <div class="subs">Audio: {audio_links or '<span class="muted">Not generated yet</span>'}</div>
                <div class="subs">Subtitles: {sub_links or '<span class="muted">None yet</span>'}</div>
              </div>
            </article>
            """
        )

    brand = config.get("brand") or {}
    tpl_path = templates_dir / "dashboard.template.html"
    cards_markup = "".join(cards_html) if cards_html else '<p class="muted">No stories built yet. Run <code>python3 -m storyreel build stories/sample_01_curious_fox.md</code></p>'
    dashboard_html = (
        tpl_path.read_text(encoding="utf-8")
        .replace("__CHANNEL_HANDLE__", html.escape(config["handle"]))
        .replace("__CHANNEL_NAME__", html.escape(config.get("channel_name", "StoryReel Studio")))
        .replace("__FONTS_URL__", html.escape(brand.get("fonts_url", "")))
        .replace("__FONT_FAMILY__", brand.get("font_family", "sans-serif"))
        .replace("__BUILT_COUNT__", str(len(stories_data)))
        .replace("__EPISODE_CARDS__", cards_markup)
    )
    (output_dir / "index.html").write_text(dashboard_html, encoding="utf-8")


def build_story(
    md_path: Path,
    config: Dict[str, Any],
    provider: Optional[BaseProvider],
    project_root: Path,
    skip_audio: bool = False,
    skip_subtitles: bool = False,
    skip_images: bool = False,
    force_audio: bool = False,
    force_subtitles: bool = False,
    force_images: bool = False,
) -> Path:
    """Build a complete multi-format, multi-language output bundle for one Markdown story."""
    story = parse_story_md(md_path)
    slug = story["slug"]
    out_dir = project_root / "output" / slug
    out_assets = out_dir / "assets"
    out_audio = out_dir / "audio"
    out_subs = out_dir / "subtitles"
    out_prompts = out_dir / "prompts"
    assets_dir = project_root / "assets" / slug
    templates_dir = project_root / "templates"
    for d in (out_assets, out_audio, out_subs, out_prompts):
        d.mkdir(parents=True, exist_ok=True)

    brand = config.get("brand") or {}
    fallback_img = project_root / brand.get("fallback_image", "brand/placeholder.svg")
    missing_prompts: List[str] = []

    # 1. Resolve or generate scene & thumbnail images
    for scene in story["scenes"]:
        img_ref = scene["image_ref"]
        if (
            not skip_images
            and provider is not None
            and img_ref
            and not img_ref.startswith("brand/")
            and scene.get("image_prompt")
        ):
            target_asset = assets_dir / img_ref
            existing_asset = _find_existing_asset(target_asset)
            if force_images or not existing_asset.is_file():
                try:
                    print(f"[{slug}] Generating Scene {scene['id']} art -> {img_ref} ({provider.name})...", flush=True)
                    used_model = provider.generate_image(scene["image_prompt"], target_asset, config)
                    print(f"  Saved scene art ({used_model})", flush=True)
                except Exception as exc:
                    print(f"[{slug}] Warning: image gen failed for Scene {scene['id']}: {exc}", file=sys.stderr)

        rel_img, used_fallback = resolve_scene_image(img_ref, slug, project_root, out_assets, fallback_img)
        scene["image"] = rel_img
        if used_fallback and scene.get("image_prompt"):
            suggested = img_ref or f"scene_{scene['id']}.jpg"
            missing_prompts.append(f"## Scene {scene['id']} (`assets/{slug}/{suggested}`)\n\n```text\n{scene['image_prompt']}\n```\n")

    thumb_ref = story["meta"].get("thumbnail_image") or ""
    thumb_prompt = story["meta"].get("thumbnail_prompt") or ""
    if not skip_images and provider is not None and thumb_ref and not thumb_ref.startswith("brand/") and thumb_prompt:
        thumb_target = assets_dir / thumb_ref
        if force_images or not _find_existing_asset(thumb_target).is_file():
            try:
                print(f"[{slug}] Generating Thumbnail art -> {thumb_ref} ({provider.name})...", flush=True)
                provider.generate_image(thumb_prompt, thumb_target, config)
            except Exception as exc:
                print(f"[{slug}] Warning: thumbnail art gen failed: {exc}", file=sys.stderr)

    if missing_prompts:
        (out_prompts / "image_prompts.md").write_text(
            f"# Missing Scene Image Prompts — {slug}\n\n" + "\n".join(missing_prompts),
            encoding="utf-8",
        )

    # 2. Multi-language narration translations (cached in translations.json)
    timing = config.get("timing") or {}
    padding = float(timing.get("scene_padding_sec", 0.8))
    speech_offset = float(timing.get("speech_offset_sec", 0.15))
    default_dur = float(timing.get("default_scene_duration_sec", 14))
    primary_lang = config.get("primary_language", "en")
    audio_langs = config["audio_languages"]
    sub_langs = config.get("subtitle_languages") or audio_langs
    all_lang_names: Dict[str, str] = {cfg["code"]: cfg["name"] for cfg in audio_langs + sub_langs}

    src_lang = detect_source_language(story["scenes"], default_lang=primary_lang)
    src_lang_name = all_lang_names.get(src_lang, "English")
    src_map: Dict[str, List[str]] = {
        s["key"]: (s["vo_lines"] or [s["vo"]]) for s in story["scenes"]
    }

    trans_path = out_dir / "translations.json"
    translations: Dict[str, Dict[str, List[str]]] = {}
    if trans_path.is_file() and not force_subtitles:
        try:
            translations = json.loads(trans_path.read_text(encoding="utf-8"))
        except ValueError:
            translations = {}
    translations[src_lang] = src_map

    if provider is not None and (not skip_audio or not skip_subtitles):
        flat_src: List[str] = []
        counts: List[int] = []
        for s in story["scenes"]:
            lines = src_map[s["key"]]
            flat_src.extend(lines)
            counts.append(len(lines))

        for code, lang_name in all_lang_names.items():
            if code == src_lang:
                continue
            cached = translations.get(code)
            if cached and all(s["key"] in cached for s in story["scenes"]):
                continue
            try:
                print(f"[{slug}] Translating script -> {lang_name} ({code})...", flush=True)
                translated_flat = provider.translate_lines(flat_src, src_lang_name, lang_name, config)
                lang_map: Dict[str, List[str]] = {}
                pos = 0
                for s, cnt in zip(story["scenes"], counts):
                    lang_map[s["key"]] = translated_flat[pos : pos + cnt]
                    pos += cnt
                translations[code] = lang_map
            except Exception as exc:
                print(f"[{slug}] Warning: translation to {code} failed: {exc}", file=sys.stderr)

        trans_path.write_text(json.dumps(translations, ensure_ascii=False, indent=2), encoding="utf-8")

    # 3. Synthesize per-language WAV audio & compute shared master timeline
    voice_cfg = config.get("voice") or {}
    default_voice = voice_cfg.get("default", "Achird")
    voice_by_lang = voice_cfg.get("by_language") or {}
    voice_style = voice_cfg.get("style", "")

    manifest_data: Dict[str, Any] = {
        "primary_language": primary_lang,
        "provider": provider.name if provider else "offline",
        "voice": default_voice,
        "scenes": {},
        "full_tracks": {},
    }

    for scene in story["scenes"]:
        key = scene["key"]
        audio_by_lang: Dict[str, Dict[str, Any]] = {}
        vo_by_lang: Dict[str, str] = {}
        vo_lines_by_lang: Dict[str, List[str]] = {}
        durations: List[float] = []

        for cfg in audio_langs:
            code = cfg["code"]
            lang_lines = (translations.get(code) or {}).get(key)
            if not lang_lines:
                if code == src_lang:
                    lang_lines = scene["vo_lines"] or [scene["vo"]]
                else:
                    continue
            vo_text = " ".join(lang_lines).strip()
            vo_by_lang[code] = vo_text
            vo_lines_by_lang[code] = lang_lines

            lang_dir = out_audio / code
            lang_dir.mkdir(parents=True, exist_ok=True)
            wav_path = lang_dir / f"scene_{scene['id']}.wav"

            if not skip_audio and provider is not None and (force_audio or not wav_path.is_file()):
                try:
                    voice_name = voice_by_lang.get(code, default_voice)
                    print(f"[{slug}] Generating TTS [{code.upper()}] Scene {scene['id']} ({voice_name})...", flush=True)
                    raw_audio, mime = provider.synthesize_speech(vo_text, voice_name, voice_style, config)
                    write_wav_bytes(raw_audio, mime, wav_path)
                except Exception as exc:
                    print(f"[{slug}] Warning: TTS [{code}] failed on Scene {scene['id']}: {exc}", file=sys.stderr)

            if wav_path.is_file():
                dur = wav_duration_sec(wav_path)
                audio_by_lang[code] = {"file": f"audio/{code}/{wav_path.name}", "durationSec": dur}
                durations.append(dur)

        master_audio_dur = max(durations) if durations else default_dur
        primary_info = audio_by_lang.get(primary_lang) or next(iter(audio_by_lang.values()), None)
        scene["audio_by_lang"] = audio_by_lang
        scene["vo_by_lang"] = vo_by_lang
        scene["vo_lines_by_lang"] = vo_lines_by_lang
        scene["audioFile"] = primary_info["file"] if primary_info else ""
        scene["audioDurationSec"] = primary_info["durationSec"] if primary_info else master_audio_dur
        scene["durationSec"] = round(master_audio_dur + padding, 2)
        if primary_lang in vo_by_lang:
            scene["vo"] = vo_by_lang[primary_lang]
            scene["vo_lines"] = vo_lines_by_lang[primary_lang]
        manifest_data["scenes"][key] = {
            "masterDurationSec": scene["durationSec"],
            "languages": audio_by_lang,
        }

    # Stitch frame-aligned full-episode tracks per audio language
    full_audio_files: List[str] = []
    for cfg in audio_langs:
        code = cfg["code"]
        full_wav_path = out_audio / f"full_{code}.wav"
        stitched = stitch_full_wav(story["scenes"], code, out_dir, speech_offset, full_wav_path)
        if stitched is not None:
            full_audio_files.append(full_wav_path.name)
            manifest_data["full_tracks"][code] = {"file": f"audio/{full_wav_path.name}", "durationSec": stitched}

    story["full_audio_files"] = full_audio_files
    story["primary_language"] = primary_lang
    story["audio_languages"] = audio_langs
    story["ui_copy"] = config.get("ui_copy") or {}
    story["brand"] = brand
    (out_audio / "manifest.json").write_text(json.dumps(manifest_data, indent=2), encoding="utf-8")

    # 4. Write synced multi-language .srt subtitles
    subtitle_files: List[str] = []
    if not skip_subtitles:
        for cfg in sub_langs:
            code = cfg["code"]
            target_srt = out_subs / f"{code}.srt"
            lang_map = translations.get(code)
            if lang_map:
                target_srt.write_text(
                    build_srt_content(story["scenes"], lang_map, speech_offset, padding, lang_code=code),
                    encoding="utf-8",
                )
                subtitle_files.append(target_srt.name)
            elif target_srt.is_file():
                subtitle_files.append(target_srt.name)
    elif out_subs.is_dir():
        subtitle_files = sorted(p.name for p in out_subs.glob("*.srt"))

    # 5. Thumbnail config + thumbnail.html
    resolved_thumb_ref = thumb_ref or (story["scenes"][0]["image_ref"] if story["scenes"] else "")
    thumb_img, _ = resolve_scene_image(resolved_thumb_ref, slug, project_root, out_assets, fallback_img)
    title_display = story["meta"].get("title") or story["meta"].get("title_en") or slug
    thumb_cfg = {
        "slug": slug,
        "handle": config["handle"],
        "headline": story["meta"].get("thumbnail_headline", title_display),
        "sub": story["meta"].get("thumbnail_sub", story["meta"].get("episode_number", "")),
        "image": thumb_img,
    }
    story["thumbnail"] = thumb_cfg
    story["subtitle_files"] = subtitle_files

    thumb_tpl = (templates_dir / "thumbnail.template.html").read_text(encoding="utf-8")
    thumb_html = (
        thumb_tpl.replace("__PAGE_TITLE__", html.escape(f"{config['handle']} — {slug} Thumbnail"))
        .replace("__PAGE_HEADING__", html.escape(f"{config['handle']} — {story['meta'].get('episode_number', slug)} Thumbnail"))
        .replace("__FONTS_URL__", html.escape(brand.get("fonts_url", "")))
        .replace("__FONT_FAMILY__", brand.get("font_family", "sans-serif"))
        .replace("__THUMB_JSON__", json.dumps(thumb_cfg, ensure_ascii=False))
    )
    (out_dir / "thumbnail.html").write_text(thumb_html, encoding="utf-8")

    # 6. Localized multi-language SEO pack (cached in seo_translations.json)
    seo_cache_path = out_dir / "seo_translations.json"
    localized_seo: Dict[str, Dict[str, Any]] = {}
    if seo_cache_path.is_file() and not force_subtitles:
        try:
            localized_seo = json.loads(seo_cache_path.read_text(encoding="utf-8"))
        except ValueError:
            localized_seo = {}
    needed_seo = [cfg["code"] for cfg in audio_langs]
    if provider is not None and not skip_subtitles and any(c not in localized_seo for c in needed_seo):
        try:
            print(f"[{slug}] Generating localized Title & Description ({'/'.join(c.upper() for c in needed_seo)})...", flush=True)
            localized_seo = provider.generate_localized_seo(story, config)
            seo_cache_path.write_text(json.dumps(localized_seo, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as exc:
            print(f"[{slug}] Warning: localized SEO generation failed: {exc}", file=sys.stderr)

    story["seo"] = build_seo_data(story, config, padding, localized_seo=localized_seo)
    (out_dir / "episode.json").write_text(json.dumps(story, ensure_ascii=False, indent=2), encoding="utf-8")

    # 7. Render 16:9 player.html, 9:16 reel.html, seo.md & dashboard index.html
    ep_prefix = f"{story['meta'].get('episode_number', '')}: " if story["meta"].get("episode_number") else ""
    page_heading = f"{config['handle']} — {ep_prefix}{title_display}"

    player_tpl = (templates_dir / "player.template.html").read_text(encoding="utf-8")
    player_html = (
        player_tpl.replace("__PAGE_TITLE__", html.escape(page_heading))
        .replace("__PAGE_HEADING__", html.escape(page_heading))
        .replace("__FONTS_URL__", html.escape(brand.get("fonts_url", "")))
        .replace("__FONT_FAMILY__", brand.get("font_family", "sans-serif"))
        .replace("__EPISODE_JSON__", json.dumps(story, ensure_ascii=False))
    )
    (out_dir / "player.html").write_text(player_html, encoding="utf-8")

    reel_tpl = (templates_dir / "reel.template.html").read_text(encoding="utf-8")
    reel_html = (
        reel_tpl.replace("__PAGE_TITLE__", html.escape(f"{page_heading} — Insta Reel"))
        .replace("__PAGE_HEADING__", html.escape(f"{ep_prefix}{title_display}"))
        .replace("__FONTS_URL__", html.escape(brand.get("fonts_url", "")))
        .replace("__FONT_FAMILY__", brand.get("font_family", "sans-serif"))
        .replace("__EPISODE_JSON__", json.dumps(story, ensure_ascii=False))
    )
    (out_dir / "reel.html").write_text(reel_html, encoding="utf-8")

    (out_dir / "seo.md").write_text(build_seo_md(story, config, padding), encoding="utf-8")
    render_dashboard(config, project_root)
    print(f"[{slug}] Built -> {out_dir}", flush=True)
    return out_dir
