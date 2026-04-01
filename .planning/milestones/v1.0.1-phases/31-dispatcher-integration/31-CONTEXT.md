# Phase 31: Dispatcher Integration - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire ScrollSender into ActionDispatcher so scroll actions fire via MOVING_FIRE signal. Add scroll branch in _handle_moving_fire(), pass ScrollSender as optional constructor param, retrieve scroll params from ActionResolver.

</domain>

<decisions>
## Implementation Decisions

### Scroll Dispatch Routing
- Branch inside `_handle_moving_fire()` — check action.fire_mode == FireMode.SCROLL after resolve, before send
- Pass raw velocity from OrchestratorSignal — ScrollSender does its own EMA smoothing internally
- Retrieve scroll params from ActionResolver's get methods: get_scroll_speed(), get_scroll_min_ticks(), get_scroll_max_ticks()

### Safety & Scroll Lifecycle
- No special stop mechanism needed — scroll is fire-and-forget, no held state. When MOVING_FIRE stops, scroll stops naturally.
- No hold_key conflict — scroll uses MOVING_FIRE path, hold_key uses HOLD_START path. Different signal paths, no mutex needed.
- ActionDispatcher accepts ScrollSender as optional constructor param: `scroll_sender: Optional[ScrollSender] = None`. None means scroll actions are no-ops.

### Claude's Discretion
- Internal implementation details, test structure, error handling

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ActionDispatcher._handle_moving_fire()` in `action.py` — existing moving fire handler to extend
- `ScrollSender.scroll(direction, velocity)` from Phase 29
- `ActionResolver.get_scroll_speed()`, `get_scroll_min_ticks()`, `get_scroll_max_ticks()` from Phase 30

### Established Patterns
- Dispatch interval throttling already in _handle_moving_fire
- Min velocity check already in _handle_moving_fire
- Optional sender param pattern (scroll_sender=None)

### Integration Points
- ScrollSender.scroll() takes Direction and velocity, handles everything internally
- ActionResolver provides per-action scroll overrides
- Pipeline will instantiate ScrollSender and pass to dispatcher (Phase 32)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — follows existing dispatcher patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
