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

## Migration boundary

The shell and base primitives are implemented now. Play, Group, Profile, Match Accept, Match Room, Matches and Admin still have local composition and CSS rules. Migrate them feature by feature, preserving the precise distinctions between planned and observed state, connected and aligned, active and reserve, and observed scores and the latest confirmed revision. The historical Squad entry point uses its own stylesheet and shell.
