# WARDOGS UI prototype

## Location and structure

The isolated, local-only demo is available at `/prototype/wardogs`. It has no authentication requirement so it can be reviewed independently of the CMP app state.

- `frontend/src/features/wardogs/WardogsPrototype.vue` contains the screen and responsive styles.
- `frontend/src/features/wardogs/fixtures.js` contains local mock fixtures for pre-match, partial connection, all-ready, live and completed states.
- The only routing change is the dedicated prototype route. No Squad view, lobby component, store, socket, or backend code was changed.

The fixture selector exposes each state. The pre-match states use three independently scrollable faction cards so larger rosters can be handled through scroll plus the proposed squad-group expansion. Live state uses a three-way score comparison and an explicitly demo-only event feed. Results use ordered cards for 1st/2nd/3rd and sample player stats, clearly presented as mock data.

## Product assumptions used for the mock

- The three named sides are Valkyra, Lonestar and Manticore.
- Player rows show a display name, mock Steam-linked identity, connection/readiness, commander marker and optional group.
- Map, experience, lighting and zone/alternator are exploratory display fields informed by the WARDOGS spike; they are not asserted controls or server capabilities.
- Scores, ranking and events are deliberately labeled mock/demo data. The results screen does not imply an authoritative winner, clock, score cap, match ID, completion event, or Elo policy.

## Questions surfaced

- Is the primary unit a player, a persistent squad, or an administratively assigned faction group?
- Are commanders mandatory, elective, or merely a display role?
- Does faction-level readiness require every player, a commander, or a configured quorum? How are substitutes represented?
- Should all three faction rosters have equal prominence at every breakpoint, or should a focused faction mode be allowed on smaller screens?
- Are map choice, experience, lighting and alternator selected by captains, admins, voting, or server configuration?
- What is the final ranking and tie policy, and what evidence makes a result final?
- For ~30-player factions, should groups collapse by default, expose role filters, or offer a full roster drawer?

## Reuse boundary

The prototype reuses only global CMP visual primitives (`window-panel`, title bars, cards, typography and controls). The faction cards, score layout, mock event list and ranked results stay WARDOGS-specific because they encode a three-faction presentation.

Potentially shareable later: status labels, player-row visual treatment, roster grouping primitives, and generic responsive card patterns. The existing Squad lobby and result components should remain untouched until an explicit multi-side product model and verified WARDOGS server lifecycle exist.

## Verification intent

This UI deliberately introduces no WDRCON calls, backend integration, production adapter, schema/rating changes, match lifecycle behavior, or changes to `live_roll.py`. The prototype is a product exploration layer only.
