#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3)}"
NODE_HOST="${NODE_HOST:-root@104.237.2.186}"
NODE_KEY="${NODE_KEY:-$HOME/.ssh/vps_dime_key}"
NODE_OUT_DIR="${NODE_OUT_DIR:-/opt/brockler-node/out}"
REMOTE_CASES_FILE="${REMOTE_CASES_FILE:-/opt/brocklerlaw-save/cases_data.json}"

YEAR="${YEAR:-$(date +%Y)}"
DAILY_LIMIT="${DAILY_LIMIT:-150}"
DELAY_MS="${DELAY_MS:-1000}"
WORKERS="${WORKERS:-6}"
STATE_FILE="${STATE_FILE:-$REPO_DIR/state/case_miner_state.json}"

mkdir -p "$REPO_DIR/logs" "$REPO_DIR/state"

cd "$REPO_DIR"

# 1) mine new cases incrementally (+1 progression) and refresh cases_data.json on node
"$PYTHON_BIN" scripts/daily_case_miner.py \
  --headless \
  --sync-mode ssh \
  --ssh-host "$NODE_HOST" \
  --ssh-key "$NODE_KEY" \
  --remote-cases-file "$REMOTE_CASES_FILE" \
  --daily-limit "$DAILY_LIMIT" \
  --delay-ms "$DELAY_MS" \
  --workers "$WORKERS" \
  --state-file "$STATE_FILE"

# 2) remove unchanged duplicate snapshots and log no-change events
"$PYTHON_BIN" scripts/compact_case_versions.py --year "$YEAR" --log logs/case_compaction.log

# 3) sync only Brockler JSON + PDFs to node for offline availability
"$PYTHON_BIN" scripts/sync_brockler_offline_ssh.py \
  --ssh-host "$NODE_HOST" \
  --ssh-key "$NODE_KEY" \
  --remote-root /opt/brockler-node/brockler-only

echo "[node186] pipeline complete year=$YEAR node=$NODE_HOST"
