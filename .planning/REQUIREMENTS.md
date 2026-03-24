# Requirements: Gesture Keys

**Defined:** 2026-03-24
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v1.3 Requirements

Requirements for left-hand support with 1:1 right-hand parity.

### Detection

- [x] **DET-01**: App detects left hand landmarks via MediaPipe when left hand is in frame
- [x] **DET-02**: App selects one active hand when only one hand is visible
- [x] **DET-03**: App prioritizes one hand when both are briefly visible during hand-switch transitions

### Classification

- [x] **CLS-01**: Left hand correctly classifies all 6 static gestures (open palm, fist, thumbs up, peace, pointing, pinch)
- [x] **CLS-02**: Left hand correctly detects all 4 swipe directions (left, right, up, down)
- [x] **CLS-03**: Left hand uses same debounce/cooldown/pipeline as right hand

### Configuration

- [x] **CFG-01**: Left hand mirrors right-hand key mappings by default (no config changes needed)
- [x] **CFG-02**: User can define optional separate left-hand gesture-to-key mappings in config.yaml
- [x] **CFG-03**: Config hot-reload applies to left-hand mappings

### Preview

- [x] **PRV-01**: Preview overlay indicates which hand is currently active

## Future Requirements

None deferred for this milestone.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Simultaneous two-hand detection | One hand at a time for v1.3; complexity deferred |
| Mirrored swipe directions | Swipe directions are absolute, not flipped for left hand |
| Per-hand debounce/cooldown tuning | Same pipeline behavior for both hands in v1.3 |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DET-01 | Phase 11 | Complete |
| DET-02 | Phase 11 | Complete |
| DET-03 | Phase 11 | Complete |
| CLS-01 | Phase 11 | Complete |
| CLS-02 | Phase 11 | Complete |
| CLS-03 | Phase 11 | Complete |
| CFG-01 | Phase 12 | Complete |
| CFG-02 | Phase 12 | Complete |
| CFG-03 | Phase 12 | Complete |
| PRV-01 | Phase 13 | Complete |

**Coverage:**
- v1.3 requirements: 10 total
- Mapped to phases: 10
- Unmapped: 0

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after roadmap creation*
