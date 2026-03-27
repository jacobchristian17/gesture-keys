# Roadmap: Gesture Keys

## Milestones

- ✅ **v1.0 MVP** - Phases 1-3 (shipped 2026-03-21)
- ✅ **v1.1 Distance Gating & Swipes** - Phases 4-6 (shipped 2026-03-22)
- ✅ **v1.2 Continuous and Seamless Commands** - Phases 8-10 (shipped 2026-03-23)
- ✅ **v1.3 Left Hand Support** - Phases 11-13 (shipped 2026-03-24)
- ✅ **v2.0 Structured Gesture Architecture** - Phases 14-16 (shipped 2026-03-25)
- ✅ **v3.0 Tri-State Gesture Model** - Phases 17-24 (shipped 2026-03-26)
- 🚧 **v3.1 Moving Fire Dispatch Throttling** - Phase 25 (in progress)

## Phases

- [ ] **Phase 25: Dispatch Throttling** - Configurable rate-limiting for moving_fire dispatches with global default and per-action overrides

## Phase Details

### Phase 25: Dispatch Throttling
**Goal**: Users can control how frequently moving_fire triggers dispatch during continuous motion
**Depends on**: Phase 24 (v3.0 complete)
**Requirements**: THRT-01, THRT-02, THRT-03
**Success Criteria** (what must be TRUE):
  1. User can set a global `dispatch_interval` in config.yaml and moving_fire actions throttle to that rate during continuous motion
  2. User can override the dispatch interval on a specific moving trigger action and that action throttles independently of the global default
  3. When a moving_fire dispatch is skipped due to throttling, no keystroke is sent and the next dispatch fires as soon as the interval elapses
  4. Existing moving_fire behavior is unchanged when no dispatch_interval is configured (backward compatible)
**Plans**: TBD

Plans:
- [ ] 25-01: TBD

## Progress

**Execution Order:**
Phase 25 is the only phase in this milestone.

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 25. Dispatch Throttling | v3.1 | 0/? | Not started | - |
