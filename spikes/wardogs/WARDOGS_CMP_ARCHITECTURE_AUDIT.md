# CMP server automation architecture audit for WARDOGS

Audit date: 2026-09-22. Scope: read-only inspection of the current CMP repository and `spikes/wardogs/WARDOGS_SPIKE.md`. No genuine WARDOGS server was available to this audit. References below use repository-relative paths and approximate starting lines so each finding can be checked against the code.

## 1. Executive summary

CMP **does have a substantial server orchestration service**, chiefly `backend/services/live_roll.py`, with server operations passed in as callbacks by `backend/app_core.py`. It also has a central HTTP bridge client and a per-server registry. Those are useful seams for a future integration. They are **not a game-neutral server contract**: the callbacks, registry capability checks, live-state tests, round result, join links, persistence payloads, and user interface all assume Squad or a two-side Squad-style match. A new server transport alone would not make WARDOGS playable through CMP.

The largest architectural gap is competitive match finalization. CMP accepts a SquadJS round result containing a winner, loser, ticket totals, and a matching layer, then advances a two-round, side-swapping match and updates two-team Elo. The WARDOGS spike has no CMP-verified real-server start/end/winner signal. Its reported live status omits the clock and score cap present in demos, and the known push feed has only kill events. Three-faction matchmaking, results, rating, and UI are a second broad change.

The practical conclusion is **promising server-control reuse, but no minimal transport-only integration**. Preserve current Squad behavior. First test a genuine WARDOGS server for lifecycle/result and faction semantics; only then choose the smallest boundary and product changes supported by evidence.

## 2. Current CMP → Squad server architecture

```text
Frontend Lobby / Results (Vue, Pinia)
  │ Socket.IO lobby actions; HTTP roster, presence, join-link reads
  ▼
backend/wiring.py → backend/sockets/lobby.py / backend/services/queue.py
  │                         │
  │                         └─ backend/matchmaking.py
  │                            two-team assignment, map vote, server allocation
  ▼
backend/app_core.py (wiring and server-scoped callback selection)
  │
  ├─ backend/services/server_registry.py
  │    SQLite server pool, health/capability probe, allocation, join discovery
  │
  ├─ backend/services/live_roll.py
  │    readiness → roster enforcement → layer roll → live polling
  │    → round capture / side swap → finalize → delayed cleanup
  │
  └─ backend/services/bridge.py
       HTTP bearer client and Squad-shaped roster/layer/result normalization
       │ per-server bridge_url or global SQUADJS_BRIDGE_URL
       ▼
     squadjs/bridge-server.js + squadjs/cmp/routes.js
       ├─ squadjs/cmp/commands.js → Squad RCON commands
       ├─ squadjs/cmp/rcon.js, players.js, layers.js → SquadJS/RCON reads
       └─ squadjs/cmp/state.js, stats.js, rounds.js, scoreboard.js
            SquadJS/log-parser events → cached round results and stats
       ▼
     squadjs/squad-server/plugins/cmp-bridge.js → SquadJS server → Squad server

Results return through bridge.py → live_roll.py → history/Elo and lobby_update
→ Vue Lobby / Results. Lobby snapshots are restored by state_persistence.py.
```

This is a callback-based orchestrator over a **SquadJS-specific bridge**, not an explicit `MatchOrchestrator → ServerAutomation → interchangeable game adapter` stack. The backend does not normally issue raw Squad RCON itself; the bundled SquadJS integration does. One direct HTTP read in `backend/wiring.py:298-310` calls the global bridge for server players, bypassing the usual lobby-specific bridge selection.

## 3. Detailed server-control flow

