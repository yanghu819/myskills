#!/usr/bin/env bash
set -euo pipefail

FENGVIDEO_ROOT="${FENGVIDEO_ROOT:-/Users/torusmini/Downloads/fengvideo}"
EPISODE_JSON="${EPISODE_JSON:-$FENGVIDEO_ROOT/content/episodes/hard-things-mvp/e01-paid-crisis-truth.json}"
OUT_DIR="${OUT_DIR:-$FENGVIDEO_ROOT/out/bilibili-upload}"
OUT_MP4="${OUT_MP4:-$OUT_DIR/e01-paid-crisis-truth.v25.authority.smoke25s.mp4}"

mkdir -p "$OUT_DIR"
cd "$FENGVIDEO_ROOT"

if [[ -f "$FENGVIDEO_ROOT/setting-api.sh" ]]; then
  # shellcheck disable=SC1091
  source "$FENGVIDEO_ROOT/setting-api.sh"
fi

node - "$EPISODE_JSON" <<'NODE'
const fs = require('node:fs');
const p = process.argv[2];
const j = JSON.parse(fs.readFileSync(p, 'utf8'));
j.visual_style = 'theinward';
j.author_portrait_path = j.author_portrait_path || 'assets/hard-things/ben-horowitz-photo.png';
j.author_avatar_path = j.author_avatar_path || 'assets/hard-things/ben-horowitz-avatar.png';
j.highlight_mode = 'keyword_static';
if (Array.isArray(j.beats)) {
  for (const b of j.beats) b.highlight_mode = 'keyword_static';
}
fs.writeFileSync(p, JSON.stringify(j, null, 2) + '\n', 'utf8');
console.log('[ok] style pinned on', p);
NODE

EPISODE_DIR="$FENGVIDEO_ROOT/content/episodes/hard-things-mvp" EPISODE_ID="e01-paid-crisis-truth" bash "$FENGVIDEO_ROOT/scripts/generate_voice.sh"

node "$FENGVIDEO_ROOT/scripts/build_caption_cues.mjs" \
  --root "$FENGVIDEO_ROOT" \
  --episode "$EPISODE_JSON" \
  --mode sidecar_strict \
  --force 1

node "$FENGVIDEO_ROOT/scripts/align_episode_audio_timing.mjs" \
  --root "$FENGVIDEO_ROOT" \
  --episode "$EPISODE_JSON" \
  --out "$EPISODE_JSON" \
  --pad-sec 0.02 \
  --min-sec 4 \
  --max-sec 120

npx remotion render src/index.ts Episode "$OUT_MP4" \
  --props "$EPISODE_JSON" \
  --codec h264 \
  --audio-codec aac \
  --crf 20 \
  --concurrency 1 \
  --frames 0-749

ffprobe -v error -show_entries stream=codec_name,codec_type,width,height,r_frame_rate -show_entries format=duration,size -of json "$OUT_MP4"
echo "[done] $OUT_MP4"
