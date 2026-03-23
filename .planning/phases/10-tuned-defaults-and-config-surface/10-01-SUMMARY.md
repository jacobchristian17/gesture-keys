---
phase: 10-tuned-defaults-and-config-surface
plan: 01
subsystem: config
tags: [timing, defaults, yaml, debounce, smoother, swipe]

requires:
  - phase: 09-swipe-static-transition-latency
    provides: "proven timing values (activation_delay=0.15, cooldown=0.3, window=2, settling=3)"
provides:
  - "AppConfig/Debouncer/Smoother defaults tuned to 0.15/0.3/2"
  - "config.yaml ships with tuned values out of box"
  - "swipe_settling_frames configurable via config.yaml"
  - "settling_frames hot-reload in both detection loops"
affects: [10-02]

tech-stack:
  added: []
  patterns:
    - "Config field wiring: AppConfig field -> load_config parse -> constructor -> hot-reload"

key-files:
  created: []
  modified:
    - gesture_keys/config.py
    - gesture_keys/debounce.py
    - gesture_keys/smoother.py
    - gesture_keys/__main__.py
    - gesture_keys/tray.py
    - config.yaml
    - tests/test_config.py

key-decisions:
  - "Updated config.yaml smoothing_window from 30 to 2 (was experimental/accidental value)"
  - "Updated config.yaml activation_delay from 0.2 to 0.15 (matches proven tuning)"

patterns-established:
  - "Config surface pattern: add field to AppConfig, parse in load_config, wire to constructor, add hot-reload"

requirements-completed: [TUNE-01, TUNE-02]

duration: 4min
completed: 2026-03-23
---

# Phase 10 Plan 01: Tuned Defaults and Config Surface Summary

**Code defaults updated to 0.15/0.3/2 for responsive out-of-box timing, settling_frames exposed as configurable swipe parameter via config.yaml**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-23T10:10:37Z
- **Completed:** 2026-03-23T10:14:21Z
- **Tasks:** 2
- **Files modified:** 7

## Accomplishments
- All code defaults (AppConfig, GestureDebouncer, GestureSmoother) updated to proven Phase 8-9 tuning values
- config.yaml ships with tuned values (smoothing_window=2, activation_delay=0.15, cooldown_duration=0.3)
- settling_frames is configurable via swipe.settling_frames in config.yaml with default 3
- settling_frames wired to SwipeDetector in both __main__.py and tray.py including hot-reload
- All 186 tests pass

## Task Commits

Each task was committed atomically:

1. **Task 1: Update code defaults and config.yaml to tuned values** - `a9ddb91` (feat)
2. **Task 2: Add settling_frames config surface** - `4107381` (feat)

_Note: TDD tasks had test updates and implementation combined per commit._

## Files Created/Modified
- `gesture_keys/config.py` - Updated AppConfig defaults, added swipe_settling_frames field, updated load_config fallbacks
- `gesture_keys/debounce.py` - Updated GestureDebouncer default params to 0.15/0.3
- `gesture_keys/smoother.py` - Updated GestureSmoother default window_size to 2
- `gesture_keys/__main__.py` - Wired settling_frames to SwipeDetector constructor and hot-reload
- `gesture_keys/tray.py` - Wired settling_frames to SwipeDetector constructor and hot-reload
- `config.yaml` - Updated smoothing_window (30->2), activation_delay (0.2->0.15), added settling_frames: 3
- `tests/test_config.py` - Updated default assertions, added settling_frames tests, fixed config.yaml drift

## Decisions Made
- Updated config.yaml smoothing_window from 30 to 2 (was experimental/accidental value, not the tuned target)
- Updated config.yaml activation_delay from 0.2 to 0.15 (matches proven Phase 8-9 tuning)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed pre-existing test assertions drifted from config.yaml**
- **Found during:** Task 1 (updating defaults)
- **Issue:** test_default_threshold_values expected thumbs_up=0.7 (actual 0.9), pinch=0.05 (actual 0.06). test_key_mappings expected old key bindings. test_default_config_yaml_has_distance_enabled expected min_hand_size=0.15 (actual 0.12).
- **Fix:** Updated test assertions to match current config.yaml values
- **Files modified:** tests/test_config.py
- **Verification:** All tests pass
- **Committed in:** a9ddb91 (Task 1 commit)

---

**Total deviations:** 1 auto-fixed (1 blocking)
**Impact on plan:** Test assertions had drifted from user-modified config.yaml. Fixed to unblock test suite.

## Issues Encountered
None beyond the pre-existing test drift documented above.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Tuned defaults and settling_frames config surface complete
- Ready for Plan 02 (per-gesture cooldown overrides)

---
*Phase: 10-tuned-defaults-and-config-surface*
*Completed: 2026-03-23*
