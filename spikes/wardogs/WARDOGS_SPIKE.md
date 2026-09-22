# WARDOGS / WDRCON feasibility spike

Research date: 2026-09-22. Scope: this isolated directory only. No CMP or SquadJS modules were changed. No genuine WARDOGS server, credentials, or game clients were available for this spike.

## Evidence and sources

- [Official WDRCON console](http://rcon.wardogs.com/) and its [HTTP client JavaScript](http://rcon.wardogs.com/js/api.js), [in-browser mock](http://rcon.wardogs.com/js/mock-server.js), [mock data](http://rcon.wardogs.com/js/test-data.js), and [reference ServerSettings.ini](http://rcon.wardogs.com/ServerSettings.ini), fetched 2026-09-22. The official mock is a JavaScript client inside the console, **not** an HTTP WDRCON listener.
- [Warcon reverse-engineered API notes](https://github.com/warcon-app/warcon/blob/309a188c5468ce3363e16cf9ab22f93b0003a32a/docs/wardogs-api.md), pinned to the main commit inspected on 2026-09-22. This independent project reports direct observations on live builds CL-499480 and CL-501228. Its [README](https://github.com/warcon-app/warcon/blob/309a188c5468ce3363e16cf9ab22f93b0003a32a/README.md) describes its own demo and polling architecture.
- This directory's `mock_server.py` is a small **synthetic HTTP fixture** derived from the public shapes above. It proves only that `probe.py` sends and parses those shapes. It does not independently validate the game protocol or the behavior of a real server. The official console's mock was also run directly in Node against its published test data; Warcon's demo was inspected as a reference but not run. Neither external demo is an HTTP WDRCON endpoint usable by this probe without a separate bridge.

The status labels in this report refer to **verification performed by this CMP spike**. Warcon's live-server observations are valuable third-party evidence, explicitly attributed below, but are not first-hand real-server verification by CMP.

## Running the isolated tools

Python 3.10+ standard library only. Set a fresh local test password in the process environment; there is no credential in the repository.

```powershell
$env:WDRCON_PASSWORD = '<local-test-secret>'
$env:WDRCON_MOCK_PORT = '17776'
python spikes/wardogs/mock_server.py
```

In another terminal:

```powershell
$env:WDRCON_PASSWORD = '<same-local-test-secret>'
$env:WDRCON_URL = 'http://127.0.0.1:17776'
python spikes/wardogs/probe.py snapshot
python spikes/wardogs/probe.py watch --samples 3 --interval 2
python spikes/wardogs/probe.py action assign --steam-id 76561198000000001 --faction Lonestar --confirm-mutation
python spikes/wardogs/probe.py action map --map Europe --confirm-mutation
python spikes/wardogs/probe.py action end --confirm-mutation
```

Set `WDRCON_URL` to a reachable real-server origin, or `WDRCON_HOST` and `WDRCON_PORT` (default port 7776), without changing the client. `WDRCON_TIMEOUT` sets the request timeout in seconds. Standard HTTPS certificate verification remains enabled. `action` requires `--confirm-mutation` and checks the advertised route first. Its `{message}` response means the request was accepted; inspect subsequent status and player reads to learn whether the effect occurred. `watch` reports deltas, never a definitive match-start/end event. The mock's `WDRCON_MOCK_VARIANT=live-like` default omits `matchSeconds` and `scoreCap`; `full` includes them. Both are synthetic.

Run the transport tests with `python -m unittest discover -s spikes/wardogs -p 'test_*.py' -v`. The fixture uses an ephemeral loopback port and a generated test secret.

Direct exercise of the **official in-browser mock** returned a 13-player synthetic roster: 12 rows had Steam IDs and one deliberately unlinked player was labelled `no platform id`. It accepted a faction change and reported that the mock player was killed to respawn on the new faction. Changing map to Ozeti immediately changed the displayed map, reset the displayed match length to `0:00:00`, and reset the three displayed scores; its client-side text still describes a match-end screen before travel. It supplied numeric `matchSeconds` and `scoreCap=100`. This independently confirms the console mock's **high-level client behavior**, not the raw HTTP transport or a live server. Its immediate map change directly differs from Warcon's reported live delayed travel, and its timing fields differ from the reported live status. The local HTTP fixture deliberately queues map change to exercise the more cautious observation flow.

An optional push capture endpoint is `feed_receiver.py`. Set `WD_FEED_TOKEN` and run it behind a reachable HTTPS reverse proxy (or on a private test network); by default it listens on `127.0.0.1:18080`. It accepts authenticated `POST /api/ingest/events` and prints raw batches as JSON lines. Kill batches include player names and Steam IDs, so store its output accordingly. This receiver has **not** received a real WARDOGS post.

## Authentication, network and version negotiation

WDRCON is an HTTP/1.1 JSON API under `/v1`. Every request, including reads and `GET /v1/capabilities`, uses `Authorization: Bearer <RCON password>`. The official reference ini defines `[/Script/WDRCON.WDRCONSettings]`: `bEnabled`, `BindAddress`, `Port`, `Password`, `PasswordHash`. The listener is off by default. Its documented default port is 7776, although the published sample ini explicitly sets `Port=1031`; use the **actual configured/host-provided port**. A blank plaintext password generates a boot-time secret at `Saved/RCON/ADMIN-PASSWORD.txt`; `PasswordHash` takes precedence over `Password`. The hash can be made with `WardogsServer -GenerateRCONHash=<pw>`. RCON has one powerful password, not separate read/write roles. Do not put it in a URL or logs.

The reference ini says loopback allows plaintext `Password` while a non-loopback bind needs TLS plus `PasswordHash`. Warcon reports that actual hosts may instead expose plain HTTP behind a reverse proxy or firewall. Treat the host's real listener behavior as a configuration fact to check, not a universal guarantee. For a remote probe, arrange a provider-approved HTTPS endpoint, tunnel/private network, or same-host loopback access. Allow inbound TCP to the configured WDRCON port (or to the TLS proxy port), restrict it to the probe host, and verify routing/firewall and certificate trust. The game server needs its separate game ports for players; those are provider-specific and not specified by these RCON sources. Browser `AllowedOrigins` affects direct browser use; this Python probe is server-side and does not rely on CORS.

`GET /v1/capabilities` returns an object shaped like:

```json
{"apiVersion":1,"build":"++Wardogs+Live-CL-501228","auth":{"scheme":"bearer","header":"Authorization"},"limits":{"maxBodyBytes":65536,"maxRequestsPerMinutePerIp":600},"config":{"writable":true,"document":"/v1/config"},"routes":["GET /v1/status","PATCH /v1/players/{id}"]}
```

The values above are **illustrative** from Warcon's reported live observations, not this spike's captured real response. Query the actual server before using a route. The probe gates mutations by the route list and accepts `{id}` or `{steamId}` for the player placeholder. `apiVersion`, `build`, `routes`, `limits`, and `config` are the negotiation surface. Do not infer a route from `apiVersion=1` alone. CL-499480 reportedly advertised 28 routes; CL-501228 had 29, adding `GET /v1/server-id`. Both omitted live rotation edit routes, live settings, reserved-slot writes, and `PUT /v1/sponsor` that appear in console/demo surfaces. `PATCH /v1/players/{id}` should be feature-detected. The spike has no hard-coded assumption that any optional route exists.

Warcon reports 600 requests/minute per client IP and 65,536 request-body bytes on CL-499480. A real server may report other limits. A `429` has `Retry-After` on newer builds; a production poller would need to back off and coordinate traffic from other clients and proxies sharing an IP. This probe records the header in errors but does not automatically retry, which keeps test outcomes visible.

## Relevant request and response models

The official console and Warcon notes describe these routes. Unless stated otherwise, request bodies are JSON; mutation success is generally `{ "message": "..." }`, **not** proof of completed in-game state change. Non-2xx usually returns `{ "error": { "code": "...", "message": "..." } }`. `401` means failed/missing auth; `404 not_found` can mean a route is absent, while item-specific 404s have different codes; `405` is wrong method; `429` is rate limiting. The synthetic fixture directly exercised 401 and route-404 parsing only.

| Operation | Request | Response / interpretation |
| --- | --- | --- |
| Discover | `GET /v1/capabilities` | `apiVersion`, `build`, auth, limits, config and advertised route strings. |
| Status and scores | `GET /v1/status` | `serverName`, `map`, `experiences[]`, `lighting`, `alternator`, `scoreTick:{current,min,max}`, `players:{current,max}`, `factionScores:[{name,colorHex,score}]`, `rotation:{nowIndex,nextIndex}`. `scoreCap` and `matchSeconds` exist in mocks but were **absent** in Warcon's CL-499480/CL-501228 live captures. |
| Players | `GET /v1/players` | `{players:[{name,steamId,faction,kills,deaths,cash,pingMs}],count}`. Steam IDs are strings. Poll differences can detect observed joins/leaves and faction changes, subject to missed transitions. |
| Map catalog | `GET /v1/catalog/maps`, optionally map experiences/alternators | Maps have `{id,displayName}`; choose valid IDs and compatible experience/lighting/alternator values before a map command. |
| Rotation | `GET /v1/rotation` | `{enabled,mode,entries:[{index,map,experiences,lighting,zoneAlternator,status,denied}]}`. Live rotation write routes are absent on the reported builds; document apply can edit next rotation where writable. |
| Queue map override | `POST /v1/match/map` with `{map,experiences?,lighting?,zoneAlternator?}` | `{message}`. Warcon says travel occurs after the match-end screen finishes, so do not expect an immediate `status.map` change. |
| Assign faction | `PATCH /v1/players/{steamId}` with `{faction:"Valkyra"}` | `{message}`. Optional route. The console subsequently calls `POST /v1/players/{steamId}/kill` to respawn on the new side; that second action can fail when no living character exists. This probe does **not** automatically kill a player. |
| Restart match | `POST /v1/match/restart` with no body | `{message}`. Warcon says the current map reloads and rotation pointer stays put. A same-map restart may be invisible from live status if the clock is absent. |
| End match | `POST /v1/match/end` with no body | `{message}`. Warcon says rotation advances, or current map reloads if rotation is off. There is no documented synchronous completion marker. |
| Config | `GET /v1/config`, `POST /v1/config/validate`, `PUT /v1/config?force=true&fullApply=true` | `GET` returns revision, writable flag, raw ini text, section metadata, warnings. Validate/PUT use `text/plain`; PUT uses `If-Match: "<revision>"`, and `412` indicates a revision conflict. Apply outcomes include `applied`, `next-match`, `next-restart`, `pending`. **Not implemented in this spike** to avoid broad config writes. |

The reference ini exposes `MinimumRequiredPlayers` under `[MatchState.PreMatch.WaitingForPlayers.PlayerCount]` and map rotation under `[/Script/WDGame.WDServerMapRotationSettings]`. It does not demonstrate an API route that emits authoritative match lifecycle events or a winner. `GET /v1/health` can report listener/server uptime on reported live builds, but uptime is not a match clock. `GET /v1/server-id` on CL-501228 is a join code, not a match ID.

## Push delivery and match-state limits

Warcon reports a real `WDServerFeed` push mechanism in CL-499480/CL-501228. At startup, `[WDServerFeed] Url=<base>` and `Token=<secret>` cause the game process to `POST` batches to **`<base>/api/ingest/events`** with `Authorization: Bearer <Token>`. The suffix is appended by the game, so do not include it in `Url`. A reported batch is `{serverId,serverName,events:[{eventId,type:"killed",eventTime,matchId,mapName,killerSteamId?,victimSteamId,...}]}`. Warcon captured kill events roughly every two seconds when kills occurred. It observed only `killed`; no connection, score, phase, start, end, or winner events are established. Factions are absent from these events. Its captured `matchId` did **not** change across a map change, and `eventTime` reset; neither is an authoritative match boundary. Delivery, retry and buffering after receiver outage remain unknown.

Polling `status` and `players` can show score changes, currently connected Steam IDs/factions, map changes, and candidate restarts from score or clock resets. A new round on the **same map** can look identical to the prior round when `matchSeconds` is absent. A map change can be delayed until after the end screen. The push feed needs kills to provide timing and has no established match-completion event. Therefore a decisive winner and reliable natural completion detection are **UNKNOWN** at this stage; inferring them from a score cap is unsafe because reported live status omits `scoreCap`.

## Capability matrix

`Real server verified` means **by this spike**, not by Warcon's reporting. `VERIFIED AGAINST MOCK/DEMO` here means our synthetic HTTP fixture only.

| Capability | Current status | Real server verified | Operation/endpoint | Notes |
| --- | --- | --- | --- | --- |
| Authenticate | VERIFIED AGAINST MOCK/DEMO | No | Bearer header on all `/v1` routes | Official console and Warcon document password/hash model. |
| Query capabilities | VERIFIED AGAINST MOCK/DEMO | No | `GET /v1/capabilities` | Warcon reports captures from CL-499480/CL-501228. |
| Read status | VERIFIED AGAINST MOCK/DEMO | No | `GET /v1/status` | Live-reported absence of match clock/cap. |
| Read players | VERIFIED AGAINST MOCK/DEMO | No | `GET /v1/players` | Warcon reports live list. |
| Read Steam IDs | VERIFIED AGAINST MOCK/DEMO | No | `players[].steamId` | Presence and stability across reconnect need real test. |
| Read factions | VERIFIED AGAINST MOCK/DEMO | No | `players[].faction`; `status.factionScores[].name` | Verify exact labels and faction count on real server. |
| Read faction scores | VERIFIED AGAINST MOCK/DEMO | No | `status.factionScores[].score` | Verify update timing and score reset. |
| Change map | VERIFIED AGAINST MOCK/DEMO | No | `POST /v1/match/map` | Request can queue travel; actual timing needs real test. |
| Assign faction | VERIFIED AGAINST MOCK/DEMO | No | `PATCH /v1/players/{id}` | Optional; real respawn/team-balance behavior untested. |
| Restart match | VERIFIED AGAINST MOCK/DEMO | No | `POST /v1/match/restart` | Fixture request/read-back tested; real in-game reload unverified. |
| End match | VERIFIED AGAINST MOCK/DEMO | No | `POST /v1/match/end` | Fixture transition tested; genuine completion/winner unknown. |
| Detect match start | UNKNOWN | No | Poll status/feed | No documented authoritative start/phase event. |
| Detect match completion | UNKNOWN | No | Poll status/feed | No documented authoritative end/winner event; same-map rounds are problematic. |
| Receive events | DOCUMENTED BUT NOT VERIFIED | No | `[WDServerFeed]` push to `/api/ingest/events` | Receiver written, no real or external feed received. Reported events are kills only. |
| Detect connection/disconnection | VERIFIED AGAINST MOCK/DEMO | No | Diff successive `GET /v1/players` | Polling can miss short sessions. |
| Detect score change | VERIFIED AGAINST MOCK/DEMO | No | Diff `status.factionScores` | Synthetic diff only; real cadence unknown. |
| Detect map transition/restart | DOCUMENTED BUT NOT VERIFIED | No | Poll status, optional `matchSeconds` | Map delta tested in fixture; same-map restart not reliably identifiable. |
| Handle failures/unsupported operations | VERIFIED AGAINST MOCK/DEMO | No | `401`, `404`, route list | Mock exercised 401/404; real 405/429/backoff not tested. |

## Genuine-server test checklist

Prerequisites for all rows: an actual WARDOGS community server whose operator can edit `ServerSettings.ini` or the host panel; enable `bEnabled=true`; obtain the actual bind address and port (default 7776 unless overridden), RCON password or generated password, and access through a trusted TLS proxy/private tunnel or same-host loopback. Verify the firewall permits the probe and that the probe can reach the listener. Record `apiVersion`, `build`, full route list and limits first. Arrange an isolated test window because match commands affect players. Game-client ownership below means at least the controlled participant(s) need a WARDOGS client; the API operator alone does not.

| Test still requiring genuine server | Game client required? | Players required |
| --- | --- | --- |
| Authenticate; capture capabilities and limits; read status, catalog and rotation; verify 401, absent-route response, and TLS/network failure handling. | No | 0 |
| Join/leave; check Steam ID persistence, player faction, roster poll cadence and any missing transitions. | Yes, one controlled participant | 1 |
| Move a connected player to each valid faction; check `PATCH` availability, balancing restrictions, read-back and whether a separate kill/respawn is needed. | Yes | 1; more if balancing rules prevent move |
| Observe score changes and natural start/end/winner with fixed map **and** a map rotation; compare status, feed, clock and roster, including same-map restart. Set `MinimumRequiredPlayers` low enough for the test if permitted. | Yes | Multiple recommended; exact minimum must be established on that build |
| Queue map, end, restart; measure command acknowledgment versus actual transition, rotation pointer, player effects, and whether a same-map restart has any reliable signal. | Client recommended for visual effect; API-only state test needs none | 0 for API read-back; 1+ for in-game effect |
| Configure `[WDServerFeed] Url` and `Token`, restart server, expose receiver's `/api/ingest/events` through a reachable endpoint, induce kills, check batch/auth/delivery outage and whether any non-kill lifecycle event appears. | Yes | At least 2 for player kills; environment death may need 1 |
| Safely trigger/rate-limit or inspect `429 Retry-After`; verify 64 KiB body rule only if necessary and permitted by host. | No | 0 |

## Feasibility assessment

**Appears possible today:** authenticated status/roster/Steam ID/faction/score reads, map override, faction assignment, restart and end requests, with per-build route discovery. The official console defines these calls and Warcon reports real-build route/status captures. Our probe demonstrates the HTTP client and response handling only against a synthetic fixture.

**Actually proven by CMP:** seven local tests pass: reads and capability negotiation, auth/unsupported-route errors, queued-map/end observation, faction assignment with explicit confirmation, restart acceptance, roster diffs, and the feed receiver's handling of a synthetic authenticated batch. No genuine-server operation was performed. No real WARDOGS push batch was received.

**Main blocker:** neither an authoritative match-start/end/winner signal nor reliable same-map round identity is established. Reported live builds omit `matchSeconds` and `scoreCap`; the known feed contains kills, and its `matchId` reportedly persists across a map change. This prevents treating polling heuristics as reliable automatic competitive result finalization. Real-server experiments must establish whether another exposed signal exists or whether CMP would need a manual referee step.

A **read-only audit** of CMP's existing SquadJS/server-automation integration is justified now to identify the lifecycle and result guarantees CMP needs. Implementing a WARDOGS adapter or changing CMP architecture should wait for the genuine-server tests above, especially match completion and faction control.
