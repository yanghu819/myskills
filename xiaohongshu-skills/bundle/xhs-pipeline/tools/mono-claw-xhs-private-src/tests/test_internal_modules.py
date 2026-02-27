from __future__ import annotations

import importlib.util
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


def test_env_check_helpers() -> None:
    env_check = load_module("env_check", "scripts/env_check.py")
    ok, value = env_check.check_path(str(ROOT / "README.md"))
    assert ok and value.endswith("README.md")
    ok2, _ = env_check.check_path(str(ROOT / "no_such_file.txt"))
    assert not ok2


def test_export_results_helpers() -> None:
    exporter = load_module("export_results_index", "scripts/export_results_index.py")
    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abc")
        temp_path = Path(tf.name)
    try:
        digest = exporter.sha256(temp_path)
        assert len(digest) == 64
        assert exporter.human_size(1024).endswith("KB")
    finally:
        temp_path.unlink(missing_ok=True)


def test_orchestrator_env_loader_expands_vars(monkeypatch) -> None:
    orch = load_module("pipeline_orchestrator", "scripts/pipeline_orchestrator.py")
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / "env.txt"
        p.write_text("FOO=$HOME\nBAR=baz\n", encoding="utf-8")
        monkeypatch.delenv("FOO", raising=False)
        monkeypatch.delenv("BAR", raising=False)
        orch.load_env_file(p)
        assert (orch.os.environ.get("BAR") or "") == "baz"
        assert (orch.os.environ.get("FOO") or "").startswith(str(Path.home()))


def test_orchestrator_loads_feishu_creds_from_openclaw_json(monkeypatch) -> None:
    orch = load_module("pipeline_orchestrator", "scripts/pipeline_orchestrator.py")
    with tempfile.TemporaryDirectory() as td:
        cfg_home = Path(td)
        (cfg_home).mkdir(parents=True, exist_ok=True)
        (cfg_home / "openclaw.json").write_text(
            '{"channels":{"feishu":{"appId":"aid","appSecret":"asec"}}}',
            encoding="utf-8",
        )
        monkeypatch.delenv("FEISHU_APP_ID", raising=False)
        monkeypatch.delenv("FEISHU_APP_SECRET", raising=False)
        monkeypatch.setenv("OPENCLAW_HOME", str(cfg_home))
        app_id, app_secret = orch.load_feishu_credentials()
        assert app_id == "aid"
        assert app_secret == "asec"
