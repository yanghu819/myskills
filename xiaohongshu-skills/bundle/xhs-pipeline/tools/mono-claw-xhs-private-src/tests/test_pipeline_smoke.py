from __future__ import annotations

import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_cmd(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["python3", *args],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )


def test_check_env_stage_outputs_contract() -> None:
    p = run_cmd("scripts/pipeline_orchestrator.py", "--stage", "check-env")
    assert p.returncode == 0, p.stdout
    out = p.stdout
    assert "STAGE=check-env" in out
    assert "STATUS=ok" in out
    assert "OUTPUT_PATH=" in out
    assert "NEXT_ACTION=" in out


def test_export_summary_generates_results_doc() -> None:
    p = run_cmd("scripts/pipeline_orchestrator.py", "--stage", "export-summary")
    assert p.returncode == 0, p.stdout
    results = ROOT / "docs" / "RESULTS_SUMMARY.md"
    assert results.exists()
    text = results.read_text(encoding="utf-8")
    assert "# RESULTS SUMMARY" in text
    assert "HardThing 4-part" in text
    assert "resources/books/The Hard Thing About Hard Things.epub" in text


def test_env_check_json_block_present() -> None:
    p = run_cmd("scripts/env_check.py")
    assert p.returncode == 0, p.stdout
    out = p.stdout
    assert "\"repo_root\"" in out
    assert "\"status\": \"ok\"" in out
