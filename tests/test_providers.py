"""Unit tests for BYOK Gemini endpoint auto-detection and MockProvider."""

import tempfile
import unittest
from pathlib import Path

from storyreel.config import build_image_prompt, load_config
from storyreel.providers import get_provider
from storyreel.providers.gemini import build_generate_content_url, detect_gemini_endpoint_mode

ROOT = Path(__file__).resolve().parent.parent


class ProviderTests(unittest.TestCase):
    def test_detect_gemini_endpoint_mode_aistudio_vs_vertex(self) -> None:
        self.assertEqual(detect_gemini_endpoint_mode("AIzaSyFakeKeyForUnitTests"), "aistudio")
        self.assertEqual(detect_gemini_endpoint_mode("AQ.FakeVertexExpressKey"), "vertex")
        self.assertEqual(detect_gemini_endpoint_mode("AIzaSyFakeKey", override="vertex"), "vertex")
        self.assertEqual(detect_gemini_endpoint_mode("AQ.FakeKey", override="aistudio"), "aistudio")

    def test_build_generate_content_url(self) -> None:
        ai_url = build_generate_content_url("gemini-2.5-flash", "AIzaFake", "aistudio")
        vx_url = build_generate_content_url("gemini-2.5-flash", "AQ.Fake", "vertex")
        self.assertIn("generativelanguage.googleapis.com", ai_url)
        self.assertIn("aiplatform.googleapis.com", vx_url)

    def test_character_sheet_injected_into_image_prompt(self) -> None:
        cfg = load_config(ROOT)
        full_prompt = build_image_prompt("Milo stands under the stars.", cfg)
        self.assertIn("Milo", full_prompt)
        self.assertIn("Pip", full_prompt)
        self.assertIn("Milo stands under the stars.", full_prompt)

    def test_mock_provider_generates_audio_svg_and_translations(self) -> None:
        cfg = load_config(ROOT)
        provider = get_provider("mock")
        translated = provider.translate_lines(["Line 1", "Line 2"], "English", "Spanish", cfg)
        self.assertEqual(translated, ["[Spanish] Line 1", "[Spanish] Line 2"])

        raw_audio, mime = provider.synthesize_speech("Hello curious minds!", "Achird", "", cfg)
        self.assertGreater(len(raw_audio), 1000)
        self.assertIn("audio/L16", mime)

        with tempfile.TemporaryDirectory() as tmp:
            out_img = Path(tmp) / "scene_1.jpg"
            model_used = provider.generate_image("A starry sky", out_img, cfg)
            self.assertEqual(model_used, "mock-svg")
            self.assertTrue(out_img.with_suffix(".svg").is_file())


if __name__ == "__main__":
    unittest.main()
