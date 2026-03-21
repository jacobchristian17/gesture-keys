# Requirements: Gesture Keys

**Defined:** 2026-03-21
**Milestone:** v1.1 — Distance Threshold and Swiping Gestures
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v1.1 Requirements

Requirements for distance gating and swipe gesture detection. Each maps to roadmap phases.

### Distance Gating

- [ ] **DIST-01**: User can configure a minimum hand size threshold in config.yaml to ignore hands too far from the camera
- [ ] **DIST-02**: Gestures are only detected when the hand's palm span (wrist-to-MCP distance) exceeds the configured threshold
- [ ] **DIST-03**: Preview window displays the current palm span value so the user can calibrate the distance threshold

### Swipe Gestures

- [ ] **SWIPE-01**: User can perform swipe left, swipe right, swipe up, and swipe down hand movements that are detected as distinct gesture types
- [ ] **SWIPE-02**: Each swipe direction can be mapped to a keyboard command in config.yaml, same as static gestures
- [ ] **SWIPE-03**: Swipe detection uses wrist velocity tracking in a rolling buffer, firing once per swipe with its own cooldown
- [ ] **SWIPE-04**: Swipe detection works with any hand pose (no pose gating required)
- [ ] **SWIPE-05**: Preview window shows detected swipe direction as visual feedback

### Integration

- [ ] **INT-01**: Swipe and static gesture detection are mutually exclusive — swipe motion does not trigger static gestures, and held poses do not trigger false swipes
- [ ] **INT-02**: Distance threshold gates both static gestures and swipe detection — if hand is too far, neither fires

## Future Requirements

Deferred to later milestones:

- Auto-calibration of distance threshold across different webcams/FOVs
- Diagonal swipe directions (NE, NW, SE, SW)
- Swipe pose gating (require specific hand pose to trigger swipe)
- Swipe sensitivity profiles (fast vs slow swipe modes)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Custom gesture training / ML models | MediaPipe landmarks sufficient |
| Depth camera / hardware distance sensor | Palm span proxy is accurate enough for gating |
| Continuous gesture tracking (drag) | Discrete events only — swipe fires once per motion |
| Gesture recording / replay | Out of scope for v1.1 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DIST-01 | - | - |
| DIST-02 | - | - |
| DIST-03 | - | - |
| SWIPE-01 | - | - |
| SWIPE-02 | - | - |
| SWIPE-03 | - | - |
| SWIPE-04 | - | - |
| SWIPE-05 | - | - |
| INT-01 | - | - |
| INT-02 | - | - |

**Coverage:**
- v1.1 requirements: 10 total
- Mapped to phases: 0
- Unmapped: 10

---
*Requirements defined: 2026-03-21*
