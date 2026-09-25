# WARDOGS design foundation

WARDOGS is a compact tool for competitive matches. Keep the canvas quiet and the next useful action clear. Treat match data as evidence with varying authority; visual emphasis must never imply an observed score is official or a stale observation is current.

## Visual language

- Canvas: near-black slate (`--cmp-bg`). Header and inset details use a slightly raised dark tone. Standard surfaces are flat and bordered once; shadows are reserved for overlays and menus.
- Text: off-white primary, cool grey secondary, muted grey metadata. A restrained steel-blue marks actions and navigation. Green, amber and red communicate healthy, attention and exceptional states. Use text labels with color.
- Factions: Valkyra rose, Lonestar blue, Manticore olive. Use a narrow marker or small header accent; keep the rest of each roster neutral. The three factions have equal visual weight.
- Type: page titles use `--cmp-type-page`, section titles `--cmp-type-section`, body 1rem, metadata `--cmp-type-meta`, uppercase labels `--cmp-type-label`. Reserve monospace for IDs, scores and other values that benefit from alignment.
- Spacing: use the 4, 8, 12, 16, 24, 32, 48px tokens. A page has the shared gutter and top offset. Major sections use `--cmp-section-gap`. Radius is 4px for controls and 8px for panels.

## Composition

Use `cmp-page-content` for general pages. Narrow forms may use an intentional reading width; the match room may use the full width for three rosters. Put the page title above content rather than inside a card. Use one primary surface per meaningful task or data set. Use inset detail areas and dividers inside it instead of nesting more cards. Put supporting facts in metadata rows. Use disclosures for secondary evidence.

On desktop, preserve useful density. At tablet widths, collapse wide content before it becomes cramped. At mobile widths, keep a 16px gutter, stack section headings and actions where necessary, and keep controls at least 42px high. Horizontal overflow is reserved for data that genuinely needs it.

## Controls and state

`cmp-button` is neutral, `cmp-button--primary` is the single leading action in an area, `cmp-button--secondary` is a quiet outlined action, and `cmp-button--danger` marks destructive actions. `cmp-input` covers text fields and selects. Focus is a visible outline. Disabled controls dim and retain their shape.

`cmp-status` is a small dot plus label. Use neutral for waiting or unknown, success for verified healthy, warning for stale or attention, and danger for actionable mismatch or failure. `cmp-status--stale` uses a hollow dot. Quiet facts can be plain metadata. Do not render every state as a chip. These visual categories do not change domain states.

`cmp-empty-state`, `cmp-error-state`, and `cmp-loading-state` establish concise feedback treatments. `cmp-disclosure`, `cmp-player-row`, `cmp-page-header`, `cmp-section-header`, `cmp-meta-row`, `cmp-inset`, and `cmp-faction-marker` are the shared presentation pieces for later page passes.

## Matchmaking flow

Play uses one compact queue surface. Show the participant's session before the queue decision: solo actions or group size, leader and queue authority. Queue population is a discrete occupancy meter with an explicit count; it does not promise an estimated wait or imply download progress. A queued session changes the surface accent and offers Leave Queue only to someone with authority. A blocked state explains why without showing an inert primary button. An assigned match makes Open Match the primary action.

Match Accept carries the same narrow top accent and state language into a focused dialog. Its timer and close control stay in the header, acceptance lists scroll independently, and the decision or resulting status stays in the footer. Pending, accepted, finalizing and cancelled are visually distinct. Finalization remains visible until authoritative lobby navigation; visual transitions never infer a lobby from the countdown.

## Match room

Lead with the current match state and the participant's planned assignment, then place contextual server access ahead of three equal faction rosters. The personal summary separates assignment, observed presence and CMP readiness. Faction rosters use a narrow identity marker, persistent group headings and plain player rows; current-user and group emphasis stays subtle, while mismatches and uncertainty are explicit in text. Active players and reserves remain separate.

Show observation freshness once near the top and retain its timestamp and server detail in a disclosure. A stale observation describes last known presence; missing observation stays unknown. Keep observed scores in a compact evidence section labelled as unofficial. A referee-confirmed result takes visual priority when present, including the current revision, correction, tie, incomplete or void status. Place referee forms and history behind clearly labelled operator disclosures.

## Secondary participant pages

Matches, Profile and Group use the shared page header rhythm with a narrower reading width than the Match Room. Repeated history entries are compact rows: authoritative outcome leads, faction and date provide context, and backend rating entries sit alongside. Corrected revisions are noted without presenting an admin ledger. A missing rating entry is stated as missing, never inferred from outcome or roster role.

Profile treats display name and account link as identity, with a recent WARDOGS rating only when a backend history entry provides it. Group uses a single premade overview, readable code, member rows and contextual leader actions. Play remains the queue summary; Group remains the management page. Loading, empty and error feedback use the shared state primitives.

## Migration boundary

The shell, base primitives, opening Play → Match Accept journey, Match Room and secondary participant pages are implemented. Admin still has local composition and CSS rules. Migrate it while preserving the precise distinctions between planned and observed state, connected and aligned, active and reserve, and observed scores and the latest confirmed revision. The historical Squad entry point uses its own stylesheet and shell. The WARDOGS Auth page is approved and visually frozen.