| Stage | Current path and behavior | Server effect / assumption |
| --- | --- | --- |
| Queue accepted and match created | `backend/wiring.py:923` handles accept; `backend/services/queue.py:185-193` calls `backend/matchmaking.py:create_lobby` (`484-631`). `assign_teams` (`432-481`) produces `team1`/`team2`; queue format checks both sizes. | Lobby is created at step 2. This is internal state; no server match has begun. |
| Server selection | `create_lobby` calls `app.allocate_server_for_lobby` and `get_server_connection_details` (`backend/matchmaking.py:518-539`). `backend/app_core.py:801-811` delegates to `server_registry.py:1549-1620`. | Registry allocates an enabled free server via `current_lobby_id`; in the no-registry fallback the pool capacity is one and operations use the global SquadJS bridge. Registry and health semantics are Squad-shaped. |
| Lobby/map vote | `backend/matchmaking.py:294-429` tallies votes, resolves a Squad layer variant, fills `selected_map`, `team_labels`, `server_details`, sets step 3, starts monitor. Socket actions in `backend/sockets/lobby.py:912-969`; admin ready/skip paths at `52-143` and `399-529` enter the same flow. | Selection is an internal lobby value until live roll. Map pools and variants are Squad layer identifiers (`backend/app_state.py:177-342`; `backend/matchmaking.py:78-98`). |
| Join and player identity | `backend/wiring.py:298-374` exposes reads; `backend/app_core.py:813-862` builds lobby join URL. `backend/services/server_registry.py:1623-1637` builds Steam connect or app-ID-393380 lobby URLs. `backend/services/bridge.py:689-811` maps bridge roster `steamID` to profile `steam_id`, expected team 1/2, actual `teamID`, and EOS ID. | Steam identity is CMP's roster join key; EOS ID is also used for Squad server control/cleanup. Join routing is game-specific. |
| Readiness and team enforcement | `backend/app_core.py:894-951` injects callbacks into `backend/services/live_roll.py:start_live_roll_monitor` (`573+`). Readiness (`141-196`) requires connected/aligned players plus time/ratio grace. Monitor (`1149-1874`) polls roster, kicks unauthorized players, and attempts force switches on mismatches. | `backend/services/bridge.py` calls `/players`; SquadJS `routes.js:119-148` uses `server.rcon.switchTeam`, a **toggle**. CMP checks subsequent roster alignment; it cannot directly specify an arbitrary target faction with this command. |
| Server preparation / live roll | Monitor sends broadcast and slomo, sets next layer, issues selected-layer change (with compatibility retry), and confirms the current layer plus `matchStartTime`/playtime (`backend/services/live_roll.py:125-138, 1583-1722`). `app_core.py:607-694` gates writes and calls bridge functions. | `bridge.py:550-674` resolves Squad layer IDs and faction options; `squadjs/cmp/routes.js:24-205` exposes routes; `squadjs/cmp/commands.js:51-195` sends `AdminSetNextLayer`, `AdminChangeLayer`, `AdminBroadcast`, `AdminSlomo`. Step 4 marks CMP's live state after observed roll. |
| Live monitoring and collection | `live_roll.py:1149-1874` polls layer/status and `/round/best`. SquadJS bridge `state.js:26-105` receives `NEW_GAME`, `ROUND_ENDED`; `stats.js:160-321` receives player connect/disconnect/wound/death/revive events. `rounds.js:35-195` matches cached results to selected layer and timestamps. | `squadjs/cmp/rcon.js:1-84` and `layers.js:72-119` report Squad current/next layer, `matchStartTime`, playtime and team names. `scoreboard.js:49-99` expects winner/loser ticket sides. Log parsers `round-ended.js` and `round-tickets.js` assemble `ROUND_ENDED` from Squad logs. |
| Completion and multiple rounds | `live_roll.py:371-388` requires a recent result with winner/loser ticket totals and matching layer (if supplied). `handle_match_round_result` (`1101-1147`) captures a round; default match shape is two rounds, with side swap preparation at `867-979`. If layer changes before a complete result, `1531-1580` waits a settle window and can record an unresolved fallback. | `app_core.py:677-694` fetches bridge `/round/best`. A map delta by itself is not a valid scored result. `should_end_live_match` (`519-520`) always returns false; the timer status (`523-532`) never requests an automatic end. `end_server_match` is wired (`app_core.py:648-652, 916`) and bridge route exists (`squadjs/cmp/routes.js:159-167`), but normal live monitor does **not** call it. |
| Finalize, persist, release | `live_roll.py:1066-1099` sets step 5, stores round result in lobby/server details, calls `app_core.py:712-729` → `history.py:69-120` and Elo, releases server allocation, emits `lobby_update`. `cleanup_finalized_lobby` (`981-1064`) later kicks players and clears lobby/session state. | Server allocation is released **before** delayed cleanup kicks; a future integration must account for potential overlap before reallocation. `backend/app.py:473-516` resumes restored monitors after process restart; `state_persistence.py:34-110` restores lobby state. |

