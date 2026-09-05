# Self-Hosting Runbook

This runbook is for running the CMP stack from your own desktop over Docker on your local network.

## What This Stack Includes

- `frontend`: built Vue app served by `nginx`
- `backend`: Flask + Socket.IO app
- `squadjs`: SquadJS plus the local bridge service
- `caddy`: reverse proxy exposed on port `8080`

The app entrypoint for devices on your LAN is:

```text
http://<desktop-ip>:8080
```

Examples:

```text
http://192.168.1.50:8080
http://localhost:8080
```

## Important Local Files

These files are runtime configuration and should stay local:

- `backend/.env`
- `frontend/.env`
- `squadjs/config.json`

These are templates and are safe to commit:

- `backend/.env.example`
- `frontend/.env.example`
- `squadjs/config.oasis-template.json`

## Start The Stack

From the repo root:

```powershell
docker compose up -d
```

If you changed source code, Dockerfiles, or build-time frontend config:

```powershell
docker compose up -d --build
```

If you changed only the backend:

```powershell
docker compose up -d --build backend
```

If you changed only the frontend:

```powershell
docker compose up -d --build frontend
```

## Stop The Stack

Stop and remove the containers:

```powershell
docker compose down
```

Stop containers but keep them created:

```powershell
docker compose stop
```

## View Status And Logs

Check container status:

```powershell
docker compose ps
```

Follow all logs:

```powershell
docker compose logs -f
```

Follow the most useful logs:

```powershell
docker compose logs -f backend caddy squadjs
```

## Health Checks

Backend health through the reverse proxy:

```powershell
curl.exe http://localhost:8080/api/health
```

From another device on the LAN:

```powershell
curl.exe http://<desktop-ip>:8080/api/health
```

Healthy response should include:

- `"status":"ok"`
- `"database":{"ok":true,...}`
- `"squadjsBridge":{"ok":true,...}`

Degraded response usually means a dependency is unavailable, most often SquadJS.

## Match Server Details

The Match Ready and Live lobby cards read server connection details from the backend. Configure them in `backend/.env`:

```env
SQUAD_SERVER_NAME=Your Squad Server Name
SQUAD_SERVER_PASSWORD=optional-server-password
SQUAD_SERVER_CONNECT_ADDRESS=optional-ip-or-host:port
```

`SQUAD_SERVER_NAME` can be left blank if the SquadJS bridge can read the server name from RCON. `SQUAD_SERVER_CONNECT_ADDRESS` is optional; when present, the UI renders it as a `steam://connect/...` convenience link, but players can always use the displayed server name and password in the Squad server browser.

## Steam Sign-In

Steam sign-in uses Steam OpenID and does not require a Steam Web API key for basic authentication.
Steam should be the only production login method. Password login is a local development/test fallback only.

The flow is:

1. Frontend opens `/api/auth/steam/start`.
2. Backend redirects the browser to Steam.
3. Steam redirects back to `/api/auth/steam/callback`.
4. Backend verifies the OpenID response with Steam.
5. Backend links or creates a local CMP user by SteamID64.
6. Frontend receives the normal CMP access token and continues into the app.

Important config:

```env
CMP_DEV_MODE=0
CMP_PASSWORD_AUTH_ENABLED=0
FRONTEND_ORIGINS=http://localhost:5173,http://localhost,http://localhost:8080,https://localhost,http://192.168.1.50:8080,https://example.com
SECRET_KEY=<strong-random-secret>
JWT_SECRET_KEY=<strong-random-secret>
JWT_ACCESS_TOKEN_EXPIRES_HOURS=12
```

The frontend origin you use in the browser must be present in `FRONTEND_ORIGINS`, because Steam auth redirects back into that origin after backend verification. Use `http://localhost:5173` for Vite development, or `http://localhost` / `https://localhost` when testing through Caddy.

For local development only, you can enable the username/password test form with:

```env
CMP_DEV_MODE=1
CMP_PASSWORD_AUTH_ENABLED=1
```

and in `frontend/.env`:

```env
VITE_PASSWORD_AUTH_ENABLED=1
```

When `CMP_DEV_MODE=0`, the backend refuses to start if password auth is enabled or if `SECRET_KEY` / `JWT_SECRET_KEY` are weak placeholders.

If you change `backend/.env`, recreate the backend container:

```powershell
docker compose up -d --force-recreate backend
```

## LAN Access Checklist

To access the app from another device:

1. Make sure Docker is running on the desktop.
2. Start the stack with `docker compose up -d`.
3. Confirm Windows firewall allows inbound TCP on port `8080` for your private network.
4. Use the desktop machine's IPv4 address:

```text
http://<desktop-ip>:8080
```

5. Ensure `backend/.env` includes all LAN origins you want to allow in `FRONTEND_ORIGINS`.

Example:

```env
FRONTEND_ORIGINS=http://localhost:8080,http://192.168.1.50:8080
```

If you change `backend/.env`, recreate the backend container:

```powershell
docker compose up -d --force-recreate backend
```

## Common Operations

Recreate everything without rebuilding images:

```powershell
docker compose up -d --force-recreate
```

Rebuild a single service:

```powershell
docker compose build backend
docker compose up -d backend
```

Rebuild the whole stack:

```powershell
docker compose up -d --build
```

## Troubleshooting

### The page loads but login/register fails

Likely causes:

- `FRONTEND_ORIGINS` does not include the LAN URL you are using
- backend container has not been recreated after changing `backend/.env`
- websocket requests are failing through Caddy/backend

Check:

```powershell
docker compose logs -f backend caddy
```

### Health is degraded

Check:

```powershell
curl.exe http://localhost:8080/api/health
```

Likely meanings:

- `database.ok = false`: database path/volume problem
- `squadjsBridge.ok = false`: SquadJS bridge is down or unreachable

### SquadJS bridge unavailable

Check SquadJS logs:

```powershell
docker compose logs -f squadjs
```

Make sure `squadjs/config.json` exists locally and the `CmpBridge` plugin is enabled with the bridge host set to:

```json
{
  "plugin": "CmpBridge",
  "enabled": true,
  "host": "0.0.0.0",
  "port": 3001
}
```

### Code changes do not appear

This Docker setup is production-style, not hot-reload development.

You must rebuild the affected service:

```powershell
docker compose up -d --build <service>
```

## Before Internet Exposure

Before exposing this beyond your LAN:

- rotate sensitive credentials if they may have been exposed
- keep real secrets only in local runtime files
- set `STEAM_WEB_API_KEY` so Steam display names resolve instead of falling back to `steam_########`
- verify `FRONTEND_ORIGINS` for public URLs
- confirm health is `ok`
- confirm login, queue, lobby, and SquadJS presence all work over LAN first
- confirm queue fulfilment pauses while the only match server is in use
- stop and restart the Squad server once to confirm the web app stays online and SquadJS reconnects
- test admin-only lobby controls with a non-admin account and confirm they are rejected server-side
- run `.\scripts\backup-production.ps1` and verify the backup zip before relying on the deployment
