# WARDOGS capability matrix

This is a deployment-time feature gate, not a list of promises made by `/v1/capabilities`. Re-evaluate after a build/configuration change and keep the last successful observation timestamp. **Advertised** means the route exists in the captured route list; it does not mean a request succeeded or changed the game. **Observed** means a real-server read succeeded. **Mutated** requires a confirmed request *and subsequent effect*. **Established** lifecycle semantics require an independently identifiable boundary/result, including the same-map case. An unknown or stale capability must fail closed for automation.

The [backend contract](../../backend/services/game_server_contracts.py) uses `unknown`, `unavailable`, `advertised`, `observed`, `effect_verified`, and `semantic_verified`. The isolated WDRCON client starts at unknown, derives advertisement from the route list, and advances a read only after that call parses successfully. An empty player list verifies the roster endpoint, **not** Steam identity or faction fields. It has no mutation method and never advances lifecycle confidence. The registry now saves a sanitized snapshot of these states in WARDOGS `metadata_json` after a successful read-only capabilities/status probe; it is last-observed evidence, not an eternal authorization to automate. Squad's legacy boolean capability columns are untouched.

Evidence: the checked-in [real-server session](../../spikes/wardogs/evidence/20260923T110826683162Z/summary.md) on `++Wardogs+Live-CL-501228` contains successful capability negotiation, 18 status reads, 17 empty-roster reads, and 17 rotation reads. It shows three named factions with score fields, but all scores are zero and all roster snapshots have zero players. The [WDRCON spike](../../spikes/wardogs/WARDOGS_SPIKE.md) describes synthetic/console tests and attributed third-party reports; its earlier real-server claims should not be confused with this bundle. The project brief reports additional real-player Steam/faction observations, but their raw populated snapshots are not in this checked-in session. No `actions.jsonl` or natural-end capture is in the bundle. Status below is conservative about what can be reproduced from the repository.

Additional live Join By ID verification was reported for this milestone: `GET /v1/server-id` returned an ID; entering it through WARDOGS **Deploy → Community → Join By ID** resolved the correct deployed server and a player joined successfully. CMP now reads that value dynamically; the tested live ID is intentionally not stored in the repository.

Allocated WARDOGS lobbies now use a single periodic, read-only worker for `GET /v1/status` and `GET /v1/players`. Roster, faction, map, population, and score values are observations with freshness and last-read status. They cannot establish match start, end, winner, or official result. The worker does not poll capabilities, rotation, Join ID, or control routes.

An authenticated admin can explicitly confirm a completed win (with a selected winner), tie, incomplete/abandoned, or void/cancelled result. Latest observed faction scores are optional suggestions; a manual result remains possible without WDRCON. Automatic lifecycle and winner detection remain unsupported/unverified.

`Verified (read)` applies only to the shape and conditions actually captured; `reported` marks a real-server observation supplied by the project but not reproducible from the checked-in bundle; `advertised only` and `unverified` do not enable production mutation/finalisation. None of the unknown lifecycle capabilities is asserted *unsupported* by the protocol.

