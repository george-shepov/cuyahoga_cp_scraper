#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKUP_ROOT="${BACKUP_ROOT:-$ROOT_DIR/backups}"
RCLONE_REMOTE="${RCLONE_REMOTE:-gdrive:cuyahoga-backups}"

if ! command -v rclone >/dev/null 2>&1; then
  echo "rclone is required. Install it first: https://rclone.org/install/"
  exit 1
fi

if [[ ! -d "$BACKUP_ROOT" ]]; then
  echo "Backup directory not found: $BACKUP_ROOT"
  exit 1
fi

rclone copy "$BACKUP_ROOT" "$RCLONE_REMOTE" --transfers=4 --checkers=8 --progress

echo "Synced backups from $BACKUP_ROOT to $RCLONE_REMOTE"
