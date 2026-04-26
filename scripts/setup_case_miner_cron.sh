#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
CRON_SCHEDULE="${CRON_SCHEDULE:-20 3 * * *}"
SYNC_MODE="${SYNC_MODE:-ssh}"
SSH_HOST="${SSH_HOST:-root@104.237.2.186}"
SSH_KEY="${SSH_KEY:-$HOME/.ssh/vps_dime_key}"
REMOTE_CASES_FILE="${REMOTE_CASES_FILE:-/opt/brocklerlaw-save/cases_data.json}"

if [[ "$SYNC_MODE" == "api" && -z "${BROCKLER_API_TOKEN:-}" ]]; then
  echo "ERROR: BROCKLER_API_TOKEN is not set (required in SYNC_MODE=api)"
  echo "Example: export BROCKLER_API_TOKEN='your-admin-password'"
  exit 1
fi

STATE_FILE="${STATE_FILE:-$REPO_DIR/state/case_miner_state.json}"
LOG_FILE="${LOG_FILE:-$REPO_DIR/logs/case_miner_daily.log}"

mkdir -p "$(dirname "$LOG_FILE")" "$(dirname "$STATE_FILE")"

if [[ "$SYNC_MODE" == "api" ]]; then
  CMD="cd $REPO_DIR && BROCKLER_API_TOKEN='$BROCKLER_API_TOKEN' $PYTHON_BIN scripts/daily_case_miner.py --headless --sync-mode api --daily-limit 150 --delay-ms 1000 --workers 6 --state-file '$STATE_FILE' --push-host 'https://prosecutordefense.com' >> '$LOG_FILE' 2>&1"
else
  CMD="cd $REPO_DIR && $PYTHON_BIN scripts/daily_case_miner.py --headless --sync-mode ssh --ssh-host '$SSH_HOST' --ssh-key '$SSH_KEY' --remote-cases-file '$REMOTE_CASES_FILE' --daily-limit 150 --delay-ms 1000 --workers 6 --state-file '$STATE_FILE' >> '$LOG_FILE' 2>&1"
fi

CRON_LINE="$CRON_SCHEDULE $CMD"

TMP_CRON="$(mktemp)"
crontab -l 2>/dev/null | grep -v "scripts/daily_case_miner.py" > "$TMP_CRON" || true
echo "$CRON_LINE" >> "$TMP_CRON"
crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "Installed cron job:"
echo "$CRON_LINE"
