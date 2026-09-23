# WARDOGS product model

## Confirmed decisions (2026-09-23)

- WARDOGS v1 matchmaking is **Hybrid**: the beta queue accepts solos and CMP parties of up to three, then assigns them to Valkyra, Lonestar, and Manticore. Larger clan/team detachments need a later queue capacity policy.
- Preserve premade groups intact. The isolated v1 matcher places larger premades before solos, balances active headcounts, and uses solos to fill gaps. It never splits a premade; entries that fit no active or reserve slot remain explicit overflow. Capacities are supplied to the matcher, not assumed from a production server. Skill balancing is deferred.
- The competitive hierarchy is Match → Factions → Groups → Players. A solo can be a one-player group. Groups may be `solo`, unclassified `premade`, `squad`, or `clan`.
- CMP solo/premade source kind does not infer WARDOGS `squad` or `clan` display type; the assignment algorithm gives no group type a balancing weight.
- Until a separate group classification exists, a finalized CMP party is shown as a neutral `premade` group. Finalized players start unready; connection and faction alignment come only from server observation.
- The frontend distinguishes active players from reserves. It does not move a reserve to active automatically.
- Group leaders and faction commanders are optional, independently represented roles. Assignment in the mock is manual.
- Steam-linked identity, connection, observed faction alignment, and explicit readiness are separate player properties. A player can be marked ready while disconnected in a diagnostic scenario; the UI displays both facts rather than silently treating one as the other.
- Three observed scores can be shown live. They do not prove a winner or match completion.

## Frontend representation

Each faction has identity, color, a mock capacity target (not a production rule), optional commander ID, and groups. Each group has a stable ID, type, optional leader ID, and players. A player has a stable ID, display name, CMP registration state, mock Steam identifier when linked, connection and observed faction states, readiness, active/reserve status, and optional sample statistics. Match configuration is display metadata. Results are either unconfirmed or explicitly confirmed **within the mock**; only the latter can produce a ranked preview. Equal scores share a displayed rank; the real tie policy remains open.

The mock data source supplies complete frontend domain objects. An optional backend data source now normalizes the authenticated CMP lobby read response into the same shape; components do not receive raw WDRCON objects. Confirmed demo results remain mock-only.

## Unresolved product questions

- Production faction capacities and acceptable population imbalance.
- Queue acceptance and replacement rules for reserves and substitutes; whether reserves may stay connected.
- Who assigns group leaders and commanders, and whether either role has permissions or readiness authority.
- Meaning of individual, group, and faction readiness; relationship to observed server alignment.
- Map/config selection ownership and whether voting is individual, group-weighted, or captain/admin controlled.
- Whether all three rosters remain equally prominent on small screens; group filtering for 30-player factions.
- Final result evidence, tie handling, missing scores, disputes, and manual referee workflow.
- Rating unit and algorithm: individual, group/clan, faction result, or a combination.
- Repeated premade pairing avoidance and later skill balancing.

The first enabled queue, `wardogs_beta9`, uses three active players per faction, no reserves, and nine accepted players total. CMP parties of at most three queue together and remain intact. These are initial beta values supplied by the queue mode, not protocol or server limits. Shared CMP acceptance creates a planned lobby only after all nine accept. CMP then attempts to reserve a healthy, approved WARDOGS server. If none is free, the lobby remains visible as waiting for a server. An allocated lobby shows its server name, but player join instructions remain unavailable until a gameplay join mechanism is verified. The frontend feature has no lifecycle detection, substitution action, or rating policy.
