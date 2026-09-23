# WARDOGS product model

## Confirmed decisions (2026-09-23)

- WARDOGS v1 matchmaking is **Hybrid**: solos, squads, and larger clan/team detachments enter the queue. CMP eventually assembles those entries into Valkyra, Lonestar, and Manticore.
- Preserve premade groups whenever possible. Special handling is needed when a group cannot fit the remaining faction capacity. Solos and smaller groups fill gaps. Population balance precedes any future rating balance policy.
- The competitive hierarchy is Match → Factions → Groups → Players. A solo can be a one-player group. Groups have `solo`, `squad`, or `clan` type.
- The frontend distinguishes active players from reserves. It does not move a reserve to active automatically.
- Group leaders and faction commanders are optional, independently represented roles. Assignment in the mock is manual.
- Steam-linked identity, connection, observed faction alignment, and explicit readiness are separate player properties. A player can be marked ready while disconnected in a diagnostic scenario; the UI displays both facts rather than silently treating one as the other.
- Three observed scores can be shown live. They do not prove a winner or match completion.

## Frontend representation

Each faction has identity, color, a mock capacity target (not a production rule), optional commander ID, and groups. Each group has a stable ID, type, optional leader ID, and players. A player has a stable ID, display name, CMP registration state, mock Steam identifier when linked, connection and observed faction states, readiness, active/reserve status, and optional sample statistics. Match configuration is display metadata. Results are either unconfirmed or explicitly confirmed **within the mock**; only the latter can produce a ranked preview. Equal scores share a displayed rank; the real tie policy remains open.

The mock data source supplies complete frontend domain objects. An optional backend data source now normalizes the authenticated CMP lobby read response into the same shape; components do not receive raw WDRCON objects. Confirmed demo results remain mock-only.

## Unresolved product questions

- Exact faction capacity and acceptable population imbalance; treatment of a premade too large for available capacity.
- Queue acceptance and replacement rules for reserves and substitutes; whether reserves may stay connected.
- Who assigns group leaders and commanders, and whether either role has permissions or readiness authority.
- Meaning of individual, group, and faction readiness; relationship to observed server alignment.
- Map/config selection ownership and whether voting is individual, group-weighted, or captain/admin controlled.
- Whether all three rosters remain equally prominent on small screens; group filtering for 30-player factions.
- Final result evidence, tie handling, missing scores, disputes, and manual referee workflow.
- Rating unit and algorithm: individual, group/clan, faction result, or a combination.
- Repeated premade pairing avoidance and later skill balancing.

No matchmaking algorithm, lifecycle detection, substitution action, or rating policy is implemented in the frontend feature.
