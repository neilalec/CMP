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
http://192.168.1.117:8080
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
FRONTEND_ORIGINS=http://localhost:8080,http://192.168.1.117:8080
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

Make sure `squadjs/config.json` exists locally and the bridge host is set to:

```json
"host": "0.0.0.0"
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
- verify `FRONTEND_ORIGINS` for public URLs
- confirm health is `ok`
- confirm login, queue, lobby, and SquadJS presence all work over LAN first
