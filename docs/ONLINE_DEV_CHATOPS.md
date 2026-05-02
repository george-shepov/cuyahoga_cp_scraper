# Online Dev + ChatOps Deploy To .52

This setup gives you:

- Online development in GitHub Codespaces
- A chat-style task intake flow through GitHub Issues
- Automatic deploy to `104.237.9.52` after merge to `master`

## 1) Enable Online Development

This repo now includes [.devcontainer/devcontainer.json](../.devcontainer/devcontainer.json), so Codespaces boots with:

- Python 3.11
- Project virtualenv and `requirements.txt`
- Playwright Chromium installed
- Copilot + Copilot Chat extensions

How to use:

1. Open the repository in GitHub.
2. Click `Code` -> `Codespaces` -> `Create codespace on master`.
3. Open Copilot Chat in the Codespace and give tasks in plain language.

## 2) Configure Deploy Secrets

In GitHub repository settings, add these **Actions secrets**:

- `VPS_HOST`: `104.237.9.52`
- `VPS_USER`: your SSH user (example: `shepov`)
- `VPS_SSH_PRIVATE_KEY`: private key text for that user
- `VPS_APP_DIR`: deploy path on VPS (example: `/opt/cuyahoga_cp_scraper`)

## 3) Prepare The VPS Once

SSH to the VPS and make sure these are installed:

```bash
sudo apt-get update
sudo apt-get install -y git docker.io docker-compose-plugin
sudo usermod -aG docker "$USER"
```

Also make sure the VPS user can clone the repository over SSH (`git@github.com:owner/repo.git`).

## 4) Deployment Behavior

Workflow file: [.github/workflows/deploy-vps-52.yml](../.github/workflows/deploy-vps-52.yml)

Trigger:

- Push to `master`
- Manual `workflow_dispatch`

What it does:

1. SSH into VPS.
2. Clone repo if missing.
3. Reset VPS checkout to `origin/master`.
4. Run `docker compose up -d --build` from `deploy/`.

Manual equivalent:

```bash
export VPS_HOST=104.237.9.52
export VPS_USER=shepov
export VPS_APP_DIR=/opt/cuyahoga_cp_scraper
bash scripts/deploy_vps_52.sh
```

## 5) Chat Window For Tasks

Use the issue template:

- [.github/ISSUE_TEMPLATE/task-to-deploy.yml](../.github/ISSUE_TEMPLATE/task-to-deploy.yml)

Recommended loop:

1. Create issue with the template and describe the task conversationally.
2. Implement in Codespaces using Copilot Chat.
3. Open PR and merge to `master`.
4. GitHub Actions deploys to `.52`.

## 6) Optional Tight Loop (No PR)

If you want immediate deploy from chat-driven changes:

1. Work in Codespaces on `master` directly.
2. Commit + push.
3. Deployment runs automatically.

Use this only if you accept skipping PR review.
