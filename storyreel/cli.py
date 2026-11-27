"""Unified Command-Line Interface for StoryReel Studio."""

import argparse
import json
import os
import shutil
import sys
import time
from pathlib import Path
from typing import List, Optional

from storyreel import __version__
from storyreel.config import DEFAULT_CONFIG_NAME, find_project_root, load_config, load_dotenv, validate_config
from storyreel.pipeline.builder import build_story, plan_build
from storyreel.providers import get_provider
from storyreel.providers.gemini import detect_gemini_endpoint_mode
from storyreel.server import run_server


def list_story_files(project_root: Path) -> List[Path]:
    stories_dir = project_root / "stories"
    if not stories_dir.is_dir():
        return []
    return sorted(p for p in stories_dir.glob("*.md") if not p.name.startswith("_"))


def cmd_init(project_root: Path) -> int:
    """Create studio.config.json and .env from examples if not present."""
    created: List[str] = []
    cfg_dst = project_root / DEFAULT_CONFIG_NAME
    cfg_src = project_root / "studio.config.example.json"
    if not cfg_dst.is_file() and cfg_src.is_file():
        shutil.copy2(cfg_src, cfg_dst)
        created.append(DEFAULT_CONFIG_NAME)

    env_dst = project_root / ".env"
    env_src = project_root / ".env.example"
    if not env_dst.is_file() and env_src.is_file():
        shutil.copy2(env_src, env_dst)
        created.append(".env")

    if created:
        print("Initialized:", ", ".join(created))
        print("Next step: add your GEMINI_API_KEY in `.env` (or test offline with `--provider mock`).")
    else:
        print("Already initialized (`studio.config.json` and `.env` exist).")
    return 0


def cmd_doctor(project_root: Path) -> int:
    """Preflight check for Python version, studio.config.json, and BYOK .env setup."""
    print(f"StoryReel Studio v{__version__} — Preflight Doctor")
    print(f"- Project root: {project_root}")
    print(f"- Python: {sys.version.split()[0]}")

    load_dotenv(project_root / ".env")
    try:
        cfg = load_config(project_root)
        errs = validate_config(cfg)
        if errs:
            print("- Config: INVALID")
            for e in errs:
                print(f"    * {e}")
            return 1
        langs = ", ".join(c["code"] for c in cfg["audio_languages"])
        print(f"- Config: OK (handle={cfg['handle']}, primary={cfg['primary_language']}, audio=[{langs}])")
    except Exception as exc:
        print(f"- Config: ERROR ({exc})")
        return 1

    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key or key == "your_gemini_api_key_here":
        print("- GEMINI_API_KEY: NOT SET (add to `.env` for real AI generation, or run with `--provider mock`)")
    else:
        mode = detect_gemini_endpoint_mode(key, os.environ.get("GEMINI_PROVIDER", "auto"))
        masked = key[:4] + "..." + key[-4:] if len(key) > 10 else "***"
        print(f"- GEMINI_API_KEY: SET ({masked}, detected mode={mode})")

    stories = list_story_files(project_root)
    print(f"- Stories found in stories/: {len(stories)} ({', '.join(p.name for p in stories) or 'none'})")
    return 0


