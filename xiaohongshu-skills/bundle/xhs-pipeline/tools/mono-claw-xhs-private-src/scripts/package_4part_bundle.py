#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import subprocess

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / 'state' / 'hard_thing_episode_manifest.json'
DEFAULT_OUT_BASE = REPO_ROOT / 'state' / 'runtime' / 'outputs'


def parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description='Package Hard Thing 4-part bundle')
    ap.add_argument('--manifest', default=str(DEFAULT_MANIFEST))
    ap.add_argument('--out-base', default=str(DEFAULT_OUT_BASE))
    ap.add_argument('--ffmpeg-bin', default='ffmpeg')
    return ap.parse_args()


def main() -> int:
    args = parse_args()
    manifest_path = pathlib.Path(args.manifest)
    out_base = pathlib.Path(args.out_base)

    obj = json.loads(manifest_path.read_text(encoding='utf-8'))
    ts = dt.datetime.now().strftime('%Y%m%dT%H%M%S')
    out_root = out_base / f'hardthing_4part_bundle_{ts}'
    out_root.mkdir(parents=True, exist_ok=True)

    lines = [
        '# Hard Thing 4-Part Bundle',
        '',
        f'- Generated at: {dt.datetime.now().isoformat()}',
        f'- Source manifest: {manifest_path}',
        '',
    ]

    for e in obj.get('episodes', []):
        if e.get('status') != 'done':
            continue
        ep = e['episode_id']
        title = e['title']
        dst = out_root / f"{ep}_{title}"
        dst.mkdir(parents=True, exist_ok=True)

        lines.append(f'## {ep} {title}')
        for key, short in [
            ('video', 'video'),
            ('report', 'report'),
            ('quiz', 'quiz'),
            ('flashcards', 'flashcards'),
            ('citation_csv', 'citations'),
            ('copy_md', 'publish_copy'),
        ]:
            p = e.get('artifacts', {}).get(key, '')
            if p and pathlib.Path(p).is_file():
                src = pathlib.Path(p)
                out = dst / f'{short}{src.suffix}'
                shutil.copy2(src, out)
                lines.append(f'- {key}: `{out}` ({out.stat().st_size} bytes)')

        v = dst / 'video.mp4'
        vs = dst / 'video_small.mp4'
        if v.exists():
            subprocess.run(
                [
                    args.ffmpeg_bin,
                    '-y',
                    '-i',
                    str(v),
                    '-vf',
                    'scale=1280:-2',
                    '-c:v',
                    'libx264',
                    '-preset',
                    'veryfast',
                    '-crf',
                    '30',
                    '-c:a',
                    'aac',
                    '-b:a',
                    '96k',
                    str(vs),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
            )
            if vs.exists():
                lines.append(f'- video_small: `{vs}` ({vs.stat().st_size} bytes)')
        lines.append('')

    (out_root / 'INDEX.md').write_text('\n'.join(lines), encoding='utf-8')
    zip_path = pathlib.Path(str(out_root) + '.zip')
    subprocess.run(['zip', '-r', str(zip_path), str(out_root)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    print(f'BUNDLE_DIR={out_root}')
    print(f'BUNDLE_ZIP={zip_path}')
    print(f'INDEX={out_root / "INDEX.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
