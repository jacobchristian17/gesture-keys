# Roadmap: Gesture Keys

## Milestones

- ✅ **v1.0 MVP** -- Phases 1-3 (shipped 2026-03-21)
- ✅ **v1.1 Distance Threshold and Swiping Gestures** -- Phases 4-7 (shipped 2026-03-21)
- 🚧 **v1.2 Continuous and Seamless Commands** -- Phases 8-10 (in progress)

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

### v1.2 Continuous and Seamless Commands

- [ ] **Phase 8: Direct Gesture Transitions** - 2 plans
  - [ ] 08-01-PLAN.md -- TDD: direct transition state machine (COOLDOWN->ACTIVATING for different gestures)
  - [ ] 08-02-PLAN.md -- Debounce state preview indicator + wiring
- [ ] **Phase 9: Swipe/Static Transition Latency** - 2 plans
  - [ ] 09-01-PLAN.md -- Fix swipe-exit reset bug + hot-reload smoother reset (LAT-02)
  - [ ] 09-02-PLAN.md -- Reduce settling frames to 3 + latency budget verification (LAT-03, LAT-01)
- [ ] **Phase 10: Tuned Defaults and Config Surface** - 4 plans
  - [x] 10-01-PLAN.md -- Update code defaults to tuned values + settling_frames config surface (TUNE-01, TUNE-02)
  - [x] 10-02-PLAN.md -- Per-gesture cooldown overrides in config.yaml (TUNE-03)
  - [x] 10-03-PLAN.md -- Gap closure: static gesture priority over swipe detection (UAT fix)
  - [ ] 10-04-PLAN.md -- Gap closure: hand-entry settling guard + remove destructive pipeline reset

## Phase Details

### Phase 8: Direct Gesture Transitions
**Goal**: Users can switch between static gestures fluidly -- each new gesture fires immediately without dropping the hand to neutral first
**Depends on**: Phase 7 (v1.1 complete)
**Requirements**: TRANS-01, TRANS-02, TRANS-03
**Plans:** 2 plans
**Success Criteria** (what must be TRUE):
  1. User can switch from one static gesture to a different static gesture and the new gesture fires its mapped keystroke without the user needing to release their hand to "none" first
  2. Holding the same gesture continuously (through and beyond cooldown) produces exactly one keystroke fire -- no repeat-fire on sustained hold
  3. Preview window displays the current debounce state (IDLE / ACTIVATING / COOLDOWN) so the user can see why a gesture has or has not fired
  4. Transitional hand poses during gesture switches (e.g., passing through POINTING when going from FIST to PEACE) do not cause spurious extra fires

### Phase 9: Swipe/Static Transition Latency
**Goal**: Switching from a swipe back to a static gesture feels responsive -- the static gesture fires within ~300ms of swipe cooldown ending instead of the current ~1.3s delay
**Depends on**: Phase 7 (v1.1 complete); independent of Phase 8
**Requirements**: LAT-01, LAT-02, LAT-03
**Plans:** 2 plans
**Success Criteria** (what must be TRUE):
  1. After completing a swipe and its cooldown, holding a static gesture fires within approximately 300ms (down from ~1.3s)
  2. The smoother and debouncer are properly reset when transitioning from swipe mode back to static mode (no stale state carrying over)
  3. Settling frames after swipe cooldown are reduced to 3-5 frames without causing false static fires from residual hand motion
  4. Existing swipe detection accuracy and mutual exclusion with static gestures are not degraded by the latency reduction

### Phase 10: Tuned Defaults and Config Surface
**Goal**: New users get a responsive out-of-box experience with proven timing defaults, and power users can fine-tune settling frames and per-gesture cooldowns via config.yaml
**Depends on**: Phase 8, Phase 9 (structural changes must be stable before tuning)
**Requirements**: TUNE-01, TUNE-02, TUNE-03
**Plans:** 4 plans

Plans:
- [x] 10-01-PLAN.md -- Update code defaults to tuned values + settling_frames config surface (TUNE-01, TUNE-02)
- [x] 10-02-PLAN.md -- Per-gesture cooldown overrides in config.yaml (TUNE-03)
- [x] 10-03-PLAN.md -- Gap closure: static gesture priority over swipe detection (UAT fix)
- [ ] 10-04-PLAN.md -- Gap closure: hand-entry settling guard + remove destructive pipeline reset

## Progress

**Execution Order:** 8 -> 9 -> 10 (8 and 9 are independent but sequential for simplicity; 10 depends on both)

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Detection and Preview | v1.0 | 3/3 | Complete | 2026-03-21 |
| 2. Gesture-to-Keystroke Pipeline | v1.0 | 2/2 | Complete | 2026-03-21 |
| 3. System Tray and Background Operation | v1.0 | 2/2 | Complete | 2026-03-21 |
| 4. Distance Gating | v1.1 | 2/2 | Complete | 2026-03-21 |
| 5. Swipe Detection | v1.1 | 2/2 | Complete | 2026-03-21 |
| 6. Integration and Mutual Exclusion | v1.1 | 4/4 | Complete | 2026-03-21 |
| 7. Preview Overlays and Calibration | v1.1 | 0/? | Complete | 2026-03-21 |
| 8. Direct Gesture Transitions | v1.2 | 0/2 | Planning | - |
| 9. Swipe/Static Transition Latency | v1.2 | 0/2 | Planning | - |
| 10. Tuned Defaults and Config Surface | v1.2 | 3/4 | In Progress | - |
