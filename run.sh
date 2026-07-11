#!/usr/bin/env bash
# Revert autonomous marketing — daily loop. This is what cron calls.
# 1) generate a fresh content batch for every channel
# 2) render the tiktok/shorts clip (Kling — skipped if no key set)
# 3) post it (dry-run/queue unless live creds are present)
# 4) sync run.log/performance.csv/outbox text to GitHub so the cloud status
#    routine (imhappyyo/revert-marketing) can read TODAY's real results —
#    .env and generated media (img/video) stay out, see .gitignore.
set -euo pipefail
cd "$(dirname "$0")"

# load .env if present (also loaded inside the python tools)
[ -f .env ] && set -a && . ./.env && set +a

LOG="run.log"
{
  echo "──────── $(date '+%Y-%m-%d %H:%M:%S') ────────"
  python3 engine.py      # copy for every channel
  python3 video_gen.py   # Kling clip for tiktok/youtube_shorts (needs batch.json)
  python3 creative.py    # on-brand graphics (code-rendered, no credits)
  python3 post.py        # attach graphics/video + publish (or queue if not live)
  echo
} >> "$LOG" 2>&1

git add run.log performance.csv "outbox/*/QUEUE.md" "outbox/*/batch.json" "outbox/*/*.md" >> "$LOG" 2>&1 || true
if ! git diff --cached --quiet 2>/dev/null; then
  git commit -q -m "daily run $(date '+%Y-%m-%d %H:%M')" >> "$LOG" 2>&1 || true
  git push -q >> "$LOG" 2>&1 || true
fi

# also echo to stdout when run by hand
tail -n 40 "$LOG"
