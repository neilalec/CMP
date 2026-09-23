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
- [x] CMP queue/group/acceptance reuse audit and lobby branch point
- [x] Stack/runtime suitability review (design; load validation remains)
- [x] Normalized game-server observation and capability contracts
- [x] Generic game-server adapter/control capability contract (read boundary and fail-closed control gate; no writes)
- [x] Read-only WDRCON mapping for verified capability/status/player/rotation shapes
- [x] Shared game-aware queue/acceptance foundation (mode identity, capacity isolation, safe restore, restart reset, finalization guard)
- [x] Immutable WARDOGS accepted-player party/solo snapshot contract
- [x] Deterministic Hybrid faction assignment algorithm with explicit configuration
- [x] Internal WARDOGS accepted-match finalizer and lobby creation from complete Hybrid assignment
- [x] First WARDOGS beta queue exposure, shared match acceptance, and accepted-match finalizer wiring
- [x] Game-aware registry records, read-only health probe, and Squad allocation isolation
- [x] Transactional WARDOGS server allocation and persisted lobby/server association
- [x] Normalized waiting and allocated-without-join states
- [x] Verified manual Join By ID support (`GET /v1/server-id`; live client lookup and player join verified)
- [x] Isolated production-shaped read-only WDRCON client for verified endpoints
- [x] WARDOGS adapter skeleton with per-build capability gating (read-only)
- [x] WARDOGS backend lobby/read model with CMP-owned roster persistence and observation reconciliation
- [x] Allocated WARDOGS lobby live synchronization (single read-only worker, stale cache, private Socket.IO update, authenticated HTTP recovery)
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
- [x] Admin-confirmed three-faction results, append-only history, and audited corrections
- [ ] Production results presentation with verified outcome source
- [x] Isolated Hybrid assignment algorithm
- [x] WARDOGS individual rating policy and replay contract designed
- [x] Explicit authoritative placement groups on WARDOGS result revisions, including tie for second
- [ ] WARDOGS rating calculation, immutable ledger, and deterministic replay
- [ ] Player-facing WARDOGS rating and per-match delta
- [x] Backend integration (public beta queue, persisted WARDOGS allocation and lobby read with verified manual Join By ID)
