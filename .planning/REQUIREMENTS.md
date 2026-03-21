# Requirements: Gesture Keys

**Defined:** 2026-03-21
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Detection

- [x] **DET-01**: Detect 6 hand gestures (open palm, fist, thumbs up, peace, pointing, pinch) from webcam via MediaPipe Task API landmarks
- [x] **DET-02**: Apply frame smoothing (majority-vote window) before debounce to prevent flicker
- [x] **DET-03**: Capture camera frames on a separate thread (non-blocking)
- [x] **DET-04**: Right-hand detection only (left hand ignored)

### Keyboard Control

- [x] **KEY-01**: Map each gesture to configurable keyboard commands (single keys and combos) via YAML config
- [x] **KEY-02**: Debounce state machine with configurable activation delay (0.4s) and cooldown (0.8s)
- [x] **KEY-03**: Fire keyboard commands that work in any foreground application
- [x] **KEY-04**: Log detections and key fires with timestamps for debugging
- [ ] **KEY-05**: Hot-reload config.yaml without restarting the app

### System Tray

- [ ] **TRAY-01**: Run as Windows system tray app with no camera preview by default
- [ ] **TRAY-02**: Active/inactive toggle in tray menu
- [ ] **TRAY-03**: Edit Config option opens config.yaml in default editor
- [ ] **TRAY-04**: Quit option stops camera and exits

### Developer Experience

- [x] **DEV-01**: `--preview` flag opens camera preview window
- [x] **DEV-02**: Console output of detected gestures in preview mode
- [x] **DEV-03**: FPS display in preview window

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Detection

- **DET-05**: Handedness-aware classification (left and right hand support)
- **DET-06**: Confidence gating (reject low-confidence detections)
- **DET-07**: Detection quality indicator in preview mode

### System Tray

- **TRAY-05**: Tray icon color changes for active/inactive state
- **TRAY-06**: Toast notifications on gesture fire
- **TRAY-07**: Launch at Windows startup option

### Keyboard Control

- **KEY-06**: Gesture logging to file (persistent debug logs)

## Out of Scope

| Feature | Reason |
|---------|--------|
| Custom gesture training / ML models | MediaPipe landmarks sufficient for 6 gestures; custom ML 10x scope |
| Mouse control via gestures | Universally imprecise; staying focused on discrete keyboard commands |
| Multiple camera support | Single camera index from config is sufficient |
| Gesture profiles / per-app mappings | Single global config for v1 |
| Mobile or cross-platform | Windows-only experiment |
| GUI configuration | YAML file editing is sufficient |
| Two-hand gestures | HIGH complexity, defer until 6-gesture ceiling is hit |
| GPU acceleration (onnxruntime-gpu) | MediaPipe Python on Windows is CPU-only; 30-60 FPS CPU is sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| DET-01 | Phase 1 | Complete |
| DET-02 | Phase 1 | Complete |
| DET-03 | Phase 1 | Complete |
| DET-04 | Phase 1 | Complete |
| KEY-01 | Phase 2 | Complete |
| KEY-02 | Phase 2 | Complete |
| KEY-03 | Phase 2 | Complete |
| KEY-04 | Phase 2 | Complete |
| KEY-05 | Phase 2 | Pending |
| TRAY-01 | Phase 3 | Pending |
| TRAY-02 | Phase 3 | Pending |
| TRAY-03 | Phase 3 | Pending |
| TRAY-04 | Phase 3 | Pending |
| DEV-01 | Phase 1 | Complete |
| DEV-02 | Phase 1 | Complete |
| DEV-03 | Phase 1 | Complete |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 16
- Unmapped: 0

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after roadmap creation*
