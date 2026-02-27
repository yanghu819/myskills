#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_render_manifest.py"


class BuildRenderManifestTests(unittest.TestCase):
    def test_manifest_generation_and_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work = Path(tmp_dir)
            for name in ("card_2.png", "cover.png", "card_1.png", "10-card.png"):
                (work / name).write_bytes(b"png")

            cmd = [
                "python3",
                str(SCRIPT),
                "--input-dir",
                str(work),
                "--width",
                "1080",
                "--height",
                "1440",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)

            manifest_path = work / "render_manifest.v1.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertEqual(manifest["width"], 1080)
            self.assertEqual(manifest["height"], 1440)
            self.assertEqual(manifest["card_count"], 4)
            self.assertEqual(
                manifest["images"],
                ["cover.png", "card_1.png", "card_2.png", "10-card.png"],
            )
            self.assertTrue(manifest["generated_at"].endswith("Z"))

    def test_fails_when_no_png(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            work = Path(tmp_dir)
            (work / "a.txt").write_text("x", encoding="utf-8")
            cmd = ["python3", str(SCRIPT), "--input-dir", str(work)]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("no png files", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
