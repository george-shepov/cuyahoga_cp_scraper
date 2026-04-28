#!/bin/bash
# ============================================================================
# COMPLETE_DEPLOYMENT.sh - Finish deploying the auth bypass to live site
#
# The modified admin.html with auth bypass is staged at:
#   /tmp/brockler_admin_bypass.html (on VPS at 104.237.9.52)
#
# This script completes the deployment by moving it to the correct locations
# and setting permissions. You need to provide your VPS sudo password.
# ============================================================================

set -e

# Configuration
VPS_HOST="shepov@104.237.9.52"
VPS_SSH_KEY="$HOME/.ssh/vps_dime_key"
STAGED_FILE="/tmp/brockler_admin_bypass.html"
TARGET_DIR_FOXXIIE="/var/www/foxxiie.com/brocklerlaw"
TARGET_DIR_PROSECUT="/var/www/prosecutordefense.com/brocklerlaw"

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║              COMPLETING AUTH BYPASS DEPLOYMENT                            ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "VPS Host: $VPS_HOST"
echo "SSH Key: $VPS_SSH_KEY"
echo "Staged File: $STAGED_FILE"
echo ""

# Read sudo password
read -sp "Enter sudo password for VPS: " SUDO_PASS
echo ""
echo ""

# Deploy to foxxiie.com
echo "Step 1: Deploying to $TARGET_DIR_FOXXIIE..."
echo "$SUDO_PASS" | ssh -i "$VPS_SSH_KEY" -o StrictHostKeyChecking=no "$VPS_HOST" \
  "sudo -S mv $STAGED_FILE $TARGET_DIR_FOXXIIE/admin.html && \
   sudo -S chown www-data:www-data $TARGET_DIR_FOXXIIE/admin.html && \
   sudo -S chmod 644 $TARGET_DIR_FOXXIIE/admin.html && \
   echo '✓ Deployed to foxxiie.com'"

# Deploy to prosecutordefense.com
echo "Step 2: Deploying to $TARGET_DIR_PROSECUT..."
echo "$SUDO_PASS" | ssh -i "$VPS_SSH_KEY" -o StrictHostKeyChecking=no "$VPS_HOST" \
  "sudo -S cp $TARGET_DIR_FOXXIIE/admin.html $TARGET_DIR_PROSECUT/admin.html && \
   sudo -S chown www-data:www-data $TARGET_DIR_PROSECUT/admin.html && \
   sudo -S chmod 644 $TARGET_DIR_PROSECUT/admin.html && \
   echo '✓ Deployed to prosecutordefense.com'"

# Reload nginx
echo "Step 3: Reloading nginx..."
echo "$SUDO_PASS" | ssh -i "$VPS_SSH_KEY" -o StrictHostKeyChecking=no "$VPS_HOST" \
  "sudo -S systemctl reload nginx && \
   echo '✓ Nginx reloaded'"

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                    ✓ DEPLOYMENT COMPLETE                                  ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo "✓ Auth bypass is now live at:"
echo "  https://prosecutordefense.com/admin/"
echo ""
echo "Expected behavior:"
echo "  • Login modal will NOT appear"
echo "  • FAQ admin interface will be immediately visible"
echo "  • No authentication required"
echo ""
