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
#   1. Copies Brockler site + admin pages to /var/www/foxxiie.com/brocklerlaw/
#      and copies foxxiie homepage to /var/www/foxxiie.com/index.html
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
SECONDARY_SITE_DIR="/var/www/prosecutordefense.com/brocklerlaw"
API_DIR="/opt/brocklerlaw-save"
SECONDARY_DOMAIN_ROOT="/var/www/prosecutordefense.com"

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
ROOT_HTML_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)/foxxiie"

echo "==> Deploying BrocklerLaw to $VPS_HOST"
echo "    SSH key: $SSH_KEY"
if [[ -n "${VPS_SUDO_PASS:-}" ]]; then
    echo "    (using provided sudo password)"
else
    echo "    (assuming passwordless sudo on VPS)"
fi

# ── 1. Upload site files ─────────────────────────────────────────────────────
echo "--- Uploading Brockler site + admin pages"
remote_sudo "mkdir -p $SITE_DIR/admin $SITE_DIR/seo"
remote_sudo "mkdir -p $SECONDARY_SITE_DIR/admin $SECONDARY_SITE_DIR/seo"
$SCP "$HTML_DIR/index.html" "$VPS_HOST:/tmp/brockler_index.html"
$SCP "$HTML_DIR/admin.html" "$VPS_HOST:/tmp/brockler_admin.html"
if [[ -f "$HTML_DIR/admin/index.html" ]]; then
    $SCP "$HTML_DIR/admin/index.html" "$VPS_HOST:/tmp/brockler_admin_index.html"
