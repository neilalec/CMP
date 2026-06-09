# CMP SquadJS Modules

This directory contains CMP-specific Squad server integration code.

`CmpBridge` is mounted as a normal SquadJS plugin from `squad-server/plugins/cmp-bridge.js`.
The plugin starts the HTTP bridge, while these modules keep each server-facing concern separate:

- `routes.js`: HTTP endpoint routing for the backend bridge contract.
- `commands.js`: command execution and recent command diagnostics.
- `scoreboard.js`: CMP-owned round result/scoreboard collection from log events and server snapshots.
- `rcon.js`: RCON reconnect, refresh, and command helpers.
- `layers.js`: server layer payloads and layer listing.
- `hotdrop-layers.js`: CMP-owned workshop layer registry.
- `players.js`: player payload normalization.
- `state.js`: bridge-local runtime state such as latest round result and raw layer status.
- `http.js`: small HTTP request/response helpers.

The Flask backend should continue to own CMP product logic like queues, lobbies,
readiness policy, permissions, and match history. These modules should own only
Squad server facts and commands.

Round scoreboard capture is intentionally best-effort. SquadJS log events can provide
complete winner/loser ticket data for normal finishes, but admin-ended or tied rounds
may only provide partial/inferred data. In those cases CMP marks the result as
`draw_or_unresolved` rather than presenting an inferred winner as a confirmed score.
