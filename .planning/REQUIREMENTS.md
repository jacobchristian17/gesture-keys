# Requirements: Gesture Keys

**Defined:** 2026-04-01
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v1.0.1 Requirements

Requirements for scroll gesture support. Each maps to roadmap phases.

### Scroll Fire Mode

- [x] **SCROLL-01**: User can configure a `scroll` fire mode on any gesture's moving trigger to fire mouse scroll events instead of keyboard commands
- [x] **SCROLL-02**: Scroll actions do not require a `key` field — config validates that scroll actions omit key and non-scroll actions require it

### Scroll Dispatch

- [x] **SCROLL-03**: User can scroll vertically (up/down) by holding a gesture and moving hand up or down
- [x] **SCROLL-04**: User can scroll horizontally (left/right) by holding a gesture and moving hand left or right
- [x] **SCROLL-05**: Scroll speed is proportional to hand velocity — faster movement produces faster scrolling
- [x] **SCROLL-06**: Scroll fires continuously while hand is in motion with appropriate dispatch_interval (~0.05s)

### Scroll Tuning

- [x] **SCROLL-07**: User can configure `scroll_speed` per action to control velocity-to-scroll multiplier
- [x] **SCROLL-08**: Scroll uses an acceleration curve — slow hand movement gives precise control, fast movement gives rapid scrolling
- [x] **SCROLL-09**: User can configure min/max scroll step bounds to prevent micro-scrolls or runaway scroll

### Scroll Safety

- [x] **SCROLL-10**: Scroll stops immediately when hand stops moving or gesture is released — no runaway scroll

### Logging

- [ ] **SCROLL-11**: Scroll events are logged with direction, velocity, and step count for debugging and tuning

### Default Config

- [ ] **SCROLL-12**: Default config.yaml includes pinch scroll actions for all 4 directions with sensible defaults

## Future Requirements

### Scroll Polish

- **SCROLLPOL-01**: Scroll preview overlay showing direction arrow and speed indicator in camera preview
- **SCROLLPOL-02**: Per-direction scroll sensitivity tuning (different vertical vs horizontal defaults)

### New Capabilities

- **CAP-01**: Pinch-to-zoom via tracking finger distance changes (separate input signal from hand movement)
- **CAP-02**: Scroll inertia/momentum after hand stops (only if clean-stop feels abrupt)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Smooth/sub-pixel scroll interpolation | OS-level smooth scroll handles this for discrete events; adding animation thread adds complexity without value for webcam input |
| Scroll inertia/momentum | MotionDetector disarms on velocity drop — no release velocity event; webcam latency makes momentum unreliable |
| Diagonal/free-axis scrolling | MotionDetector axis_ratio filter rejects diagonals by design; cardinal-only is more controllable |
| Scroll-then-click combos | Requires mouse cursor control (separate feature domain); mixing scroll and click adds state complexity |
| Pinch-to-zoom | Different input signal (finger distance vs hand movement); separate milestone |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| SCROLL-01 | Phase 30 | Complete |
| SCROLL-02 | Phase 30 | Complete |
| SCROLL-03 | Phase 29 | Complete |
| SCROLL-04 | Phase 29 | Complete |
| SCROLL-05 | Phase 29 | Complete |
| SCROLL-06 | Phase 31 | Complete |
| SCROLL-07 | Phase 30 | Complete |
| SCROLL-08 | Phase 30 | Complete |
| SCROLL-09 | Phase 30 | Complete |
| SCROLL-10 | Phase 31 | Complete |
| SCROLL-11 | Phase 32 | Pending |
| SCROLL-12 | Phase 33 | Pending |

**Coverage:**
- v1.0.1 requirements: 12 total
- Mapped to phases: 12
- Unmapped: 0

---
*Requirements defined: 2026-04-01*
*Last updated: 2026-04-01 after roadmap creation*