fi
remote_sudo "mv /tmp/brockler_index.html $SITE_DIR/index.html && mv /tmp/brockler_admin.html $SITE_DIR/admin.html"
remote_sudo "if [ -f /tmp/brockler_admin_index.html ]; then mv /tmp/brockler_admin_index.html $SITE_DIR/admin/index.html; fi"
remote_sudo "cp $SITE_DIR/index.html $SECONDARY_SITE_DIR/index.html && cp $SITE_DIR/admin.html $SECONDARY_SITE_DIR/admin.html"
remote_sudo "if [ -f $SITE_DIR/admin/index.html ]; then cp $SITE_DIR/admin/index.html $SECONDARY_SITE_DIR/admin/index.html; fi"
if [[ -d "$HTML_DIR/seo" ]]; then
    echo "--- Uploading SEO pages"
    $SSH "$VPS_HOST" "mkdir -p /tmp/brockler_seo"
    $SCP -r "$HTML_DIR/seo"/* "$VPS_HOST:/tmp/brockler_seo/"
    remote_sudo "mkdir -p $SITE_DIR/seo && cp -a /tmp/brockler_seo/. $SITE_DIR/seo/ && rm -rf /tmp/brockler_seo"
    remote_sudo "mkdir -p $SECONDARY_SITE_DIR/seo && cp -a $SITE_DIR/seo/. $SECONDARY_SITE_DIR/seo/"
fi

echo "--- Uploading foxxiie.com homepage"
if [[ -f "$ROOT_HTML_DIR/index.html" ]]; then
    remote_sudo "mkdir -p /var/www/foxxiie.com"
    $SCP "$ROOT_HTML_DIR/index.html" "$VPS_HOST:/tmp/foxxiie_root_index.html"
    remote_sudo "mv /tmp/foxxiie_root_index.html /var/www/foxxiie.com/index.html"
    # Also sync to prosecutordefense.com root
    remote_sudo "cp /var/www/foxxiie.com/index.html /var/www/prosecutordefense.com/index.html"

    # Upload pre-built data.json if available (no on-page computation)
    if [[ -f "$ROOT_HTML_DIR/data.json" ]]; then
        echo "--- Uploading data.json (pre-built attorney/judge/prosecutor cache)"
        $SCP "$ROOT_HTML_DIR/data.json" "$VPS_HOST:/tmp/foxxiie_data.json"
        remote_sudo "mv /tmp/foxxiie_data.json /var/www/foxxiie.com/data.json && cp /var/www/foxxiie.com/data.json /var/www/prosecutordefense.com/data.json && chown www-data:www-data /var/www/foxxiie.com/data.json /var/www/prosecutordefense.com/data.json"
    else
        echo "WARN: docs/foxxiie/data.json not found. Run: python3 scripts/fetch_sc_attorneys.py"
    fi
else
    echo "WARN: $ROOT_HTML_DIR/index.html not found. Root homepage will not be updated."
fi

# ── 2. Upload save API ───────────────────────────────────────────────────────
echo "--- Uploading save API"
remote_sudo "mkdir -p $API_DIR"
$SCP "$SCRIPT_DIR/save_api.py" "$VPS_HOST:/tmp/save_api.py"
remote_sudo "mv /tmp/save_api.py $API_DIR/save_api.py && chmod 755 $API_DIR/save_api.py"

# Set site root ownership so save API can create backup/index files on both domains.
remote_sudo "chown -R www-data:www-data $SITE_DIR"
remote_sudo "if [ -d $SECONDARY_SITE_DIR ]; then chown -R www-data:www-data $SECONDARY_SITE_DIR; fi"
remote_sudo "if [ -f /var/www/foxxiie.com/index.html ]; then chown www-data:www-data /var/www/foxxiie.com/index.html; fi"

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
$SCP "$SCRIPT_DIR/nginx-prosecutordefense.conf" "$VPS_HOST:/tmp/nginx-prosecutordefense.conf"
remote_sudo "mv /tmp/nginx-prosecutordefense.conf /etc/nginx/sites-available/prosecutordefense.com"
remote_sudo "ln -sf /etc/nginx/sites-available/prosecutordefense.com /etc/nginx/sites-enabled/prosecutordefense.com"
remote_sudo "mkdir -p /var/www/certbot"

# If cert files are missing, load HTTP-only first so certbot can validate.
if ! $SSH "$VPS_HOST" "test -f /etc/letsencrypt/live/foxxiie.com/fullchain.pem"; then
        echo "--- Bootstrapping HTTP-only config for first-time cert issuance"
    awk '/^# ── HTTPS/{exit} {print}' "$SCRIPT_DIR/nginx-foxxiie.conf" > /tmp/nginx-foxxiie-http.conf
    $SCP /tmp/nginx-foxxiie-http.conf "$VPS_HOST:/tmp/nginx-foxxiie-http.conf"
    remote_sudo "mv /tmp/nginx-foxxiie-http.conf /etc/nginx/sites-available/foxxiie.com"
fi
if ! $SSH "$VPS_HOST" "test -f /etc/letsencrypt/live/prosecutordefense.com/fullchain.pem"; then
    echo "--- Bootstrapping HTTP-only config for prosecutordefense first-time cert issuance"
    awk 'BEGIN { c=0 } /^server \{/ { c++ } c < 2 { print }' "$SCRIPT_DIR/nginx-prosecutordefense.conf" > /tmp/nginx-prosecutordefense-http.conf
    $SCP /tmp/nginx-prosecutordefense-http.conf "$VPS_HOST:/tmp/nginx-prosecutordefense-http.conf"
    remote_sudo "mv /tmp/nginx-prosecutordefense-http.conf /etc/nginx/sites-available/prosecutordefense.com"
fi
remote_sudo "nginx -t && nginx -s reload"

# ── 5. Obtain SSL cert (Let's Encrypt) ───────────────────────────────────────
echo "--- Ensuring SSL certificate (Let's Encrypt)"
remote_sudo "
    if ! command -v certbot >/dev/null 2>&1; then
        apt-get update -qq && apt-get install -y certbot python3-certbot-nginx
    fi
    if [ ! -f /etc/letsencrypt/live/foxxiie.com/fullchain.pem ]; then
        certbot --nginx --non-interactive --agree-tos -m admin@foxxiie.com -d foxxiie.com -d www.foxxiie.com
    else
        certbot renew --nginx || true
    fi
    if [ ! -f /etc/letsencrypt/live/prosecutordefense.com/fullchain.pem ]; then
        certbot --nginx --non-interactive --agree-tos -m admin@foxxiie.com -d prosecutordefense.com -d www.prosecutordefense.com || true
    fi
"

# ── 6. Restore full config + reload ──────────────────────────────────────────
echo "--- Restoring full Nginx config and reloading"
$SCP "$SCRIPT_DIR/nginx-foxxiie.conf" "$VPS_HOST:/tmp/nginx-foxxiie.conf"
remote_sudo "mv /tmp/nginx-foxxiie.conf /etc/nginx/sites-available/foxxiie.com"
$SCP "$SCRIPT_DIR/nginx-prosecutordefense.conf" "$VPS_HOST:/tmp/nginx-prosecutordefense.conf"
remote_sudo "mv /tmp/nginx-prosecutordefense.conf /etc/nginx/sites-available/prosecutordefense.com"
remote_sudo "nginx -t && nginx -s reload"

echo ""
echo "==> Done!"
echo "    https://foxxiie.com/brocklerlaw/"
echo "    Admin: https://foxxiie.com/brocklerlaw/admin/"
echo "    https://prosecutordefense.com/brocklerlaw/"
echo "    Admin: https://prosecutordefense.com/brocklerlaw/admin/"
