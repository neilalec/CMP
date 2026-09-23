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

Each faction has identity, color, a mock capacity target (not a production rule), optional commander ID, and groups. Each group has a stable ID, type, optional leader ID, and players. A player has a stable ID, display name, CMP registration state, mock Steam identifier when linked, connection and observed faction states, readiness, active/reserve status, and optional sample statistics. Match configuration is display metadata. Results are either unconfirmed or explicitly confirmed **within the mock**; only the latter can produce a ranked preview. The mock's score-based ranking remains demo-only; production placement is explicitly confirmed and stored with the result.

The mock data source supplies complete frontend domain objects. An optional backend data source now normalizes the authenticated CMP lobby read response into the same shape; components do not receive raw WDRCON objects. Confirmed demo results remain mock-only.

## Unresolved product questions

- Production faction capacities and acceptable population imbalance.
- Queue acceptance and replacement rules for reserves and substitutes; whether reserves may stay connected.
- Who assigns group leaders and commanders, and whether either role has permissions or readiness authority.
- Meaning of individual, group, and faction readiness; relationship to observed server alignment.
- Map/config selection ownership and whether voting is individual, group-weighted, or captain/admin controlled.
- Whether all three rosters remain equally prominent on small screens; group filtering for 30-player factions.
- Dispute policy and whether a dedicated referee role should replace admin-only confirmation.
- Repeated premade pairing avoidance and later skill balancing.

The first enabled queue, `wardogs_beta9`, uses three active players per faction, no reserves, and nine accepted players total. CMP parties of at most three queue together and remain intact. These are initial beta values supplied by the queue mode, not protocol or server limits. Shared CMP acceptance creates a planned lobby only after all nine accept. CMP then attempts to reserve a healthy, approved WARDOGS server. If none is free, the lobby remains visible as waiting for a server. For an allocated lobby, CMP retrieves the server's Join ID and shows the ID with a copy control and the verified client path: **Deploy → Community → Join By ID**, enter the ID, select **Lookup**, then join the resolved server. If the ID read fails, the server stays allocated and the lobby reports join unavailable. CMP does not assume direct-IP or Steam URI joining. The frontend feature has no lifecycle detection or substitution action. Eligible confirmed results feed the WARDOGS rating consumer.

Allocated lobbies now refresh server status and player presence about every 20 seconds. The lobby shows current or last-known server name, map, population, faction alignment, unexpected players, and three live server scores beside the unchanged planned roster. A failed read keeps the last observation with a stale warning; the lobby remains available. Live scores are never an official result.
## Results

WARDOGS results are authoritative only after an administrator explicitly confirms them. A recent live score snapshot can prefill the three faction values, but it remains observational evidence; admins explicitly enter placement groups as well as scores. Completed results support normal 1st/2nd/3rd placement, ties for first or second, and three-way ties. Scores must agree with the chosen placement; they never define it. Incomplete/abandoned and void/cancelled outcomes have no competitive placement. Ordinary lobby participants can view the confirmed placement and scores. Eligible confirmations apply WARDOGS ratings transactionally; confirmation does not release the allocated server.

Admins can correct a confirmed result by creating an append-only revision with a required reason. The original confirmation remains in history; the latest revision is authoritative. Participants see the current result and a neutral corrected indicator, not the audit chain.

## Ratings

The first rating system gives each CMP player one WARDOGS rating. It compares the three factions pair by pair, so first place beats both other factions and second place beats third. An authoritative tie counts as a half result between the tied factions. Close and wide scorelines have the same effect when placements match.

Only registered players on the planned active roster are rated. Whether a player connected, stayed connected, or appeared on the expected server faction does not change the roster used for a match. Reserves and unexpected server players do not receive rating changes. The beta requires equal active roster sizes in all three factions; a match without that eligibility is not rated. A future substitute or unequal-roster policy must be explicit before those matches can count.

Solos and premades use the same individual rating rules. Queueing together does not create a party or clan rating and does not change a player's expected result or update size. A new WARDOGS rating starts at 1000. Every rated match uses K=24; there is no provisional-player multiplier or zero floor. A rating may go below zero.

The only rating inputs are the latest authoritative completed result revision and its recorded placements/tie groups. Unconfirmed, incomplete, abandoned, void and cancelled results do not change ratings. Live server observations never decide a rating. If an administrator corrects a result, the corrected result and later rated matches are recalculated; the old event history remains auditable. The WARDOGS match room shows the current rating and signed change from each rated match. Squad Elo remains separate. Results confirmed before rating activation are not backfilled. Tiers and a WARDOGS leaderboard are deferred.

Every completed result revision stores all three factions in ordered placement groups. Rating code consumes those groups directly and does not reconstruct placement by sorting scores.
