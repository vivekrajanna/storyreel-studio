"""Security & open-source hygiene tests (path confinement, no hardcoded secrets or brand leaks)."""

import re
import unittest
from pathlib import Path

from storyreel.server import is_safe_subpath

ROOT = Path(__file__).resolve().parent.parent


class SecurityHygieneTests(unittest.TestCase):
    def test_is_safe_subpath_blocks_traversal_and_dotenv(self) -> None:
        out_dir = ROOT / "output"
        self.assertTrue(is_safe_subpath(out_dir, out_dir / "index.html"))
        self.assertFalse(is_safe_subpath(out_dir, ROOT / ".env"))
        self.assertFalse(is_safe_subpath(out_dir, out_dir / ".." / ".env"))
        self.assertFalse(is_safe_subpath(out_dir, Path("/etc/passwd")))

    def test_no_hardcoded_api_keys_or_personal_brand_in_repo(self) -> None:
        key_re = re.compile(r"AIza[0-9A-Za-z_-]{20,}|AQ\.[0-9A-Za-z_-]{20,}|sk-[0-9A-Za-z]{20,}")
        scan_dirs = [ROOT / "storyreel", ROOT / "templates", ROOT / "stories"]
        for d in scan_dirs:
            for f in d.rglob("*"):
                if not f.is_file() or "__pycache__" in f.parts:
                    continue
                content = f.read_text(encoding="utf-8", errors="ignore")
                self.assertIsNone(key_re.search(content), f"Potential secret found in {f}")
                self.assertNotIn("MindMagicKN", content, f"Personal brand handle leaked into {f}")


if __name__ == "__main__":
    unittest.main()
