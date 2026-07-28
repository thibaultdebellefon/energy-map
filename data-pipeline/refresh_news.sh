#!/usr/bin/env bash
# Refresh the news feed: pull the last day of GDELT headlines into SQLite, then
# rebuild the static news.json the frontend reads. Idempotent — the UNIQUE(url)
# upsert means re-runs only add genuinely new articles. Safe to schedule.
#
# Manual run:   bash data-pipeline/refresh_news.sh
# Logs to:      data-pipeline/refresh_news.log
set -euo pipefail

REPO="/Users/thibaultdebellefon/Desktop/Claude/Projects/Energy Map"
PY="$(command -v python3)"
LOG="$REPO/data-pipeline/refresh_news.log"

cd "$REPO"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') refresh start ====="
  "$PY" data-pipeline/fetch_news_gdelt.py --timespan 1d
  "$PY" app/build_news_trading.py
  echo "----- refresh done -----"
} >> "$LOG" 2>&1
