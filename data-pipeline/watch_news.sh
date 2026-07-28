#!/usr/bin/env bash
# Keep the news feed fresh WITHOUT any system permissions: refresh now, then
# every hour, for as long as this terminal stays open. It inherits your
# Terminal's file access, so it sidesteps the macOS "Operation not permitted"
# that blocks launchd/cron from the Desktop folder.
#
# Run it in a spare terminal tab next to serve.py:
#     bash data-pipeline/watch_news.sh
# Stop with Ctrl-C.
set -u
REPO="/Users/thibaultdebellefon/Desktop/Claude/Projects/Energy Map"
echo "[news] hourly refresh loop started — Ctrl-C to stop"
while true; do
  bash "$REPO/data-pipeline/refresh_news.sh" || echo "[news] refresh hit an error (see refresh_news.log)"
  echo "[news] refreshed $(date '+%Y-%m-%d %H:%M') — next in 60 min"
  sleep 3600
done
