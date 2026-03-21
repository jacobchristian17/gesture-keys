# Phase 4: Distance Gating - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Filter gesture detection by hand proximity using palm span threshold. Users can configure a minimum hand size in config.yaml so gestures only fire when the hand is close enough to the camera. Existing static gestures continue to work exactly as before when distance gating is disabled or the hand is within range. Preview overlays for distance values are Phase 7.

</domain>

<decisions>
## Implementation Decisions

### Config structure
- New top-level `distance:` section in config.yaml with `enabled` (bool) and `min_hand_size` (float) keys
- When the `distance:` section is missing entirely, distance gating is disabled — v1.0 configs work with zero changes
- Users opt in by adding the `distance:` section to their config

### Gating feedback
- DEBUG-level log when hand is filtered by distance (e.g., "Hand filtered: palm span 0.08 < threshold 0.15")
- Log on transitions only — once when hand goes out of range, once when it returns — not every frame
- Reset smoother buffer and debouncer state when hand is gated out of range, preventing stale gestures from firing when hand returns
- Distance gating settings (`enabled`, `min_hand_size`) hot-reload when config.yaml is edited, consistent with existing detection setting hot-reload

### Claude's Discretion
- Default `min_hand_size` threshold value
- Whether `enabled: false` preserves or ignores the threshold value (must satisfy success criteria #2: toggle without removing values)
- Exact position of distance check in the pipeline (before classifier vs after detector)
- Any additional config validation or error messages

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `classifier.py`: Already defines `WRIST = 0` and `MIDDLE_MCP = 9` landmark indices — palm span calculation uses these
- `config.py`: `AppConfig` dataclass and `load_config()` — needs new `distance_enabled` and `min_hand_size` fields
- `config.py`: `ConfigWatcher` — already handles hot-reload; distance settings piggyback on existing reload path

### Established Patterns
- Pipeline: camera → detector → classifier → smoother → debouncer → keystroke sender
- Config hot-reload: watcher checks mtime, reloads full config, updates component fields inline
- Logging: `gesture_keys` logger, INFO for fired events, DEBUG for transitions

### Integration Points
- Both `__main__.py:run_preview_mode()` and `tray.py:TrayApp._detection_loop()` have duplicated detection loops — distance gating must be added to both identically
- Distance check goes between `detector.detect()` (landmarks) and `classifier.classify()` (gesture) in both loops
- Hot-reload sections in both loops need to update distance gating settings

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

*Phase: 04-distance-gating*
*Context gathered: 2026-03-21*
