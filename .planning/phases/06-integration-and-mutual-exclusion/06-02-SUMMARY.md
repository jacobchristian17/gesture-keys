---
phase: 06-integration-and-mutual-exclusion
plan: 02
subsystem: detection
tags: [mutual-exclusion, swipe, static-gesture, pipeline-ordering]

requires:
  - phase: 06-integration-and-mutual-exclusion
    provides: is_swiping property and reset() method on SwipeDetector
provides:
  - Swipe-first pipeline ordering in both detection loops
  - is_swiping suppression preventing static gesture cross-fire during swipe motion
  - Distance gating reset of swipe detector on range transitions
affects: [uat, phase-07]

tech-stack:
  added: []
  patterns: [swipe-first mutual exclusion, smoother-fed-None suppression]

key-files:
  created: []
  modified:
    - gesture_keys/__main__.py
    - gesture_keys/tray.py

key-decisions:
  - "Swipe detection runs before static classification to get raw landmarks before any pipeline processing"
  - "is_swiping suppression feeds None to smoother (natural decay) rather than hard-resetting the smoother"

patterns-established:
  - "Mutual exclusion via pipeline ordering: swipe runs first, is_swiping gates static path"
  - "Suppression via None-feeding: smoother.update(None) naturally decays accumulated state"

requirements-completed: [INT-01, INT-02]

duration: 2min
completed: 2026-03-21
---

# Phase 06 Plan 02: Mutual Exclusion Wiring Summary

**Swipe-first pipeline ordering with is_swiping suppression in both __main__.py and tray.py detection loops**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-21T17:59:42Z
- **Completed:** 2026-03-21T18:01:37Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments
- Reordered both detection loops: swipe detection now runs before static gesture classification
- Added is_swiping flag check that suppresses static pipeline during ARMED and COOLDOWN swipe states
- Added swipe_detector.reset() to distance gating block for clean range transitions
- Both __main__.py and tray.py have identical mutual exclusion logic

## Task Commits

Each task was committed atomically:

1. **Task 1: Reorder both detection loops with mutual exclusion** - `dadadc8` (feat)

## Files Created/Modified
- `gesture_keys/__main__.py` - Reordered detection loop: swipe-first with is_swiping suppression and reset in distance gating
- `gesture_keys/tray.py` - Identical reordered detection loop matching __main__.py

## Decisions Made
- Swipe detection runs before static classification so it receives raw landmarks before any pipeline processing
- is_swiping suppression feeds None to smoother (natural decay) rather than hard-resetting, allowing smooth transitions back to static gestures when swipe ends

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test_config.py failures (config.yaml modified outside plans, smoothing_window/threshold/key defaults changed) -- out of scope, not related to this plan's changes. All 122 non-config tests pass.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Mutual exclusion is fully wired -- swiping suppresses static gestures, distance gating resets swipe detector
- Ready for UAT testing to validate real-world behavior
- No blockers

---
*Phase: 06-integration-and-mutual-exclusion*
*Completed: 2026-03-21*
