"""Unit tests for StoryReel Studio Markdown parser and language detection."""

import unittest
from pathlib import Path

from storyreel.parser import detect_source_language, parse_story_md

ROOT = Path(__file__).resolve().parent.parent


class ParserTests(unittest.TestCase):
    def test_parse_sample_story_extracts_meta_scenes_rules_and_vo(self) -> None:
        sample = ROOT / "stories" / "sample_01_curious_fox.md"
        story = parse_story_md(sample)
        self.assertEqual(story["slug"], "sample_01_curious_fox")
        self.assertEqual(story["meta"]["episode_number"], "EP 01")
        self.assertEqual(len(story["scenes"]), 4)
        self.assertEqual(len(story["scenes"][2]["rules"]), 3)
        self.assertTrue(story["scenes"][3]["outro"])
        self.assertGreaterEqual(len(story["scenes"][0]["vo_lines"]), 3)
        self.assertIn("night sky", story["description_md"].lower())

    def test_detect_source_language(self) -> None:
        self.assertEqual(detect_source_language([{"vo": "Hello world!"}]), "en")
        self.assertEqual(detect_source_language([{"vo": "नमस्ते दोस्तों!"}]), "hi")
        self.assertEqual(detect_source_language([{"vo": "ಹಾಯ್ ಫ್ರೆಂಡ್ಸ್!"}]), "kn")


if __name__ == "__main__":
    unittest.main()
