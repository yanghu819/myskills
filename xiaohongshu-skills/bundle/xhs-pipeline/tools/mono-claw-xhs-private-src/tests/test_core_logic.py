from __future__ import annotations

import datetime as dt
import importlib.util
import json
import subprocess
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


def test_xhs_watch_helpers_and_aggregate() -> None:
    m = load_module("xhs_watch", "scripts/xhs_kol_theme_watch.py")
    assert m.to_int("1.5万") == 15000
    assert m.to_int("2亿") == 200000000
    assert m.to_int(True) == 0
    assert "流量增长" in m.extract_themes("如何涨粉和流量增长")
    assert m.monetization_score("知识付费 训练营 转化") > 0
    assert m.is_noise_record("某某官方", "普通新闻", "", "")
    assert m.creator_profile("bilibili", "123") == "https://space.bilibili.com/123"

    notes = [
        {
            "platform": "bilibili",
            "user_id": "u1",
            "nickname": "增长教练A",
            "title": "知识付费转化与涨粉",
            "keyword": "知识付费",
            "likes": 100,
            "collects": 50,
            "comments": 20,
            "plays": 10000,
            "publish_ts": int(dt.datetime.now().timestamp()),
            "url": "https://example.com/1",
        },
        {
            "platform": "bilibili",
            "user_id": "u1",
            "nickname": "增长教练A",
            "title": "训练营定价与私域成交",
            "keyword": "训练营",
            "likes": 80,
            "collects": 30,
            "comments": 10,
            "plays": 8000,
            "publish_ts": int(dt.datetime.now().timestamp()),
            "url": "https://example.com/2",
        },
        {
            "platform": "xiaohongshu",
            "user_id": "u2",
            "nickname": "知识博主B",
            "title": "内容脚本模板",
            "keyword": "内容创业",
            "likes": 40,
            "collects": 10,
            "comments": 5,
            "plays": 0,
            "publish_ts": 0,
            "url": "https://example.com/3",
        },
    ]
    agg = m.aggregate(notes, top_n=10)
    assert len(agg["top_creators"]) == 2
    assert agg["top_creators"][0]["nickname"] == "增长教练A"
    assert any(theme for theme, _ in agg["top_themes"])
    actions = m.build_action_items(agg["top_themes"])
    assert 1 <= len(actions) <= 6


def test_xhs_autojudge_helpers() -> None:
    m = load_module("xhs_judge", "scripts/xhs_kol_autojudge_iterate.py")
    out = m.parse_kv_stdout("RUN_ID=1\nfoo=bar\nJSON_PATH=/tmp/x.json")
    assert out["RUN_ID"] == "1"
    assert out["JSON_PATH"] == "/tmp/x.json"
    assert m.safe_date("2026-02-26") is not None
    assert m.safe_date("-") is None

    today = dt.date.today().strftime("%Y-%m-%d")
    payload = {
        "notes_count": 25,
        "top_creators": [
            {
                "last_publish_date": today,
                "notes": 3,
                "nickname": "增长教练A",
                "top_themes": ["流量增长", "转化成交"],
                "primary_platform": "bilibili",
                "rank_score": 99.1,
                "profile": "https://space.bilibili.com/1",
            }
        ],
        "top_themes": [["内容生产", 8], ["流量增长", 6], ["转化成交", 5]],
        "actions": ["题1", "题2", "题3"],
        "top_tokens": [["知识付费", 9]],
    }
    score, details = m.judge_payload(payload)
    assert score > 0
    assert details["notes_count"] == 25
    msg = m.build_message(
        payload,
        {"profile_name": "fresh_balanced", "score": score, "judge": details},
        "run_1",
    )
    assert "知识变现博主雷达" in msg
    assert "run_1" in msg


