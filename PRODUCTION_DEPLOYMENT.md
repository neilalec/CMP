# CMP Production Deployment

This is the production runbook for CMP. It is intentionally practical: set the
required config, start the stack, check health, and know how to recover.

## Required Config

`backend/.env` should use production-safe values:

```env
CMP_DEV_MODE=0
CMP_PASSWORD_AUTH_ENABLED=0
FRONTEND_ORIGINS=https://cmp.zapto.org
BACKEND_PUBLIC_URL=https://cmp.zapto.org/api
DATABASE_PATH=/app/data/app.db
SQUADJS_BRIDGE_URL=http://squadjs:3001
SQUADJS_BRIDGE_TOKEN=<same-token-as-squadjs-config>
SECRET_KEY=<strong-random-secret-32-plus-chars>
JWT_SECRET_KEY=<strong-random-secret-32-plus-chars>
JWT_ACCESS_TOKEN_EXPIRES_HOURS=12
ADMIN_STEAM_IDS=<your-steamid64>
```

Production startup now fails if:

- Password login is enabled while `CMP_DEV_MODE=0`.
- `SECRET_KEY` or `JWT_SECRET_KEY` is weak.
- Public frontend/backend origins are not HTTPS.
- `SQUADJS_BRIDGE_TOKEN` is missing.
- `DATABASE_PATH` is not an absolute persistent path.

`squadjs/config.json` should enable the CMP bridge plugin with the same token:

```json
{
  "plugin": "CmpBridge",
  "enabled": true,
  "host": "0.0.0.0",
  "port": 3001,
  "token": "<same-token-as-backend-env>"
}
```

`frontend` is built by Docker with:

```yaml
VITE_API_BASE_URL: /api
VITE_PASSWORD_AUTH_ENABLED: "0"
```

## Persistence

The production Compose stack persists:

- Backend database: `backend_data:/app/data`
- Caddy certificates: `caddy_data:/data`
- Caddy runtime config: `caddy_config:/config`

Do not delete these volumes unless you intend to wipe production state/certs.

## Start Or Update

```powershell
docker compose up -d --build
docker compose ps
```

Healthy output should show `backend`, `frontend`, and `caddy` as healthy after
their start periods. The backend container healthcheck uses `/health/live`,
which proves the process is alive. Use `/health` for the deeper readiness check
that includes database and SquadJS bridge status.

## Health Checks

From the host:

```powershell
curl.exe http://localhost/health
curl.exe http://localhost/health/live
curl.exe http://localhost/api/health
curl.exe https://cmp.zapto.org/api/health
```

Useful logs:

```powershell
docker compose logs -f backend
docker compose logs -f squadjs
docker compose logs -f caddy
```

Docker log files are rotated by Compose using `10m` max size and `5` files per
service.

## Stop Safely

```powershell
docker compose down
```

This stops containers but keeps named volumes. Do not use `docker compose down -v`
for production unless intentionally wiping persistent data.

## Backup

Create a backup of the backend database and key local config files:

```powershell
.\scripts\backup-production.ps1
```

The script writes a timestamped zip under `.\backups`.

## Restore Outline

1. Stop the stack:

```powershell
docker compose down
```

2. Start only enough to recreate volumes if needed:

```powershell
docker compose up -d backend
```

3. Copy the saved database back:

```powershell
docker compose cp .\backups\<backup>\app.db backend:/app/data/app.db
```

4. Restore `backend/.env`, `squadjs/config.json`, and `deploy/Caddyfile` if
needed, then restart:

```powershell
docker compose up -d --build
```

## Post-Deploy Checklist

- `https://cmp.zapto.org` loads.
- Steam login succeeds.
- `/api/health` returns `ok` or explains degradation.
- Admin page diagnostics load.
- Queue status updates in real time.
- SquadJS bridge shows healthy once RCON is connected.
- Caddy certificates survive `docker compose up -d --build`.
