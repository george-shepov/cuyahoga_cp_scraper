#!/usr/bin/env bash
# Sync scraped data to a dedicated storage VPS over rsync+SSH.
#
# Required env vars (or set in .env):
#   STORAGE_VPS_HOST   — VPS hostname or IP
#   STORAGE_VPS_USER   — SSH username
#   STORAGE_VPS_PORT   — SSH port (default: 22)
#   STORAGE_VPS_PATH   — Remote destination directory (default: /data/cuyahoga)
#   STORAGE_VPS_SSH_KEY — Path to SSH private key (default: ~/.ssh/storage_vps_key)
#
# Usage:
#   ./scripts/sync_to_storage_vps.sh [--dirs "out docs logs"] [--dry-run]

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# ── Load .env if present ──────────────────────────────────────────────────────
ENV_FILE="$ROOT_DIR/.env"
if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC2046
  export $(grep -v '^\s*#' "$ENV_FILE" | grep -v '^\s*$' | xargs)
fi

# ── Config with fallbacks ─────────────────────────────────────────────────────
VPS_HOST="${STORAGE_VPS_HOST:-}"
VPS_USER="${STORAGE_VPS_USER:-}"
VPS_PORT="${STORAGE_VPS_PORT:-22}"
VPS_PATH="${STORAGE_VPS_PATH:-/data/cuyahoga}"
SSH_KEY="${STORAGE_VPS_SSH_KEY:-$HOME/.ssh/storage_vps_key}"

# Expand tilde if present
SSH_KEY="${SSH_KEY/#\~/$HOME}"

# ── Parse arguments ───────────────────────────────────────────────────────────
SYNC_DIRS="out"
DRY_RUN=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dirs)
      SYNC_DIRS="$2"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    *)
      echo "Unknown option: $1" >&2
      echo "Usage: $0 [--dirs \"out docs logs\"] [--dry-run]" >&2
      exit 1
      ;;
  esac
done

# ── Validate ──────────────────────────────────────────────────────────────────
if [[ -z "$VPS_HOST" ]]; then
  echo "Error: STORAGE_VPS_HOST is not set. Set it in .env or export it." >&2
  exit 1
fi
if [[ -z "$VPS_USER" ]]; then
  echo "Error: STORAGE_VPS_USER is not set. Set it in .env or export it." >&2
  exit 1
fi
if [[ ! -f "$SSH_KEY" ]]; then
  echo "Error: SSH key not found at: $SSH_KEY" >&2
  echo "Set STORAGE_VPS_SSH_KEY to your private key path." >&2
  exit 1
fi

RSYNC_OPTS=(
  -avz
  --progress
  --partial
  --delete
  --exclude="*.pyc"
  --exclude="__pycache__/"
  --exclude=".git/"
  -e "ssh -i $SSH_KEY -p $VPS_PORT -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new"
)

if $DRY_RUN; then
  RSYNC_OPTS+=(--dry-run)
  echo "=== DRY RUN — no files will be transferred ==="
fi

# ── Ensure remote base directory exists ──────────────────────────────────────
if ! $DRY_RUN; then
  ssh -i "$SSH_KEY" -p "$VPS_PORT" \
    -o ConnectTimeout=15 \
    -o StrictHostKeyChecking=accept-new \
    "${VPS_USER}@${VPS_HOST}" \
    "mkdir -p '${VPS_PATH}'"
fi

# ── Sync each requested directory ────────────────────────────────────────────
ERRORS=0
for dir in $SYNC_DIRS; do
  local_path="$ROOT_DIR/$dir"
  if [[ ! -d "$local_path" ]]; then
    echo "Warning: directory not found, skipping: $local_path" >&2
    continue
  fi
  echo ""
  echo "── Syncing $dir/ → ${VPS_USER}@${VPS_HOST}:${VPS_PATH}/${dir}/"
  rsync "${RSYNC_OPTS[@]}" "$local_path/" "${VPS_USER}@${VPS_HOST}:${VPS_PATH}/${dir}/" || {
    echo "Error: rsync failed for $dir" >&2
    ((ERRORS++))
  }
done

echo ""
if [[ $ERRORS -eq 0 ]]; then
  echo "Done. All directories synced to ${VPS_USER}@${VPS_HOST}:${VPS_PATH}"
else
  echo "$ERRORS directory/directories failed to sync." >&2
  exit 1
fi
