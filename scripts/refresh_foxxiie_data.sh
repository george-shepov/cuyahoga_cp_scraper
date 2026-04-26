#!/usr/bin/env bash
# ============================================================================
# refresh_foxxiie_data.sh  –  Regenerate data.json and push to VPS
#
# Runs fetch_sc_attorneys.py (uses cached SC data, only fetches new entries),
# then SCPs the resulting data.json to both VPS web roots.
#
# Setup (run once):
#   chmod +x scripts/refresh_foxxiie_data.sh
#   crontab -e
#   # Add line: 0 3 * * * /path/to/cuyahoga_cp_scraper/scripts/refresh_foxxiie_data.sh >> /tmp/foxxiie_refresh.log 2>&1
#
# Requires environment or ~/.foxxiie_env:
#   VPS_HOST=shepov@104.237.9.52
#   VPS_SSH_KEY=/home/shepov/.ssh/vps_dime_key
# ============================================================================

set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DATA_JSON="$REPO/docs/foxxiie/data.json"
LOG_PREFIX="[$(date '+%Y-%m-%d %H:%M:%S')]"

# Load env from dotfile if not already set
if [[ -f "$HOME/.foxxiie_env" ]]; then
    # shellcheck disable=SC1091
    source "$HOME/.foxxiie_env"
fi

VPS_HOST="${VPS_HOST:-}"
VPS_SSH_KEY="${VPS_SSH_KEY:-}"

if [[ -z "$VPS_HOST" || -z "$VPS_SSH_KEY" ]]; then
    echo "$LOG_PREFIX ERROR: VPS_HOST and VPS_SSH_KEY must be set (or in ~/.foxxiie_env)"
    exit 1
fi

SSH_KEY="${VPS_SSH_KEY/#\~/$HOME}"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no -o BatchMode=yes"

echo "$LOG_PREFIX Regenerating data.json from CSV + cache..."
cd "$REPO"
python3 scripts/fetch_sc_attorneys.py

if [[ ! -f "$DATA_JSON" ]]; then
    echo "$LOG_PREFIX ERROR: data.json was not created"
    exit 1
fi

SIZE=$(wc -c < "$DATA_JSON")
echo "$LOG_PREFIX data.json generated ($SIZE bytes)"

echo "$LOG_PREFIX Uploading to foxxiie.com..."
$SCP "$DATA_JSON" "$VPS_HOST:/var/www/foxxiie.com/data.json"

echo "$LOG_PREFIX Uploading to prosecutordefense.com..."
$SCP "$DATA_JSON" "$VPS_HOST:/var/www/prosecutordefense.com/data.json"

echo "$LOG_PREFIX Done. data.json deployed to both VPS web roots."
