# Roadmap: Gesture Keys

## Overview

Gesture Keys is built bottom-up following the pipeline's natural dependency chain: first get the camera reading hands and classifying gestures (verifiable via preview window), then wire in the debounce state machine and keyboard firing (verifiable by typing into a text editor), then wrap everything in the system tray for daily background use. Three phases, each delivering a complete, independently testable capability.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Detection and Preview** - Camera captures hand landmarks, classifies 6 gestures, and displays results in a preview window
- [x] **Phase 2: Gesture-to-Keystroke Pipeline** - Detected gestures pass through frame smoothing and debounce, then fire mapped keyboard commands (completed 2026-03-21)
- [x] **Phase 3: System Tray and Background Operation** - App runs headless in the system tray with active toggle, config editing, and clean shutdown (completed 2026-03-21)

## Phase Details

### Phase 1: Detection and Preview
**Goal**: User can see their hand gestures detected and classified in real time through a camera preview window
**Depends on**: Nothing (first phase)
**Requirements**: DET-01, DET-02, DET-03, DET-04, DEV-01, DEV-02, DEV-03
**Success Criteria** (what must be TRUE):
  1. Running with `--preview` opens a camera window showing the live feed with hand landmarks drawn
  2. Each of the 6 gestures (open palm, fist, thumbs up, peace, pointing, pinch) is detected and labeled on screen when performed with the right hand
  3. Left hand is ignored -- no gesture label appears when only the left hand is visible
  4. Console output prints detected gesture names as they change
  5. FPS counter is visible in the preview window
**Plans:** 3 plans

Plans:
- [ ] 01-01-PLAN.md — Project scaffold, config system, gesture classifier, and majority-vote smoother
- [ ] 01-02-PLAN.md — Camera capture thread and MediaPipe hand detection with right-hand filtering
- [ ] 01-03-PLAN.md — Preview window, CLI entry point, and full integration with human verification

### Phase 2: Gesture-to-Keystroke Pipeline
**Goal**: Holding a gesture for the activation delay fires the mapped keyboard command exactly once in any foreground application
**Depends on**: Phase 1
**Requirements**: KEY-01, KEY-02, KEY-03, KEY-04, KEY-05
**Success Criteria** (what must be TRUE):
  1. Holding a gesture for 0.4 seconds fires the mapped key command in a text editor (single keys and key combos both work)
  2. Holding the same gesture continuously does not repeat-fire -- cooldown prevents re-triggering until the gesture is released and re-performed
  3. Brief or flickering gestures (under 0.4 seconds) do not fire any key command
  4. Detection events and key fires are logged with timestamps to the console
  5. Editing config.yaml and triggering a reload applies new gesture-to-key mappings without restarting the app
**Plans:** 2/2 plans complete

Plans:
- [ ] 02-01-PLAN.md — Debounce state machine and keystroke sender with TDD tests
- [ ] 02-02-PLAN.md — Config extension, hot-reload, main loop wiring, and end-to-end verification

### Phase 3: System Tray and Background Operation
**Goal**: App runs invisibly in the background as a system tray icon, controllable without a terminal
**Depends on**: Phase 2
**Requirements**: TRAY-01, TRAY-02, TRAY-03, TRAY-04
**Success Criteria** (what must be TRUE):
  1. Launching the app with no flags shows a system tray icon and no camera preview or console window
  2. Clicking "Active/Inactive" in the tray menu toggles gesture detection on and off (camera LED turns off when inactive)
  3. Clicking "Edit Config" opens config.yaml in the system default text editor
  4. Clicking "Quit" stops detection, releases the camera, and exits the process cleanly
**Plans:** 2/2 plans complete

Plans:
- [ ] 03-01-PLAN.md — TrayApp class with pystray integration, detection thread, and unit tests
- [ ] 03-02-PLAN.md — Wire entry point to default tray mode, console hiding, and human verification

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Detection and Preview | 3/3 | Complete | - |
| 2. Gesture-to-Keystroke Pipeline | 2/2 | Complete   | 2026-03-21 |
| 3. System Tray and Background Operation | 2/2 | Complete   | 2026-03-21 |
