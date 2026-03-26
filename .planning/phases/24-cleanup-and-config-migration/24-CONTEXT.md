# Phase 24: Cleanup and Config Migration - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

All legacy swipe code and config formats are removed, leaving a clean codebase with only the tri-state model.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- gesture_keys/swipe.py — legacy SwipeDetector to be deleted
- tests/test_swipe.py — legacy swipe tests to be deleted
- gesture_keys/config.py — config parsing with old gestures/swipe field names to clean up
- config.yaml — needs migration from gestures/swipe sections to actions format

### Established Patterns
- Phase 23 completed MotionDetector integration — SwipeDetector is no longer referenced in pipeline
- Phase 20 added actions config parsing — new format already works alongside old
- Phase 22 updated ActionResolver for 4 trigger types — no longer needs old compound fire

### Integration Points
- config.yaml format change affects user's config file
- Any remaining imports of swipe.py need removal
- config.py old field name references need cleanup

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