def cmd_build(args: argparse.Namespace, project_root: Path) -> int:
    cfg = load_config(project_root)
    targets: List[Path] = []
    if args.all:
        targets = list_story_files(project_root)
    elif args.story_md:
        p = Path(args.story_md)
        if not p.is_file():
            p = project_root / args.story_md
        if not p.is_file():
            print(f"Story file not found: {args.story_md}", file=sys.stderr)
            return 1
        targets = [p]
    else:
        print("Pass a story file path (e.g. `stories/sample_01_curious_fox.md`) or `--all`.", file=sys.stderr)
        return 1

    if args.dry_run:
        plans = [
            plan_build(
                t,
                cfg,
                project_root,
                skip_images=args.skip_images,
                skip_audio=args.skip_audio,
                skip_subtitles=args.skip_subtitles,
                force_images=args.force_images,
                force_audio=args.force_audio,
                force_subtitles=args.force_subtitles,
            )
            for t in targets
        ]
        print(json.dumps(plans, indent=2))
        return 0

    provider_name = args.provider or os.environ.get("STORYREEL_PROVIDER") or "gemini"
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if provider_name == "gemini" and (not key or key == "your_gemini_api_key_here"):
        if not (args.skip_images and args.skip_audio and args.skip_subtitles):
            print(
                "Note: GEMINI_API_KEY is not set in `.env`. Falling back to offline build (no AI calls).\n"
                "Tip: Add your key to `.env`, or run with `--provider mock` for an interactive demo!",
                file=sys.stderr,
            )
        provider = None
    else:
        provider = get_provider(provider_name)

    for target in targets:
        build_story(
            target,
            cfg,
            provider,
            project_root,
            skip_audio=args.skip_audio,
            skip_subtitles=args.skip_subtitles,
            skip_images=args.skip_images,
            force_audio=args.force_audio,
            force_subtitles=args.force_subtitles,
            force_images=args.force_images,
        )
    return 0


def cmd_watch(args: argparse.Namespace, project_root: Path) -> int:
    print(f"Watching {project_root / 'stories'} for new or edited .md files (Ctrl+C to stop)...", flush=True)
    seen = {}
    while True:
        for md in list_story_files(project_root):
            mtime = md.stat().st_mtime
            if seen.get(md) != mtime:
                seen[md] = mtime
                args.story_md = str(md)
                args.all = False
                try:
                    cmd_build(args, project_root)
                except Exception as exc:
                    print(f"Build error on {md.name}: {exc}", file=sys.stderr, flush=True)
        time.sleep(2.0)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="storyreel",
        description="StoryReel Studio — BYOK Markdown-to-Video & Insta Reel Studio.",
    )
    parser.add_argument("--version", action="version", version=f"storyreel-studio {__version__}")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("init", help="Initialize studio.config.json and .env from templates")
    sub.add_parser("doctor", help="Validate config, Python version, and API key mode")

    def add_build_flags(p: argparse.ArgumentParser) -> None:
        p.add_argument("--provider", choices=["gemini", "mock"], help="AI provider backend (default: gemini)")
        p.add_argument("--dry-run", action="store_true", help="Print planned API calls without executing them")
        p.add_argument("--skip-images", action="store_true", help="Skip AI image generation")
        p.add_argument("--skip-audio", action="store_true", help="Skip AI TTS audio generation")
        p.add_argument("--skip-subtitles", action="store_true", help="Skip translation/SRT/SEO generation")
        p.add_argument("--force-images", action="store_true", help="Regenerate images even if cached")
        p.add_argument("--force-audio", action="store_true", help="Regenerate audio even if cached")
        p.add_argument("--force-subtitles", action="store_true", help="Regenerate translations & SEO even if cached")

    p_build = sub.add_parser("build", help="Build one story or all stories in stories/")
    p_build.add_argument("story_md", nargs="?", help="Path to story .md file")
    p_build.add_argument("--all", action="store_true", help="Build all .md files in stories/")
    add_build_flags(p_build)

    p_watch = sub.add_parser("watch", help="Watch stories/ and auto-build on save")
    add_build_flags(p_watch)

    p_serve = sub.add_parser("serve", help="Start the local Studio web UI (default: 127.0.0.1:8096)")
    p_serve.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    p_serve.add_argument("--port", type=int, default=8096, help="Port number (default: 8096)")

    args = parser.parse_args(argv)
    project_root = find_project_root()

    if args.command == "init":
        return cmd_init(project_root)
    if args.command == "doctor":
        return cmd_doctor(project_root)
    if args.command == "build":
        return cmd_build(args, project_root)
    if args.command == "watch":
        return cmd_watch(args, project_root)
    if args.command == "serve":
        run_server(project_root, host=args.host, port=args.port)
        return 0

    parser.print_help()
    return 0