## 4. Relevant files/modules and classification

Classification describes **current code**, not an endorsement of reuse without product changes. A component can contain both reusable machinery and a coupled contract.

| Component | Classification | Evidence and reason |
| --- | --- | --- |
| Socket.IO rooms, action dispatch, lobby notifications: `backend/wiring.py`, `backend/sockets/lobby.py`, frontend socket transport | **GENERIC / REUSABLE** at transport level | Rooms, emits, accept/ready/vote dispatch are not inherently a game protocol. The payloads they carry include two-team/layer fields, which are covered below. |
| Queue state and voting timers: `backend/services/queue.py`, `backend/matchmaking.py:294-429` | **GENERIC CONCEPT, SQUAD-COUPLED IMPLEMENTATION** | Acceptance, timers, votes are reusable concepts; queue target, assignment, selected map variants and labels are for two Squad sides. |
| Match orchestration: `backend/services/live_roll.py`; callback wiring `backend/app_core.py:894-951` | **GENERIC CONCEPT, SQUAD-COUPLED IMPLEMENTATION** | A real lifecycle coordinator exists, but readiness uses team 1/2, starting uses a layer roll, and scoring requires Squad ticket results and side swap. |
| Server pool/allocation: `backend/services/server_registry.py:1132-1196, 1549-1620` | **GENERIC CONCEPT, SQUAD-COUPLED IMPLEMENTATION** | Approval, health, ownership and allocation are reusable ideas; fields, route probes, capabilities and join discovery are SquadJS/Steam-specific. |
| HTTP bridge request transport: `backend/services/bridge.py:33-81`; per-server selection `app_core.py:541-548` | **GENERIC / REUSABLE** mechanism | Bearer JSON requests and per-server URL/token selection are broad patterns. This is not a generic operation contract; endpoint wrappers are SquadJS-specific. |
| Bridge roster normalization: `backend/services/bridge.py:689-811` | **WARDOGS MAPPING REQUIRED** | It translates server players to CMP presence, but consumes `steamID`, `teamID` 1/2 and Squad IDs. WARDOGS reports Steam ID and faction strings; alignment would need different semantics. |
| Layer/label/result wrappers: `backend/services/bridge.py:126-435, 550-674` | **SQUAD-SPECIFIC** and **WARDOGS MAPPING REQUIRED** | `/round/best`, Squad layer IDs, `faction1/faction2`, Squad faction aliases and two labels are embedded in the backend operation shape. |
| SquadJS bridge: `squadjs/bridge-server.js`, `squadjs/cmp/{routes,commands,rcon,players,layers,state,rounds,scoreboard,stats}.js` and log parsers | **SQUAD-SPECIFIC** | It directly uses SquadJS plugin events, RCON commands, Squad team/layer fields and Squad ticket results. Keep it a Squad integration. |
| Completed-match storage: `backend/services/history.py:36-135` | **GENERIC CONCEPT, SQUAD-COUPLED IMPLEMENTATION** | JSON fields can hold more than two sides, but `selected_map`, `server_details`, and `round_result` retain Squad-shaped semantics; scored-history tests require winner/loser tickets. |
| Lobby snapshot persistence: `backend/services/state_persistence.py:34-110` | **POTENTIAL BLOCKER** for three sides | Generic JSON persistence exists, but restore explicitly rebuilds only `team1` and `team2`, which would discard a third key. |
| Elo: `backend/services/elo.py:69-105, 165-223` | **POTENTIAL BLOCKER** | Winner mapping and head-to-head expected score handle only team 1/2. A three-faction result needs an explicit rating policy, not just another parser. |
| Lobby/result frontend: `frontend/src/views/Lobby.vue`, `Results.vue`, `frontend/src/features/lobby`, `frontend/src/features/match` | **POTENTIAL BLOCKER** for unchanged WARDOGS flow | Two fixed columns and winner/loser ticket display are visible product assumptions. Socket transport and generic UI primitives may still be reusable. |

## 5. Squad-specific coupling and current abstraction boundary

