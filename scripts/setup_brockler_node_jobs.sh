#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
NODE_HOST="${NODE_HOST:-root@104.237.2.186}"
NODE_KEY="${NODE_KEY:-$HOME/.ssh/vps_dime_key}"
REMOTE_CASES_FILE="${REMOTE_CASES_FILE:-/opt/brocklerlaw-save/cases_data.json}"

# Frequency model requested:
# - current year: daily
# - prior year and 5 years before: every 2-3 days (using every 3 days)
# - older years: weekly
DAILY_CURRENT_SCHEDULE="${DAILY_CURRENT_SCHEDULE:-10 2 * * *}"
EVERY3D_SCHEDULE="${EVERY3D_SCHEDULE:-25 2 */3 * *}"
WEEKLY_SCHEDULE="${WEEKLY_SCHEDULE:-40 2 * * 0}"
BROCKLER_SYNC_SCHEDULE="${BROCKLER_SYNC_SCHEDULE:-20 3 * * *}"

mkdir -p "$REPO_DIR/logs" "$REPO_DIR/state"
chmod +x \
  "$REPO_DIR/scripts/main_node_tiered_refresh.py" \
  "$REPO_DIR/scripts/node186_pipeline.sh" \
  "$REPO_DIR/scripts/sync_brockler_offline_ssh.py" \
  "$REPO_DIR/scripts/sync_cases_payload_ssh.py" \
  "$REPO_DIR/scripts/compact_case_versions.py"

DAILY_CMD="cd $REPO_DIR && $PYTHON_BIN scripts/main_node_tiered_refresh.py --tier daily --headless --pdf-types CR --manual-cases-file my_cases.json >> '$REPO_DIR/logs/mainnode_daily.log' 2>&1"
EVERY3D_CMD="cd $REPO_DIR && $PYTHON_BIN scripts/main_node_tiered_refresh.py --tier every3d --headless --pdf-types CR --manual-cases-file my_cases.json >> '$REPO_DIR/logs/mainnode_every3d.log' 2>&1"
WEEKLY_CMD="cd $REPO_DIR && $PYTHON_BIN scripts/main_node_tiered_refresh.py --tier weekly --headless --pdf-types CR --manual-cases-file my_cases.json >> '$REPO_DIR/logs/mainnode_weekly.log' 2>&1"

# .186 only gets Brockler case intelligence payload + Brockler-only offline mirror
BROCKLER_SYNC_CMD="cd $REPO_DIR && $PYTHON_BIN scripts/sync_cases_payload_ssh.py --days 36500 --ssh-host '$NODE_HOST' --ssh-key '$NODE_KEY' --remote-cases-file '$REMOTE_CASES_FILE' >> '$REPO_DIR/logs/node186_brockler_payload.log' 2>&1 && $PYTHON_BIN scripts/sync_brockler_offline_ssh.py --ssh-host '$NODE_HOST' --ssh-key '$NODE_KEY' --remote-root /opt/brockler-node/brockler-only >> '$REPO_DIR/logs/node186_brockler_offline.log' 2>&1"

TMP_CRON="$(mktemp)"
crontab -l 2>/dev/null | grep -Ev "main_node_tiered_refresh.py|sync_brockler_offline_ssh.py|sync_cases_payload_ssh.py|node186_pipeline.sh|daily_case_miner.py|monthly_recent_refresh.py" > "$TMP_CRON" || true

echo "$DAILY_CURRENT_SCHEDULE $DAILY_CMD" >> "$TMP_CRON"
echo "$EVERY3D_SCHEDULE $EVERY3D_CMD" >> "$TMP_CRON"
echo "$WEEKLY_SCHEDULE $WEEKLY_CMD" >> "$TMP_CRON"
echo "$BROCKLER_SYNC_SCHEDULE $BROCKLER_SYNC_CMD" >> "$TMP_CRON"

crontab "$TMP_CRON"
rm -f "$TMP_CRON"

echo "Installed jobs:"
echo "$DAILY_CURRENT_SCHEDULE $DAILY_CMD"
echo "$EVERY3D_SCHEDULE $EVERY3D_CMD"
echo "$WEEKLY_SCHEDULE $WEEKLY_CMD"
echo "$BROCKLER_SYNC_SCHEDULE $BROCKLER_SYNC_CMD"
