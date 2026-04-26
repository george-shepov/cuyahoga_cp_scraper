#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
NODE_HOST="${NODE_HOST:-root@104.237.2.186}"
NODE_KEY="${NODE_KEY:-$HOME/.ssh/vps_dime_key}"
REMOTE_CASES_FILE="${REMOTE_CASES_FILE:-/opt/brocklerlaw-save/cases_data.json}"

DAILY_SCHEDULE="${DAILY_SCHEDULE:-20 3 * * *}"
MONTHLY_SCHEDULE="${MONTHLY_SCHEDULE:-35 4 1 * *}"

mkdir -p "$REPO_DIR/logs" "$REPO_DIR/state"
chmod +x "$REPO_DIR/scripts/node186_pipeline.sh" "$REPO_DIR/scripts/monthly_recent_refresh.py" "$REPO_DIR/scripts/compact_case_versions.py" "$REPO_DIR/scripts/sync_cases_payload_ssh.py"

DAILY_CMD="cd $REPO_DIR && NODE_HOST='$NODE_HOST' NODE_KEY='$NODE_KEY' REMOTE_CASES_FILE='$REMOTE_CASES_FILE' bash scripts/node186_pipeline.sh >> '$REPO_DIR/logs/node186_daily.log' 2>&1"
MONTHLY_CMD="cd $REPO_DIR && $PYTHON_BIN scripts/monthly_recent_refresh.py --headless --download-pdfs --days 90 --max-cases 250 >> '$REPO_DIR/logs/node186_monthly.log' 2>&1 && $PYTHON_BIN scripts/compact_case_versions.py --year \$(date +%Y) --log '$REPO_DIR/logs/case_compaction.log' >> '$REPO_DIR/logs/node186_monthly.log' 2>&1 && $PYTHON_BIN scripts/sync_cases_payload_ssh.py --days 90 --ssh-host '$NODE_HOST' --ssh-key '$NODE_KEY' --remote-cases-file '$REMOTE_CASES_FILE' >> '$REPO_DIR/logs/node186_monthly.log' 2>&1"

TMP_CRON="$(mktemp)"
crontab -l 2>/dev/null | grep -Ev "node186_pipeline.sh|monthly_recent_refresh.py|compact_case_versions.py|daily_case_miner.py" > "$TMP_CRON" || true

echo "$DAILY_SCHEDULE $DAILY_CMD" >> "$TMP_CRON"
echo "$MONTHLY_SCHEDULE $MONTHLY_CMD" >> "$TMP_CRON"

crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "Installed jobs:"
echo "$DAILY_SCHEDULE $DAILY_CMD"
echo "$MONTHLY_SCHEDULE $MONTHLY_CMD"