**Natural plug-in point.** The narrowest existing backend seam is the dependency injection at `backend/app_core.py:894-951` into `backend/services/live_roll.py:573+`, backed by `get_bridge_request_for_server` (`app_core.py:541-548`) and the operation wrappers in `backend/services/bridge.py`. The server registry already associates an individual lobby with a server and request credentials. That makes server communication relatively concentrated.

**Limit of the seam.** The injected operations are named and interpreted as Squad operations: change/current/next layer, Squad roster/team IDs, SquadJS `/round/best`, broadcast/slomo, and faction labels for two sides. Live-roll itself decides that a layer change plus Squad timing means “live” and that winner/loser tickets mean “finished.” Substituting WDRCON HTTP at `bridge.py` would still leave the coordinator unable to represent a three-faction match or prove completion.

**How distributed are operations?** Most backend server actions go through `app_core.py` → `services/bridge.py` → one SquadJS bridge route collection. `server_registry.py` also invokes bridge probes and constructs Steam join information. `backend/wiring.py:298-310` has a global bridge roster read. Squad-specific meaning continues into matchmaking, persistence, history/Elo and the frontend, even though those layers usually do not speak RCON.

**Event translation.** SquadJS turns raw log/parser events into cached `/round/best` and player snapshots (`squadjs/cmp/state.js`, `rounds.js`, `scoreboard.js`, `stats.js`). The backend partially normalizes player presence into expected/actual team alignment (`bridge.py:689-811`). It does **not** convert server activity into a fully game-neutral event/result model. Round result, layer, team IDs/names and `server_details.roundResult` flow into lobby state, completed-match JSON, Socket.IO and frontend result formatting.

**Database and configuration.** `backend/services/server_registry.py:1132-1196` stores `steam_lobby_id`, `connect_address`, `join_password`, `bridge_url`, encrypted bridge token and capability columns named `cap_layer_change`, `cap_round_result`, etc. Its health test (`1415-1508`) infers players/layer/result capability from SquadJS route responses and sets broadcast capability optimistically; this is not WDRCON capability negotiation. `backend/services/history.py:36-47` has generic JSON `teams_json`/`round_result_json` columns alongside `selected_map`, but consumers assume two-side tickets. `backend/app_state.py:177-372` defines two-side queue sizes and Squad layer pools plus `SQUADJS_BRIDGE_URL/TOKEN` and `SQUAD_SERVER_*` settings. Docker configuration also carries Squad/Steam/EOS setup. These are design facts; this audit makes no schema/config change.

**Frontend knowledge.** `Lobby.vue:80-161` renders two team columns. `frontend/src/features/lobby/composables/useLobbyView.js:83-140` exposes `groupedTeam1`/`groupedTeam2` and BLUFOR/OPFOR fallbacks. `frontend/src/features/lobby/components/LobbyMatchInfo.vue:60-170`, `frontend/src/features/match/utils/matchHistory.js:26-38, 177-215`, and `Results.vue` format winner/loser ticket summaries. Frontend join links use the Steam strategy returned by the backend. These outputs would need an intentional three-faction design.

## 6. Two-team assumptions

The repository uses `team1`/`team2` rather than `team_a`/`team_b`; the effect is the same. “Change scope” below describes likely future work and is not an implementation request.

