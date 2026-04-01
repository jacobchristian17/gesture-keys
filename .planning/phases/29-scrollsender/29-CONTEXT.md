# Phase 29: ScrollSender - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Pure new scroll dispatch class (`gesture_keys/scroll.py`) with velocity-to-ticks mapping and direction routing. Peer to `KeystrokeSender` in `keystroke.py`. No existing files change in this phase.

</domain>

<decisions>
## Implementation Decisions

### Velocity-to-Ticks Mapping
- Nonlinear (acceleration curve) from day one — SCROLL-08 requires it, bake in early
- Default scroll_speed multiplier: 3.0 (conservative, tunable via config)
- Max scroll ticks ceiling: 10 (prevents runaway while allowing fast navigation)
- Minimum ticks floor: 1 (always scroll at least 1 tick when moving)

### Jitter Smoothing
- EMA (Exponential Moving Average) for velocity smoothing — single float state, cheap per-frame
- EMA alpha: 0.3 (favors recent readings, dampens jitter)
- Smoothing lives inside ScrollSender — isolated from MotionDetector and ActionDispatcher

### ScrollSender API Design
- Single `scroll(direction, velocity)` method — direction routing is internal
- Constructor matches KeystrokeSender pattern: `__init__()` creates `pynput.mouse.Controller`
- Module: `gesture_keys/scroll.py` — peer to `keystroke.py`

### Claude's Discretion
- Internal implementation details (variable names, helper methods, error handling)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `KeystrokeSender` in `keystroke.py` — pattern to mirror (constructor creates controller, send methods, release_all)
- `Direction` enum in `trigger.py` — UP, DOWN, LEFT, RIGHT values
- `MotionState` in `motion.py` — provides `velocity` and `direction` per frame

### Established Patterns
- Frozen dataclasses for immutable state (`MotionState`, `Action`)
- Single controller instance reused for all operations
- `release_all()` idempotent safety method on senders
- Module-level logger: `logger = logging.getLogger("gesture_keys")`

### Integration Points
- ScrollSender will be consumed by ActionDispatcher in Phase 31
- Direction enum from `trigger.py` is the input type
- pynput.mouse.Controller.scroll(dx, dy) is the output call

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following KeystrokeSender patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
