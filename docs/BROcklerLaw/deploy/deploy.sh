#!/usr/bin/env bash
# ============================================================================
# deploy.sh  –  Deploy BrocklerLaw site to foxxiie.com on VPS
#
# SECURITY: VPS credentials are NOT in this file. Set via environment:
#   export VPS_HOST="user@hostname"          # e.g. user@your-vps-host.com
#   export VPS_SSH_KEY="~/.ssh/your_key"     # SSH private key path
#   export VPS_SUDO_PASS="your_sudo_pass"    # (optional) sudo password on VPS
#   bash docs/BROcklerLaw/deploy/deploy.sh
#
# What it does:
#   1. Copies index.html, admin.html to /var/www/foxxiie.com/brocklerlaw/
#   2. Installs the save API (/opt/brocklerlaw-save/save_api.py)
#   3. Enables & starts the brocklerlaw-save systemd service
#   4. Installs Nginx config (sites-available/foxxiie.com)
#   5. Creates /var/www/certbot for ACME challenges
#   6. Obtains Let's Encrypt SSL cert via certbot --nginx
#   7. Reloads Nginx
# ============================================================================
set -euo pipefail

# Require environment variables
if [[ -z "${VPS_HOST:-}" ]]; then
    echo "ERROR: VPS_HOST not set. Example:"
    echo "  export VPS_HOST='user@your-vps-host.com'"
    echo "  export VPS_SSH_KEY='~/.ssh/vps_dime_key'"
    echo "  export VPS_SUDO_PASS='your_sudo_password'  # optional if passwordless sudo"
    exit 1
fi

if [[ -z "${VPS_SSH_KEY:-}" ]]; then
    echo "ERROR: VPS_SSH_KEY not set. Example:"
    echo "  export VPS_SSH_KEY='~/.ssh/vps_dime_key'"
    exit 1
fi

SSH_KEY="${VPS_SSH_KEY/#\~/$HOME}"
if [[ ! -f "$SSH_KEY" ]]; then
    echo "ERROR: SSH key not found: $SSH_KEY"
    exit 1
fi

SSH="ssh -i $SSH_KEY -o StrictHostKeyChecking=no"
SCP="scp -i $SSH_KEY -o StrictHostKeyChecking=no"
SITE_DIR="/var/www/foxxiie.com/brocklerlaw"
API_DIR="/opt/brocklerlaw-save"

# Helper to run sudo on remote (with optional password)
remote_sudo() {
    local cmd="$1"
    if [[ -n "${VPS_SUDO_PASS:-}" ]]; then
        $SSH "$VPS_HOST" "echo '$VPS_SUDO_PASS' | sudo -S sh -c '$cmd'"
    else
        # Try without password (passwordless sudo)
        $SSH "$VPS_HOST" "sudo sh -c '$cmd'"
    fi
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HTML_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Deploying BrocklerLaw to $VPS_HOST"
echo "    SSH key: $SSH_KEY"
if [[ -n "${VPS_SUDO_PASS:-}" ]]; then
    echo "    (using provided sudo password)"
else
    echo "    (assuming passwordless sudo on VPS)"
fi

# ── 1. Upload site files ─────────────────────────────────────────────────────
echo "--- Uploading index.html + admin.html"
remote_sudo "mkdir -p $SITE_DIR"
$SCP "$HTML_DIR/index.html" "$VPS_HOST:/tmp/brockler_index.html"
$SCP "$HTML_DIR/admin.html" "$VPS_HOST:/tmp/brockler_admin.html"
remote_sudo "mv /tmp/brockler_index.html $SITE_DIR/index.html && mv /tmp/brockler_admin.html $SITE_DIR/admin.html"

# ── 2. Upload save API ───────────────────────────────────────────────────────
echo "--- Uploading save API"
remote_sudo "mkdir -p $API_DIR"
$SCP "$SCRIPT_DIR/save_api.py" "$VPS_HOST:/tmp/save_api.py"
remote_sudo "mv /tmp/save_api.py $API_DIR/save_api.py && chmod 755 $API_DIR/save_api.py"

# Set site root ownership so www-data can write index.html
remote_sudo "chown -R www-data:www-data $SITE_DIR"

# ── 3. Install + start systemd service ──────────────────────────────────────
echo "--- Installing systemd service"
$SCP "$SCRIPT_DIR/brocklerlaw-save.service" "$VPS_HOST:/tmp/brocklerlaw-save.service"
remote_sudo "mv /tmp/brocklerlaw-save.service /etc/systemd/system/brocklerlaw-save.service"
remote_sudo "systemctl daemon-reload && systemctl enable brocklerlaw-save && systemctl restart brocklerlaw-save"
$SSH "$VPS_HOST" "systemctl is-active brocklerlaw-save" || true

# ── 4. Install Nginx config ──────────────────────────────────────────────────
echo "--- Installing Nginx config"
$SCP "$SCRIPT_DIR/nginx-foxxiie.conf" "$VPS_HOST:/tmp/nginx-foxxiie.conf"
remote_sudo "mv /tmp/nginx-foxxiie.conf /etc/nginx/sites-available/foxxiie.com"
remote_sudo "ln -sf /etc/nginx/sites-available/foxxiie.com /etc/nginx/sites-enabled/foxxiie.com"
remote_sudo "nginx -t && nginx -s reload"

# ── 5. Create certbot webroot dir ────────────────────────────────────────────
remote_sudo "mkdir -p /var/www/certbot"

# ── 6. Obtain SSL cert (Let's Encrypt) ──────────────────────────────────────
echo "--- Obtaining SSL certificate (Let's Encrypt)"
echo "    This requires port 80 to be reachable from the internet."
echo "    certbot will modify the Nginx config automatically."

remote_sudo "
  if ! command -v certbot &>/dev/null; then
    apt-get update -qq && apt-get install -y certbot python3-certbot-nginx
  fi
  # Only request cert if it doesn't already exist
  if [ ! -f /etc/letsencrypt/live/foxxiie.com/fullchain.pem ]; then
    certbot --nginx \
      --non-interactive \
      --agree-tos \
      -m admin@foxxiie.com \
      -d foxxiie.com \
      -d www.foxxiie.com
  else
    echo 'Cert already exists, skipping issuance.'
    certbot renew --dry-run || true
  fi
"

# ── 7. Final Nginx reload ────────────────────────────────────────────────────
echo "--- Reloading Nginx"
remote_sudo "nginx -t && nginx -s reload"

echo ""
echo "==> Done!"
echo "    http://foxxiie.com/brocklerlaw/"
echo "    https://foxxiie.com/brocklerlaw/"
echo "    Admin: http://foxxiie.com/brocklerlaw/admin.html"
