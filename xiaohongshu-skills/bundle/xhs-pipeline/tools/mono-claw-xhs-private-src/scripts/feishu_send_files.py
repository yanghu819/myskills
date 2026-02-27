#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import pathlib
import requests


def token(app_id: str, app_secret: str) -> str:
    r = requests.post(
        'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
        headers={'Content-Type': 'application/json; charset=utf-8'},
        data=json.dumps({'app_id': app_id, 'app_secret': app_secret}),
        timeout=30,
    )
    r.raise_for_status()
    obj = r.json()
    if obj.get('code') != 0:
        raise RuntimeError(f"token error: {obj}")
    return obj['tenant_access_token']


def upload_file(tok: str, path: pathlib.Path, alias_name: str | None = None) -> str:
    with open(path, 'rb') as f:
        files = {'file': (alias_name or path.name, f)}
        data = {'file_type': 'stream', 'file_name': alias_name or path.name}
        r = requests.post(
            'https://open.feishu.cn/open-apis/im/v1/files',
            headers={'Authorization': f'Bearer {tok}'},
            files=files,
            data=data,
            timeout=180,
        )
    r.raise_for_status()
    obj = r.json()
    if obj.get('code') != 0:
        raise RuntimeError(f"upload error: {obj}")
    return obj['data']['file_key']


def send_file(tok: str, open_id: str, file_key: str) -> str:
    payload = {
        'receive_id': open_id,
        'msg_type': 'file',
        'content': json.dumps({'file_key': file_key}, ensure_ascii=False),
    }
    r = requests.post(
        'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id',
        headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json; charset=utf-8'},
        data=json.dumps(payload, ensure_ascii=False),
        timeout=60,
    )
    r.raise_for_status()
    obj = r.json()
    if obj.get('code') != 0:
        raise RuntimeError(f"send error: {obj}")
    return obj['data']['message_id']


def send_text(tok: str, open_id: str, message: str) -> str:
    payload = {
        'receive_id': open_id,
        'msg_type': 'text',
        'content': json.dumps({'text': message}, ensure_ascii=False),
    }
    r = requests.post(
        'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id',
        headers={'Authorization': f'Bearer {tok}', 'Content-Type': 'application/json; charset=utf-8'},
        data=json.dumps(payload, ensure_ascii=False),
        timeout=60,
    )
    r.raise_for_status()
    obj = r.json()
    if obj.get('code') != 0:
        raise RuntimeError(f"send text error: {obj}")
    return obj['data']['message_id']


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--app-id', required=True)
    ap.add_argument('--app-secret', required=True)
    ap.add_argument('--target-open-id', required=True)
    ap.add_argument('--message', default='')
    ap.add_argument('files', nargs='+')
    args = ap.parse_args()

    tok = token(args.app_id, args.app_secret)
    if args.message:
        text_mid = send_text(tok, args.target_open_id, args.message)
        print(f'TEXT_SENT message_id={text_mid}')
    for f in args.files:
        p = pathlib.Path(f)
        if not p.exists():
            print(f'SKIP missing {p}')
            continue
        fk = upload_file(tok, p)
        mid = send_file(tok, args.target_open_id, fk)
        print(f'SENT {p.name} message_id={mid}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
