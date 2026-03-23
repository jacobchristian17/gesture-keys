---
phase: 12-left-hand-configuration
plan: 02
subsystem: runtime
tags: [hand-detection, mapping-resolution, hot-reload, gesture-pipeline]

# Dependency graph
requires:
  - phase: 12-left-hand-configuration
    provides: resolve_hand_gestures and resolve_hand_swipe_mappings functions from Plan 01
  - phase: 11-left-hand-detection
    provides: HandDetector with handedness tracking (Left/Right labels)
provides:
  - Hand-aware key mapping resolution in both detection loops
  - Hand-switch mapping swap in __main__.py and tray.py
  - Hot-reload re-parsing of left-hand config in both loops
affects: [12-03 UAT testing]

# Tech tracking
tech-stack:
  added: []
  patterns: [pre-parse both hand mappings at startup, swap active set on hand switch]

key-files:
  created: []
  modified:
    - gesture_keys/__main__.py
    - gesture_keys/tray.py

key-decisions:
  - "Pre-parse both left and right mappings at startup for instant hand-switch swap"
  - "Initial hand detection sets mappings on first hand appearance (not just on switch)"
  - "Hot-reload merges left_gesture_cooldowns onto right defaults for debouncer"

patterns-established:
  - "Dual-mapping pre-parse: right_key_mappings + left_key_mappings parsed at startup, swapped by handedness"
  - "Hand-aware hot-reload: re-resolve both hand sets and select active based on prev_handedness"

requirements-completed: [CFG-01, CFG-02, CFG-03]

# Metrics
duration: 3min
completed: 2026-03-24
---

# Phase 12 Plan 02: Hand-Aware Mapping Wiring Summary

**Hand-aware key mapping resolution wired into both detection loops with startup pre-parse, hand-switch swap, and hot-reload re-resolution**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-23T23:53:58Z
- **Completed:** 2026-03-23T23:57:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Both __main__.py and tray.py pre-parse right and left hand key/swipe mappings at startup
- Hand switch detection swaps active mapping set instantly (no re-parse needed)
- Initial hand appearance sets correct mappings (not just hand switches)
- Config hot-reload re-parses both hand mapping sets and selects active based on current hand
- Debouncer cooldowns/modes merge left overrides on hot-reload when left hand is active

## Task Commits

Each task was committed atomically:

1. **Task 1: Wire hand-aware mapping resolution into __main__.py preview loop** - `ab8838a` (feat)
2. **Task 2: Wire hand-aware mapping resolution into tray.py detection loop** - `6971aa2` (feat)

## Files Created/Modified
- `gesture_keys/__main__.py` - Added dual-mapping pre-parse, hand-switch swap, initial hand detection, hand-aware hot-reload with debouncer merge
- `gesture_keys/tray.py` - Same pattern applied to tray detection loop for consistency

## Decisions Made
- Pre-parse both hand mappings at startup rather than resolving per-frame (performance: avoid per-frame function calls and dict copies)
- Set initial mappings on first hand appearance (prev_handedness is None) to handle cases where left hand appears first
- Merge left_gesture_cooldowns onto right defaults in hot-reload so left hand gets correct debounce behavior

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- 3 pre-existing test failures in TestLoadConfigDefault, TestAppConfigTimingFields, TestSettlingFramesConfig due to user-modified config.yaml (fist->space, activation_delay->0.2, settling_frames->2). Not caused by this plan's changes. 252/252 relevant tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Both detection loops now resolve mappings per-hand
- Ready for UAT testing of left-hand configuration feature
- Users can add `left_gestures:` section to config.yaml to override per-gesture keys for left hand

---
*Phase: 12-left-hand-configuration*
*Completed: 2026-03-24*

## Self-Check: PASSED
