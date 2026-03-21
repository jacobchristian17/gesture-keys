# Roadmap: Gesture Keys

## Milestones

- ✅ **v1.0 MVP** -- Phases 1-3 (shipped 2026-03-21)
- 🚧 **v1.1 Distance Threshold and Swiping Gestures** -- Phases 4-7 (in progress)

## Phases

<details>
<summary>v1.0 MVP (Phases 1-3) -- SHIPPED 2026-03-21</summary>

- [x] **Phase 1: Detection and Preview** - 3/3 plans -- completed 2026-03-21
- [x] **Phase 2: Gesture-to-Keystroke Pipeline** - 2/2 plans -- completed 2026-03-21
- [x] **Phase 3: System Tray and Background Operation** - 2/2 plans -- completed 2026-03-21

</details>

### v1.1 Distance Threshold and Swiping Gestures

- [ ] **Phase 4: Distance Gating** - Filter gestures by hand proximity using palm span threshold
- [ ] **Phase 5: Swipe Detection** - Detect four cardinal swipe directions as new gesture types
- [ ] **Phase 6: Integration and Mutual Exclusion** - Wire distance and swipe into pipeline with cross-fire prevention
- [ ] **Phase 7: Preview Overlays and Calibration** - Visual feedback for distance values and swipe events in preview window

## Phase Details

### Phase 4: Distance Gating
**Goal**: Users can gate gesture detection by hand distance from camera so gestures only fire when the hand is close enough
**Depends on**: Phase 3 (v1.0 complete)
**Requirements**: DIST-01, DIST-02
**Success Criteria** (what must be TRUE):
  1. User can set a `min_hand_size` threshold in config.yaml and gestures are ignored when the hand is too far away
  2. User can enable/disable distance gating in config without removing threshold values
  3. Existing static gestures continue to work exactly as before when distance gating is disabled or hand is within range
**Plans:** 2 plans
Plans:
- [ ] 04-01-PLAN.md -- DistanceFilter class and config integration (TDD)
- [ ] 04-02-PLAN.md -- Wire DistanceFilter into both detection loops

### Phase 5: Swipe Detection
**Goal**: Users can perform directional hand swipes that fire mapped keyboard commands, expanding the gesture vocabulary beyond static poses
**Depends on**: Phase 4
**Requirements**: SWIPE-01, SWIPE-02, SWIPE-03, SWIPE-04
**Success Criteria** (what must be TRUE):
  1. User can swipe their hand left, right, up, or down and each direction is detected as a distinct gesture
  2. User can map each swipe direction to a keyboard command in config.yaml using the same format as static gestures
  3. Swipes fire once per motion with a cooldown that prevents double-firing on a single swipe movement
  4. Swipe detection works regardless of what hand pose the user holds during the swipe
  5. Casual hand repositioning and MediaPipe landmark jitter do not trigger false swipe detections
**Plans**: TBD

### Phase 6: Integration and Mutual Exclusion
**Goal**: Distance gating and swipe detection work together with static gestures without cross-firing or interference
**Depends on**: Phase 5
**Requirements**: INT-01, INT-02
**Success Criteria** (what must be TRUE):
  1. Swiping the hand does not trigger static gesture keystrokes even though the hand passes through recognizable poses mid-swipe
  2. Holding a static pose does not trigger false swipe events even though the wrist has minor movement
  3. When the hand is beyond the distance threshold, neither static gestures nor swipes fire
  4. Transitioning between swipe motion and held pose resolves cleanly without stuck states or missed gestures
**Plans**: TBD

### Phase 7: Preview Overlays and Calibration
**Goal**: Users can see live distance and swipe feedback in the preview window to calibrate thresholds for their specific setup
**Depends on**: Phase 6
**Requirements**: DIST-03, SWIPE-05
**Success Criteria** (what must be TRUE):
  1. Preview window displays the current palm span value so the user can determine what `min_hand_size` threshold to set
  2. Preview window shows a clear indicator when the hand is detected but filtered out by distance gating
  3. Preview window displays the detected swipe direction when a swipe fires
**Plans**: TBD

## Progress

**Execution Order:** 4 -> 5 -> 6 -> 7

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Detection and Preview | v1.0 | 3/3 | Complete | 2026-03-21 |
| 2. Gesture-to-Keystroke Pipeline | v1.0 | 2/2 | Complete | 2026-03-21 |
| 3. System Tray and Background Operation | v1.0 | 2/2 | Complete | 2026-03-21 |
| 4. Distance Gating | v1.1 | 0/2 | Planning | - |
| 5. Swipe Detection | v1.1 | 0/? | Not started | - |
| 6. Integration and Mutual Exclusion | v1.1 | 0/? | Not started | - |
| 7. Preview Overlays and Calibration | v1.1 | 0/? | Not started | - |
