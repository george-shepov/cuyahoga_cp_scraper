# Cloud VPS Runbook

This guide makes the scraper + API stack runnable and maintainable without your local computer.

## 1) Recommended cloud setup

- One Linux VPS (2-4 vCPU, 8-16GB RAM, 100GB+ disk)
- Docker + Docker Compose
- Optional domain + reverse proxy
- Automated backups pushed off-server

## 2) First-time VPS bootstrap

```bash
sudo apt update
sudo apt install -y docker.io docker-compose-plugin git curl
sudo usermod -aG docker "$USER"
newgrp docker

git clone <YOUR_REPO_URL>
cd cuyahoga_cp_scraper
cp .env.example .env
# edit .env and set real secrets
```

Set script permissions:

```bash
chmod +x scripts/vps_ops.sh scripts/backup_data.sh scripts/sync_backup_rclone.sh
```

## 3) Start in production mode

```bash
scripts/vps_ops.sh up
scripts/vps_ops.sh status
scripts/vps_ops.sh logs api
```

API docs should be available at port 8000 on the VPS (or behind your proxy) at `/docs`.

## 4) Mobile-friendly operations

From your phone SSH app, you only need these commands:

```bash
scripts/vps_ops.sh status
scripts/vps_ops.sh logs api
scripts/vps_ops.sh restart api
scripts/vps_ops.sh backup
```

## 5) Backups

Create a backup snapshot:

```bash
scripts/backup_data.sh
```

This saves timestamped backup folders under `backups/` containing:
- compressed `out/`
- compressed `logs/`
- PostgreSQL SQL dump
- MongoDB archive dump

## 6) Cloud storage sync options

### Option A: Google Drive via rclone

```bash
curl https://rclone.org/install.sh | sudo bash
rclone config
# create remote named "gdrive"
scripts/sync_backup_rclone.sh
```

### Option B: Backblaze B2 (cheap object storage)

Use rclone remote like `b2:<bucket-name>` and set:

```bash
export RCLONE_REMOTE=b2:cuyahoga-backups
scripts/sync_backup_rclone.sh
```

### Option C: Cloudflare R2 / Wasabi / S3-compatible

Configure via rclone and set `RCLONE_REMOTE` accordingly.

## 7) Cron jobs for resilience

Run `crontab -e` and add:

```cron
# Daily local backup at 2:30 AM
30 2 * * * cd /home/<user>/cuyahoga_cp_scraper && ./scripts/backup_data.sh >> logs/backup.log 2>&1

# Daily cloud sync at 2:45 AM
45 2 * * * cd /home/<user>/cuyahoga_cp_scraper && ./scripts/sync_backup_rclone.sh >> logs/backup-sync.log 2>&1
```

## 8) Security checklist

- Keep `.env` out of git
- Use strong DB passwords
- Avoid exposing DB ports publicly
- Restrict VPS firewall to SSH + API/proxy ports
- Use HTTPS (Caddy/Nginx + Let's Encrypt)

## 9) Disaster recovery quick restore

1. Provision a new VPS
2. Clone repo + copy `.env`
3. Start stack: `scripts/vps_ops.sh up`
4. Restore dumps from latest `backups/<timestamp>/`
5. Re-run cloud sync setup
