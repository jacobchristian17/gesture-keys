# Phase 15: Gesture Orchestrator - Context

**Gathered:** 2026-03-25
**Status:** Ready for planning

<domain>
## Phase Boundary

A single GestureOrchestrator state machine replaces GestureDebouncer and scattered Pipeline.process_frame() coordination logic, managing all gesture type prioritization and state transitions. Static gestures form the base layer, hold and swiping are temporal state modifiers. All v1.3 behaviors preserved identically.

</domain>

<decisions>
## Implementation Decisions

### State hierarchy model
- Hierarchical FSM: outer lifecycle FSM + inner temporal FSM
- Outer FSM states: IDLE → ACTIVATING → SWIPE_WINDOW → ACTIVE → COOLDOWN
  - SWIPE_WINDOW only entered for gestures with mapped swipe directions
  - SWIPE_WINDOW outcomes: swipe detected → ACTIVE(inner=SWIPING), window expired + gesture held → ACTIVE(inner=CONFIRMED), gesture lost → IDLE
- Inner FSM states (only exists in ACTIVE): CONFIRMED → HOLD, CONFIRMED → SWIPING
- Inner FSM owns its own timing (hold threshold tracking, hold_start_time)
- ACTIVATING is a distinct outer state, not part of ACTIVE

### Orchestrator boundary
- Orchestrator absorbs all gesture logic: debounce timing, swipe exit resets, pre-swipe suppression, compound swipe suppression, static-first priority gate
- Pipeline still runs classifier → smoother and swipe_detector.update(), then passes smoothed gesture + swipe direction to orchestrator.update()
- Orchestrator handles swiping transitions internally (receives swiping flag each frame, detects entry/exit)
- Hold repeat logic stays in Pipeline (keystroke timing, not gesture state)
- Pipeline.process_frame() reduces to: camera read → detect → hand switch/distance checks → orchestrator.update() → config reload → return FrameResult (~30 lines)

### Output contract
- orchestrator.update() returns OrchestratorResult dataclass with: base_gesture, temporal_state, outer_state, signals list, suppress_standalone_swipe
- Signals use same actions as current DebounceAction: FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE
- OrchestratorSignal is a NamedTuple with action, gesture, direction
- Orchestrator exposes is_activating property for Pipeline to suppress swipe arming
- FrameResult gets new orchestrator field (OrchestratorResult | None), existing flat fields kept for backward compatibility

### Edge-case preservation
- All 10 v1.3 edge cases enumerated and each gets dedicated test coverage:
  1. Direct gesture transitions (COOLDOWN + different gesture → ACTIVATING, skipping IDLE)
  2. Static-first priority gate (suppress swipe during ACTIVATING via is_activating property)
  3. Swipe-exit reset (orchestrator handles internally on swiping transition exit)
  4. Pre-swipe gesture suppression (orchestrator internally sets COOLDOWN on swipe exit — no private state injection)
  5. SWIPE_WINDOW fire-before-reset on config reload (orchestrator.flush_pending() method)
  6. Per-gesture cooldown durations
  7. Hold release delay grace period (inner HOLD state tracks release_delay_start timer)
  8. Compound swipe suppression (orchestrator tracks suppress_until, exposes via OrchestratorResult.suppress_standalone_swipe)
  9. Same-gesture cooldown blocking (COOLDOWN + same gesture → stay in COOLDOWN)
  10. Hand switch instant release (Pipeline calls orchestrator.reset() on hand switch)
- Old GestureDebouncer (debounce.py) deleted after orchestrator passes all tests

### Claude's Discretion
- Internal data structures and helper methods within the orchestrator
- Exact file organization (single orchestrator.py or split into outer/inner modules)
- Test organization and helper utilities
- How OrchestratorResult fields map to FrameResult during transition period

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GestureDebouncer` (debounce.py, 338 lines): State machine logic to be replaced — reference implementation for all edge cases
- `Pipeline` (pipeline.py): Unified pipeline from Phase 14 — orchestrator integrates here
- `FrameResult` dataclass: Per-frame output structure — gets new orchestrator field
- `DebounceAction` enum: Signal actions (FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE) — reused as OrchestratorSignal actions
- `DebounceState` enum: Flat states — replaced by LifecycleState (outer) + TemporalState (inner) enums

### Established Patterns
- Pipeline.process_frame() calls components in order, returns FrameResult
- Components expose .reset() for hand switch / distance gating / config reload
- Per-gesture config via gesture_cooldowns dict and gesture_modes dict
- Swipe direction sets (swipe_gesture_directions) determine which gestures enter SWIPE_WINDOW

### Integration Points
- Pipeline.process_frame() — primary consumer, replaces ~200 lines of coordination with orchestrator.update() call
- Pipeline.reload_config() — calls orchestrator.flush_pending() then orchestrator.reset(new_config)
- Preview overlay (preview.py) — reads FrameResult fields for display; orchestrator field adds richer state info
- Tests (test_debounce.py) — need migration to test orchestrator with same assertions

</code_context>

<specifics>
## Specific Ideas

- Pre-swipe suppression should use a proper orchestrator method instead of reaching into private state (current code injects `_state`, `_cooldown_gesture`, `_cooldown_start` directly)
- Orchestrator.flush_pending() cleanly handles the SWIPE_WINDOW fire-before-reset edge case on config reload

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 15-gesture-orchestrator*
*Context gathered: 2026-03-25*