| Location | Current behavior | WARDOGS change needed? / likely scope |
| --- | --- | --- |
| `backend/app_state.py:177-342` | Queue modes have `team_size`, `max_players = 2 × team_size`, `NvN` labels and Squad layer pools. | **Yes** if one WARDOGS faction maps to each CMP side: queue capacity/mode metadata/map catalog. Product decision first: three competitive squads versus another format. |
| `backend/matchmaking.py:432-481, 484-568` | `assign_teams` splits two groups, format validator requires exactly equal `team1`/`team2`, captains and lobby payload hold two. | **Yes, broad matchmaking/lobby model.** This is a structural two-side contract. |
| `backend/sockets/lobby.py:295-309`; `backend/sockets/group.py:84-87`; `backend/runtime.py:33-45` | Late arrivals join the shorter of two teams; departures/removal scan only two keys. | **Yes, socket/group state handling.** Third-faction membership would otherwise be omitted. |
| `backend/services/state_persistence.py:53-73` | Restore explicitly constructs `team1` and `team2` and default captains. | **Yes, persistence restoration.** A third faction's members would be lost on restart even if the stored JSON contained them. |
| `backend/services/bridge.py:261-435, 689-811` | Picks first two Squad team descriptors, emits `team1`/`team2` labels, maps expected team to numeric 1/2 and compares actual `teamID`. | **Yes, integration presence/label mapping.** WARDOGS uses faction names; target assignment and readback must address all three. |
| `backend/services/live_roll.py:141-196, 867-979, 1101-1147` | Readiness and enforcement expect two assigned sides; two-round side swap/faction memory presumes paired opposition. | **Yes, core orchestration.** Round format and any faction rotation must be decided explicitly. |
| `squadjs/cmp/layers.js:40-62`; `squadjs/cmp/commands.js:36-41`; `squadjs/cmp/scoreboard.js:49-99` | Two `teamOne`/`teamTwo` labels, `faction1`/`faction2`, winner/loser tickets. `scoreboard.js:25-47` can collect observed team IDs dynamically, but the exported competitive result remains paired. | **No change to Squad integration** for WARDOGS; a separate integration/result mapping would be needed. |
| `backend/services/live_roll.py:371-388`; `backend/services/history.py:146-157` | A scored result requires winner and loser ticket numbers. | **Yes, result eligibility.** Three scores, ties and absent authoritative winner need a defined policy. |
| `backend/services/elo.py:69-105, 120-223` | Only team 1/2 recognized; one opponent and head-to-head expected score; draw is 0.5 each. | **Yes, rating model.** A third side cannot be represented by current calculations. |
| `frontend/src/stores/state/lobbyState.js:12-18`; `frontend/src/stores/lobbyStore.js:115-122` | Store shape and removal handle only `team1` and `team2`. | **Yes, client state contract.** |
| `frontend/src/views/Lobby.vue:80-161`; `frontend/src/features/lobby/composables/useLobbyView.js:83-140` | Two visible columns and two computed rosters/labels. | **Yes, lobby UI/layout.** |
| `frontend/src/features/lobby/components/LobbyMatchInfo.vue:60-170`; `frontend/src/features/match/utils/matchHistory.js:26-38, 64-68, 177-215`; `frontend/src/views/Results.vue` | Displays paired winner/loser ticket results and maps players to team IDs 1/2. | **Yes, match/history UI.** Needs a three-faction result representation after outcome semantics are known. |
| `backend/services/history.py:36-47` | Stores teams and round result as JSON; no fixed `team1`/`team2` SQL columns in completed matches. | **No immediate column-count constraint**, but writers/readers and score filters above are coupled. |

## 7. Reusable components and qualitative reuse estimate

| Reuse category | Current assets | Condition / limit |
| --- | --- | --- |
| Likely reusable unchanged | Socket.IO transport/rooms and event delivery; HTTP bearer request mechanism; generic server allocation bookkeeping; vote timer mechanics; JSON/event logging plumbing. | Payload shape and capability checks would still need review. This category is about infrastructure, not the current full match flow. |
| Reusable after small adaptation | Per-server URL/secret selection, health reporting shell, presence comparison pattern, lobby server details publication, polling/scheduling infrastructure. | WDRCON capability discovery, roster shape, rate limits and join method must be supplied. Existing functions cannot merely point to a new URL. |
| Requires abstraction/refactor | Live-roll operation/result contract, start/round identity/completion semantics, server health capabilities, map/configuration selection, match result and Elo policy, three-team queue/lobby/state/UI. | Several of these are product model changes, not just adapter code. |
| Requires WARDOGS-specific implementation | WDRCON client/auth/capability negotiation; status/roster/faction score parsing; map/config selection; faction assignment/readback; restart/end command handling; join instructions; optional feed receiver. | No such implementation is recommended until real-server behavior is verified. |
| Unknown until genuine server | Authoritative match start/end/winner, same-map round identity, faction assignment and respawn effects, transition latency, score reset/cadence, feed coverage and delivery. | These determine whether automatic competitive orchestration can meet CMP's current guarantees. |

The recent SquadJS work is a strong **architecture foundation for coordinating actions and observing a server**, but its most important contract is currently “Squad layer + two team roster + winner/loser ticket result.” Qualitative reuse is therefore high for control plumbing, conditional for the monitor, and low for unmodified competitive semantics. No percentage is justified by the evidence.

