---
gsd_state_version: 1.0
milestone: v3.1
milestone_name: Moving Fire Dispatch Throttling
status: defining
stopped_at: null
last_updated: "2026-03-27"
last_activity: 2026-03-27
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
  percent: 0
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.
**Current focus:** Defining requirements

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-27 — Milestone v3.1 started

## Performance Metrics

**Velocity:**

- Total plans completed: 45 (v1.0: 7, v1.1: 8, v1.2: 8, v1.3: 5, v2.0: 9 + 1 gap closure, v3.0: 7)

## Accumulated Context

### Decisions

Archived to .planning/milestones/v2.0-ROADMAP.md. See PROJECT.md Key Decisions table for full history.

- [Phase 18]: Direction enum uses clean cardinal names (left/right/up/down) not swipe-prefixed
- [Phase 19]: MotionState uses frozen dataclass with _NOT_MOVING singleton for zero-alloc not-moving frames
- [Phase 19]: Direction reused from trigger.py (single source of truth, not duplicated)
- [Phase 20]: Trigger uniqueness uses hand-scoped tracking: 'both' registers in left+right+both scopes
- [Phase 20]: ActionEntry stores raw key string, pre-parsing deferred to action map building
- [Phase 20]: Fire mode inferred from trigger state: static->tap, holding->hold_key, moving->tap, sequence->tap
- [Phase 20]: Left-hand parsing removed immediately per user decision (not deferred)
- [Phase 21]: Removed COMPOUND_FIRE from ActionDispatcher alongside orchestrator swipe cleanup
- [Phase 21]: Kept DebounceState.SWIPE_WINDOW as legacy enum value to avoid breaking preview.py
- [Phase 21]: Simplified flush_pending() to always return empty result (no SWIPE_WINDOW to flush)
- [Phase 21]: Sequence tracking uses dict[Gesture, float] for O(1) last-fire-time lookup per gesture
- [Phase 21]: SEQUENCE_FIRE triggers only on FIRE signals (not HOLD_START) per user constraint
- [Phase 21]: _last_fire_time cleared on reset() to prevent stale sequence matches
- [Phase 22]: Legacy 4-arg ActionResolver constructor preserved for pipeline.py backward compatibility
- [Phase 22]: Trigger-type-specific maps: static/holding keyed by gesture value, moving by (gesture, direction), sequence by (first, second)
- [Phase 22]: build_compound_action_maps and build_action_maps kept for pipeline.py legacy path

### Pending Todos

None.

### Blockers/Concerns

None.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260327-jjq | Add per-action motion sensitivity overrides for moving gestures | 2026-03-27 | b1f8d0d | [260327-jjq-add-per-action-motion-sensitivity-overri](./quick/260327-jjq-add-per-action-motion-sensitivity-overri/) |

## Session Continuity

Last session: 2026-03-26T19:48:20.974Z
Stopped at: Phase 23 context gathered
