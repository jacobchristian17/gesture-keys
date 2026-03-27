# Phase 23: Pipeline Integration - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire MotionDetector and new signal types (MOVING_FIRE, SEQUENCE_FIRE) through the full pipeline end-to-end. Replace SwipeDetector usage in pipeline.py with MotionDetector. Switch from legacy config functions to DerivedConfig for ActionResolver and orchestrator inputs. All existing static/holding gesture functionality must be preserved.

</domain>

<decisions>
## Implementation Decisions

### Activation gate wiring
- MOVING_FIRE and SEQUENCE_FIRE follow the same gate rules as FIRE/HOLD_START (gesture-value-based gating)
- For SEQUENCE_FIRE, the gate checks the second gesture (the one being detected now), not the first
- Remove standalone swipe handling block from process_frame entirely (MOVING_FIRE through orchestrator/dispatcher replaces it)
- Remove swiping safety-release block — orchestrator handles state transitions for held keys during motion

### FrameResult shape change
- Replace `swiping: bool` with `motion_state: MotionState` (single MotionState object from MotionDetector)
- No preview.py changes — preview doesn't use swiping field; motion state visible through existing gesture overlay
- Remove swiping-based classification suppression — always classify gestures from landmarks; orchestrator receives both gesture + motion_state and handles signal logic

### Config wiring strategy
- Switch fully to DerivedConfig: pipeline uses parse_actions() + derive_from_actions(), not legacy build_action_maps/build_compound_action_maps
- ActionResolver built with new 8-map constructor from DerivedConfig
- Orchestrator receives gesture_modes, cooldowns, and activation_gate_bypass from DerivedConfig (single source of truth)
- Sequence definitions derived from DerivedConfig's right_sequence + left_sequence map keys (union of tuples), passed to orchestrator

### Hot-reload scope
- Full DerivedConfig rebuild on each reload (re-parse actions, re-derive, rebuild ActionResolver, update orchestrator params)
- MotionDetector updated via property setters (arm_threshold, disarm_threshold, axis_ratio, settling_frames, buffer_size) then reset()
- All swipe-related hot-reload code stripped from reload_config in this phase
- Activation gate bypass list rebuilt from DerivedConfig on reload

### Claude's Discretion
- Sequence definitions rebuild on hot-reload (part of full DerivedConfig rebuild)
- Exact ordering of component initialization in start()
- Test structure and organization for pipeline integration tests
- Error handling for config parsing failures during reload

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `MotionDetector` (motion.py): Ready to use, has property setters for hot-reload, reset() method
- `MotionState` (motion.py): Frozen dataclass with `_NOT_MOVING` singleton, `moving` bool + `direction` field
- `DerivedConfig` (config.py): 8 typed maps + gesture_modes + cooldowns + bypass list
- `parse_actions()` / `derive_from_actions()` (config.py): Full config parsing pipeline
- `ActionResolver` new constructor: Accepts 8 maps from DerivedConfig (Phase 22)
- `OrchestratorSignal.direction` and `.second_gesture` fields: Already support MOVING_FIRE/SEQUENCE_FIRE

### Established Patterns
- Hot-reload: Update component properties in-place, then reset(). Used by distance_filter, orchestrator, smoother
- Gate filtering: `_filter_signals_through_gate()` iterates signals checking gesture.value — same pattern works for new signal types
- Legacy backward-compat: 4-arg ActionResolver constructor still exists but pipeline should use new constructor

### Integration Points
- `Pipeline.__init__`: Replace `_swipe_detector` with `_motion_detector`
- `Pipeline.start()`: Build DerivedConfig → ActionResolver (8-map) + orchestrator params + MotionDetector
- `Pipeline.process_frame()`: Call `_motion_detector.update()` each frame, pass result to `orchestrator.update(motion_state=...)`
- `Pipeline.reload_config()`: Full DerivedConfig rebuild, MotionDetector property updates, strip swipe code
- `Pipeline.reset_pipeline()`: Replace `_swipe_detector.reset()` with `_motion_detector.reset()`
- `FrameResult`: `swiping: bool` → `motion_state: MotionState`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — standard integration following established patterns. Key principle: single source of truth from DerivedConfig, clean removal of all swipe handling from pipeline.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope. (Phase 24 handles deletion of swipe.py, config.yaml migration, and removal of legacy config functions.)

</deferred>

---

*Phase: 23-pipeline-integration*
*Context gathered: 2026-03-27*
