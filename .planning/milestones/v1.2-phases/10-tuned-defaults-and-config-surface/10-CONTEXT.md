# Phase 10: Tuned Defaults and Config Surface - Context

**Gathered:** 2026-03-23
**Status:** Ready for planning

<domain>
## Phase Boundary

Update code defaults to match proven real-usage timing values from Phase 8-9 insights, expose settling_frames as a configurable swipe parameter, and add per-gesture cooldown overrides in config.yaml. No new algorithms or detection logic -- purely config-layer and defaults tuning.

</domain>

<decisions>
## Implementation Decisions

### Default timing values (TUNE-01)
- Update AppConfig defaults: activation_delay=0.15, cooldown_duration=0.3, smoothing_window=2
- Update Debouncer __init__ defaults to match: activation_delay=0.15, cooldown_duration=0.3
- Update Smoother __init__ default window_size from 3 to 2
- Update config.yaml shipped values: activation_delay: 0.15, cooldown_duration: 0.3, smoothing_window: 2
- Config.yaml currently has smoothing_window: 30 -- this is almost certainly experimental/accidental, update to 2
- Update all test assertions that reference old defaults (0.4, 0.8, 3)

### Settling frames config surface (TUNE-02)
- Add `swipe_settling_frames` field to AppConfig with default 3 (current hardcoded value from Phase 9)
- Parse from `swipe.settling_frames` in config.yaml
- Wire to SwipeDetector constructor in both __main__.py and tray.py
- Add hot-reload support in both detection loops
- Config.yaml example: `settling_frames: 3` under swipe section

### Per-gesture cooldown overrides (TUNE-03)
- Config key name: `cooldown` (not `cooldown_duration`) -- shorter, consistent with swipe section's `cooldown` key
- Nested under each gesture entry alongside existing `key` and `threshold` fields
- Gestures WITHOUT a `cooldown` key fall back to global `detection.cooldown_duration`
- Debouncer receives a `gesture_cooldowns: dict[str, float]` param, looks up on FIRED->COOLDOWN transition
- Config.yaml: do NOT add default cooldown overrides to any gesture -- only add commented examples showing the syntax so users know the option exists
- Hot-reload must update debouncer's gesture cooldown dict in both loops

### Claude's Discretion
- Exact variable naming for per-gesture cooldown internal state in debouncer
- Whether to use `_cooldown_duration_active` or similar for the per-fire cooldown value
- Comment formatting and placement in config.yaml for new options
- Test structure for new config parsing tests

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `config.py:AppConfig`: Dataclass with all timing fields -- add new fields here
- `config.py:load_config()`: YAML parsing with `.get()` fallback pattern -- follow for new fields
- `debounce.py:GestureDebouncer`: State machine with single `_cooldown_duration` -- extend for per-gesture lookup
- `smoother.py:GestureSmoother`: Window-based smoother with configurable `window_size`
- `swipe.py:SwipeDetector`: Already accepts `settling_frames` param (default 3) -- just needs config wiring

### Established Patterns
- Config field pattern: AppConfig field -> load_config() parse -> component constructor -> hot-reload setter
- Per-gesture config nesting: `threshold` already parsed per-gesture from nested dict -- `cooldown` follows same pattern
- Both `__main__.py` and `tray.py` have duplicated detection loops -- MUST modify both identically (STATE.md concern)

### Integration Points
- `__main__.py` and `tray.py`: Constructor calls and hot-reload blocks for new config fields
- `debounce.py:_handle_fired()`: Where per-gesture cooldown lookup happens (sets cooldown duration based on fired gesture)
- `debounce.py:_handle_cooldown()`: Must use per-fire cooldown duration instead of global default

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- all decisions auto-accepted from Claude's recommendations based on research findings and established codebase patterns.

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 10-tuned-defaults-and-config-surface*
*Context gathered: 2026-03-23*
