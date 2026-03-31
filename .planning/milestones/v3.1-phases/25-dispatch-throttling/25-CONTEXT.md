# Phase 25: Dispatch Throttling - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

Add configurable dispatch throttling to moving_fire actions. Users set a `dispatch_interval` (seconds) globally in the `motion:` config section or per-action as a field override. The ActionDispatcher tracks last-dispatch timestamps and skips dispatches that arrive before the interval has elapsed. No throttling when not configured (backward compatible).

</domain>

<decisions>
## Implementation Decisions

### Config & Default Values
- Global `dispatch_interval` lives under `motion:` section in config.yaml (e.g., `motion.dispatch_interval: 0.2`) — consistent with existing `motion.cooldown`, `motion.min_velocity`
- Default value is `0` (or `None`) — no throttling when unconfigured, existing behavior fully preserved
- Per-action override field name is `dispatch_interval` on `ActionEntry` — mirrors `min_velocity` per-action pattern

### Throttle Implementation
- Throttle logic lives in `ActionDispatcher._handle_moving_fire()` — co-located with existing velocity check, keeps orchestrator as pure signal emitter
- Last-dispatch time tracked in a dict keyed by `(gesture_value, direction_value)` → `float` timestamp — per-action granularity, matches `velocity_overrides` pattern in ActionResolver
- Throttled dispatches emit a debug log: `"MOVING_FIRE throttled: %.3fs since last dispatch < interval %.3fs"` — consistent with velocity-skip logging style

### Claude's Discretion
- How `dispatch_interval` is wired through `AppConfig` and `DerivedConfig` (new field vs passed directly)
- Test structure — follow existing `TestMovingFireDispatch` pattern in `test_action.py`

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ActionEntry.min_velocity` — per-action float override field pattern to follow for `dispatch_interval`
- `ActionResolver.get_min_velocity()` / `ActionResolver.velocity_overrides` — pattern to follow for `get_dispatch_interval()` / `dispatch_interval_overrides`
- `ActionDispatcher._handle_moving_fire()` — the insertion point for throttle check
- `motion:` section in config.yaml and `AppConfig.motion_*` fields — where global `dispatch_interval` is parsed

### Established Patterns
- Velocity skip in `_handle_moving_fire()`: check, skip with debug log, return early — same pattern for throttle
- `DerivedConfig.moving_velocity_overrides: dict[tuple[str, str], float]` — exact same shape needed for `moving_dispatch_interval_overrides`
- `parse_actions()` in config.py: reads `min_velocity` from action settings dict — add `dispatch_interval` the same way

### Integration Points
- `gesture_keys/config.py`: `AppConfig` (add `motion_dispatch_interval`), `ActionEntry` (add `dispatch_interval` field), `parse_actions()` (read field), `DerivedConfig` + `derive_from_actions()` (add override map)
- `gesture_keys/action.py`: `ActionResolver` (add interval override dict + getter), `ActionDispatcher` (add `_last_moving_fire_time` dict + throttle check in `_handle_moving_fire`)
- `config.yaml`: add `dispatch_interval` under `motion:` section with comment

</code_context>

<specifics>
## Specific Ideas

No specific requirements beyond the decided approach — open to standard implementation within the patterns above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
