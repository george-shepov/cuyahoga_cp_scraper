#!/usr/bin/env bash
set -euo pipefail

# Manual deploy helper for 104.237.9.52.
# Required env vars:
#   VPS_HOST=104.237.9.52
#   VPS_USER=shepov
#   VPS_APP_DIR=/opt/cuyahoga_cp_scraper
# Optional:
#   DEPLOY_BRANCH=master

if [[ -z "${VPS_HOST:-}" || -z "${VPS_USER:-}" || -z "${VPS_APP_DIR:-}" ]]; then
  echo "Missing required env vars: VPS_HOST, VPS_USER, VPS_APP_DIR" >&2
  exit 1
fi

BRANCH="${DEPLOY_BRANCH:-master}"

ssh "${VPS_USER}@${VPS_HOST}" "bash -s" << EOF
set -euo pipefail

APP_DIR="${VPS_APP_DIR}"
BRANCH="${BRANCH}"

if [[ ! -d "\$APP_DIR/.git" ]]; then
  echo "Repo not found at \$APP_DIR. Clone it first on the server." >&2
  exit 1
fi

cd "\$APP_DIR"
git fetch origin "\$BRANCH"
git checkout "\$BRANCH"
git reset --hard "origin/\$BRANCH"

cd deploy
docker compose up -d --build
docker compose ps
EOF
