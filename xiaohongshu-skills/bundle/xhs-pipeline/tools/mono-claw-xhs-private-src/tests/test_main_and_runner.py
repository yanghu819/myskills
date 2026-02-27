from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_module(name: str, rel: str):
    path = ROOT / rel
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_env_check_main_emits_contract(monkeypatch) -> None:
    mod = load_module("env_check_main", "scripts/env_check.py")
    monkeypatch.setattr(mod, "parse_args", lambda: argparse.Namespace(strict=False))
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        rc = mod.main()
    out = buf.getvalue()
    assert rc == 0
    assert "STAGE=check-env" in out
    assert "STATUS=ok" in out


def test_export_results_main_with_temp_output(monkeypatch) -> None:
    mod = load_module("export_main", "scripts/export_results_index.py")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "summary.md"
        monkeypatch.setattr(mod, "parse_args", lambda: argparse.Namespace(write=str(out)))
        monkeypatch.setattr(mod, "collect_files", lambda: [ROOT / "README.md"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.main()
        assert rc == 0
        assert out.exists()
        assert "RESULTS_PATH=" in buf.getvalue()


def test_pipeline_orchestrator_stages(monkeypatch) -> None:
    mod = load_module("orchestrator_main", "scripts/pipeline_orchestrator.py")
    recorded: list[list[str]] = []

    def fake_run_cmd(argv):  # type: ignore[no-untyped-def]
        recorded.append(argv)
        out = "ok"
        if "feishu_send_files.py" in " ".join(argv):
            out = "TEXT_SENT"
        return 0, out

    monkeypatch.setattr(mod, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(mod, "load_env_file", lambda _p: None)
    monkeypatch.setattr(mod, "load_feishu_credentials", lambda: ("aid", "asec"))

    stages = [
        "check-env",
        "xhs-watch",
        "xhs-judge",
        "hardthing-manifest",
        "hardthing-next",
        "hardthing-bundle",
        "feishu-deliver",
        "verify-offline",
        "verify-live",
        "export-summary",
    ]
    for stage in stages:
        monkeypatch.setattr(
            mod,
            "parse_args",
            lambda s=stage: argparse.Namespace(
                stage=s,
                target="ou_xxx",
                top_n=20,
                days=30,
                bili_pages=1,
                episodes=4,
                mode="test",
                episode="E01",
                send_media="false",
                strict=False,
            ),
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.main()
        assert rc == 0
        assert f"STAGE={stage}" in buf.getvalue()

    assert recorded


def test_manifest_builder_main_with_stubbed_source_list(monkeypatch) -> None:
    mod = load_module("manifest_builder_main", "scripts/notebooklm_manifest_builder.py")
    with tempfile.TemporaryDirectory() as td:
        out = Path(td) / "manifest.json"
        fake_sources = [{"id": f"id-{i}", "title": f"CH{i:02d}-topic"} for i in range(1, 15)]
        monkeypatch.setattr(
            mod,
            "parse_args",
            lambda: argparse.Namespace(
                notebook_id="nb1",
                episodes=4,
                out=str(out),
                language="zh_Hans",
                nblm_bin="/tmp/nblm",
                notebooklm_home="/tmp/auth",
            ),
        )
        monkeypatch.setattr(mod, "run_nblm_json", lambda *a, **k: {"sources": fake_sources})
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.main()
        assert rc == 0
        obj = json.loads(out.read_text(encoding="utf-8"))
        assert len(obj["episodes"]) == 4
        assert "MANIFEST_PATH=" in buf.getvalue()


def test_series_runner_run_episode_reuse_path(monkeypatch) -> None:
    mod = load_module("series_runner_ep", "scripts/notebooklm_series_runner.py")
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        src = tdir / "src"
        src.mkdir(parents=True, exist_ok=True)
        (src / "video.mp4").write_bytes(b"v")
        (src / "report.md").write_text("r", encoding="utf-8")
        (src / "quiz.json").write_text("{}", encoding="utf-8")
        (src / "flashcards.json").write_text("{}", encoding="utf-8")
        (src / "citations.csv").write_text("a,b\n", encoding="utf-8")
        (src / "publish_copy.md").write_text("copy", encoding="utf-8")

        manifest = {
            "notebook_id": "nb1",
            "defaults": {"language": "zh_Hans", "video_format": "explainer", "video_style": "classic"},
            "episodes": [],
        }
        episode = {
            "episode_id": "E01",
            "title": "第一部分：测试",
            "source_ids": ["sid1"],
            "source_titles": ["CH01-topic"],
            "steering_prompt": "test prompt",
            "status": "pending",
            "artifacts": {
                "video": str(src / "video.mp4"),
                "report": str(src / "report.md"),
                "slide_deck": "",
                "quiz": str(src / "quiz.json"),
                "flashcards": str(src / "flashcards.json"),
                "citation_csv": str(src / "citations.csv"),
                "copy_md": str(src / "publish_copy.md"),
            },
            "last_error": "",
            "updated_at": "",
        }
        manifest["episodes"].append(episode)
        manifest_path = tdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")

        args = argparse.Namespace(
            output_root=str(tdir / "out"),
            reuse_existing="true",
            send_media="false",
            require_full_pack="true",
            require_slide_deck="false",
            nblm_bin="/tmp/nblm",
            notebooklm_home="/tmp/auth",
            target="ou_xxx",
            fallback_script=str(ROOT / "scripts" / "notebooklm_video_fallback_ui.py"),
            enable_fallback="true",
            video_timeout_seconds=30,
            artifact_timeout_seconds=30,
        )
        monkeypatch.setattr(mod, "send_feishu_text_retry", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(mod, "send_feishu_media_retry", lambda *a, **k: (True, "ok"))

        result = mod.run_episode(
            args=args,
            manifest=manifest,
            manifest_path=manifest_path,
            run_id="run1",
            episode=episode,
            retries_min=[1],
            title_map={"sid1": "CH01-topic"},
            offers={"keyword": "HardThing", "tiers": [{"name": "入门包", "price": "¥9.9"}]},
            ledger_path=tdir / "ledger.csv",
        )
        assert result["episode"] == "E01"
        assert Path(result["video_path"]).exists()
        assert (tdir / "ledger.csv").exists()


def test_series_runner_main_with_stubs(monkeypatch) -> None:
    mod = load_module("series_runner_main", "scripts/notebooklm_series_runner.py")
    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        nblm_bin = tdir / "notebooklm"
        nblm_bin.write_text("#!/bin/sh\necho ok\n", encoding="utf-8")
        home_dir = tdir / "auth"
        home_dir.mkdir(parents=True, exist_ok=True)
        manifest = {
            "series_id": "s1",
            "notebook_id": "nb1",
            "episodes": [
                {
                    "episode_id": "E01",
                    "title": "T1",
                    "source_ids": ["sid1"],
                    "source_titles": ["CH01-topic"],
                    "status": "pending",
                    "artifacts": {},
                }
            ],
        }
        manifest_path = tdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        offers_path = tdir / "offers.json"
        ledger_path = tdir / "ledger.csv"

        monkeypatch.setattr(
            mod,
            "parse_args",
            lambda: argparse.Namespace(
                manifest=str(manifest_path),
                mode="test",
                episode="E01",
                target="ou_xxx",
                output_root=str(tdir / "out"),
                retry_minutes="1,2",
                enable_fallback="true",
                reuse_existing="true",
                send_media="false",
                require_full_pack="true",
                require_slide_deck="false",
                video_timeout_seconds=30,
                artifact_timeout_seconds=30,
                offers_path=str(offers_path),
                ledger_path=str(ledger_path),
                nblm_bin=str(nblm_bin),
                notebooklm_home=str(home_dir),
                fallback_script=str(ROOT / "scripts" / "notebooklm_video_fallback_ui.py"),
            ),
        )
        monkeypatch.setattr(mod, "refresh_nblm_tokens", lambda *a, **k: (True, "ok"))
        monkeypatch.setattr(mod, "source_map_by_id", lambda *a, **k: {"sid1": "CH01-topic"})
        monkeypatch.setattr(
            mod,
            "run_episode",
            lambda **kwargs: {
                "episode": "E01",
                "video_path": "v.mp4",
                "pack_dir": "pack",
                "feishu_sent": False,
                "fallback_used": False,
                "artifact_ids": {},
            },
        )
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            rc = mod.main()
        assert rc == 0
        assert "RUN_LOG=" in buf.getvalue()
