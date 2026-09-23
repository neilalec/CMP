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
- [ ] Generic game-server observation/control contract
- [ ] Minimum CMP refactor
- [ ] Game-aware server registry/configuration and join strategy
- [ ] Production WDRCON client for verified read endpoints
- [ ] WARDOGS adapter skeleton with per-build capability gating
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
- [ ] Backend integration
