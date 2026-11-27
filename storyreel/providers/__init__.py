"""Provider factory for StoryReel Studio."""

import os
from typing import Dict, Optional

from storyreel.providers.base import BaseProvider
from storyreel.providers.gemini import GeminiProvider
from storyreel.providers.mock import MockProvider


def get_provider(
    provider_name: Optional[str] = None,
    api_key: Optional[str] = None,
    endpoint_mode: Optional[str] = None,
) -> BaseProvider:
    name = (provider_name or os.environ.get("STORYREEL_PROVIDER") or "gemini").strip().lower()
    if name == "mock":
        return MockProvider()
    if name == "gemini":
        key = api_key if api_key is not None else os.environ.get("GEMINI_API_KEY", "")
        mode = endpoint_mode or os.environ.get("GEMINI_PROVIDER", "auto")
        return GeminiProvider(api_key=key, endpoint_mode=mode)
    raise ValueError(f"Unknown provider '{name}'. Supported providers: gemini, mock")


__all__ = ["BaseProvider", "GeminiProvider", "MockProvider", "get_provider"]
