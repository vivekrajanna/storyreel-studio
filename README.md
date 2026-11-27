# 🎬 StoryReel Studio

**Open-Source, Bring-Your-Own-Key (BYOK) Markdown-to-Video Studio.**  
Write a simple Markdown story, bring your own Gemini API key, and automatically generate:

- **16:9 YouTube Videos (`player.html`)** — Ken Burns motion, floating particles, animated takeaway cards, synced single-sentence captions, background music, SFX, and 1-click browser MP4/WebM export.
- **9:16 Instagram Reels & YouTube Shorts (`reel.html`)** — Face-safe Cinema Blur framing, Full-Bleed mode, on-demand Scene Picker (`Viral Highlights <60s` or `Full Episode`), Instagram Safe-Zone guide, 1080×1920 export, and copy-ready Instagram Captions & Hashtags.
- **Multi-Language Narration & Synced Tracks** — Configure 1 or N audio languages in `studio.config.json`; StoryReel Studio translates, synthesizes voiceovers, and stitches frame-aligned `audio/full_<lang>.wav` tracks ready for **YouTube Multi-Language Audio**.
- **Synced Multi-Language Subtitles (`subtitles/<lang>.srt`)** — Frame-accurate timestamps across every language.
- **1280×720 Thumbnail Studio (`thumbnail.html`)** — Auto-generated art + live headline compositor + 1-click JPG export.
- **Localized YouTube SEO Packs (`seo.md`)** — Titles, Descriptions with synced `0:00` Chapters, Takeaways, and Tags in every configured language.
- **Zero Mandatory Dependencies** — Pure Python 3.9+ standard library core. No `ffmpeg`, no `node`, no `pip install` required to get started.

---

## ⚡ 60-Second Quickstart

### 1. Clone & Initialize
```bash
git clone https://github.com/vivekrajanna/storyreel-studio.git
cd storyreel-studio
python3 -m storyreel init
```

### 2. Try an Instant Offline Demo (No API Key Needed!)
Test the entire 16:9 + 9:16 studio locally using the built-in `mock` provider:
```bash
python3 -m storyreel build stories/sample_01_curious_fox.md --provider mock
python3 -m storyreel serve --port 8096
```
Open **`http://127.0.0.1:8096/`** in your browser to preview the 16:9 YouTube Player, 9:16 Insta Reel Studio, Thumbnail Maker, and SEO Pack!

### 3. Bring Your Own API Key (BYOK)
Open `.env` (created by `init`, automatically gitignored) and paste your own Gemini API key:
```env
# Works with BOTH Google AI Studio keys (AIza...) AND Vertex AI Express keys (AQ....)
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_PROVIDER=auto
```
Check your setup before spending any API quota:
```bash
python3 -m storyreel doctor
python3 -m storyreel build stories/sample_01_curious_fox.md --dry-run
```
Then build with real AI illustrations, voiceover, subtitles, and SEO:
```bash
python3 -m storyreel build stories/sample_01_curious_fox.md
```

---

## ✍️ Bring Your Own Story (`stories/*.md`)

Copy `stories/_TEMPLATE.md` to `stories/my_story.md`:

```markdown
---
episode_number: EP 01
title: Why Do Stars Twinkle?
thumbnail_headline: STAR MAGIC!
thumbnail_sub: Science • EP 01
thumbnail_image: ep01_thumb.jpg
thumbnail_prompt: High-contrast 16:9 storybook thumbnail (zero text)...
tags: astronomy, science animation, storytelling
---

## Description
A short summary of your episode for YouTube and Instagram SEO.

## Scene 1: 1. Hook
image: scene_1.jpg
anim: zoom-in
sfx: pop
particles: ✨ 🌟
badge_left: 🔭 Mystery!
badge_left_color: gold
hero_big: Why Do Stars Twinkle?
hero_sub: Let's find out!
image_prompt: Curious fox looking up at a starry night sky...

### VO
Write one crisp sentence per line.
Each line automatically becomes a synced subtitle cue!
```

Build your story (or auto-build on every save with `--watch`):
```bash
python3 -m storyreel build stories/my_story.md
python3 -m storyreel watch
```

---

## ⚙️ Customize Your Brand, Cast & Languages (`studio.config.json`)

Everything is controlled from `studio.config.json` — no code edits required:

- **Channel Identity & Theme:** `handle`, `channel_name`, `brand.fonts_url`, `brand.font_family`, `ui_copy` (custom CTA buttons & hashtags).
- **Recurring Characters (`characters`):** Define character names and appearances once — StoryReel Studio automatically injects them into every `image_prompt` for consistent visual identity!
- **Multi-Language Audio & Subtitles:** Start with English only, or add as many languages as you want:
  ```json
  "primary_language": "en",
  "audio_languages": [
    { "code": "en", "name": "English", "label": "English (Primary)" },
    { "code": "es", "name": "Spanish", "label": "Español" },
    { "code": "hi", "name": "Hindi", "label": "हिन्दी (Hindi)" }
  ]
  ```
- **Voice & Models (`models`, `voice`):** Customize `models.text`, `models.tts`, `models.images`, `voice.default`, `voice.by_language`, and `voice.style`.

---

## 🛡️ Cost Control & Security Design

- **`--dry-run` Cost Preview:** Inspect exact uncached API calls (`images`, `translations`, `tts_clips`, `seo_pack`) before running a build.
- **Smart Caching:** Existing illustrations (`assets/<slug>/`), voiceovers (`output/<slug>/audio/`), translations (`translations.json`), and SEO (`seo_translations.json`) are cached automatically. Use `--skip-images`, `--skip-audio`, `--skip-subtitles`, or `--force-*` for fine-grained control.
- **Strict Key Hygiene:** `.env`, `client_secret.json`, and `token.json` are gitignored and never embedded into generated HTML/JSON.
- **Local-Only Server:** `storyreel serve` binds to `127.0.0.1` and strictly confines static file serving to `output/`.

---

## 🏗️ Architecture

```text
storyreel/
├── cli.py                # Unified CLI: init, doctor, build, watch, serve
├── config.py             # studio.config.json & .env loader + schema validator
├── parser.py             # Markdown story parser & script language detector
├── providers/
│   ├── base.py           # Abstract BaseProvider interface (extensible for OpenAI, ElevenLabs, etc.)
│   ├── gemini.py         # Auto-detecting Google AI Studio (AIza...) & Vertex Express (AQ....) backend
│   └── mock.py           # 100% offline deterministic provider for demos & CI
├── pipeline/
│   ├── assets.py         # Safe image resolution & fallback handling
│   ├── audio.py          # Pure-Python WAV writer & frame-aligned full_<lang>.wav stitcher
│   ├── subtitles.py      # Master-timeline synced .srt generator
│   ├── seo.py            # Multi-language YouTube Title/Description/Chapters/Tags generator
│   └── builder.py        # Build orchestrator, dry-run planner & HTML template renderer
└── server.py             # Local 127.0.0.1 Studio & Content Calendar HTTP server
```

---

## 🧪 Running Tests

```bash
python3 -m unittest discover -s tests -v
```

## 🤝 Contributing & License

Contributions are welcome — especially new providers (OpenAI, ElevenLabs, Flux, local TTS) and vertical layout themes! See [CONTRIBUTING.md](CONTRIBUTING.md), [SECURITY.md](SECURITY.md), and [LICENSE](LICENSE) (MIT).
