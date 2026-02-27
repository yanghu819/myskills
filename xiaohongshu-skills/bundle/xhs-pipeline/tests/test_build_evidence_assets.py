#!/usr/bin/env python3
import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "build_evidence_assets.py"
SAMPLE = ROOT / "examples" / "sample_book_outline.v1.json"


class BuildEvidenceAssetsTests(unittest.TestCase):
    def test_generate_assets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            out_dir = Path(tmp_dir) / "assets"
            cmd = [
                "python3",
                str(SCRIPT),
                "--input",
                str(SAMPLE),
                "--output-dir",
                str(out_dir),
                "--width",
                "1080",
                "--height",
                "1440",
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, msg=proc.stderr)
            for i in range(1, 7):
                p = out_dir / f"evidence_{i:02d}.png"
                self.assertTrue(p.exists(), msg=str(p))
                self.assertGreater(p.stat().st_size, 1024)

            manifest_path = out_dir / "assets_manifest.json"
            self.assertTrue(manifest_path.exists())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["count"], 6)
            self.assertEqual(manifest["width"], 1080)
            self.assertEqual(manifest["height"], 1440)

    def test_invalid_outline_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            bad = Path(tmp_dir) / "bad.json"
            bad.write_text("{}", encoding="utf-8")
            out_dir = Path(tmp_dir) / "assets"
            cmd = [
                "python3",
                str(SCRIPT),
                "--input",
                str(bad),
                "--output-dir",
                str(out_dir),
            ]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("validation failed", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