def test_notebooklm_manifest_and_series_helpers() -> None:
    builder = load_module("manifest_builder", "scripts/notebooklm_manifest_builder.py")
    series = load_module("series_runner", "scripts/notebooklm_series_runner.py")

    assert builder.parse_ch_num("CH09-demo") == 9
    assert builder.parse_ch_num("chapter demo") is None
    assert builder.slugify_title("  a   b  ") == "a b"
    assert "目标" in builder.steering_prompt("第一部分", "目标说明")

    assert series.parse_retry_minutes("10,abc,30") == [10, 30]
    assert series.parse_retry_minutes("") == [30, 90]
    assert series.str2bool("true")
    assert not series.str2bool("0")
    assert series.sanitize_slug(" E01: 第一部分 / demo ") == "e01-第一部分-demo"
    assert series.choose_next_pending(
        [
            {"episode_id": "E02", "status": "pending"},
            {"episode_id": "E01", "status": "done"},
        ]
    )["episode_id"] == "E02"
    assert series.should_process_episode("test", {"episode_id": "E01", "status": "done"}, None)
    assert not series.should_process_episode("full", {"episode_id": "E01", "status": "done"}, None)
    assert isinstance(series.parse_json_mixed("x\n{\"a\":1}")["a"], int)
    assert series.build_run_id({"series_id": "s", "notebook_id": "n"}).startswith("hardthing-")


def test_package_bundle_and_feishu_helpers(monkeypatch) -> None:
    pack = load_module("pack_bundle", "scripts/package_4part_bundle.py")
    feishu = load_module("feishu_send", "scripts/feishu_send_files.py")
    assert pack.parse_args is not None

    with tempfile.TemporaryDirectory() as td:
        tdir = Path(td)
        src_dir = tdir / "src"
        src_dir.mkdir(parents=True, exist_ok=True)
        (src_dir / "video.mp4").write_bytes(b"fake-video")
        (src_dir / "report.md").write_text("report", encoding="utf-8")
        (src_dir / "quiz.json").write_text("{}", encoding="utf-8")
        (src_dir / "flashcards.json").write_text("{}", encoding="utf-8")
        (src_dir / "citations.csv").write_text("a,b\n", encoding="utf-8")
        (src_dir / "publish_copy.md").write_text("copy", encoding="utf-8")
        manifest = {
            "episodes": [
                {
                    "episode_id": "E01",
                    "title": "测试",
                    "status": "done",
                    "artifacts": {
                        "video": str(src_dir / "video.mp4"),
                        "report": str(src_dir / "report.md"),
                        "quiz": str(src_dir / "quiz.json"),
                        "flashcards": str(src_dir / "flashcards.json"),
                        "citation_csv": str(src_dir / "citations.csv"),
                        "copy_md": str(src_dir / "publish_copy.md"),
                    },
                }
            ]
        }
        manifest_path = tdir / "manifest.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        out_base = tdir / "out"

        p = subprocess.run(
            [
                "python3",
                str(ROOT / "scripts" / "package_4part_bundle.py"),
                "--manifest",
                str(manifest_path),
                "--out-base",
                str(out_base),
                "--ffmpeg-bin",
                "false",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
        )
        assert p.returncode == 0, p.stdout
        assert "BUNDLE_DIR=" in p.stdout

    class DummyResp:
        def __init__(self, payload: dict):
            self._payload = payload
            self.status_code = 200

        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return self._payload

    def fake_post(url: str, headers=None, data=None, files=None, timeout=0):  # type: ignore[no-untyped-def]
        if "tenant_access_token" in url:
            return DummyResp({"code": 0, "tenant_access_token": "tok"})
        if "/im/v1/files" in url:
            return DummyResp({"code": 0, "data": {"file_key": "fk"}})
        if "/im/v1/messages" in url:
            return DummyResp({"code": 0, "data": {"message_id": "mid"}})
        return DummyResp({"code": 0})

    monkeypatch.setattr(feishu.requests, "post", fake_post)
    tok = feishu.token("aid", "asec")
    assert tok == "tok"
    mid = feishu.send_text(tok, "openid", "hello")
    assert mid == "mid"

    with tempfile.NamedTemporaryFile(delete=False) as tf:
        tf.write(b"abc")
        temp_file = Path(tf.name)
    try:
        fk = feishu.upload_file(tok, temp_file)
        assert fk == "fk"
        mid2 = feishu.send_file(tok, "openid", fk)
        assert mid2 == "mid"
    finally:
        temp_file.unlink(missing_ok=True)
