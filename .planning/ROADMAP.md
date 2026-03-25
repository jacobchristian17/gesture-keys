# Roadmap: Gesture Keys

## Milestones

- [x] **v1.0 MVP** -- Phases 1-3 (shipped 2026-03-21)
- [x] **v1.1 Distance Threshold and Swiping Gestures** -- Phases 4-7 (shipped 2026-03-21)
- [x] **v1.2 Continuous and Seamless Commands** -- Phases 8-10 (shipped 2026-03-24)
- [x] **v1.3 Left Hand Support** -- Phases 11-13 (shipped 2026-03-24)
- [ ] **v2.0 Structured Gesture Architecture** -- Phases 14-17 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-3) -- SHIPPED 2026-03-21</summary>

- [x] **Phase 1: Detection and Preview** - 3/3 plans -- completed 2026-03-21
- [x] **Phase 2: Gesture-to-Keystroke Pipeline** - 2/2 plans -- completed 2026-03-21
- [x] **Phase 3: System Tray and Background Operation** - 2/2 plans -- completed 2026-03-21

</details>

<details>
<summary>v1.1 Distance Threshold and Swiping Gestures (Phases 4-7) -- SHIPPED 2026-03-21</summary>

- [x] **Phase 4: Distance Gating** - 2/2 plans -- completed 2026-03-21
- [x] **Phase 5: Swipe Detection** - 2/2 plans -- completed 2026-03-21
- [x] **Phase 6: Integration and Mutual Exclusion** - 4/4 plans -- completed 2026-03-21
- [x] **Phase 7: Preview Overlays and Calibration** - completed 2026-03-21

</details>

<details>
<summary>v1.2 Continuous and Seamless Commands (Phases 8-10) -- SHIPPED 2026-03-24</summary>

- [x] **Phase 8: Direct Gesture Transitions** - 2/2 plans -- completed 2026-03-22
- [x] **Phase 9: Swipe/Static Transition Latency** - 2/2 plans -- completed 2026-03-23
- [x] **Phase 10: Tuned Defaults and Config Surface** - 4/4 plans -- completed 2026-03-23

</details>

<details>
<summary>v1.3 Left Hand Support (Phases 11-13) -- SHIPPED 2026-03-24</summary>

- [x] **Phase 11: Left Hand Detection and Classification** - 2/2 plans -- completed 2026-03-23
- [x] **Phase 12: Left Hand Configuration** - 2/2 plans -- completed 2026-03-24
- [x] **Phase 13: Preview and Polish** - 1/1 plan -- completed 2026-03-24

</details>

### v2.0 Structured Gesture Architecture (In Progress)

**Milestone Goal:** Clean rewrite of the gesture pipeline with activation gating, gesture hierarchy (static + temporal states), and action-based dispatch with multiple fire modes.

- [x] **Phase 14: Shared Types and Pipeline Unification** - Eliminate duplicated loop logic with shared data types and a unified pipeline class (completed 2026-03-24)
- [x] **Phase 15: Gesture Orchestrator** - Unified state machine replacing debouncer and main-loop coordination (completed 2026-03-24)
- [x] **Phase 16: Action Dispatch and Fire Modes** - Structured gesture-to-action mapping with tap and hold_key fire modes (gap closure in progress) (completed 2026-03-25)
- [ ] **Phase 17: Activation Gate** - Gesture-based arm/disarm gating with configurable bypass

## Phase Details

### Phase 14: Shared Types and Pipeline Unification
**Goal**: Both preview and tray modes run through a single unified pipeline with shared data types, eliminating 90% code duplication between __main__.py and tray.py
**Depends on**: Phase 13 (v1.3 complete)
**Requirements**: PIPE-01, PIPE-02, PIPE-03, PIPE-04
**Success Criteria** (what must be TRUE):
  1. Running `--preview` mode uses the unified Pipeline class and produces identical detection behavior to v1.3
  2. Running tray mode uses the same unified Pipeline class and fires the same keystrokes as v1.3 for all gestures
  3. Preview mode wrapper is under 80 lines (down from ~570) and tray mode wrapper is under 50 lines (down from ~515)
  4. All existing tests pass against the new pipeline without modification to test assertions
  5. Hot-reload (config edit while running) works through Pipeline.reload_config() in both modes
**Plans:** 2/2 plans complete
Plans:
- [ ] 14-01-PLAN.md -- Create FrameResult dataclass and unified Pipeline class
- [ ] 14-02-PLAN.md -- Rewrite preview and tray wrappers to use Pipeline

