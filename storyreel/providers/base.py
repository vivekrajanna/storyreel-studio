"""Abstract provider interface for pluggable AI backends."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Tuple


class BaseProvider(ABC):
    """Contract implemented by all StoryReel Studio AI providers."""

    name: str = "base"

    @abstractmethod
    def translate_lines(
        self,
        lines: List[str],
        source_language_name: str,
        target_language_name: str,
        config: Dict[str, Any],
    ) -> List[str]:
        """Translate narration lines preserving exact list length."""

    @abstractmethod
    def generate_localized_seo(
        self,
        story: Dict[str, Any],
        config: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        """Generate localized Title, Intro, Chapters, Takeaways, and Tags per audio language."""

    @abstractmethod
    def synthesize_speech(
        self,
        text: str,
        voice_name: str,
        style_prompt: str,
        config: Dict[str, Any],
    ) -> Tuple[bytes, str]:
        """Return (raw_audio_bytes, mime_type) for a single scene narration."""

    @abstractmethod
    def generate_image(
        self,
        prompt: str,
        out_path: Path,
        config: Dict[str, Any],
    ) -> str:
        """Generate an illustration to out_path and return the model name used."""
