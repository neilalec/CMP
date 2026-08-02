#!/usr/bin/env bash
set -euo pipefail

backup_archive="${1:-}"
restore_config="${2:-}"

if [[ -z "$backup_archive" ]]; then
  echo "Usage: ./scripts/restore-production.sh <backup.tar.gz> [--restore-config]" >&2
  exit 2
fi

if [[ ! -f "$backup_archive" ]]; then
  echo "Backup archive not found: $backup_archive" >&2
  exit 2
fi

timestamp="$(date +%Y%m%d-%H%M%S)"
restore_root="$(mktemp -d "/tmp/cmp-restore-${timestamp}.XXXXXX")"

cleanup() {
  rm -rf "$restore_root"
}
trap cleanup EXIT

tar -xzf "$backup_archive" -C "$restore_root"

if [[ ! -f "${restore_root}/app.db" ]]; then
  echo "Backup does not contain app.db" >&2
  exit 2
fi

echo "Stopping CMP stack..."
docker compose down

echo "Creating backend container and data volume..."
docker compose create backend >/dev/null

echo "Restoring backend database..."
docker compose cp "${restore_root}/app.db" backend:/app/data/app.db

if [[ "$restore_config" == "--restore-config" ]]; then
  cp "${restore_root}/root.env" .env 2>/dev/null || true
  cp "${restore_root}/backend.env" backend/.env 2>/dev/null || true
  cp "${restore_root}/squadjs-config.json" squadjs/config.json 2>/dev/null || true
  cp "${restore_root}/Caddyfile" deploy/Caddyfile 2>/dev/null || true
fi

echo "Starting CMP stack..."
docker compose up -d --build
echo "Restore complete. Check status with: docker compose ps"