| Capability | Status / evidence | CMP dependent feature | Safe fallback |
| --- | --- | --- | --- |
| Server health/status | Verified (read): `GET /v1/status`; `GET /v1/health` advertised only | Availability, live observation, operator diagnostics | Mark stale/offline on timeout; retain last timestamped snapshot, block controls if reachability is unknown |
| Player roster | Verified (empty read): `GET /v1/players`; populated read reported separately | Connection count, expected-roster comparison | Show connection as unknown, not absent; allow referee check-in |
| Steam identity | Reported real-player observation of `players[].steamId`; no populated bundle row | Link CMP profile to observed player; prevent misassignment | Do not auto-match or move ambiguous identities; referee reconciliation |
| Faction assignment (read) | Reported real-player observation of `players[].faction`; score faction names verified in status | Alignment and three-faction roster | Show unknown alignment; do not count it as ready/verified |
| Three faction scores | Verified (read shape): `status.factionScores[]` contains Valkyra, Lonestar, Manticore at zero; live change/finality unverified | Live server scores only | Display timestamped observed values or stale last-known values; never finalise from them |
| Rotation | Verified (read): `GET /v1/rotation` in bundle | Map scheduling/diagnostics | Show configured schedule as unknown; referee selects/announces map |
| Player Join ID | Verified (read and workflow): `GET /v1/server-id` returned an ID; the live client resolved the correct server and a player joined using Join By ID | Show dynamic Join ID and manual instructions for an allocated lobby | Keep allocation and show join unavailable if the read fails; do not infer a direct URI |
| Map/config snapshot | Verified (read): map, experiences, lighting, alternator in status; `GET /v1/config` advertised only | Match information and map compatibility | Display known values with observation time; use operator-provided details if absent |
| Broadcast | Advertised only: `POST /v1/broadcast` | Join/start/referee announcements | CMP/Socket.IO announcement or manual server admin |
| Assign/move faction | Advertised only: `PATCH /v1/players/{id}`; no checked-in mutation/read-back | Enforce assembled roster | Manual player switch/admin assistance; mark alignment pending |
| Change map | Advertised only: `POST /v1/match/map`; request may queue travel | Server preparation | Referee/operator sets map outside CMP; wait for observed map before claiming success |
| Restart match | Advertised only: `POST /v1/match/restart` | Controlled replay/reset | Referee/operator action and explicit new CMP match attempt; no inferred boundary |
| End match | Advertised only: `POST /v1/match/end` | Controlled close | Referee/operator ends match; CMP result remains pending until confirmed |
| Kick player | Advertised only: `POST /v1/players/{id}/kick` | Unauthorized-player enforcement/cleanup | Alert referee; no silent automatic kick |
| Authoritative match start | Unverified: no established phase/start field or event | Automatic live transition and timing | Explicit referee start/phase confirmation; timestamp its provenance |
| Authoritative match end | Unverified: no natural-end capture | Automatic finalisation | Referee confirms end; status remains pending until then |
| Authoritative final scores | Unverified: live status is not a final-score record | Result draft/final scores | Referee enters/confirms three values with evidence; missing values block acceptance |
| Authoritative winner/ranking | Unverified: no winner/tie semantics established | Rankings and later rating | Referee confirms ranking/tie disposition; otherwise unconfirmed/void |
| Stable match/round identity | Unverified: `/v1/server-id` is a Join ID, not a match ID; third-party feed `matchId` reportedly persisted across a map change | Deduplication and result association | CMP-generated match/attempt ID; referee associates observations explicitly |
| Reliable same-map restart identity | Unverified: no controlled capture | Distinguish replay from prior match | Explicit referee restart/attempt boundary; never infer from score reset |

## Gate rules

- Record each adapter capability as `unavailable`, `advertised`, `observed`, `effect_verified`, or `semantic_verified`, with build, timestamp and evidence reference. For actions, advertised is insufficient; a mutation gate requires a verified effect on the current build and policy permission. Reads may be enabled at observed level, with freshness/quality reported separately.
- Distinguish command **requested**, HTTP **acknowledged**, game effect **observed**, and authoritative lifecycle/result **established**. A successful `POST /v1/match/end` is not a completed match or accepted result.
- Operational checks also include authentication, endpoint reachability, rate-limit/backoff, and server allocation. A capability may be known but temporarily unavailable; show degraded state rather than manufacturing a negative observation.
- Neither score caps, score resets, map deltas, timers, nor push-feed kill events are completion proof. Review new feed event types separately before enabling a lifecycle gate.
- The useful minimum is Hybrid matchmaking, grouped/reserve rosters, allocation/join details, supported reads/controls, and referee-confirmed results. Rating consumers remain disabled for unaccepted results.
