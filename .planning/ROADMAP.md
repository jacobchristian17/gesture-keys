# Roadmap: Gesture Keys

## Milestones

- ✅ **v1.0 MVP** - Phases 1-3 (shipped 2026-03-21)
- ✅ **v1.1 Distance Gating & Swipes** - Phases 4-6 (shipped 2026-03-22)
- ✅ **v1.2 Continuous and Seamless Commands** - Phases 8-10 (shipped 2026-03-23)
- ✅ **v1.3 Left Hand Support** - Phases 11-13 (shipped 2026-03-24)
- ✅ **v2.0 Structured Gesture Architecture** - Phases 14-16 (shipped 2026-03-25)
- ✅ **v3.0 Tri-State Gesture Model** - Phases 17-24 (shipped 2026-03-26)
- ✅ **v3.1 Moving Fire Dispatch Throttling** - Phase 25 (shipped 2026-03-27)
- ✅ **v3.2 Unified Preview & Exec Mode** - Phases 26-28 (shipped 2026-03-31)
- 🚧 **v1.0.1 Scroll Gesture Support** - Phases 29-33 (in progress)

## Phases

<details>
<summary>✅ v3.2 Unified Preview & Exec Mode (Phases 26-28) — SHIPPED 2026-03-31</summary>

- [x] Phase 26: Logging Consolidation (1/1 plans) — completed 2026-03-30
- [x] Phase 27: Entry Point Refactor (1/1 plans) — completed 2026-03-30
- [x] Phase 28: Tray View Camera (1/1 plans) — completed 2026-03-30

</details>

### 🚧 v1.0.1 Scroll Gesture Support (In Progress)

**Milestone Goal:** Add mouse scroll events as a new fire mode, triggered by holding a gesture and moving the hand in any cardinal direction, with velocity-based scroll speed.

- [ ] **Phase 29: ScrollSender** - Pure scroll dispatch class with velocity-to-ticks mapping and direction routing
- [ ] **Phase 30: Fire Mode & Config** - FireMode.SCROLL enum, config parsing, and scroll tuning parameters
- [ ] **Phase 31: Dispatcher Integration** - ActionDispatcher scroll branch with continuous dispatch and safety stop
- [ ] **Phase 32: Pipeline Wiring & Logging** - ScrollSender instantiation in Pipeline and scroll event logging
- [ ] **Phase 33: Default Config** - Default config.yaml scroll actions for all 4 directions

## Phase Details

### Phase 29: ScrollSender
**Goal**: Users can scroll vertically and horizontally with velocity-proportional speed via a tested scroll dispatch component
**Depends on**: Nothing (pure new code, no existing files change)
**Requirements**: SCROLL-03, SCROLL-04, SCROLL-05
**Success Criteria** (what must be TRUE):
  1. ScrollSender converts hand direction (up/down/left/right) to correct pynput scroll axis calls
  2. Faster hand velocity produces more scroll ticks per dispatch (velocity-proportional)
  3. WHEEL_DELTA multiplier is accounted for — raw velocity values do not produce catastrophic scroll speed
  4. Velocity jitter at low speeds is smoothed before tick calculation
**Plans**: TBD

### Phase 30: Fire Mode & Config
**Goal**: Users can configure scroll actions in YAML with explicit fire_mode, scroll_speed, and min/max bounds without requiring a key field
**Depends on**: Phase 29
**Requirements**: SCROLL-01, SCROLL-02, SCROLL-07, SCROLL-08, SCROLL-09
**Success Criteria** (what must be TRUE):
  1. User can set `fire_mode: scroll` on any gesture's moving trigger in config.yaml
  2. Config validation accepts scroll actions without a `key` field and rejects non-scroll actions missing `key`
  3. User can set `scroll_speed` per action to control velocity-to-scroll multiplier
  4. Acceleration curve gives precise control at slow hand speeds and rapid scrolling at fast speeds
  5. User can configure min/max scroll step bounds to prevent micro-scrolls or runaway scroll
**Plans**: TBD

### Phase 31: Dispatcher Integration
**Goal**: Scroll events fire continuously while hand moves and stop immediately when hand stops or gesture is released
**Depends on**: Phase 29, Phase 30
**Requirements**: SCROLL-06, SCROLL-10
**Success Criteria** (what must be TRUE):
  1. Scroll fires continuously at ~20 events/sec (dispatch_interval ~0.05s) while hand is in motion
  2. Scroll stops immediately when hand stops moving — no residual scroll events
  3. Scroll stops immediately when gesture is released — no runaway scroll on any exit path
  4. hold_key actions on the same gesture do not conflict with scroll dispatch
**Plans**: TBD

### Phase 32: Pipeline Wiring & Logging
**Goal**: ScrollSender is integrated into the Pipeline lifecycle with proper logging for debugging and tuning
**Depends on**: Phase 31
**Requirements**: SCROLL-11
**Success Criteria** (what must be TRUE):
  1. ScrollSender is instantiated once in Pipeline.start() and injected into ActionDispatcher
  2. Hot-reload resets scroll state cleanly without stale state
  3. Scroll events are logged with direction, velocity, and step count at debug level
**Plans**: TBD

### Phase 33: Default Config
**Goal**: Users get working scroll out of the box with sensible defaults for pinch gesture in all 4 directions
**Depends on**: Phase 32
**Requirements**: SCROLL-12
**Success Criteria** (what must be TRUE):
  1. Default config.yaml includes pinch scroll actions for up, down, left, and right directions
  2. Default scroll_speed and dispatch_interval values produce smooth, usable scrolling without tuning
  3. End-to-end scroll works with default config — hold pinch, move hand, content scrolls
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 29 → 30 → 31 → 32 → 33

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 26. Logging Consolidation | v3.2 | 1/1 | Complete | 2026-03-30 |
| 27. Entry Point Refactor | v3.2 | 1/1 | Complete | 2026-03-30 |
| 28. Tray View Camera | v3.2 | 1/1 | Complete | 2026-03-30 |
| 29. ScrollSender | v1.0.1 | 0/0 | Not started | - |
| 30. Fire Mode & Config | v1.0.1 | 0/0 | Not started | - |
| 31. Dispatcher Integration | v1.0.1 | 0/0 | Not started | - |
| 32. Pipeline Wiring & Logging | v1.0.1 | 0/0 | Not started | - |
| 33. Default Config | v1.0.1 | 0/0 | Not started | - |
