---
phase: 05-swipe-detection
plan: 01
subsystem: detection
tags: [swipe, velocity, deque, state-machine, config]

# Dependency graph
requires:
  - phase: 04-distance-gating
    provides: DistanceFilter pattern, AppConfig extension pattern, property setters for hot-reload
provides:
  - SwipeDetector class with velocity-based cardinal direction detection
  - SwipeDirection enum with values matching config key names
  - AppConfig swipe fields and YAML parsing for swipe section
affects: [05-02-pipeline-integration]

# Tech tracking
tech-stack:
  added: []
  patterns: [3-state swipe machine (IDLE/ARMED/COOLDOWN), deceleration-based fire timing, rolling deque buffer]

key-files:
  created: [gesture_keys/swipe.py, tests/test_swipe.py]
  modified: [gesture_keys/config.py, tests/test_config.py]

key-decisions:
  - "3-state machine (IDLE/ARMED/COOLDOWN) instead of 4-state like debouncer -- no FIRED state needed since swipe fires on ARMED->COOLDOWN transition"
  - "Deceleration firing: speed drop while ARMED triggers fire, prevents premature fires during acceleration"
  - "Buffer clears on both hand loss AND fire to prevent stale position data after cooldown"
  - "axis_ratio=2.0 default rejects diagonal movement by requiring 2:1 dominant-to-minor axis ratio"

patterns-established:
  - "SwipeDetector follows same property-setter pattern as DistanceFilter for hot-reload"
  - "Config swipe section parsing follows distance section pattern (missing = disabled)"
  - "swipe_mappings stores direction->key_string, parse_key_string called at integration time"

requirements-completed: [SWIPE-01, SWIPE-02, SWIPE-03, SWIPE-04]

# Metrics
duration: 4min
completed: 2026-03-21
---

# Phase 5 Plan 1: SwipeDetector and Config Summary

**Velocity-based cardinal swipe detection using rolling deque with deceleration firing and YAML config parsing for thresholds and key mappings**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-21T15:23:59Z
- **Completed:** 2026-03-21T15:28:02Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments
- SwipeDetector detects left, right, up, down swipes from wrist position sequences with deceleration-based firing
- Cooldown prevents double-fires, buffer clears on hand loss and fire, axis ratio rejects diagonals
- AppConfig extended with swipe fields (enabled, cooldown, velocity, displacement, axis_ratio, mappings) and YAML parsing

## Task Commits

Each task was committed atomically:

1. **Task 1: SwipeDetector class with TDD** - `b45fdc2` (test: RED), `d14d3a2` (feat: GREEN)
2. **Task 2: Swipe config parsing and key mapping** - `5c5165c` (test: RED), `cbcbb0d` (feat: GREEN)

_Note: TDD tasks have separate RED/GREEN commits_

## Files Created/Modified
- `gesture_keys/swipe.py` - SwipeDetector class, SwipeDirection enum, 3-state machine
- `tests/test_swipe.py` - 18 tests covering direction detection, thresholds, cooldown, buffer lifecycle
- `gesture_keys/config.py` - AppConfig swipe fields + load_config swipe section parsing
- `tests/test_config.py` - TestSwipeConfig class with 11 tests for config parsing

## Decisions Made
- Used 3-state machine (IDLE/ARMED/COOLDOWN) rather than 4-state like the debouncer -- swipe fires on the ARMED->COOLDOWN transition directly, no separate FIRED state needed
- Deceleration detection uses frame-to-frame speed comparison (current vs previous) rather than buffer-wide velocity drop
- swipe_mappings dict maps direction name to key string; parse_key_string() deferred to pipeline integration (Plan 02)
- axis_ratio default of 2.0 provides good diagonal rejection without being too strict

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Pre-existing test failures in TestLoadConfigDefault and related classes due to user-modified config.yaml (different key mappings and timing values). These are not caused by plan changes and are out of scope.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- SwipeDetector ready for pipeline integration in Plan 02
- Config parsing complete -- swipe_mappings available for key binding at integration time
- Property setters ready for hot-reload wiring

---
*Phase: 05-swipe-detection*
*Completed: 2026-03-21*
