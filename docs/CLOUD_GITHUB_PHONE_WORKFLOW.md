# Cloud + GitHub + Phone Workflow

This is the simplest way to build, test, and run your apps without depending on your personal computer.

## 1. Use GitHub as your control plane

- Push all changes to GitHub branches.
- Let GitHub Actions run tests automatically.
- Merge only green pull requests.

CI workflow file:
- [.github/workflows/ci.yml](../.github/workflows/ci.yml)

## 2. Keep production on your VPS

Use your VPS as the always-on runtime environment.

- [docs/CLOUD_VPS_RUNBOOK.md](CLOUD_VPS_RUNBOOK.md)
- [scripts/vps_ops.sh](../scripts/vps_ops.sh)
- [deploy/docker-compose.prod.yml](../deploy/docker-compose.prod.yml)

## 3. Suggested deployment model

- GitHub: source, branches, pull requests, CI.
- VPS: runtime with Docker Compose.
- Cloud storage: backup destination via rclone.

Recommended deploy flow:
1. Push branch to GitHub.
2. Wait for CI to pass.
3. Merge to master.
4. On VPS: run scripts/vps_ops.sh pull.

## 4. iPhone options

There is no full native VS Code on iPhone, but these options work:

1. GitHub Mobile app:
- Review PRs, comments, CI status, merge approved PRs.

2. Browser + GitHub web:
- Quick file edits and workflow dispatch from Safari.

3. SSH app to VPS (Termius or Blink):
- Run deploy, logs, restart, backup commands.

4. Codespaces in browser:
- Possible for light edits, but iPhone UX is limited for heavy coding.

Best practical setup on iPhone:
- GitHub Mobile for code review/merge + SSH app for server operations.

## 5. Free or low-cost storage for backups

- Google Drive via rclone (easy start)
- Backblaze B2 (cheap, durable)
- Cloudflare R2 (S3-compatible)

Use:
- [scripts/backup_data.sh](../scripts/backup_data.sh)
- [scripts/sync_backup_rclone.sh](../scripts/sync_backup_rclone.sh)

## 6. Minimal command set to memorize

Run from repo root on VPS:

- scripts/vps_ops.sh status
- scripts/vps_ops.sh logs api
- scripts/vps_ops.sh pull
- scripts/vps_ops.sh backup
