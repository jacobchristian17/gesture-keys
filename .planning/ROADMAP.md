# Roadmap: Gesture Keys

## Milestones

- [x] **v1.0 MVP** -- Phases 1-3 (shipped 2026-03-21)
- [x] **v1.1 Distance Threshold and Swiping Gestures** -- Phases 4-7 (shipped 2026-03-21)
- [x] **v1.2 Continuous and Seamless Commands** -- Phases 8-10 (shipped 2026-03-24)
- [x] **v1.3 Left Hand Support** -- Phases 11-13 (shipped 2026-03-24)
- [x] **v2.0 Structured Gesture Architecture** -- Phases 14-17 (shipped 2026-03-26)
- [ ] **v3.0 Tri-State Gesture Model + Action Library** -- Phases 18-24

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

<details>
<summary>v2.0 Structured Gesture Architecture (Phases 14-17) -- SHIPPED 2026-03-26</summary>

- [x] **Phase 14: Shared Types and Pipeline Unification** - 2/2 plans -- completed 2026-03-24
- [x] **Phase 15: Gesture Orchestrator** - 2/2 plans -- completed 2026-03-24
- [x] **Phase 16: Action Dispatch and Fire Modes** - 3/3 plans -- completed 2026-03-25
- [x] **Phase 17: Activation Gate** - 2/2 plans -- completed 2026-03-25

</details>

### v3.0 Tri-State Gesture Model + Action Library

- [x] **Phase 18: Trigger Parser and Data Model** - 1 plan (completed 2026-03-26)
- [x] **Phase 19: MotionDetector** - 1 plan - Continuous per-frame motion detection replacing SwipeDetector internals (completed 2026-03-26)
- [x] **Phase 20: Config Loader for Actions** - New `actions:` config section parsing and orchestrator input derivation (completed 2026-03-26)
- [ ] **Phase 21: Orchestrator Refactor** - Remove swipe states, add motion and sequence signals
- [ ] **Phase 22: ActionResolver and Dispatcher Update** - Resolve and dispatch all new signal types
- [ ] **Phase 23: Pipeline Integration** - Wire MotionDetector and new signals through the full pipeline
- [ ] **Phase 24: Cleanup and Config Migration** - Delete swipe.py, convert config, remove legacy code

## Phase Details

### Phase 18: Trigger Parser and Data Model
**Goal**: Users can express any gesture trigger as a compact string that the system validates and parses into structured data
**Depends on**: Nothing (independent foundation)
**Requirements**: TRIG-01, TRIG-02, TRIG-03, TRIG-04, TRIG-05
**Success Criteria** (what must be TRUE):
  1. A trigger string like `fist:static` parses into a structured object with gesture=fist, state=static
  2. A trigger string like `open_palm:moving:left` parses into gesture=open_palm, state=moving, direction=left
  3. A sequence trigger string like `fist > open_palm` parses into a two-gesture sequence with both gestures identified
  4. An invalid trigger string (e.g., `fist:invalid_state`, `fist:moving` without direction) raises a clear validation error with the bad token identified
**Plans:** 1/1 plans complete
Plans:
- [x] 18-01-PLAN.md -- Trigger data model (enums, dataclasses) and parser with TDD

### Phase 19: MotionDetector
**Goal**: System continuously reports per-frame motion state and direction from hand landmarks without maintaining gesture-level state
**Depends on**: Nothing (independent foundation, parallel with Phase 18)
**Requirements**: MOTN-01, MOTN-02, MOTN-03, MOTN-04
**Success Criteria** (what must be TRUE):
  1. Given consecutive frames with hand movement, MotionDetector reports moving=True with a cardinal direction (left, right, up, down)
  2. Given consecutive frames with a stationary hand, MotionDetector reports moving=False
  3. Rapid jitter near the motion threshold does not cause flickering between moving/not-moving (hysteresis works)
  4. A hand appearing in frame for the first time does not trigger false motion detection (settling frames applied)
**Plans:** 1/1 plans complete
Plans:
- [ ] 19-01-PLAN.md -- MotionDetector and MotionState with TDD (hysteresis, settling, direction classification)

### Phase 20: Config Loader for Actions
**Goal**: Users can define all gesture-to-key mappings in a single `actions:` config section with trigger strings, replacing separate gestures/swipe sections
**Depends on**: Phase 18 (trigger parser for validating trigger strings)
**Requirements**: CONF-01, CONF-02, CONF-03, CONF-04, CONF-05
**Success Criteria** (what must be TRUE):
  1. User can write an action entry with name, trigger string, and key in `actions:` and the system loads it
  2. User can set per-action cooldown and bypass_gate overrides that take effect
  3. System derives gesture_modes, cooldown maps, and gate bypass sets from action definitions (no manual orchestrator config needed)
  4. Old `gestures:` and `swipe:` config sections are no longer read or required
