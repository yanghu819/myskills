#!/usr/bin/env python3
"""
List Feishu chats the bot is in (chat_id + name).

Reads appId/appSecret from ~/.openclaw/openclaw.json:
  channels.feishu.appId
  channels.feishu.appSecret

Notes:
- Does NOT print any secrets.
- Feishu API uses tenant_access_token (internal app).
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request


def _resolve_base_url(domain_value: str | None) -> str:
    v = (domain_value or "").strip().lower()
    if not v or v == "feishu":
        return "https://open.feishu.cn"
    if v in ("lark", "larksuite"):
        return "https://open.larksuite.com"
    if v.startswith("http://") or v.startswith("https://"):
        return v.rstrip("/")
    # Unknown value: fall back to Feishu default
    return "https://open.feishu.cn"


def _load_openclaw_config() -> dict:
    path = os.path.expanduser("~/.openclaw/openclaw.json")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _post_json(url: str, payload: dict, headers: dict | None = None, timeout: int = 10) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return json.loads(body)


def _get_json(url: str, headers: dict | None = None, timeout: int = 10) -> dict:
    req = urllib.request.Request(url, headers=headers or {}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", "replace")
        return json.loads(body)


def main() -> int:
    try:
        cfg = _load_openclaw_config()
    except FileNotFoundError:
        print("error: ~/.openclaw/openclaw.json not found", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"error: failed to read ~/.openclaw/openclaw.json: {e}", file=sys.stderr)
        return 2

    feishu = (cfg.get("channels") or {}).get("feishu") or {}
    app_id = feishu.get("appId")
    app_secret = feishu.get("appSecret")
    base = _resolve_base_url(feishu.get("domain"))

    if not app_id or not app_secret:
        print("error: missing channels.feishu.appId/appSecret in ~/.openclaw/openclaw.json", file=sys.stderr)
        return 3

    try:
        token_resp = _post_json(
            f"{base}/open-apis/auth/v3/tenant_access_token/internal",
            {"app_id": app_id, "app_secret": app_secret},
            timeout=10,
        )
    except urllib.error.URLError as e:
        print(f"error: token request failed: {e}", file=sys.stderr)
        return 4
    except Exception as e:
        print(f"error: token request failed: {e}", file=sys.stderr)
        return 4

    if token_resp.get("code") != 0:
        print(f"error: token response code={token_resp.get('code')} msg={token_resp.get('msg')}", file=sys.stderr)
        return 5

    token = token_resp.get("tenant_access_token")
    if not token:
        print("error: token missing in response", file=sys.stderr)
        return 5

    page_token = None
    chats: list[dict] = []
    while True:
        url = f"{base}/open-apis/im/v1/chats?page_size=100"
        if page_token:
            url += f"&page_token={urllib.parse.quote(page_token)}"
        try:
            payload = _get_json(url, headers={"Authorization": f"Bearer {token}"}, timeout=10)
        except urllib.error.URLError as e:
            print(f"error: list chats failed: {e}", file=sys.stderr)
            return 6
        except Exception as e:
            print(f"error: list chats failed: {e}", file=sys.stderr)
            return 6

        if payload.get("code") != 0:
            print(f"error: list chats code={payload.get('code')} msg={payload.get('msg')}", file=sys.stderr)
            return 7

        data = payload.get("data") or {}
        items = data.get("items") or []
        for it in items:
            if isinstance(it, dict) and it.get("chat_id"):
                chats.append(it)

        has_more = bool(data.get("has_more"))
        page_token = data.get("page_token")
        if not has_more or not page_token:
            break

    print(f"base={base}")
    print(f"chats={len(chats)}")
    for it in chats:
        chat_id = it.get("chat_id")
        name = it.get("name") or ""
        # Some payloads include 'chat_mode' or 'chat_type'; keep best-effort.
        mode = it.get("chat_mode") or it.get("chat_type") or ""
        print(f"{chat_id}\t{name}\t{mode}".rstrip())

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
