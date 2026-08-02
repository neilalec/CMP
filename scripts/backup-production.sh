#!/usr/bin/env bash
set -euo pipefail

output_dir="${1:-./backups}"
timestamp="$(date +%Y%m%d-%H%M%S)"
backup_root="${output_dir}/cmp-backup-${timestamp}"
container_backup_path="/app/data/app-backup-${timestamp}.db"

mkdir -p "$backup_root"

backup_command="import os, sqlite3; source = os.environ.get('DATABASE_PATH', '/app/data/app.db'); target = os.environ['CMP_BACKUP_TARGET']; source_conn = sqlite3.connect(source); target_conn = sqlite3.connect(target); source_conn.backup(target_conn); target_conn.close(); source_conn.close()"
cleanup_command="import os; path = os.environ['CMP_BACKUP_TARGET']; os.path.exists(path) and os.remove(path)"

cleanup() {
  docker compose exec -T -e "CMP_BACKUP_TARGET=${container_backup_path}" backend python -c "$cleanup_command" >/dev/null 2>&1 || true
}
trap cleanup EXIT

docker compose exec -T -e "CMP_BACKUP_TARGET=${container_backup_path}" backend python -c "$backup_command"
docker compose cp "backend:${container_backup_path}" "${backup_root}/app.db"

cp .env "${backup_root}/root.env" 2>/dev/null || true
cp backend/.env "${backup_root}/backend.env" 2>/dev/null || true
cp squadjs/config.json "${backup_root}/squadjs-config.json" 2>/dev/null || true
cp deploy/Caddyfile "${backup_root}/Caddyfile" 2>/dev/null || true

archive_path="${backup_root}.tar.gz"
tar -czf "$archive_path" -C "$backup_root" .
rm -rf "$backup_root"

echo "Backup created: $archive_path"
