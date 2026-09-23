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
