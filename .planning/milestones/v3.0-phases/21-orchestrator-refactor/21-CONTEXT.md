# Phase 21: Orchestrator Refactor - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Remove swipe-related states and signals from the orchestrator FSM, add native motion_state consumption with MOVING_FIRE signal, and add sequence gesture tracking with SEQUENCE_FIRE signal. The orchestrator no longer needs to know about swipe routing — it emits signals for any gesture+motion combination and lets ActionResolver (Phase 22) decide if there's a matching action. Pipeline wiring is Phase 23. Legacy code deletion is Phase 24.

</domain>

<decisions>
## Implementation Decisions

### Sequence tracking and SEQUENCE_FIRE
- Gesture A counts as "completed" for a sequence after it emits a FIRE signal (must pass activation delay and fire)
- Sequence window timer starts from gesture A's FIRE moment (not from release)
- Both standalone actions AND the sequence action fire — sequence is purely additive (A fires its standalone, then when B fires within window, B fires its standalone AND the sequence fires)
- Orchestrator receives registered sequence pairs as a constructor parameter (e.g., set of (gesture_A, gesture_B) tuples), matching the existing pattern of gesture_modes, gesture_cooldowns as constructor params
- Sequence window duration configurable, default 0.5s (ORCH-04)

### Swipe state removal
- Remove all three in this phase: SWIPE_WINDOW from LifecycleState, SWIPING from TemporalState, COMPOUND_FIRE from OrchestratorAction
- Remove suppress_standalone_swipe field from OrchestratorResult entirely
- Remove swipe_direction and swiping params from update() method
- Remove _handle_swiping_transitions method and all swiping tracking state (_was_swiping, _pre_swipe_gesture, _suppress_until)
- Remove swipe_gesture_directions constructor parameter and _swipe_gesture_directions field
- Remove swipe_window constructor parameter (repurposed as sequence_window)
- No routing needed for MOVING_FIRE — orchestrator emits whenever gesture + moving + direction detected, ActionResolver decides if there's a matching action

### Signal and type migration
- OrchestratorSignal.direction changes from Optional[SwipeDirection] to Optional[Direction] (from trigger.py)
- SwipeDirection import removed from orchestrator.py entirely
- Add MOVING_FIRE and SEQUENCE_FIRE to OrchestratorAction enum (total: FIRE, HOLD_START, HOLD_END, MOVING_FIRE, SEQUENCE_FIRE)
- Add optional second_gesture: Optional[Gesture] = None field to OrchestratorSignal (for SEQUENCE_FIRE: gesture = first, second_gesture = second)
- OrchestratorResult keeps same shape minus suppress_standalone_swipe: base_gesture, temporal_state, outer_state, signals

### Claude's Discretion
- MOVING_FIRE emission logic (when exactly to emit during gesture lifecycle — activation delay interaction, hold mode interaction)
- Internal sequence tracking data structure (deque of recent fires, dict of last fire time per gesture, etc.)
- How motion_state param interacts with existing lifecycle states (IDLE, ACTIVATING, ACTIVE, COOLDOWN)
- Whether flush_pending() needs changes for the new states
- Test strategy and which existing swipe tests to rewrite vs delete

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `trigger.py:Direction` enum (LEFT/RIGHT/UP/DOWN): Replaces SwipeDirection in OrchestratorSignal
- `motion.py:MotionState` frozen dataclass (moving: bool, direction: Optional[Direction]): New param type for update()
- `config.py:DerivedConfig`: Provides gesture_modes, gesture_cooldowns — sequence pairs will need similar derivation
- Existing lifecycle FSM (IDLE -> ACTIVATING -> ACTIVE -> COOLDOWN): Core flow preserved, only swipe branching removed

### Established Patterns
- Constructor params for orchestrator config: activation_delay, cooldown_duration, gesture_cooldowns, gesture_modes — sequence_definitions follows same pattern
- OrchestratorSignal as NamedTuple with optional fields defaulting to None
- Per-state handler methods (_handle_idle, _handle_activating, etc.) — new motion/sequence logic follows same dispatch pattern
- Transition-only logging (log state changes, not every frame)

### Integration Points
- `pipeline.py`: Creates GestureOrchestrator and calls update() — will need updated constructor args and update() call signature (Phase 23)
- `action.py:ActionResolver`: Receives OrchestratorSignal — will need to handle MOVING_FIRE and SEQUENCE_FIRE (Phase 22)
- `activation.py:ActivationGate`: Checks OrchestratorAction for gating — will need MOVING_FIRE and SEQUENCE_FIRE cases (Phase 23)
- Tests: `tests/test_orchestrator.py` — extensive swipe-related tests to rewrite/delete

</code_context>

<specifics>
## Specific Ideas

- The orchestrator becomes simpler overall: fewer lifecycle states (no SWIPE_WINDOW), fewer temporal states (no SWIPING), cleaner update() signature
- Sequence tracking is a new lightweight addition layered on top of the existing FIRE signal flow — when FIRE emits, check if it completes a registered sequence
- MotionState consumption is straightforward: read motion_state.moving and motion_state.direction, emit MOVING_FIRE signal when conditions met

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 21-orchestrator-refactor*
*Context gathered: 2026-03-26*
