# MANUAL DEPLOYMENT INSTRUCTIONS

## Current Status
✓ Modified admin.html with auth bypass created and staged  
✓ File uploaded to VPS at: `/tmp/brockler_admin_bypass.html`  
✓ File verified to contain auth bypass code  
⏳ Waiting: Requires VPS sudo password to complete deployment

---

## What Needs to Happen

The modified `admin.html` needs to be moved from `/tmp/brockler_admin_bypass.html` to:
1. `/var/www/foxxiie.com/brocklerlab/admin.html`
2. `/var/www/prosecutordefense.com/brocklerlaw/admin.html`

Then nginx needs to be reloaded to serve the new files.

---

## Option 1: Use the Helper Script (Recommended)

```bash
bash /home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper/COMPLETE_DEPLOYMENT.sh
```

This script will:
- Prompt for your VPS sudo password
- Deploy to both locations
- Set correct permissions
- Reload nginx
- Verify completion

---

## Option 2: Manual SSH Commands

SSH into the VPS and run these commands:

```bash
ssh -i ~/.ssh/vps_dime_key shepov@104.237.9.52
```

Then on the VPS, run:

```bash
# Move to foxxiie.com
sudo mv /tmp/brockler_admin_bypass.html /var/www/foxxiie.com/brocklerlaw/admin.html
sudo chown www-data:www-data /var/www/foxxiie.com/brocklerlaw/admin.html
sudo chmod 644 /var/www/foxxiie.com/brocklerlaw/admin.html

# Copy to prosecutordefense.com
sudo cp /var/www/foxxiie.com/brocklerlaw/admin.html /var/www/prosecutordefense.com/brocklerlaw/admin.html
sudo chown www-data:www-data /var/www/prosecutordefense.com/brocklerlaw/admin.html
sudo chmod 644 /var/www/prosecutordefense.com/brocklerlaw/admin.html

# Reload nginx
sudo systemctl reload nginx

# Verify
echo "✓ Deployment complete"
ls -lh /var/www/prosecutordefense.com/brocklerlaw/admin.html
grep "bypass-token-auth-disabled" /var/www/prosecutordefense.com/brocklerlaw/admin.html && echo "✓ Auth bypass verified"
```

---

## Option 3: Using sudo -S with Password Input

```bash
# Create a temporary password file (be careful!)
SUDO_PASS="your_password_here"

# Deploy
echo "$SUDO_PASS" | ssh -i ~/.ssh/vps_dime_key shepov@104.237.9.52 \
  "sudo -S mv /tmp/brockler_admin_bypass.html /var/www/prosecutordefense.com/brocklerlaw/admin.html && \
   sudo -S chown www-data:www-data /var/www/prosecutordefense.com/brocklerlaw/admin.html && \
   sudo -S chmod 644 /var/www/prosecutordefense.com/brocklerlaw/admin.html && \
   sudo -S systemctl reload nginx"
```

---

## Verification

After deployment, verify it worked:

1. **Check via SSH:**
   ```bash
   ssh -i ~/.ssh/vps_dime_key shepov@104.237.9.52 \
     "ls -lh /var/www/prosecutordefense.com/brocklerlaw/admin.html && \
      grep -c 'bypass-token-auth-disabled' /var/www/prosecutordefense.com/brocklerlaw/admin.html"
   ```

2. **Check via curl:**
   ```bash
   curl -s https://prosecutordefense.com/admin/ | grep -o "bypass-token-auth-disabled" && echo "✓ Auth bypass live"
   ```

3. **Test in browser:**
   - Visit https://prosecutordefense.com/admin/
   - Login modal should NOT appear
   - FAQ admin interface should be immediately visible
   - Refresh cache if still seeing login (Ctrl+Shift+Delete)

---

## File Details

- **Local Staging**: `/home/shepov/dev/scrapers/criminal/cuyahoga_cp_scraper/docs/BROcklerLaw/admin.html`
- **Source Repo**: `/home/shepov/dev/Brockler/brockler-legal-faq/content/index.html`
- **VPS Temp**: `/tmp/brockler_admin_bypass.html` (already uploaded)
- **Live Locations**:
  - `/var/www/foxxiie.com/brocklerlaw/admin.html`
  - `/var/www/prosecutordefense.com/brocklerlaw/admin.html`

---

## Troubleshooting

### "sudo: a password is required"
- You need the VPS sudo password for the user `shepov`
- This is a security feature - no password stored in scripts

### "File permission denied"
- Ensure you're using the correct SSH key: `~/.ssh/vps_dime_key`
- Verify SSH connection works: `ssh -i ~/.ssh/vps_dime_key shepov@104.237.9.52 "whoami"`

### "admin.html not found at expected location"
- Check if nginx config has custom routing
- Verify directory path: `ssh ... "ls -la /var/www/prosecutordefense.com/brocklerlaw/"`

---

## What the Auth Bypass Does

The modified `admin.html`:
1. Initializes `_sessionToken` as dummy value: `"bypass-token-auth-disabled"`
2. Skips the failing `fetch("/api/auth/config")` call (which returns 404)
3. Auto-enables review mode on page load via `setTimeout(() => enableReviewMode(), 200)`
4. Result: Login modal never appears, FAQ interface is immediately accessible

No actual authentication is performed - the backend auth endpoints are unavailable.

---

**Next Steps:**
1. Run the deployment script or manual commands with your VPS sudo password
2. Test at https://prosecutordefense.com/admin/
3. Confirm login modal is gone and FAQ interface is accessible
