---
phase: 01-detection-and-preview
plan: 03
subsystem: detection
tags: [opencv, argparse, preview-window, integration, cli]

# Dependency graph
requires:
  - phase: 01-01
    provides: "GestureClassifier, GestureSmoother, AppConfig, config.yaml"
  - phase: 01-02
    provides: "CameraCapture threaded capture, HandDetector with right-hand filtering"
provides:
  - "CLI entry point: python -m gesture_keys --preview"
  - "OpenCV preview window with landmark skeleton, gesture label bar, and FPS counter"
  - "Main detection loop wiring all modules: camera -> detector -> classifier -> smoother -> preview"
  - "Gesture transition logging at INFO level with [HH:MM:SS] timestamps"
affects: [02-01-PLAN, 03-01-PLAN]

# Tech tracking
tech-stack:
  added: []
  patterns: [main-detection-loop, bottom-bar-overlay, direct-opencv-landmark-drawing]

key-files:
  created: []
  modified:
    - gesture_keys/__main__.py
    - gesture_keys/preview.py
    - tests/test_integration.py

key-decisions:
  - "Direct OpenCV drawing for landmarks instead of mediapipe.solutions.drawing_utils (unavailable on Python 3.13)"
  - "Extract per-gesture thresholds from nested config dict before passing to classifier"

patterns-established:
  - "Direct OpenCV circle/line drawing with finger-group color coding for hand landmarks"
  - "Threshold extraction pattern: config.gestures[name]['threshold'] -> flat dict for classifier"

requirements-completed: [DEV-01, DEV-02, DEV-03]

# Metrics
duration: 3min
completed: 2026-03-21
---

# Phase 1 Plan 3: Preview Window and CLI Entry Point Summary

**OpenCV preview window with 21-landmark skeleton, bottom bar (gesture label + FPS), and CLI detection loop wiring camera, detector, classifier, smoother modules**

## Performance

- **Duration:** 3 min
- **Started:** 2026-03-21T08:33:56Z
- **Completed:** 2026-03-21T08:36:28Z
- **Tasks:** 2 of 2
- **Files modified:** 3

## Accomplishments
- Main detection loop wires all modules: CameraCapture -> HandDetector -> GestureClassifier -> GestureSmoother -> preview
- Preview window renders 21-landmark skeleton with finger-group color coding, dark gray bottom bar with gesture label and FPS
- CLI entry point with --preview and --config flags, 4-line startup banner
- Gesture transitions logged at INFO level (including None transitions), non-transitions silent
- Fixed threshold extraction bug: config.gestures contains nested dicts, classifier expects flat threshold values
- Full test suite: 53 tests passing (3 new integration tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Preview renderer and CLI entry point** - `e040859` (feat)
2. **Task 2: Verify complete detection and preview system** - user approved (checkpoint:human-verify)

## Files Created/Modified
- `gesture_keys/__main__.py` - CLI entry point with argparse, main detection loop, startup banner
- `gesture_keys/preview.py` - OpenCV preview rendering with direct landmark drawing and bottom bar
- `tests/test_integration.py` - 3 integration tests for console output, banner, and transitions

## Decisions Made
- Used direct OpenCV drawing (circles + lines) for hand landmarks instead of mediapipe.solutions.drawing_utils, which is unavailable on Python 3.13 with the Task API package. Equivalent visual output with finger-group color coding.
- Extract threshold values from nested config structure (`config.gestures[name]['threshold']` -> flat dict) before passing to GestureClassifier constructor.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed config threshold extraction for classifier**
- **Found during:** Task 1 (integration test run)
- **Issue:** `GestureClassifier(config.gestures)` passed nested dicts `{key: ..., threshold: ...}` as thresholds; classifier compared float distance against dict, causing TypeError
- **Fix:** Extract `{name: threshold_float}` from nested config before constructing classifier
- **Files modified:** gesture_keys/__main__.py
- **Verification:** All 53 tests pass
- **Committed in:** e040859 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Essential fix for classifier to work with config format. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviation above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Phase 1 detection pipeline is fully wired and verified by user
- All 6 gestures confirmed working with right hand, left hand ignored
- All modules ready for Phase 2 (keyboard mapping) integration
- 53/53 tests passing across the full suite

## Self-Check: PASSED

- [x] gesture_keys/__main__.py exists
- [x] gesture_keys/preview.py exists
- [x] tests/test_integration.py exists
- [x] Commit e040859 exists
- [x] User approved human-verify checkpoint

---
*Phase: 01-detection-and-preview*
*Completed: 2026-03-21*