## 8. Potential abstraction boundary

If genuine-server testing supports integration, the smallest coherent boundary would surround the **server-facing operations and observations** currently wired at `app_core.py:894-951`, with per-server implementation selection in `app_core.py`/`server_registry.py` and protocol-specific code kept beside `services/bridge.py` and the SquadJS bridge. The boundary would need to describe, in CMP terms, server capability, roster identity/faction, map/configuration and transition acknowledgement, current match/round identity, scores, and an authoritative or explicitly unresolved outcome. It would also need to state whether an operation is requested, observed, or complete. This is a proposed design location, **not an interface introduced by this audit**.

A transport boundary alone is insufficient. Separate minimum conceptual boundaries would be required for (1) match format/side count in queue, lobby and persistence; (2) result and rating policy; and (3) lobby/result presentation. Keeping SquadJS code behind its current routes avoids changing Squad behavior, but those CMP-wide assumptions would still need deliberate changes before a three-faction WARDOGS match is supported.

## 9. Squad → generic CMP → WARDOGS mapping

All WARDOGS entries are **tentative**. “Spike” refers to `WARDOGS_SPIKE.md` and its official-console/demo and attributed third-party observations, not this audit's live verification.

| CMP/Squad concept | Current implementation | Generic CMP concept | Possible WARDOGS equivalent | Confidence / real-server dependency |
| --- | --- | --- | --- | --- |
| Player identity | CMP `steam_id`; SquadJS `steamID` plus `eosID` (`bridge.py:689-811`) | Stable player key and connection membership | WDRCON `players[].steamId` | **Medium for field mapping, unverified in CMP live test**; verify reconnect stability and account linkage. |
| Presence | SquadJS `/players`, connect/disconnect events, poll (`bridge.py`; `squadjs/cmp/stats.js`) | Connected roster and join/leave observations | `GET /v1/players` polling; reported feed does not establish join/leave events | **Medium for snapshot, low for transitions**; measure polling gaps and rate limits. |
| Team assignment | Expected `teamID` 1/2; SquadJS `switchTeam` toggle plus alignment readback | Assign an authorized player to a match side and verify it | Optional `PATCH /v1/players/{steamId}` with `{faction}`; perhaps separate kill/respawn | **Low**; verify route on actual build, restrictions, readback and player effect. Three faction model is also needed. |
| Map/layer | Squad layer ID/variant; next/current layer and `AdminChangeLayer` (`bridge.py:550-674`) | Choose match environment and observe transition | WDRCON map ID plus compatible experiences/lighting/alternator; `POST /v1/match/map` | **Medium for requested control, low for completion timing**; reported travel is queued until end screen. |
| Server status/start | SquadJS `/server` current/next layer, `matchStartTime`, playtime (`layers.js:72-119`) | Current match environment and trustworthy start/round identity | `GET /v1/status` map, scores, player count, rotation | **Low for lifecycle**; reported live builds omit `matchSeconds` and score cap. Same-map restart may be indistinguishable. |
| Server roster/faction labels | SquadJS `teamID` and teamOne/teamTwo labels | Assigned sides and observed side membership | `players[].faction`, `status.factionScores[].name` | **Medium for snapshot, low for full mapping**; verify exact three faction values and balance rules. |
| Match score | `ROUND_ENDED` → `/round/best` winner/loser tickets (`scoreboard.js`; `live_roll.py:371-388`) | Per-side score and final outcome | `status.factionScores[]` values | **Low for final result**; verify cadence, resets, tie handling and authoritative end/winner. A current score is not a final result. |
| Restart / next round | Squad layer roll and two-round side swap (`live_roll.py:867-979`) | Begin a new identifiable round | `POST /v1/match/restart` | **Low**; request acknowledgement is not proof of reload; same-map boundary may be invisible. |
| End match | SquadJS `/match/end` exists but normal monitor does not invoke it | Request an end and observe completion | `POST /v1/match/end` | **Low**; verify effect, delayed rotation and any completion marker. It does not by itself provide a winner. |
| Server capability / join | Registry probes SquadJS routes and creates Steam join URLs | Verify usable operations and instruct players how to join | `GET /v1/capabilities`, WARDOGS-specific join information | **Medium for route list concept, unknown for join**; capture actual build/route list, limits and host connection method. |

