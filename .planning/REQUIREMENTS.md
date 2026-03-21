# Requirements: Gesture Keys

**Defined:** 2026-03-21
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Detection

- [ ] **DET-01**: Detect 6 hand gestures (open palm, fist, thumbs up, peace, pointing, pinch) from webcam via MediaPipe Task API landmarks
- [ ] **DET-02**: Apply frame smoothing (majority-vote window) before debounce to prevent flicker
- [ ] **DET-03**: Capture camera frames on a separate thread (non-blocking)
- [ ] **DET-04**: Right-hand detection only (left hand ignored)

### Keyboard Control

- [ ] **KEY-01**: Map each gesture to configurable keyboard commands (single keys and combos) via YAML config
- [ ] **KEY-02**: Debounce state machine with configurable activation delay (0.4s) and cooldown (0.8s)
- [ ] **KEY-03**: Fire keyboard commands that work in any foreground application
- [ ] **KEY-04**: Log detections and key fires with timestamps for debugging
- [ ] **KEY-05**: Hot-reload config.yaml without restarting the app

### System Tray

- [ ] **TRAY-01**: Run as Windows system tray app with no camera preview by default
- [ ] **TRAY-02**: Active/inactive toggle in tray menu
- [ ] **TRAY-03**: Edit Config option opens config.yaml in default editor
- [ ] **TRAY-04**: Quit option stops camera and exits

### Developer Experience

- [ ] **DEV-01**: `--preview` flag opens camera preview window
- [ ] **DEV-02**: Console output of detected gestures in preview mode
- [ ] **DEV-03**: FPS display in preview window

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
| DET-01 | TBD | Pending |
| DET-02 | TBD | Pending |
| DET-03 | TBD | Pending |
| DET-04 | TBD | Pending |
| KEY-01 | TBD | Pending |
| KEY-02 | TBD | Pending |
| KEY-03 | TBD | Pending |
| KEY-04 | TBD | Pending |
| KEY-05 | TBD | Pending |
| TRAY-01 | TBD | Pending |
| TRAY-02 | TBD | Pending |
| TRAY-03 | TBD | Pending |
| TRAY-04 | TBD | Pending |
| DEV-01 | TBD | Pending |
| DEV-02 | TBD | Pending |
| DEV-03 | TBD | Pending |

**Coverage:**
- v1 requirements: 16 total
- Mapped to phases: 0
- Unmapped: 16 ⚠️

---
*Requirements defined: 2026-03-21*
*Last updated: 2026-03-21 after initial definition*
