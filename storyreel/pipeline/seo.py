"""Multi-language YouTube Title, Description, Chapters & Tags builder."""

from typing import Any, Dict, List, Optional


LOCALE_STRINGS: Dict[str, Dict[str, str]] = {
    "en": {
        "audio_note": "🎧 Multi-Language Audio Available ({langs}) — switch audio anytime in YouTube Settings ⚙️!",
        "credit_label": "📚 Inspired by:",
        "chapters_label": "⏱️ Chapters:",
        "takeaways_label": "🌟 Key Takeaways:",
        "cta": "🔔 Subscribe to {handle} for more animated stories and learning videos!",
    },
    "hi": {
        "audio_note": "🎧 मल्टी-लैंग्वेज ऑडियो उपलब्ध है ({langs}) — YouTube Settings ⚙️ में जाकर भाषा बदलें!",
        "credit_label": "📚 प्रेरणा स्रोत:",
        "chapters_label": "⏱️ चैप्टर्स:",
        "takeaways_label": "🌟 मुख्य बातें:",
        "cta": "🔔 ऐसे और मज़ेदार एनिमेटेड वीडियो के लिए {handle} को सब्सक्राइब करें!",
    },
    "kn": {
        "audio_note": "🎧 ಮಲ್ಟಿ-ಲ್ಯಾಂಗ್ವೇಜ್ ಆಡಿಯೋ ಲಭ್ಯವಿದೆ ({langs}) — YouTube Settings ⚙️ ನಲ್ಲಿ ಭಾಷೆ ಬದಲಿಸಿ!",
        "credit_label": "📚 ಪ್ರೇರಣೆ:",
        "chapters_label": "⏱️ ವಿಡಿಯೋ ಚಾಪ್ಟರ್ಸ್:",
        "takeaways_label": "🌟 ಮುಖ್ಯ ಅಂಶಗಳು:",
        "cta": "🔔 ಇನ್ನಷ್ಟು ಅನಿಮೇಟೆಡ್ ಕಥೆಗಳಿಗಾಗಿ {handle} ಚಾನೆಲ್ ಸಬ್‌ಸ್ಕ್ರೈಬ್ ಮಾಡಿ!",
    },
    "es": {
        "audio_note": "🎧 Audio multilingüe disponible ({langs}) — cambia el idioma en Configuración ⚙️ de YouTube.",
        "credit_label": "📚 Inspirado en:",
        "chapters_label": "⏱️ Capítulos:",
        "takeaways_label": "🌟 Puntos clave:",
        "cta": "🔔 ¡Suscríbete a {handle} para más historias animadas!",
    },
}


def fmt_chapter_time(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    mins, secs = divmod(total, 60)
    return f"{mins}:{secs:02d}"


def build_seo_data(
    story: Dict[str, Any],
    config: Dict[str, Any],
    scene_padding: float,
    localized_seo: Optional[Dict[str, Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    meta = story["meta"]
    handle = config["handle"]
    primary_lang = config.get("primary_language", "en")
    audio_langs = config["audio_languages"]
    ui_copy = config.get("ui_copy") or {}
    default_hashtags = ui_copy.get("hashtags", "#Storytelling #AnimatedVideo #StoryReelStudio")

    chapter_times: List[str] = []
    default_chapter_labels: List[str] = []
    cursor = 0.0
    for scene in story["scenes"]:
        chapter_times.append(fmt_chapter_time(cursor))
        default_chapter_labels.append(scene["label"])
        cursor += float(scene.get("durationSec") or (float(scene["audioDurationSec"]) + scene_padding))

    source_credit = meta.get("source_credit") or meta.get("source_book", "")
    default_takeaways = [
        f"{r['icon']} {r['title']} — {r['desc']}"
        for scene in story["scenes"]
        for r in (scene.get("rules") or [])
    ]
    custom_desc = (story.get("description_md") or "").strip()
    base_title = meta.get("title") or meta.get("title_en") or story["slug"]
    base_tags = meta.get("tags", "animated story, storytelling, learning")
    langs_display = " • ".join(cfg.get("label", cfg.get("name", cfg["code"].upper())) for cfg in audio_langs)

    by_lang: Dict[str, Dict[str, str]] = {}
    for cfg in audio_langs:
        code = cfg["code"]
        loc = (localized_seo or {}).get(code) or {}
        copy = LOCALE_STRINGS.get(code, LOCALE_STRINGS["en"])

        title = loc.get("title") or f"{base_title} | {handle}"
        intro = loc.get("intro") or custom_desc or base_title

        loc_chapters = loc.get("chapters") if isinstance(loc.get("chapters"), list) else []
        chapter_lines = [
            f"{ts} – {(loc_chapters[i] if i < len(loc_chapters) and loc_chapters[i] else default_chapter_labels[i])}"
            for i, ts in enumerate(chapter_times)
        ]

        loc_takeaways = loc.get("takeaways") if isinstance(loc.get("takeaways"), list) else []
        takeaway_lines = (
            loc_takeaways
            if len(loc_takeaways) == len(default_takeaways) and loc_takeaways
            else default_takeaways
        )

        parts: List[str] = []
        if len(audio_langs) > 1:
            parts.append(copy["audio_note"].format(langs=langs_display))
        parts.append(intro)
        if source_credit:
            parts.append(f"{copy['credit_label']} {source_credit}")
        parts.append(f"{copy['chapters_label']}\n" + "\n".join(chapter_lines))
        if takeaway_lines:
            parts.append(f"{copy['takeaways_label']}\n" + "\n".join(takeaway_lines))
        parts.append(f"{copy['cta'].format(handle=handle)}\n\n{default_hashtags}")

        by_lang[code] = {
            "label": cfg.get("label", cfg.get("name", code.upper())),
            "title": title,
            "description": "\n\n".join(parts),
            "tags": loc.get("tags") or base_tags,
        }

    primary_pack = by_lang.get(primary_lang) or next(iter(by_lang.values()))
    return {
        "title": primary_pack["title"],
        "description": primary_pack["description"],
        "tags": primary_pack["tags"],
        "by_lang": by_lang,
    }


def build_seo_md(story: Dict[str, Any], config: Dict[str, Any], scene_padding: float) -> str:
    meta = story["meta"]
    seo = story.get("seo") or build_seo_data(story, config, scene_padding)
    by_lang = seo.get("by_lang") or {}
    title_hdr = meta.get("title") or meta.get("title_en") or story["slug"]
    ep_num = meta.get("episode_number", "")
    lines = [
        f"# Video SEO Pack — {ep_num} {title_hdr}".strip(),
        "",
        "Paste your primary language into your main YouTube upload, then paste additional languages under **YouTube Studio → Subtitles / Languages → Add Language → Title & Description**.",
        "",
    ]
    for code, pack in by_lang.items():
        lines.extend(
            [
                f"## {pack.get('label', code.upper())} (`{code}`)",
                "",
                "### Title",
                "```text",
                pack.get("title", ""),
                "```",
                "",
                "### Description",
                "```text",
                pack.get("description", ""),
                "```",
                "",
                "### Tags",
                "```text",
                pack.get("tags", ""),
                "```",
                "",
            ]
        )
    return "\n".join(lines)
