---
phase: 14-shared-types-and-pipeline-unification
plan: 01
subsystem: pipeline
tags: [dataclass, refactoring, pipeline, detection-loop]

# Dependency graph
requires: []
provides:
  - "FrameResult dataclass with per-frame detection output fields"
  - "Pipeline class with process_frame/reload_config/reset_pipeline/start/stop"
  - "Single-source _parse_*_key_mappings helpers in pipeline.py"
affects: [14-02, 14-03]

# Tech tracking
tech-stack:
  added: []
  patterns: ["Pipeline class encapsulating detection loop body", "FrameResult dataclass for typed per-frame output"]

key-files:
  created:
    - gesture_keys/pipeline.py
    - tests/test_pipeline.py
  modified: []

key-decisions:
  - "Pipeline owns camera.read() internally so process_frame() is zero-argument"
  - "FrameResult carries exactly what preview needs: landmarks, handedness, gesture, raw_gesture, debounce_state, swiping, frame_valid"
  - "Pipeline.last_frame property exposes raw frame for preview rendering"
  - "DistanceFilter init uses max_hand_size (fixes pre-existing tray.py omission)"

patterns-established:
  - "Pipeline.process_frame() -> FrameResult: zero-arg call that reads camera and runs full detection"
  - "Pipeline.reload_config() with SWIPE_WINDOW fire-before-reset edge case preservation"

requirements-completed: [PIPE-01, PIPE-02]

# Metrics
duration: 4min
completed: 2026-03-24
---

# Phase 14 Plan 01: Pipeline & FrameResult Summary

**Unified Pipeline class with process_frame() -> FrameResult encapsulating full detection loop body from __main__.py, with config hot-reload and SWIPE_WINDOW edge case preservation**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-24T11:12:53Z
- **Completed:** 2026-03-24T11:16:28Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files created:** 2

## Accomplishments
- FrameResult dataclass with 7 typed fields carrying all per-frame detection output
- Pipeline class with start/stop lifecycle, process_frame(), reload_config(), reset_pipeline()
- Three _parse_*_key_mappings helpers consolidated into pipeline.py (eliminating duplication from __main__.py and tray.py)
- DistanceFilter correctly uses max_hand_size (fixes pre-existing bug in tray.py)
- SWIPE_WINDOW fire-before-reset edge case preserved in reload_config()
- 10 new unit tests covering FrameResult defaults/assignment, Pipeline init/start/stop/reset

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests for FrameResult and Pipeline** - `e1736f8` (test)
2. **Task 1 (GREEN): Implement Pipeline class and FrameResult** - `eb1fa5f` (feat)

_TDD task with RED/GREEN commits._

## Files Created/Modified
- `gesture_keys/pipeline.py` - FrameResult dataclass + Pipeline class with full detection loop (563 lines)
- `tests/test_pipeline.py` - Unit tests for FrameResult, Pipeline init/start/stop/reset (235 lines)

## Decisions Made
- Pipeline owns camera.read() internally making process_frame() zero-argument for simplest possible wrapper code
- FrameResult uses @dataclass (not NamedTuple) for mutable defaults and optional field assignment
- Pipeline stores last_frame as property for preview rendering access
- Used __main__.py as source of truth for process_frame() logic (not tray.py, which had the max_hand_size bug and a subtle gesture variable reference difference in swipe enter)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Pre-existing test failure in test_config.py::TestSwipeWindowConfig::test_swipe_window_default caused by modified config.yaml in working tree (not related to pipeline changes). All 313 other tests pass.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness
- Pipeline class ready for Plan 02 (preview wrapper refactoring) and Plan 03 (tray wrapper refactoring)
- __main__.py and tray.py can now import Pipeline and FrameResult to replace their duplicated detection loops

---
*Phase: 14-shared-types-and-pipeline-unification*
*Completed: 2026-03-24*
