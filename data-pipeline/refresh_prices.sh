#!/usr/bin/env bash
# Refresh the Trading prices: pull FRED (keyless) + Alpha Vantage (needs a key in
# .env) into SQLite, then rebuild prices.json. FRED returns full history each
# time, so this is safe to re-run. Alpha Vantage is best-effort (rate-limited).
#
# Manual run:   bash data-pipeline/refresh_prices.sh
# Logs to:      data-pipeline/refresh_prices.log
set -uo pipefail

REPO="/Users/thibaultdebellefon/Desktop/Claude/Projects/Energy Map"
PY="$(command -v python3)"
LOG="$REPO/data-pipeline/refresh_prices.log"

cd "$REPO"
{
  echo "===== $(date '+%Y-%m-%d %H:%M:%S') prices refresh start ====="
  "$PY" data-pipeline/fetch_prices_fred.py            || echo "(FRED fetch failed)"
  "$PY" data-pipeline/fetch_prices_alphavantage.py    || echo "(Alpha Vantage skipped/failed)"
  "$PY" app/build_news_trading.py
  echo "----- prices refresh done -----"
} >> "$LOG" 2>&1
