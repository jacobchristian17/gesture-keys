---
phase: 01-detection-and-preview
plan: 02
subsystem: detection
tags: [opencv, mediapipe, threading, hand-detection, camera-capture]

# Dependency graph
requires:
  - phase: 01-01
    provides: "AppConfig with camera_index, GestureClassifier, conftest fixtures"
provides:
  - "CameraCapture daemon thread for non-blocking frame reading"
  - "HandDetector wrapping MediaPipe Task API with right-hand filtering"
  - "Auto-downloading hand_landmarker.task model"
affects: [01-03-PLAN, 02-01-PLAN]

# Tech tracking
tech-stack:
  added: [mediapipe, opencv-python, numpy]
  patterns: [threaded-camera-capture, mediapipe-task-api-video-mode, right-hand-filtering]

key-files:
  created: []
  modified:
    - gesture_keys/detector.py
    - tests/test_detector.py

key-decisions:
  - "Patch module-level constants (HandLandmarker, BaseOptions) directly in tests rather than patching mp namespace"
  - "Model auto-downloads via urllib.request.urlretrieve with progress logging"
  - "HandDetector uses num_hands=2 to detect both hands then filters for Right only"

patterns-established:
  - "Module-level MediaPipe constant aliases (HandLandmarker, BaseOptions, etc.) for clean imports"
  - "Mock MediaPipe internals via patch.object on module-level names, not patching mp namespace"
  - "CameraCapture latest-frame-only pattern with threading.Lock"

requirements-completed: [DET-03, DET-04]

# Metrics
duration: 7min
completed: 2026-03-21
---

# Phase 1 Plan 2: Camera Capture and Hand Detection Summary

**Threaded camera capture with daemon thread and MediaPipe HandLandmarker in VIDEO mode with right-hand-only filtering and auto-downloading model**

## Performance

- **Duration:** 7 min
- **Started:** 2026-03-21T07:21:26Z
- **Completed:** 2026-03-21T07:28:35Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- CameraCapture reads frames on a daemon thread with lock-protected latest-frame-only pattern
- HandDetector wraps MediaPipe Task API in VIDEO mode, filtering for right hand only
- Model auto-downloads from Google storage if not present locally
- BGR-to-RGB conversion, monotonic timestamp enforcement, context manager support
- Full test suite: 50 tests passing (13 new detector tests + 37 existing)

## Task Commits

Each task was committed atomically:

1. **Task 1: Camera capture thread** - `7892015` (feat)
2. **Task 2: HandDetector with MediaPipe and right-hand filtering** - `6e0af94` (feat)

## Files Created/Modified
- `gesture_keys/detector.py` - CameraCapture thread + HandDetector wrapping MediaPipe
- `tests/test_detector.py` - 13 tests for threaded capture and right-hand filtering

## Decisions Made
- Used module-level constant aliases for MediaPipe imports (cleaner code, easier to patch in tests)
- Tests mock MediaPipe at the module-level name level (patch.object on HandLandmarker etc.) rather than patching the mp namespace, since constants are resolved at import time
- HandDetector detects up to 2 hands (num_hands=2) but only returns the first right hand

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed numpy and opencv-python dependencies**
- **Found during:** Task 1
- **Issue:** numpy and opencv-python not installed, tests could not import
- **Fix:** pip install numpy opencv-python
- **Files modified:** None (runtime dependency)
- **Verification:** Tests run successfully after install

**2. [Rule 3 - Blocking] Installed mediapipe dependency**
- **Found during:** Task 2
- **Issue:** mediapipe not installed, module import failed at collection time
- **Fix:** pip install mediapipe
- **Files modified:** None (runtime dependency)
- **Verification:** All tests pass after install

**3. [Rule 1 - Bug] Rewrote HandDetector test mocking strategy**
- **Found during:** Task 2
- **Issue:** Patching gesture_keys.detector.mp did not affect module-level constants (HandLandmarker, BaseOptions) already resolved at import time, causing tests to use real MediaPipe and fail on missing model file
- **Fix:** Changed tests to use patch.object on the module-level names directly via a _create_detector_with_mock() helper
- **Files modified:** tests/test_detector.py
- **Verification:** All 13 detector tests pass with fully mocked internals

---

**Total deviations:** 3 auto-fixed (2 blocking, 1 bug)
**Impact on plan:** All auto-fixes necessary for tests to run. No scope creep.

## Issues Encountered
None beyond the auto-fixed deviations above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- CameraCapture and HandDetector are ready for integration in the main loop
- Plan 01-03 (preview window and main loop) can import CameraCapture and HandDetector directly
- Model will auto-download on first run; no manual setup needed
- 50/50 tests passing across the full suite

## Self-Check: PASSED

- All 2 modified files exist on disk
- Commit 7892015 (Task 1) verified in git log
- Commit 6e0af94 (Task 2) verified in git log
- 50/50 tests passing

---
*Phase: 01-detection-and-preview*
*Completed: 2026-03-21*
