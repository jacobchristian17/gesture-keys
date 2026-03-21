# Phase 5: Swipe Detection - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Detect directional hand swipes (left, right, up, down) and fire mapped keyboard commands. Swipe detection runs as a parallel pipeline alongside static gesture detection, with its own rolling buffer and cooldown. Mutual exclusion between swipes and static gestures is Phase 6 (INT-01). Preview overlay for swipe feedback is Phase 7 (SWIPE-05).

</domain>

<decisions>
## Implementation Decisions

### Swipe firing behavior
- Swipe cooldown is configurable in config.yaml (user sets their preferred duration)
- After cooldown expires, the next swipe motion fires immediately — no "return to rest" requirement
- Cooldown-only re-arm: allows rapid back-and-forth swiping once cooldown elapses

### Sensitivity configuration
- Individual thresholds exposed in config.yaml: min_velocity, min_displacement, axis_ratio
- Global thresholds apply to all four swipe directions (no per-direction overrides)

### Claude's Discretion
- Fire timing: whether to fire on peak velocity or deceleration — optimize for preventing false fires
- Diagonal handling: axis ratio threshold and whether to snap-to-dominant-axis or reject ambiguous swipes
- Default threshold values for min_velocity, min_displacement, axis_ratio — bias toward what satisfies SWIPE-05 (no false fires from repositioning/jitter)
- Whether swipe section missing from config disables swipes or enables with defaults — follow whichever pattern is most consistent with existing config behavior
- Rolling buffer size (5-8 frames per Phase 4 research)
- Swipe cooldown default value

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `DistanceFilter` (distance.py): Uses WRIST landmark and palm span — swipe detector will also track WRIST position for velocity
- `GestureSmoother` (smoother.py): Uses `collections.deque` with majority vote — swipe detector needs similar rolling deque for velocity buffer
- `GestureDebouncer` (debounce.py): State machine pattern (IDLE→ACTIVATING→FIRED→COOLDOWN) — swipe needs its own cooldown but can follow similar state pattern
- `AppConfig` dataclass + `load_config()` (config.py): Established pattern for adding new config sections

### Established Patterns
- Config: top-level YAML section → `AppConfig` dataclass fields → `load_config()` parser with defaults
- Distance gating: `distance:` section with `enabled` + params; missing section = disabled
- Pipeline: camera → detector → distance_filter → classifier → smoother → debouncer → keystroke sender
- Hot-reload: `ConfigWatcher` polls mtime, updates component properties inline
- Logging: `gesture_keys` logger, transition-only logging for state changes

### Integration Points
- Both `__main__.py:run_preview_mode()` and `tray.py:TrayApp._detection_loop()` have duplicated detection loops — swipe detection must be added to both identically
- SwipeDetector runs as parallel path after `detector.detect()` (landmarks), bypassing smoother/debouncer (per Phase 4 research)
- Swipe gesture types need to integrate with `keystroke.py:KeystrokeSender` and `parse_key_string()` for key firing
- Config hot-reload sections in both loops need to update swipe detection settings

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 05-swipe-detection*
*Context gathered: 2026-03-21*
