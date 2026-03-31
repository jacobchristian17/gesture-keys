---
phase: 04-distance-gating
plan: 01
subsystem: detection
tags: [distance-gating, mediapipe, euclidean-distance, config]

requires:
  - phase: 03-system-tray
    provides: "AppConfig dataclass and load_config with hot-reload support"
provides:
  - "DistanceFilter class with check() and palm span computation"
  - "AppConfig distance_enabled and min_hand_size fields"
  - "Landmark fixtures for distance testing (close_hand, far_hand)"
affects: [04-02-pipeline-integration]

tech-stack:
  added: []
  patterns: ["DistanceFilter transition-only logging", "Optional config section with defaults"]

key-files:
  created:
    - gesture_keys/distance.py
    - tests/test_distance.py
  modified:
    - gesture_keys/config.py
    - tests/test_config.py
    - tests/conftest.py

key-decisions:
  - "Default min_hand_size=0.15 (mid-range, errs low to avoid false suppression)"
  - "enabled:false preserves min_hand_size value in config and AppConfig"
  - "Transition logging uses _was_in_range flag, fires once per state change"

patterns-established:
  - "DistanceFilter: stateless per-frame filter with transition tracking for logging"
  - "Optional config section: raw.get('section', {}) with defaults when missing"

requirements-completed: [DIST-01, DIST-02]

duration: 2min
completed: 2026-03-21
---

# Phase 4 Plan 01: DistanceFilter and Config Summary

**DistanceFilter class with WRIST-to-MIDDLE_MCP palm span gating and optional distance config section with backward-compatible defaults**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-21T13:33:54Z
- **Completed:** 2026-03-21T13:35:57Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 5

## Accomplishments
- DistanceFilter.check() correctly passes/rejects landmarks based on palm span vs min_hand_size threshold
- Transition-only DEBUG logging (once per in-range/out-of-range state change, not every frame)
- AppConfig extended with distance_enabled and min_hand_size fields; load_config parses optional distance section
- 18 new tests all passing (distance filter behavior, config parsing, properties, palm span math)

## Task Commits

Each task was committed atomically:

1. **RED: Failing tests for DistanceFilter and config** - `ef6cb5b` (test)
2. **GREEN: Implement DistanceFilter and config integration** - `e2d8c6a` (feat)

_TDD plan: RED wrote tests first (verified failing), GREEN implemented code (verified passing)_

## Files Created/Modified
- `gesture_keys/distance.py` - DistanceFilter class with check(), _compute_palm_span(), properties, transition logging
- `gesture_keys/config.py` - Added distance_enabled and min_hand_size fields to AppConfig, optional distance section parsing in load_config()
- `tests/test_distance.py` - 14 tests: pass/fail, disabled bypass, transition logging, palm span math, properties
- `tests/test_config.py` - 4 tests in TestDistanceConfig: enabled/disabled/missing section/default config
- `tests/conftest.py` - mock_landmarks_close_hand (span=0.25) and mock_landmarks_far_hand (span=0.08) fixtures

## Decisions Made
- Default min_hand_size=0.15 chosen as mid-range value; users calibrate via preview overlay in Phase 7
- enabled:false preserves min_hand_size value in both config YAML and AppConfig dataclass
- Used math.sqrt(dx*dx + dy*dy) pattern consistent with existing classifier.py, not math.dist

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

3 pre-existing test failures in tests/test_config.py (smoothing_window, key_mappings, timing_fields defaults don't match current config.yaml). Unrelated to Phase 04 changes. Logged to deferred-items.md.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- DistanceFilter ready for pipeline integration in 04-02
- Config parsing supports hot-reload (properties settable via distance_filter.enabled and distance_filter.min_hand_size)
- Both __main__.py and tray.py loops need identical integration (Pattern 3 from research)

---
*Phase: 04-distance-gating*
*Completed: 2026-03-21*
