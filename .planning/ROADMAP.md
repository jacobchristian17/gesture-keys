# Roadmap: Gesture Keys

## Milestones

- ✅ **v1.0 MVP** - Phases 1-3 (shipped 2026-03-21)
- ✅ **v1.1 Distance Gating & Swipes** - Phases 4-6 (shipped 2026-03-22)
- ✅ **v1.2 Continuous and Seamless Commands** - Phases 8-10 (shipped 2026-03-23)
- ✅ **v1.3 Left Hand Support** - Phases 11-13 (shipped 2026-03-24)
- ✅ **v2.0 Structured Gesture Architecture** - Phases 14-16 (shipped 2026-03-25)
- ✅ **v3.0 Tri-State Gesture Model** - Phases 17-24 (shipped 2026-03-26)
- ✅ **v3.1 Moving Fire Dispatch Throttling** - Phase 25 (shipped 2026-03-27)
- 🚧 **v3.2 Unified Preview & Exec Mode** - Phases 26-28 (in progress)

## Phases

- [x] **Phase 26: Logging Consolidation** - Centralized setup_logging() with --debug flag and opt-in debug file logging (completed 2026-03-30)
- [ ] **Phase 27: Entry Point Refactor** - Unified main() router with dev-camera and tray-headless modes
- [ ] **Phase 28: Tray View Camera** - "View Camera" tray menu item spawning camera subprocess

## Phase Details

### Phase 26: Logging Consolidation
**Goal**: All logging flows through a single setup_logging() function with --debug controlling verbosity and file logging opt-in
**Depends on**: Phase 25 (v3.1 complete)
**Requirements**: LOG-01, LOG-02, LOG-03
**Success Criteria** (what must be TRUE):
  1. User can pass --debug to any launch mode and see DEBUG-level output on the console
  2. All logging handlers are created in one place (setup_logging) with no ad-hoc handler additions elsewhere
  3. Running tray mode without --debug produces zero debug.log file writes (file logging is opt-in)
  4. Existing app behavior is unchanged when --debug is not passed (INFO-level console in dev, no console in tray)
**Plans:** 1/1 plans complete

Plans:
- [x] 26-01-PLAN.md — Centralize setup_logging() with console/debug params and update callers

### Phase 27: Entry Point Refactor
**Goal**: Users run `python -m gesture_keys` and immediately see camera preview with logging, no flags needed
**Depends on**: Phase 26
**Requirements**: ENTRY-01, ENTRY-02
**Success Criteria** (what must be TRUE):
  1. User runs `python -m gesture_keys` and sees the camera preview window with INFO-level console logging without passing any flags
  2. Running the frozen exe (GestureKeys.exe) enters tray mode silently with no camera window
  3. main() cleanly routes to run_dev_mode, run_tray_mode, or run_camera_mode based on frozen state and flags
  4. The --view-camera internal flag exists and routes to camera mode (for Phase 28 subprocess usage)
**Plans:** 1 plan
**UI hint**: yes

Plans:
- [ ] 27-01-PLAN.md — Refactor __main__.py with three-way mode routing and test coverage

### Phase 28: Tray View Camera
**Goal**: Tray users can open a camera preview window on demand via a single menu click
**Depends on**: Phase 27
**Requirements**: TRAY-01
**Success Criteria** (what must be TRUE):
  1. User clicks "View Camera" in the system tray menu and a camera preview window opens within 5 seconds
  2. The tray process releases the camera and stops detection before the camera subprocess starts (no "camera in use" errors)
  3. Closing the camera window returns control to the tray app, which resumes detection automatically
  4. The feature works identically when launched from the frozen exe (GestureKeys.exe) and from python -m gesture_keys in tray mode
  5. No stuck keys remain after the tray-to-camera restart sequence
**Plans**: TBD
**UI hint**: yes

Plans:
- [ ] 28-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 26 -> 27 -> 28

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 26. Logging Consolidation | v3.2 | 1/1 | Complete    | 2026-03-30 |
| 27. Entry Point Refactor | v3.2 | 0/1 | Not started | - |
| 28. Tray View Camera | v3.2 | 0/0 | Not started | - |
