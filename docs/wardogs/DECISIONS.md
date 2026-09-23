# WARDOGS decision log

| Date | Status | Decision | Rationale |
| --- | --- | --- | --- |
| 2026-09-23 | Accepted | WARDOGS support lives inside CMP. | Share the existing product and identity experience without copying the application. |
| 2026-09-23 | Accepted | Preserve existing Squad behavior. | Its two-side orchestration and results are established and should not change during WARDOGS exploration. |
| 2026-09-23 | Accepted | WARDOGS v1 uses Hybrid matchmaking. | Players can arrive solo, as squads, or as clan/team detachments. |
| 2026-09-23 | Accepted | Match → Faction → Group → Player is the competitive hierarchy. | Group identity must survive faction assembly and roster presentation. |
| 2026-09-23 | Accepted | Preserve premades where possible; use solos to fill gaps. | Population balance should not routinely split existing groups. |
| 2026-09-23 | Accepted | Represent active and reserve rosters. | Substitutes need a visible place without implying automatic moves. |
| 2026-09-23 | Accepted | Group leaders and faction commanders are optional. | Their selection and authority are not yet defined. |
| 2026-09-23 | Open | Match lifecycle and final result policy. | Populated natural end and same-map restart evidence remain incomplete. |
| 2026-09-23 | Open | Rating policy. | Result semantics and rating unit need product decisions. |
| 2026-09-23 | Not approved | Global N-team CMP refactor. | The target audit favors a minimum game-scoped boundary; no application-wide conversion or production refactor is authorized. |
| 2026-09-23 | Accepted | Deliver WARDOGS by verified capability, with a referee-confirmed result fallback. | Unproven lifecycle signals must not block useful matchmaking/roster features or be replaced by score/map/time heuristics. The fallback workflow itself is not yet implemented. |
| 2026-09-23 | Accepted | Registry records carry explicit `game_type`; WARDOGS probe confidence lives in metadata beside legacy Squad capability columns. | Existing rows default to Squad and existing Squad health/selection semantics remain intact; no broad registry redesign is needed yet. |
| 2026-09-23 | Accepted for this milestone | WARDOGS credentials use a restricted server-side environment reference; join details remain unset. | The existing signed `bridge_token_encrypted` serializer does not provide confidentiality. An environment reference avoids storing a powerful WDRCON password in SQLite while join behavior remains unverified. |
| 2026-09-23 | Accepted | Use a small normalized observation protocol and a separate capability gate for controls. | WARDOGS reads go through `WardogsAdapter` and the existing WDRCON client. Advertised routes cannot enable writes; even a verified control state has no write implementation yet. Squad keeps its current callbacks and bridge path. |
| 2026-09-23 | Accepted | Persist WARDOGS planned rosters separately from Squad lobbies; keep WDRCON snapshots process-local. | The versioned WARDOGS table holds groups, roles, planned factions and explicit readiness. The read model merges optional server observations without overwriting that state. |
| 2026-09-23 | Accepted | Match observed players by unambiguous Steam ID and leave unexpected players outside the planned roster. | Display names are not stable identities. Connection and observed faction belong to the server snapshot; readiness belongs to CMP. Missing/stale reads remain unknown rather than erasing roster members. |
| 2026-09-23 | Accepted | Reuse CMP queue and match acceptance; branch to a game-specific assignment/lobby builder after acceptance. | Queue and acceptance services are mode-keyed and game-neutral through finalization. The current callback always creates a Squad lobby; preserve it and add a narrow game-aware dispatch when WARDOGS matchmaking has an explicit valid assignment. |
| 2026-09-23 | Accepted | Reuse CMP parties as WARDOGS premade inputs, then snapshot them into match groups. | CMP parties provide persistent code, leader and members but have no solo/squad/clan type; WARDOGS classification is separate match metadata. |
| 2026-09-23 | Implemented | Queue modes have globally unique IDs and explicit game identity; absent legacy metadata means Squad. | The existing disabled-mode set remains per-mode. Unknown game/mode combinations fail validation and never inherit Squad capacity or lobby creation. |
| 2026-09-23 | Implemented | Invalid persisted queue modes are skipped; pending acceptance is cancelled on restart while valid queued members remain. | Queue rows record mode IDs, whereas acceptance timers are process-local. Restore never moves unknown entries to Squad or resumes a stale countdown. |
| 2026-09-23 | Implemented | Accepted matches validate pending game identity before lobby creation. | Only Squad currently dispatches to its existing builder; WARDOGS has no finalizer until assignment is defined. |
