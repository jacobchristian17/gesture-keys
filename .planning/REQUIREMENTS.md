# Requirements: Gesture Keys

**Defined:** 2026-03-30
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v3.2 Requirements

Requirements for unified preview & exec mode. Each maps to roadmap phases.

### Entry Points

- [x] **ENTRY-01**: User can run `python -m gesture_keys` and see camera preview + logging by default
- [x] **ENTRY-02**: App routes to three modes: dev-camera, tray-headless, tray-to-camera via clean main() logic

### Tray Integration

- [x] **TRAY-01**: User can click "View Camera" in tray menu to restart app with camera visible

### Logging

- [x] **LOG-01**: User can pass --debug flag to enable verbose logging in all modes
- [x] **LOG-02**: All logging configuration is centralized in a single setup_logging() function
- [x] **LOG-03**: Debug file logging in tray mode is opt-in (only with --debug), not always-on

## Future Requirements

### Entry Points

- **ENTRY-03**: Remove --preview flag entirely (currently deprecated alias)

### Tray Integration

- **TRAY-02**: Camera pause-resume coordination (tray pauses detection while camera subprocess runs)
- **TRAY-03**: Prevent double View Camera clicks (disable menu item while camera window is open)

## Out of Scope

| Feature | Reason |
|---------|--------|
| In-process camera toggle | pystray and OpenCV both require Win32 main thread — cannot coexist in one process |
| Hide camera reverse toggle | Complexity deferred; kill camera window to return to tray-only |
| GUI logging panel | Console/file logging sufficient for debugging needs |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| LOG-01 | Phase 26 | Complete |
| LOG-02 | Phase 26 | Complete |
| LOG-03 | Phase 26 | Complete |
| ENTRY-01 | Phase 27 | Complete |
| ENTRY-02 | Phase 27 | Complete |
| TRAY-01 | Phase 28 | Complete |

**Coverage:**
- v3.2 requirements: 6 total
- Mapped to phases: 6
- Unmapped: 0

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation*
