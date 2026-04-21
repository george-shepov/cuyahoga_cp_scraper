# BrocklerLaw Deploy

Safe deployment scripts for foxxiie.com/brocklerlaw with **SSL, HTTP/HTTPS support, and automated publish functionality**.

## Security

**⚠️ IMPORTANT:** This is an opensource repository. Credentials are **NEVER** stored in files—only in environment variables on your local machine.

### Files in this directory

- `deploy.sh` - Main deployment script (no credentials hardcoded)
- `save_api.py` - Python HTTP API for publishing index.html updates
- `brocklerlaw-save.service` - systemd service unit
- `nginx-foxxiie.conf` - Nginx configuration (HTTP + HTTPS)
- `.gitignore` - Prevents credential files from being committed

## Usage

### Prerequisites

1. SSH key-based access to VPS (no password needed for SSH)
2. User with `sudo` privileges on the VPS (passwordless preferred, or you can provide password)
3. Nginx already installed on VPS
4. Port 80 reachable for Let's Encrypt certificate

### Deploy

#### Option A: Passwordless sudo (recommended)

```bash
# Set credentials (local machine only, never commit)
export VPS_HOST="shepov@your-vps-host.com"
export VPS_SSH_KEY="~/.ssh/vps_dime_key"

# Run deploy
bash docs/BROcklerLaw/deploy/deploy.sh
```

#### Option B: With sudo password

```bash
export VPS_HOST="shepov@your-vps-host.com"
export VPS_SSH_KEY="~/.ssh/vps_dime_key"
export VPS_SUDO_PASS="your_sudo_password"

# Run deploy (no sudo prefix needed)
bash docs/BROcklerLaw/deploy/deploy.sh
```

### Why NOT `sudo bash deploy.sh`?

Using `sudo bash deploy.sh` locally won't work because:
1. `sudo` strips environment variables by default
2. The script itself doesn't need `sudo` — it uses SSH to run `sudo` on the remote VPS
3. Deploy commands execute on the remote server, not locally

The script will:
1. Upload `index.html` and `admin.html`
2. Install the save API (`save_api.py`)
3. Create systemd service for the API
4. Install Nginx config (both HTTP and HTTPS)
5. Obtain Let's Encrypt SSL certificate
6. Enable both HTTP and HTTPS (no forced redirect)

### Admin Page

After deploy, access the admin at:
- `https://foxxiie.com/brocklerlaw/admin.html`

**Login credentials:**
- Username: `Aaron`
- Password: set via `BROCKLER_API_TOKEN` environment variable on the server (see `/etc/brocklerlaw-save/env`)


### Publishing Updates

The admin page has two buttons:

1. **Download Public Page** - Downloads the current state as `index.html`
2. **Publish to Live Site** - Publishes directly to the VPS
   - Backs up the old `index.html` with a timestamp
   - Saves new `index.html` in place
   - Shows backup filename in status

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Admin Browser (admin.html)                             │
│  - Review/edit FAQ questions                            │
│  - Approve/hide questions                               │
│  - Download or Publish to live site                     │
└──────────────────────┬──────────────────────────────────┘
                       │
         ┌─────────────┴──────────────┐
         │                            │
    Download                   POST /brocklerlaw/save
    (browser)                  (HTTPS to VPS)
         │                            │
         ▼                            ▼
      .html file            ┌────────────────────┐
     (local save)           │  Nginx (443 → 8765)│
                            └────────────────────┘
                                     │
                                     ▼
                            ┌────────────────────┐
                            │ save_api.py (8765) │
                            │ - Backup index     │
                            │ - Write new index  │
                            └────────────────────┘
                                     │
                                     ▼
                         /var/www/foxxiie.com/
                             brocklerlaw/
                              index.html
                          (+ index_YYYYMMDD_HHMMSS.html)
```

## File Structure

```
docs/BROcklerLaw/
├── index.html              # Public-facing page (approved Q&A only)
├── admin.html              # Admin review/publish interface
└── deploy/
    ├── deploy.sh           # Deployment script
    ├── save_api.py         # HTTP endpoint for publishing
    ├── brocklerlaw-save.service  # systemd unit
    ├── nginx-foxxiie.conf        # Nginx config
    ├── .gitignore                # Prevent credential leaks
    └── README.md                 # This file
```

## SSL/HTTPS

- **Certificate**: Let's Encrypt (auto-renewed)
- **HTTP**: Accessible on port 80
- **HTTPS**: Accessible on port 443
- **Forced redirect**: None (both HTTP and HTTPS work)

To customize, edit `nginx-foxxiie.conf` and re-run deploy.

## Troubleshooting

### Certificate renewal

```bash
ssh -i ~/.ssh/vps_dime_key $VPS_HOST \
  "sudo certbot renew --dry-run"
```

### Check service status

```bash
ssh -i ~/.ssh/vps_dime_key $VPS_HOST \
  "sudo systemctl status brocklerlaw-save"
```

### View API logs

```bash
ssh -i ~/.ssh/vps_dime_key $VPS_HOST \
  "sudo journalctl -u brocklerlaw-save -f"
```

### Manual publish (if API fails)

```bash
# Generate HTML via admin page download
# Then manually upload to VPS
scp -i ~/.ssh/vps_dime_key index.html \
  $VPS_HOST:/var/www/foxxiie.com/brocklerlaw/
```
