#!/usr/bin/env python3
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "outline_to_xhs_md_v2.py"
SAMPLE = ROOT / "examples" / "sample_book_outline.v1.json"


class OutlineToMarkdownV2Tests(unittest.TestCase):
    def test_generate_10_cards_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work = Path(tmp_dir)
            assets = work / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            for i in range(1, 7):
                (assets / f"evidence_{i:02d}.png").write_bytes(b"png")

            out_md = work / "xhs_post.v2.md"
            cmd = [
                "python3",
                str(SCRIPT),
                "--input",
                str(SAMPLE),
                "--output",
                str(out_md),
                "--author",
                "测试作者",
                "--asset-dir",
                str(assets),
                "--style-preset",
                "convert_light_v1",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            self.assertTrue(out_md.exists())

            content = out_md.read_text(encoding="utf-8")
            self.assertIn("target_cards: 10", content)
            self.assertIn('style_preset: "convert_light_v1"', content)
            self.assertIn('cta_bar_text: "', content)
            self.assertIn('author: "测试作者"', content)
            self.assertEqual(content.count("## "), 10)
            self.assertIn("## 卡片2｜为什么现在必须读", content)
            self.assertIn("## 卡片6｜关键案例", content)
            self.assertIn("## 卡片7｜常见误区反驳", content)
            self.assertIn("## 卡片9｜今日行动清单", content)
            self.assertIn("![证据图：危机决策时间线](assets/evidence_01.png)", content)
            self.assertIn("![证据图：风险路径](assets/evidence_03.png)", content)
            self.assertIn("![证据图：误区与纠偏](assets/evidence_05.png)", content)
            self.assertIn("![证据图：执行清单](assets/evidence_04.png)", content)

    def test_missing_asset_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work = Path(tmp_dir)
            assets = work / "assets"
            assets.mkdir(parents=True, exist_ok=True)
            out_md = work / "xhs_post.v2.md"
            cmd = [
                "python3",
                str(SCRIPT),
                "--input",
                str(SAMPLE),
                "--output",
                str(out_md),
                "--asset-dir",
                str(assets),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("missing asset", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
