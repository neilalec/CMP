# WARDOGS roadmap

Update this checklist as evidence and implementation land. `[~]` means in progress; it is not a GitHub checkbox state.

Delivery is **capability-driven**. Missing natural-end or winner evidence does not block architecture, roster, server-read, or manual-result work. Enable each automated control or finalisation path only after its behavior is verified on the deployed build; never promote score resets, caps, map changes, or timers into completion proof. See [capabilities](CAPABILITIES.md) and [target architecture](TARGET_ARCHITECTURE.md).

## Technical investigation and integration

- [x] Current WDRCON research
- [x] Mock/demo spike
- [~] Real-server spike
- [x] Real-server authentication
- [x] Capability discovery
- [x] Status observation
- [x] Real roster and Steam identity observation
- [x] Three faction score observation
- [x] Rotation observation
- [ ] Populated live match capture
- [ ] Natural match completion capture
- [ ] Winner/result semantics established
- [ ] Same-map restart identity established
- [ ] Controlled faction assignment test
- [ ] Controlled restart/end/map tests
- [x] Capability-driven feature matrix (current evidence and fallbacks)
- [ ] Lifecycle/result capability semantics established on a populated server
- [ ] Final WARDOGS capability/lifecycle evidence documentation
- [x] Initial CMP/SquadJS architecture audit
- [x] Target CMP ↔ WARDOGS architecture/reuse audit (design)
- [x] Stack/runtime suitability review (design; load validation remains)
- [x] Normalized game-server observation and capability contracts
- [x] Generic game-server adapter/control capability contract (read boundary and fail-closed control gate; no writes)
- [x] Read-only WDRCON mapping for verified capability/status/player/rotation shapes
- [ ] Minimum CMP refactor
- [x] Game-aware registry records, read-only health probe, and Squad allocation isolation
- [ ] WARDOGS player join strategy and full game-aware allocation policy
- [x] Isolated production-shaped read-only WDRCON client for verified endpoints
- [x] WARDOGS adapter skeleton with per-build capability gating (read-only)
- [x] WARDOGS backend lobby/read model with CMP-owned roster persistence and observation reconciliation
- [ ] Production WARDOGS adapter
- [ ] Enable lifecycle/result automation only where verified evidence supports it

## Product and frontend

- [x] Choose Hybrid matchmaking
- [x] Formalise frontend domain model (mock source; backend mapping pending)
- [x] Production-shaped three-faction lobby preview
- [x] Grouped roster presentation
- [x] Active/reserve presentation
- [x] Connection/readiness/alignment states
- [x] Optional commanders and leaders presentation
- [x] Mock live-match presentation
- [x] Ties/incomplete result presentation
- [ ] Manual/referee-confirmed result workflow and provenance
- [ ] Production results presentation with verified outcome source
- [ ] Matchmaking algorithm
- [ ] Rating policy
- [~] Backend integration (authenticated read-only lobby endpoint and optional frontend backend source; matchmaking/allocation remain separate)