### Phase 15: Gesture Orchestrator
**Goal**: A single GestureOrchestrator state machine manages all gesture type prioritization and state transitions, replacing GestureDebouncer and scattered main-loop coordination
**Depends on**: Phase 14
**Requirements**: ORCH-01, ORCH-02, ORCH-03, ORCH-04, ORCH-05
**Success Criteria** (what must be TRUE):
  1. Static gestures (open palm, fist, thumbs up, peace, pointing, pinch) fire with the same timing and reliability as v1.3
  2. Holding a static gesture past a configurable threshold transitions to the hold temporal state and emits a distinct signal
  3. Swiping while holding a static gesture transitions to the swiping temporal state with the correct direction
  4. The orchestrator prevents conflicting states (no simultaneous hold + swipe, no swipe without a base gesture)
  5. All v1.3 edge-case behaviors preserved: direct gesture transitions, static-first priority gate, swipe-exit reset, per-gesture cooldowns
**Plans:** 2/2 plans complete
Plans:
- [ ] 15-01-PLAN.md -- TDD: Build GestureOrchestrator hierarchical FSM with full test coverage
- [ ] 15-02-PLAN.md -- Wire orchestrator into Pipeline, delete debounce.py

### Phase 16: Action Dispatch and Fire Modes
**Goal**: Gestures map to keyboard actions through a structured resolver with tap (press+release) and hold_key (sustained keypress) fire modes, with guaranteed stuck-key prevention
**Depends on**: Phase 15
**Requirements**: ACTN-01, ACTN-02, ACTN-03, ACTN-04, ACTN-05
**Success Criteria** (what must be TRUE):
  1. Config file supports structured gesture-to-action mappings where static gesture x temporal state resolves to a specific keyboard command and fire mode
  2. Tap fire mode presses and releases a key once when the action triggers (same as current v1.3 behavior)
  3. Hold_key fire mode holds a key down while the gesture is sustained and releases it on gesture change, hand switch, distance exit, or app toggle
  4. No stuck keys remain after any exit path: gesture change, gate expiry, hand switch, distance out-of-range, app toggle off, config reload
  5. Per-hand action mappings work (left hand can map different actions than right hand for the same gesture)
**Plans:** 3/3 plans complete
Plans:
- [x] 16-01-PLAN.md -- TDD: Build ActionResolver and ActionDispatcher with full test coverage
- [x] 16-02-PLAN.md -- Config fire_mode parsing and Pipeline integration
- [ ] 16-03-PLAN.md -- Gap closure: app-controlled tap-repeat for hold_key fire mode

### Phase 17: Activation Gate
**Goal**: Users can arm/disarm gesture detection with a configurable activation gesture, preventing accidental fires when not actively using the system
**Depends on**: Phase 16
**Requirements**: ACTV-01, ACTV-02, ACTV-03
**Success Criteria** (what must be TRUE):
  1. Performing the activation gesture (scout/peace by default) arms the system for a configurable duration, and gestures fire actions only while armed
  2. Bypass mode in config disables the activation gate entirely, preserving v1.x behavior as the default
  3. The activation gesture is consumed by the gate and does not fire its mapped action
  4. Gate expiry while a hold_key action is active releases the held key immediately (no stuck keys from gate timeout)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 14 -> 15 -> 16 -> 17

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Detection and Preview | v1.0 | 3/3 | Complete | 2026-03-21 |
| 2. Gesture-to-Keystroke Pipeline | v1.0 | 2/2 | Complete | 2026-03-21 |
| 3. System Tray and Background Operation | v1.0 | 2/2 | Complete | 2026-03-21 |
| 4. Distance Gating | v1.1 | 2/2 | Complete | 2026-03-21 |
| 5. Swipe Detection | v1.1 | 2/2 | Complete | 2026-03-21 |
| 6. Integration and Mutual Exclusion | v1.1 | 4/4 | Complete | 2026-03-21 |
| 7. Preview Overlays and Calibration | v1.1 | 0/? | Complete | 2026-03-21 |
| 8. Direct Gesture Transitions | v1.2 | 2/2 | Complete | 2026-03-22 |
| 9. Swipe/Static Transition Latency | v1.2 | 2/2 | Complete | 2026-03-23 |
| 10. Tuned Defaults and Config Surface | v1.2 | 4/4 | Complete | 2026-03-23 |
| 11. Left Hand Detection and Classification | v1.3 | 2/2 | Complete | 2026-03-23 |
| 12. Left Hand Configuration | v1.3 | 2/2 | Complete | 2026-03-24 |
| 13. Preview and Polish | v1.3 | 1/1 | Complete | 2026-03-24 |
| 14. Shared Types and Pipeline Unification | 2/2 | Complete    | 2026-03-24 | - |
| 15. Gesture Orchestrator | 2/2 | Complete    | 2026-03-24 | - |
| 16. Action Dispatch and Fire Modes | 3/3 | Complete    | 2026-03-25 | - |
| 17. Activation Gate | v2.0 | 0/? | Not started | - |