## 10. Architectural blockers and risks

1. **Unproven completion and winner:** current finalization requires a recent winner/loser ticket result (`live_roll.py:371-388`) and feeds history/Elo. The WARDOGS spike has no verified authoritative result. A score snapshot or command acknowledgement cannot safely replace this.
2. **Three factions across the product:** matchmaking, ready/alignment checks, state restore, UI, history and Elo all encode two sides (section 6). This is broader than server transport.
3. **Round identity and transition semantics:** CMP confirms Squad layer/timing changes. WARDOGS map travel may be deferred, a same-map restart may be invisible, and the reported feed `matchId` did not reliably mark a map boundary. Incorrect detection could mix rounds or duplicate results.
4. **Different team-control semantics:** Squad `switchTeam` toggles; WDRCON appears to name a target faction and may require a kill/respawn. Current correction and cleanup policies must not be assumed equivalent.
5. **Squad-shaped server registry and join path:** health checks require SquadJS routes; capability names and Steam/EOS lobby discovery are not game-neutral. A WDRCON listener cannot pass these checks unchanged.
6. **Allocation versus cleanup timing:** current finalization releases `current_lobby_id` before asynchronous player kicks (`live_roll.py:1066-1099, 981-1064`). If reused without explicit occupancy/transition policy, another lobby could select a still-occupied server.
7. **Operational observation:** WDRCON is reported to have a rate limit and powerful single bearer password; any future polling/control service would need measured cadence, backoff, per-server credentials and protected connectivity. These are operational design inputs, not proof of a current vulnerability.

## 11. What still requires genuine WARDOGS server testing

The spike's synthetic fixture and official in-browser demo establish client-shape feasibility only. A controlled genuine server test should record the actual WDRCON build, route list, limits, and connection method, then verify:

- `status`, roster Steam IDs/faction names, score count and update cadence through real joins, deaths and reconnects;
- optional faction-assignment route, target behavior, balance restrictions, readback and whether respawn is required;
- map/config override acknowledgement versus actual travel, including deferred travel after end screen;
- natural match start, end, winner, ties, score reset, same-map restart and stable round identity; capture all status fields before/during/after, especially whether clock or score cap exists on the real build;
- restart/end request effects and whether any signal actually marks completion;
- feed event types, timing, delivery/retry/outage behavior and whether any lifecycle or winner event exists beyond the reported kill batches;
- real join method, host network/TLS arrangement, authentication failures and rate-limit/backoff behavior.

The decisive experiment is a **full natural match on a fixed map followed by a same-map restart**, plus a separate rotated map. It should determine whether CMP can identify a scored final result without inference. If it cannot, a manual referee/result path would be a product choice requiring explicit design, not a drop-in adapter behavior.

## 12. Recommended minimum-change integration strategy

**Recommendation for future design only; nothing is implemented here.** Preserve the current SquadJS bridge and Squad live path. After genuine-server testing, document the exact WARDOGS capabilities and outcome guarantees. If they suffice, add a separate WDRCON implementation behind a small, server-scoped operation/observation boundary at `app_core.py`/`services.bridge`, and make the existing coordinator consume normalized CMP observations rather than Squad layer/ticket fields. Keep requested versus observed transitions explicit. Introduce the smallest match-format model that can express three factions, then update only the queue/lobby persistence, result/rating policy and frontend surfaces that actually consume side count or final outcome. Gate WARDOGS server selection on capabilities proven on that build. Do not reinterpret incomplete score data as a final competitive result.

This sequence protects the working Squad path while making the required cross-application changes visible. It is **not** a claim that only a bridge swap is needed, and it should not be started before the lifecycle test resolves the main uncertainty.

## 13. Recommended next step

Arrange the controlled genuine-server test described in section 11 and capture an evidence bundle: build/capabilities, timestamped status and roster snapshots, relevant feed batches, action requests/readback, and observed in-game start/end/winner for both same-map and rotated matches. Then decide whether automatic finalization is supported and define the three-faction competitive result policy. Only after those decisions should CMP choose and implement an abstraction or WARDOGS integration.
