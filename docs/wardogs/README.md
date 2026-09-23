# WARDOGS in CMP

This directory records durable product decisions and the implementation roadmap. The [product model](PRODUCT.md), [roadmap](ROADMAP.md), [capability matrix](CAPABILITIES.md), [target architecture](TARGET_ARCHITECTURE.md), and [decision log](DECISIONS.md) are the current planning references.

- [`spikes/wardogs/`](../../spikes/wardogs/) holds research, API probes, real-server evidence, and experiments. Start with the [WDRCON spike](../../spikes/wardogs/WARDOGS_SPIKE.md), [CMP architecture audit](../../spikes/wardogs/WARDOGS_CMP_ARCHITECTURE_AUDIT.md), and [original UI notes](../../spikes/wardogs/WARDOGS_UI_NOTES.md). Historical spike conclusions retain their original evidence scope.
- `docs/wardogs/` holds product decisions and work still to be done.
- [`frontend/src/features/wardogs/`](../../frontend/src/features/wardogs/) is the production-shaped frontend feature. Its current data source is local mock data; the route remains `/prototype/wardogs`.

The frontend supports three faction rosters and an authenticated CMP lobby read. Allocated WARDOGS lobbies use the verified manual Join By ID flow; lifecycle and result automation remain unverified. See the [capability matrix](CAPABILITIES.md) for current real-server evidence.
