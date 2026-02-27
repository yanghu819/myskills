#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "outline_to_xhs_md.py"
SAMPLE = ROOT / "examples" / "sample_book_outline.v1.json"


class OutlineToMarkdownTests(unittest.TestCase):
    def test_generate_8_cards_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_md = Path(tmp_dir) / "xhs_post.v1.md"
            cmd = [
                "python3",
                str(SCRIPT),
                "--input",
                str(SAMPLE),
                "--output",
                str(out_md),
                "--author",
                "测试作者",
                "--target-cards",
                "8",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertTrue(out_md.exists())

            content = out_md.read_text(encoding="utf-8")
            self.assertIn('ratio: "3:4"', content)
            self.assertIn("target_cards: 8", content)
            self.assertIn('author: "测试作者"', content)
            self.assertEqual(content.count("## "), 8)
            self.assertIn("## 卡片8｜行动清单（今日可做）", content)

    def test_invalid_outline_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad_json = Path(tmp_dir) / "bad.json"
            out_md = Path(tmp_dir) / "out.md"
            bad_json.write_text('{"book_meta": {"title": "", "language": "en"}, "chapters": []}', encoding="utf-8")
            cmd = [
                "python3",
                str(SCRIPT),
                "--input",
                str(bad_json),
                "--output",
                str(out_md),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("validation failed", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
