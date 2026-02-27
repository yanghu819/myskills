from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL_DIR = ROOT / "skills" / "notebooklm-book-pipeline"


def load_module(name: str, rel: str):
    path = SKILL_DIR / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_split_helpers_and_chunking() -> None:
    mod = load_module("split_book_skill", "scripts/split_book_for_notebooklm.py")
    assert mod.slugify("The Hard Thing About Hard Things") == "the-hard-thing-about-hard-things"
    assert "hello" in mod.html_to_text("<h1>Hello</h1><p>world</p>").lower()
    assert mod.first_heading("<h1>My Chapter</h1><p>x</p>") == "My Chapter"

    chapters = [
        mod.Chapter("ch001", "A", "a " * 2000),
        mod.Chapter("ch002", "B", "b " * 2000),
        mod.Chapter("ch003", "C", "c " * 2000),
    ]
    chunks = mod.assemble_chunks(chapters, target_parts=2, min_chars=800, max_chars=6000)
    assert len(chunks) >= 2
    assert chunks[0].part_id == "P01"


def test_split_cli_on_markdown_file() -> None:
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        book = tdp / "book.md"
        book.write_text(
            "# Chapter 1\n\n"
            + ("alpha " * 1200)
            + "\n\n# Chapter 2\n\n"
            + ("beta " * 1200)
            + "\n\n# Chapter 3\n\n"
            + ("gamma " * 1200),
            encoding="utf-8",
        )
        out_dir = tdp / "out"
        p = subprocess.run(
            [
                "python3",
                str(SKILL_DIR / "scripts" / "split_book_for_notebooklm.py"),
                "--book",
                str(book),
                "--target-parts",
                "3",
                "--out-dir",
                str(out_dir),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        assert p.returncode == 0, p.stdout
        manifest = out_dir / "split_manifest.json"
        assert manifest.exists()
        obj = json.loads(manifest.read_text(encoding="utf-8"))
        assert obj["chapters_count"] >= 3
        assert len(obj["parts"]) >= 2


def test_pipeline_dry_run_outputs_materials() -> None:
    with tempfile.TemporaryDirectory() as td:
        tdp = Path(td)
        part_file = tdp / "part01.md"
        part_file.write_text("# P01\n\nSome content", encoding="utf-8")
        split_manifest = tdp / "split_manifest.json"
        split_manifest.write_text(
            json.dumps(
                {
                    "book_title": "Demo Book",
                    "parts": [
                        {
                            "part_id": "P01",
                            "title": "Demo Part",
                            "file": str(part_file),
                            "chars": 1000,
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        out_dir = tdp / "outputs"
        p = subprocess.run(
            [
                "python3",
                str(SKILL_DIR / "scripts" / "run_notebooklm_book_pipeline.py"),
                "--split-manifest",
                str(split_manifest),
                "--notebook-id",
                "nb_dry",
                "--artifacts",
                "report,quiz,flashcards",
                "--output-dir",
                str(out_dir),
                "--dry-run",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        assert p.returncode == 0, p.stdout
        run_manifest = out_dir / "run_manifest.json"
        assert run_manifest.exists()
        obj = json.loads(run_manifest.read_text(encoding="utf-8"))
        assert obj["status"] == "ok"
        row = obj["rows"][0]
        assert row["status"] == "ok"
        for art in ["report", "quiz", "flashcards"]:
            assert art in row["artifacts"]
            assert Path(row["artifacts"][art]).exists()


def test_pipeline_notebook_resolution_logic(monkeypatch) -> None:
    mod = load_module("run_book_pipeline", "scripts/run_notebooklm_book_pipeline.py")
    calls: list[list[str]] = []

    def fake_run_nblm(_bin: str, _home: str, args: list[str], timeout: int = 900):  # type: ignore[no-untyped-def]
        calls.append(args)
        if args[:2] == ["list", "--json"]:
            return 0, json.dumps({"notebooks": [{"id": "nb1", "title": "A"}]}), ""
        if args and args[0] == "create":
            return 0, json.dumps({"notebook": {"id": "nb_new", "title": "B"}}), ""
        return 1, "", "unexpected"

    monkeypatch.setattr(mod, "run_nblm", fake_run_nblm)
    got = mod.ensure_notebook_id(
        nblm_bin="nblm",
        notebooklm_home="home",
        notebook_id="",
        notebook_name="A",
        create_if_missing=False,
    )
    assert got == "nb1"

    got2 = mod.ensure_notebook_id(
        nblm_bin="nblm",
        notebooklm_home="home",
        notebook_id="",
        notebook_name="B",
        create_if_missing=True,
    )
    assert got2 == "nb_new"
    assert calls


def test_pipeline_retry_helpers() -> None:
    mod = load_module("run_book_pipeline_retry", "scripts/run_notebooklm_book_pipeline.py")
    assert mod.is_retryable_error("RPC CREATE_ARTIFACT failed after 10.005s")
    assert mod.is_retryable_error("timed out")
    assert not mod.is_retryable_error("validation error: unsupported artifact")
