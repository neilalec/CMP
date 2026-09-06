# Competitive Matchmaking Platform

Competitive Matchmaking Platform is a full-stack web app for organising competitive Squad matches. Players authenticate with Steam, join queue modes, accept a match when enough players are ready, vote through lobby phases and receive server details once the match is ready.

I built this as a larger portfolio project to practise real-time application design, backend state management, deployment hardening and testable service code. It began as a university honours project and has continued as a community tool used for organised competitive matches, with around 50 active users in a typical week. It could potentially develop into a commercial matchmaking service based on demand, it showcases the shape of a production-style web app with persistent state, admin controls and external game-server integration.

## Features

- Steam OpenID authentication with local password auth kept as a development/test fallback.
- Real-time queue, group, lobby and match-acceptance flows using Socket.IO.
- Multiple queue modes with configurable team sizes and map pools.
- Lobby phases for match acceptance, map voting, team assignment, server joining, live play and score/history.
- SquadJS bridge integration for server presence, live-roll checks, RCON automation and server status.
- Admin tools for queue management, lobby recovery, server diagnostics and automation mode control.
- SQLite-backed persistence for users, queue state, lobbies, server registry, audit events and completed match history.
- Elo rating updates for completed matches.
- Docker Compose deployment with Caddy reverse proxy, health checks, log rotation, backup and restore scripts.
- Backend and frontend tests covering queue, lobby, auth, persistence, history, Elo, socket services and UI store behaviour.

## Stack

- Python, Flask, Flask-SocketIO and Eventlet
- SQLite
- Vue 3, Pinia, Vue Router and Vite
- Socket.IO
- Docker Compose, Caddy and Nginx
- Jest and Vue Test Utils
- Pytest
- Git

## Repository Structure

```text
backend/
  app.py, app_core.py       Flask app wiring and core orchestration
  services/                 Auth, queue, bridge, history, Elo, persistence and server services
  sockets/                  Socket.IO event handlers
  state/                    Runtime queue, lobby and group state helpers
  tests/                    Unit and integration tests

frontend/
  src/views/                Main Vue pages
  src/features/             Feature components and composables
  src/stores/               Pinia stores for auth, queue, lobby, group and sockets
  tests/                    Jest unit tests

squadjs/
  cmp/                      CMP bridge helpers
  squad-server/plugins/     SquadJS plugin integration

scripts/                    Local development, smoke test, backup and restore helpers
deploy/                     Caddy configuration
docs/                       Deployment and integration notes
```

## Requirements

For local development:

- Python 3.12 or newer
- Node.js 20.17 or newer for frontend development
- npm

For full stack / server integration:

- Node.js 22 or newer for the bundled SquadJS workspace
- Docker Desktop
- A Squad server and SquadJS setup
- Steam Web API credentials for production display-name lookup

## Local Development

The fastest local route is the helper script:

```powershell
npm run dev:local
```

Manual setup is also possible.

Backend:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-test.txt
Copy-Item .env.example .env
.\venv\Scripts\python.exe app.py
```

Frontend:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
npm run dev
```

The frontend dev server proxies API requests to the backend. Keep real secrets in local `.env` files only.

## Docker

Copy the example environment files and replace placeholders with your own local or server values:

```powershell
Copy-Item .env.example .env
Copy-Item backend\.env.example backend\.env
Copy-Item frontend\.env.example frontend\.env
```

Then start the stack:

```powershell
docker compose up -d --build
```

See [SELF_HOSTING.md](SELF_HOSTING.md) and [PRODUCTION_DEPLOYMENT.md](PRODUCTION_DEPLOYMENT.md) for fuller runbooks.

## Testing

Backend:

```powershell
cd backend
.\venv\Scripts\python.exe -m pytest
```

Frontend:

```powershell
cd frontend
npm test -- --runInBand
```

Production build:

```powershell
cd frontend
npm run build
```

## Security Notes

- Real `.env` files, databases, logs, backups and generated dependency folders are intentionally ignored.
- Production startup rejects weak secrets, insecure public origins and unsafe password-auth settings.
- Admin-only queue and lobby mutation paths are guarded server-side and covered by tests.
- This remains a portfolio project, so a real public launch would need deeper security review, operational monitoring and privacy policy/legal review.

## Portfolio Notes

This project is larger than the small Laravel and PWA projects on my profile. It is useful for discussing real-time systems, state recovery, test coverage, deployment trade-offs, external integrations and how I break a larger app into services, socket handlers and frontend stores.
