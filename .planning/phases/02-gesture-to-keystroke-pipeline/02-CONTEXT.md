# Phase 2: Gesture-to-Keystroke Pipeline - Context

**Gathered:** 2026-03-21
**Status:** Ready for planning

<domain>
## Phase Boundary

Detected gestures pass through a debounce state machine (activation delay + cooldown) and fire mapped keyboard commands via pynput in any foreground application. Config hot-reload applies new gesture-to-key mappings without restarting. Logging captures fire events and state machine activity.

</domain>

<decisions>
## Implementation Decisions

### Debounce state machine
- State machine: IDLE → ACTIVATING → FIRED → COOLDOWN → IDLE
- Activation delay: 0.4s (configurable in config.yaml `detection.activation_delay`)
- Cooldown duration: 0.8s (configurable in config.yaml `detection.cooldown_duration`)
- Mid-activation gesture switch: reset timer — new gesture starts fresh 0.4s hold
- Cooldown is global — after ANY gesture fires, ALL gestures blocked for cooldown duration
- Release detection: gesture must smooth to None for N frames before new activation can begin (uses existing smoother)
- Brief/flickering gestures under activation delay do not fire

### Key mapping
- Config format already established: `gestures.<name>.key` with values like `ctrl+z`, `space`, `enter`
- pynput handles single keys and key combos (from PROJECT.md decision)
- Carried forward from Phase 1: default mappings (open_palm=space, fist=ctrl+z, thumbs_up=ctrl+s, peace=ctrl+c, pointing=enter, pinch=ctrl+v)

### Hot-reload
- Config hot-reload mechanism (KEY-05) — trigger approach is Claude's discretion (file watcher, polling, or signal)
- Invalid config on reload: keep current config, log error at WARNING level
- Successful reload logged at INFO with summary (gesture count, key settings)

### Logging
- Key fire events at INFO: `[HH:MM:SS] FIRED: fist → ctrl+z` (gesture name + key fired)
- Suppressed events (cooldown blocks, too-short holds) at DEBUG level — invisible by default
- State machine transitions (IDLE → ACTIVATING → FIRED → COOLDOWN) at DEBUG level
- Hot-reload events at INFO with summary: gesture count, timing config
- Continues Phase 1 logging format: `[HH:MM:SS]` via Python logging module

### Claude's Discretion
- Hot-reload trigger mechanism (file watcher vs polling vs signal)
- Exact state machine implementation (class vs function, timer approach)
- Key combo parsing strategy (splitting `ctrl+z` into modifier + key for pynput)
- Error handling for failed key sends (e.g., invalid key names in config)
- How many frames of None constitute a "release" for cooldown reset

</decisions>

<specifics>
## Specific Ideas

- Activation delay and cooldown should be in config.yaml under `detection` section alongside existing `smoothing_window`
- Log format matches Phase 1 convention: `[HH:MM:SS]` with Python logging module
- The arrow notation in fire logs (`fist → ctrl+z`) makes it immediately clear what triggered what

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `GestureSmoother` (smoother.py): Already provides smoothed gesture output — debounce state machine consumes this
- `GestureClassifier` + `Gesture` enum (classifier.py): Gesture values used as state machine input
- `AppConfig` + `load_config()` (config.py): Extend with activation_delay, cooldown_duration fields; reload path reuses same function
- `config.yaml`: Add `detection.activation_delay` and `detection.cooldown_duration` to existing structure
- Main loop in `__main__.py`: Already has gesture transition detection (`gesture != prev_gesture`) — debounce replaces this simple check

### Established Patterns
- Dataclass config (`AppConfig`): New timing fields follow same pattern
- Module-per-concern: debounce.py and keystroke.py would follow detector.py, classifier.py pattern
- Logging via `logging.getLogger("gesture_keys")` with `[HH:MM:SS]` format

### Integration Points
- Main loop (`__main__.py`): Insert debounce state machine between smoother output and new keystroke firing
- `config.py`: Add activation_delay/cooldown_duration to AppConfig, extend load_config() parsing
- `config.yaml`: Add timing fields to detection section, key mappings already present in gestures section
- Phase 3 will add tray menu reload trigger — hot-reload infrastructure built here must be callable externally

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 02-gesture-to-keystroke-pipeline*
*Context gathered: 2026-03-21*
