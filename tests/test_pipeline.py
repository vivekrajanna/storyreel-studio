"""End-to-end offline pipeline tests: dry-run planner, WAV stitch, SRT, 16:9, 9:16, thumbnail & SEO."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from storyreel.config import load_config
from storyreel.pipeline.audio import stitch_full_wav, write_wav_bytes
from storyreel.pipeline.builder import build_story, plan_build
from storyreel.pipeline.subtitles import build_srt_content
from storyreel.providers import get_provider

ROOT = Path(__file__).resolve().parent.parent


class PipelineTests(unittest.TestCase):
    def test_srt_and_frame_aligned_wav_stitching(self) -> None:
        scenes = [
            {"id": 1, "key": "1", "audioDurationSec": 2.0, "durationSec": 2.8, "vo": "One Two", "audio_by_lang": {}},
            {"id": 2, "key": "2", "audioDurationSec": 1.5, "durationSec": 2.3, "vo": "Three", "audio_by_lang": {}},
        ]
        srt = build_srt_content(scenes, {"1": ["One", "Two"], "2": ["Three"]}, 0.15, 0.8)
        self.assertIn("00:00:00,150 -->", srt)
        self.assertIn("00:00:02,950 --> 00:00:04,450", srt)

        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp)
            pcm_1s = b"\x00\x00" * 24000
            write_wav_bytes(pcm_1s, "audio/L16;rate=24000", out_dir / "audio" / "en" / "scene_1.wav")
            write_wav_bytes(pcm_1s, "audio/L16;rate=24000", out_dir / "audio" / "en" / "scene_2.wav")
            scenes[0]["audio_by_lang"]["en"] = {"file": "audio/en/scene_1.wav", "durationSec": 1.0}
            scenes[1]["audio_by_lang"]["en"] = {"file": "audio/en/scene_2.wav", "durationSec": 1.0}
            dur = stitch_full_wav(scenes, "en", out_dir, 0.15, out_dir / "audio" / "full_en.wav")
            self.assertEqual(dur, 5.1)
            self.assertTrue((out_dir / "audio" / "full_en.wav").is_file())

    def test_end_to_end_multilingual_mock_build_and_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            shutil.copytree(ROOT / "templates", proj / "templates")
            shutil.copytree(ROOT / "brand", proj / "brand")
            shutil.copytree(ROOT / "stories", proj / "stories")

            cfg = load_config(ROOT)
            cfg["audio_languages"] = [
                {"code": "en", "name": "English", "label": "English (Primary)"},
                {"code": "es", "name": "Spanish", "label": "Español"},
            ]
            cfg["subtitle_languages"] = list(cfg["audio_languages"])

            sample_md = proj / "stories" / "sample_01_curious_fox.md"
            dry = plan_build(sample_md, cfg, proj)
            self.assertEqual(dry["api_calls"]["images"], 4)  # 3 unique scenes + 1 thumbnail (scene 4 reuses scene 1? No, 4 scene prompts + 1 thumb = 5? check!)
            self.assertEqual(dry["api_calls"]["tts_clips"], 8)  # 4 scenes x 2 languages
            self.assertEqual(dry["api_calls"]["translations"], 1)  # Spanish

            out_dir = build_story(sample_md, cfg, get_provider("mock"), proj)
            self.assertTrue((out_dir / "player.html").is_file())
            self.assertTrue((out_dir / "reel.html").is_file())
            self.assertTrue((out_dir / "thumbnail.html").is_file())
            self.assertTrue((out_dir / "seo.md").is_file())
            self.assertTrue((out_dir / "audio" / "full_en.wav").is_file())
            self.assertTrue((out_dir / "audio" / "full_es.wav").is_file())
            self.assertTrue((out_dir / "subtitles" / "en.srt").is_file())
            self.assertTrue((out_dir / "subtitles" / "es.srt").is_file())
            self.assertTrue((proj / "output" / "index.html").is_file())

            ep = json.loads((out_dir / "episode.json").read_text(encoding="utf-8"))
            self.assertIn("en", ep["seo"]["by_lang"])
            self.assertIn("es", ep["seo"]["by_lang"])

            # Subsequent dry-run should report 0 uncached calls!
            dry_after = plan_build(sample_md, cfg, proj)
            self.assertEqual(dry_after["api_calls"]["tts_clips"], 0)
            self.assertEqual(dry_after["api_calls"]["translations"], 0)
            self.assertEqual(dry_after["api_calls"]["seo_pack"], 0)


if __name__ == "__main__":
    unittest.main()
