# Contributing to StoryReel Studio

Thank you for your interest in contributing! StoryReel Studio is designed to stay lightweight, modular, and dependency-free at its core.

## Core Design Principles
1. **Zero Mandatory Runtime Dependencies:** Keep the core Python package (`storyreel/`) 100% Python 3.9+ standard library only so anyone can clone and run without `pip`, `ffmpeg`, or `node`.
2. **BYOK & Cost Transparency:** Never silently make API calls during `--dry-run` or offline tests. Respect asset caching.
3. **100% Brand- & Language-Agnostic:** Never hardcode a specific channel name, mascot, or language into templates or pipeline code — read everything from `studio.config.json`.

## Adding a New AI Provider (e.g., OpenAI, ElevenLabs, Flux, Local TTS)
1. Subclass `BaseTextProvider`, `BaseTTSProvider`, and/or `BaseImageProvider` in `storyreel/providers/base.py`.
2. Add your implementation file under `storyreel/providers/<provider_name>.py`.
3. Register it in `storyreel/providers/__init__.py`.
4. Add unit tests using mocked HTTP responses in `tests/test_providers.py`.

## Running Tests Locally
```bash
python3 -m unittest discover -s tests -v
python3 -m storyreel build stories/sample_01_curious_fox.md --provider mock
```

## Pull Request Checklist
- [ ] All unit tests pass on Python 3.9+.
- [ ] No real API keys, `.env` files, or personal media files are included.
- [ ] New config keys are documented in `studio.config.example.json` and `README.md`.
