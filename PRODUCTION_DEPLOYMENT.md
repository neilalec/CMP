# CMP Production Deployment

This is the production runbook for CMP. It is intentionally practical: set the
required config, start the stack, check health, and know how to recover.

## Required Config

Copy the root Compose template and set the public hostname used by Caddy:

```powershell
Copy-Item .env.example .env
```

```env
CMP_PUBLIC_HOST=example.com
CMP_BACKEND_PUBLIC_URL=https://example.com/api
VITE_PASSWORD_AUTH_ENABLED=0
```

If you need to swap domains later, set both values to the new HTTPS host:

```env
CMP_PUBLIC_HOST=temporary.example.com
CMP_BACKEND_PUBLIC_URL=https://temporary.example.com/api
```

`backend/.env` should use production-safe values:

```env
CMP_DEV_MODE=0
CMP_PASSWORD_AUTH_ENABLED=0
FRONTEND_ORIGINS=https://example.com
BACKEND_PUBLIC_URL=https://example.com/api
DATABASE_PATH=/app/data/app.db
SQUADJS_BRIDGE_URL=http://squadjs:3001
SQUADJS_BRIDGE_TOKEN=<same-token-as-squadjs-config>
STEAM_WEB_API_KEY=<steam-web-api-key>
SECRET_KEY=<strong-random-secret-32-plus-chars>
JWT_SECRET_KEY=<strong-random-secret-32-plus-chars>
JWT_ACCESS_TOKEN_EXPIRES_HOURS=12
LOBBY_DISCONNECT_GRACE_SECONDS=600
ADMIN_STEAM_IDS=<your-steamid64>
```

When using a temporary hostname, change `FRONTEND_ORIGINS` and
`BACKEND_PUBLIC_URL` in `backend/.env` to match it. Docker Compose also injects
`CMP_BACKEND_PUBLIC_URL` into the backend container, so keep the root `.env` and
`backend/.env` aligned.

Production startup now fails if:

- Password login is enabled while `CMP_DEV_MODE=0`.
- `SECRET_KEY` or `JWT_SECRET_KEY` is weak.
- Public frontend/backend origins are not HTTPS.
- `SQUADJS_BRIDGE_TOKEN` is missing.
- `STEAM_WEB_API_KEY` is missing.
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
VITE_PASSWORD_AUTH_ENABLED: ${VITE_PASSWORD_AUTH_ENABLED:-0}
```

Queue seed/clear tools and lobby delete/recovery controls are permanently
available to admin profiles only. Keep `ADMIN_STEAM_IDS` set to trusted admin
SteamID64 values in `backend/.env`; non-admin users cannot see or call those
actions.

## Persistence

The production Compose stack persists:

- Backend database: `backend_data:/app/data`
- Caddy certificates: `caddy_data:/data`
- Caddy runtime config: `caddy_config:/config`

The backend database contains users, Steam/profile data, queue entries, active
groups, active lobby snapshots, match history, lobby audit events, server
registry records, server health checks, and server allocations. Socket
connections themselves are not persisted; browsers reconnect and recover their
active lobby from the restored lobby snapshot.

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
curl.exe https://<public-host>/api/health
```

Useful logs:

```powershell
docker compose logs -f backend
docker compose logs -f squadjs
docker compose logs -f caddy
```

Docker log files are rotated by Compose using `10m` max size and `5` files per
service.

## Admin Monitoring

The Admin page diagnostics panel is the first place to check during early live
matches. It shows:

- Backend/database and SquadJS bridge health.
- Current automation mode and whether RCON writes are enabled.
- Active lobbies, phase, selected layer, live-roll status, and live start time.
- Recent lobby audit events, including roll failures, end-match failures, and
  enforcement warnings.
- Server registry health and latest bridge/server discovery payload.

Use the automation mode buttons before taking manual control of a match:

- `On`: normal automation.
- `Monitor Only`: keep reading server state, but block RCON writes.
- `Off`: pause live automation so admins can run the match manually.

Configured admin Steam IDs bypass lobby/team enforcement so admins can police early
matches from inside the Squad server.

## Player Disconnects

If a player disconnects from the web app, they can rejoin the same lobby during
the disconnect grace period. The production default is:

```env
LOBBY_DISCONNECT_GRACE_SECONDS=600
```

After that grace period, disconnected players are removed from pre-live lobbies
so the slot can reopen for someone else. Live and score lobbies keep their
original roster so match history and admin recovery stay predictable.

## Smoke Test

Run the smoke script after each production update:

```powershell
.\scripts\smoke-production.ps1
```

The script checks the public frontend, public backend health aliases, local
Caddy health, Compose service state, and container restart counts. It reports
backend readiness as a warning rather than a failure when the site is alive but
SquadJS/the game server is degraded. To require full readiness:

```powershell
.\scripts\smoke-production.ps1 -RequireReady
```

Steam login, live socket updates, admin page access, and server-info visibility
still need a quick manual browser check because they depend on your Steam/admin
session.

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

The script writes a timestamped zip under `.\backups`. It uses SQLite's online
backup API inside the backend container so the DB copy is consistent while the
app is running.

## Restore Outline

To restore only the database from a backup zip:

```powershell
.\scripts\restore-production.ps1 -BackupZip .\backups\<backup>.zip
```

To restore the database and saved runtime config files:

```powershell
.\scripts\restore-production.ps1 -BackupZip .\backups\<backup>.zip -RestoreConfig
```

The restore script stops the stack, recreates the backend container/data volume,
copies `app.db` back into `/app/data/app.db`, then starts the full stack again.

Manual restore equivalent:

```powershell
docker compose down
docker compose create backend
docker compose cp .\backups\<extracted-backup>\app.db backend:/app/data/app.db
docker compose up -d --build
```

## Post-Deploy Checklist

- `.\scripts\smoke-production.ps1` passes or only warns about an expected server/bridge outage.
- `https://example.com` loads.
- Steam redirects back to `https://example.com`.
- Steam login succeeds.
- `/api/health` returns `ok` or explains degradation.
- Admin page diagnostics load.
- Queue status updates in real time.
- When a match server is in use, queue fulfilment is paused and the queue UI explains why.
- SquadJS bridge shows healthy once RCON is connected.
- Caddy certificates survive `docker compose up -d --build`.

## Pre-Deploy Failure Drill

Run this on staging before opening the app to real users:

1. Fill a queue while no lobby is active and confirm match acceptance starts.
2. Fill another queue while one lobby owns the only server and confirm no second match starts.
3. Stop the Squad game server and confirm the web app stays online while `/api/health` reports bridge/server degradation.
4. Restart the Squad game server and confirm SquadJS reconnects without taking down backend/frontend.
5. Stop only the `squadjs` container and confirm queue/lobby pages still load with degraded server status.
6. Refresh a browser during queue, match acceptance, map vote, join server, live, and score phases.
7. Log in from the same Steam account in a second browser and confirm active lobby/queue state syncs.
8. Join the Squad server with a SteamID not in the active lobby and confirm the player is kicked.
9. Use admin phase forward/back/delete controls and confirm non-admin users cannot perform the same actions.
10. End a round by tickets, by timer, and by `AdminEndMatch` draw; confirm the lobby reaches `SCORE`.
11. Run `.\scripts\backup-production.ps1`, inspect the zip, and confirm it contains `app.db` and runtime config.
