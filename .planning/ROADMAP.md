# Roadmap: Gesture Keys

## Milestones

- [x] **v1.0 MVP** -- Phases 1-3 (shipped 2026-03-21)
- [x] **v1.1 Distance Threshold and Swiping Gestures** -- Phases 4-7 (shipped 2026-03-21)
- [x] **v1.2 Continuous and Seamless Commands** -- Phases 8-10 (shipped 2026-03-24)
- [ ] **v1.3 Left Hand Support** -- Phases 11-13 (in progress)

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

### v1.3 Left Hand Support (In Progress)

**Milestone Goal:** Add left-hand gesture detection with 1:1 feature parity to the right hand, one hand active at a time, with optional separate key mappings.

- [ ] **Phase 11: Left Hand Detection and Classification** - 2 plans - Detect left hand via MediaPipe and classify all gestures with right-hand parity
- [ ] **Phase 12: Left Hand Configuration** - Mirror right-hand mappings by default with optional separate left-hand overrides
- [ ] **Phase 13: Preview and Polish** - Show active hand in preview overlay and verify end-to-end left hand workflow

## Phase Details

### Phase 11: Left Hand Detection and Classification
**Goal**: Left hand triggers the same gestures as the right hand through the existing pipeline
**Depends on**: Nothing (first phase of v1.3)
**Requirements**: DET-01, DET-02, DET-03, CLS-01, CLS-02, CLS-03
**Success Criteria** (what must be TRUE):
  1. Left hand in frame is detected and its landmarks are tracked by MediaPipe
  2. All 6 static gestures (open palm, fist, thumbs up, peace, pointing, pinch) classify correctly with left hand
  3. All 4 swipe directions (left, right, up, down) detect correctly with left hand using absolute directions
  4. When only one hand is visible, that hand is the active hand regardless of left or right
  5. When both hands are briefly visible during a switch, the app settles on one hand without firing spurious gestures
**Plans**: 2 plans

Plans:
- [ ] 11-01-PLAN.md — Extend HandDetector for both-hand detection with active hand selection and preferred_hand config
- [ ] 11-02-PLAN.md — Left-hand classification parity tests and hand-switch pipeline integration

### Phase 12: Left Hand Configuration
**Goal**: Users can control left hand key mappings through config.yaml with sensible defaults
**Depends on**: Phase 11
**Requirements**: CFG-01, CFG-02, CFG-03
**Success Criteria** (what must be TRUE):
  1. With no config changes, left hand fires the same key mappings as right hand
  2. User can add a left_hand_gestures section in config.yaml to define separate left-hand mappings
  3. Editing and saving config.yaml hot-reloads left-hand mappings without restarting the app
**Plans**: TBD

Plans:
- [ ] 12-01: TBD

### Phase 13: Preview and Polish
**Goal**: Users can visually confirm which hand is active and the full left-hand workflow is verified end-to-end
**Depends on**: Phase 12
**Requirements**: PRV-01
**Success Criteria** (what must be TRUE):
  1. Preview overlay displays which hand (left or right) is currently active
  2. Switching hands in front of the camera updates the active hand indicator in real time
**Plans**: TBD

Plans:
- [ ] 13-01: TBD

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
| 11. Left Hand Detection and Classification | 1/2 | In Progress|  | - |
| 12. Left Hand Configuration | v1.3 | 0/? | Not started | - |
| 13. Preview and Polish | v1.3 | 0/? | Not started | - |
