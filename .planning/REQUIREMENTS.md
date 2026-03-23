# Requirements: Gesture Keys

**Defined:** 2026-03-22
**Milestone:** v1.2 -- Continuous and Seamless Commands
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v1.2 Requirements

Requirements for seamless gesture transitions, reduced mode-switching latency, and tuned defaults.

### Transitions

- [x] **TRANS-01**: User can switch directly from one static gesture to another and the new gesture fires without needing to return hand to neutral/"none" first
- [x] **TRANS-02**: Holding the same gesture through cooldown does NOT re-fire -- only a different gesture triggers direct transition
- [x] **TRANS-03**: Preview window displays current debounce state (IDLE/ACTIVATING/COOLDOWN) so user can see why a gesture hasn't fired yet

### Latency

- [x] **LAT-01**: Swipe-to-static transition fires a static gesture within ~300ms of swipe cooldown ending (down from ~1.3s)
- [x] **LAT-02**: Smoother and debouncer are NOT unnecessarily reset when transitioning from swipe to static mode
- [x] **LAT-03**: Settling frames after swipe cooldown are reduced from 10 to 3-5 frames

### Tuning

- [x] **TUNE-01**: Code defaults updated to match proven real-usage values (activation_delay ~0.15s, cooldown ~0.3s, smoothing_window ~2)
- [x] **TUNE-02**: Settling frames are configurable in config.yaml swipe section
- [x] **TUNE-03**: Per-gesture cooldown overrides are configurable in config.yaml (e.g., pinch gets longer cooldown than fist)

## v1.1 Requirements (Shipped)

### Distance Gating

- [x] **DIST-01**: User can configure a minimum hand size threshold in config.yaml to ignore hands too far from the camera
- [x] **DIST-02**: Gestures are only detected when the hand's palm span (wrist-to-MCP distance) exceeds the configured threshold
- [x] **DIST-03**: Preview window displays the current palm span value so the user can calibrate the distance threshold

### Swipe Gestures

- [x] **SWIPE-01**: User can perform swipe left, swipe right, swipe up, and swipe down hand movements that are detected as distinct gesture types
- [x] **SWIPE-02**: Each swipe direction can be mapped to a keyboard command in config.yaml, same as static gestures
- [x] **SWIPE-03**: Swipe detection uses wrist velocity tracking in a rolling buffer, firing once per swipe with its own cooldown
- [x] **SWIPE-04**: Swipe detection works with any hand pose (no pose gating required)
- [x] **SWIPE-05**: Preview window shows detected swipe direction as visual feedback

### Integration

- [x] **INT-01**: Swipe and static gesture detection are mutually exclusive -- swipe motion does not trigger static gestures, and held poses do not trigger false swipes
- [x] **INT-02**: Distance threshold gates both static gestures and swipe detection -- if hand is too far, neither fires

## Future Requirements

Deferred to later milestones:

- Auto-calibration of distance threshold across different webcams/FOVs
- Diagonal swipe directions (NE, NW, SE, SW)
- Swipe pose gating (require specific hand pose to trigger swipe)
- Swipe sensitivity profiles (fast vs slow swipe modes)
- Configurable transition mode toggle (legacy "require none" vs "direct transition")
- Adaptive activation delay (shorter for gesture-to-gesture vs none-to-gesture)
- Held-key mode (hold gesture = hold key down)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Custom gesture training / ML models | MediaPipe landmarks sufficient |
| Depth camera / hardware distance sensor | Palm span proxy is accurate enough for gating |
| Continuous gesture tracking (drag) | Discrete events only -- swipe fires once per motion |
| Gesture recording / replay | Out of scope |
| Zero-cooldown / instant repeat | Held gesture fires every frame, flooding OS with keystrokes |
| Simultaneous multi-gesture firing | Hand pose unreliable during motion, creates double-keystrokes |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRANS-01 | Phase 8 | Complete |
| TRANS-02 | Phase 8 | Complete |
| TRANS-03 | Phase 8 | Complete |
| LAT-01 | Phase 9 | Complete |
| LAT-02 | Phase 9 | Complete |
| LAT-03 | Phase 9 | Complete |
| TUNE-01 | Phase 10 | Complete |
| TUNE-02 | Phase 10 | Complete |
| TUNE-03 | Phase 10 | Complete |

**Coverage:**
- v1.2 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-03-22*
*Last updated: 2026-03-22 after roadmap creation*
