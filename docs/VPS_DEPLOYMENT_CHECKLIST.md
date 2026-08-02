# VPS Deployment Checklist

Use this as the practical checklist before letting players use CMP.

## 1. VPS And DNS

- Buy/start the VPS.
- Point `squadcm.duckdns.org` to the VPS public IPv4 address in DuckDNS.
- Wait for DNS to resolve to the VPS:

```bash
dig +short squadcm.duckdns.org
```

## 2. VPS Security Baseline

Run these before exposing the app:

```bash
sudo apt update
sudo apt upgrade -y
sudo apt install -y ufw fail2ban git curl
sudo ufw allow OpenSSH
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo systemctl enable --now fail2ban
```

Recommended SSH hardening:

- Add your SSH public key to `~/.ssh/authorized_keys`.
- Confirm key login works in a second terminal before changing SSH settings.
- Disable password SSH login after key login is proven.
- If your home IP is stable, restrict port `22` to your IP.

## 3. Docker

Install Docker Engine and the Compose plugin, then confirm:

```bash
docker --version
docker compose version
```

Add your user to the Docker group if desired:

```bash
sudo usermod -aG docker "$USER"
```

Log out and back in after changing groups.

## 4. App Files

Clone or copy the repo onto the VPS:

```bash
git clone <your-repo-url> cmp
cd cmp
```

Create production env files:

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp squadjs/config.oasis-template.json squadjs/config.json
```

Set `.env`:

```env
CMP_PUBLIC_HOST=squadcm.duckdns.org
CMP_BACKEND_PUBLIC_URL=https://squadcm.duckdns.org/api
VITE_PASSWORD_AUTH_ENABLED=0
```

Set `backend/.env`:

```env
CMP_DEV_MODE=0
CMP_PASSWORD_AUTH_ENABLED=0
FRONTEND_ORIGINS=https://squadcm.duckdns.org
BACKEND_PUBLIC_URL=https://squadcm.duckdns.org/api
DATABASE_PATH=/app/data/app.db
SQUADJS_BRIDGE_URL=http://squadjs:3001
SQUADJS_BRIDGE_TOKEN=<strong-random-token>
STEAM_WEB_API_KEY=<steam-web-api-key>
SECRET_KEY=<strong-random-secret-32-plus-chars>
JWT_SECRET_KEY=<strong-random-secret-32-plus-chars>
ADMIN_STEAM_IDS=<neil-steamid64>
AUTOMATION_MODE=monitor
ADMIN_TEAM_ENFORCEMENT_BYPASS_ENABLED=1
```

Set the same bridge token in `squadjs/config.json`.

Start with `AUTOMATION_MODE=monitor` for first deployment. That lets the app read server state while blocking RCON write commands until you deliberately turn automation on in Admin.

## 5. Steam / Domain Checks

- Make sure Steam sign-in redirects back to `https://squadcm.duckdns.org`.
- Make sure `FRONTEND_ORIGINS` contains only the production HTTPS origin unless you are also testing another known origin.
- Make sure DuckDNS points to the VPS, not your desktop.

## 6. First Start

```bash
docker compose up -d --build
docker compose ps
```

Expected:

- `backend` running and healthy.
- `frontend` running and healthy.
- `caddy` running and healthy.
- `squadjs` running.

Check logs:

```bash
docker compose logs -f backend caddy squadjs
```

## 7. Smoke Test

```bash
chmod +x scripts/*.sh
./scripts/smoke-production.sh https://squadcm.duckdns.org
```

For strict readiness:

```bash
REQUIRE_READY=1 ./scripts/smoke-production.sh https://squadcm.duckdns.org
```

## 8. Manual App Checks

- Open `https://squadcm.duckdns.org`.
- Hard refresh.
- Steam login succeeds.
- Admin page opens for Neil.
- Admin diagnostics load.
- Automation mode starts as `Monitor Only`.
- Bridge/server health is visible.
- Queue status updates in real time.
- Create or seed a test lobby.
- Confirm lobby delete from Admin releases the lobby/server.
- Turn automation `On` only when ready to allow RCON writes.

## 9. Backup Before Users

Run a real backup before opening access:

```bash
./scripts/backup-production.sh
tar -tzf backups/cmp-backup-*.tar.gz | sort
```

The backup should include:

- `app.db`
- `backend.env`
- `root.env`
- `squadjs-config.json`
- `Caddyfile`

## 10. Recovery Commands

Pause automation from Admin first if the site is reachable.

If the app needs a restart:

```bash
docker compose restart backend squadjs
```

If a deploy goes wrong:

```bash
docker compose logs --tail=200 backend squadjs caddy
docker compose down
docker compose up -d --build
```

Restore from a Linux backup:

```bash
./scripts/restore-production.sh backups/<backup>.tar.gz
```

Restore database plus runtime config:

```bash
./scripts/restore-production.sh backups/<backup>.tar.gz --restore-config
```

## 11. Open To Players

Only open access when:

- Smoke test passes.
- Backup has been created and inspected.
- Steam login works.
- Admin diagnostics work.
- Automation pause/monitor/on controls work.
- Neil/admin can delete a stuck lobby.
- At least one full test match has reached Results.