**Plans:** 2/2 plans complete
Plans:
- [ ] 20-01-PLAN.md -- ActionEntry dataclass and parse_actions() with TDD
- [ ] 20-02-PLAN.md -- Derive orchestrator inputs, wire into load_config, convert config.yaml

### Phase 21: Orchestrator Refactor
**Goal**: Orchestrator FSM handles motion and sequence triggers natively, with swipe-related states and signals removed
**Depends on**: Phase 18 (trigger data model for sequence definitions)
**Requirements**: ORCH-01, ORCH-02, ORCH-03, ORCH-04
**Success Criteria** (what must be TRUE):
  1. Orchestrator accepts a motion_state parameter per frame and emits MOVING_FIRE when a gesture is held while moving in a direction that matches a trigger
  2. Orchestrator tracks recent gestures and emits SEQUENCE_FIRE when two gestures match a registered sequence within the time window
  3. SWIPE_WINDOW, SWIPING, and COMPOUND_FIRE states/signals no longer exist in the codebase
  4. Sequence window duration is configurable (default 0.5s)
**Plans:** 2 plans
Plans:
- [ ] 21-01-PLAN.md -- Strip all swipe code from orchestrator FSM and tests
- [ ] 21-02-PLAN.md -- Add MOVING_FIRE and SEQUENCE_FIRE signals with TDD

### Phase 22: ActionResolver and Dispatcher Update
**Goal**: ActionResolver and ActionDispatcher handle all four trigger types (static, holding, moving, sequence) and old compound fire code is removed
**Depends on**: Phase 18 (trigger data model for lookup map construction)
**Requirements**: ACTN-01, ACTN-02, ACTN-03
**Success Criteria** (what must be TRUE):
  1. ActionResolver resolves static, holding, moving, and sequence triggers to their configured actions via separate lookup maps
  2. ActionDispatcher receives MOVING_FIRE and SEQUENCE_FIRE signals and dispatches the correct keystrokes
  3. Old compound fire handling code is removed from both resolver and dispatcher
**Plans**: TBD

### Phase 23: Pipeline Integration
**Goal**: Full pipeline uses MotionDetector and new signal types end-to-end, with all existing functionality preserved
**Depends on**: Phase 19 (MotionDetector), Phase 20 (config loader), Phase 21 (orchestrator), Phase 22 (resolver/dispatcher)
**Requirements**: INTG-01, INTG-02, INTG-03, INTG-04
**Success Criteria** (what must be TRUE):
  1. Pipeline instantiates MotionDetector instead of SwipeDetector and calls it every frame
  2. Pipeline passes motion_state from MotionDetector to orchestrator on every frame
  3. FrameResult contains motion_state (moving bool + direction) instead of the old swiping boolean
  4. Activation gate correctly gates MOVING_FIRE and SEQUENCE_FIRE signals (fires only when gate is open or bypass is set)
**Plans**: TBD

### Phase 24: Cleanup and Config Migration
**Goal**: All legacy swipe code and config formats are removed, leaving a clean codebase with only the tri-state model
**Depends on**: Phase 23 (integration complete, all tests passing with new system)
**Requirements**: CLNP-01, CLNP-02, CLNP-03
**Success Criteria** (what must be TRUE):
  1. swipe.py and test_swipe.py are deleted and no file in the project imports from them
  2. config.yaml uses the new `actions:` format with no `gestures:` or `swipe:` sections
  3. Config parsing code in config.py has no references to old gestures/swipe field names
**Plans**: TBD

## Progress

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
| 14. Shared Types and Pipeline Unification | v2.0 | 2/2 | Complete | 2026-03-24 |
| 15. Gesture Orchestrator | v2.0 | 2/2 | Complete | 2026-03-24 |
| 16. Action Dispatch and Fire Modes | v2.0 | 3/3 | Complete | 2026-03-25 |
| 17. Activation Gate | v2.0 | 2/2 | Complete | 2026-03-25 |
| 18. Trigger Parser and Data Model | v3.0 | 1/1 | Complete | 2026-03-26 |
| 19. MotionDetector | 1/1 | Complete    | 2026-03-26 | - |
| 20. Config Loader for Actions | 2/2 | Complete    | 2026-03-26 | - |
| 21. Orchestrator Refactor | v3.0 | 0/2 | Not started | - |
| 22. ActionResolver and Dispatcher Update | v3.0 | 0/? | Not started | - |
| 23. Pipeline Integration | v3.0 | 0/? | Not started | - |
| 24. Cleanup and Config Migration | v3.0 | 0/? | Not started | - |
