#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPLOY_DIR="$ROOT_DIR/deploy"

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 {up|down|restart|status|logs|pull|backup} [service]"
  exit 1
fi

cmd="$1"
service="${2:-}"

compose() {
  cd "$DEPLOY_DIR"
  docker compose --env-file ../.env -f docker-compose.yml -f docker-compose.prod.yml "$@"
}

case "$cmd" in
  up)
    compose up -d
    ;;
  down)
    compose down
    ;;
  restart)
    if [[ -n "$service" ]]; then
      compose restart "$service"
    else
      compose restart
    fi
    ;;
  status)
    compose ps
    ;;
  logs)
    if [[ -n "$service" ]]; then
      compose logs -f --tail=200 "$service"
    else
      compose logs -f --tail=200
    fi
    ;;
  pull)
    compose pull || true
    compose build
    compose up -d
    ;;
  backup)
    "$ROOT_DIR/scripts/backup_data.sh"
    ;;
  *)
    echo "Unknown command: $cmd"
    echo "Usage: $0 {up|down|restart|status|logs|pull|backup} [service]"
    exit 1
    ;;
esac
