# Phase 14: Shared Types and Pipeline Unification - Research

**Researched:** 2026-03-24
**Domain:** Python refactoring -- extract unified pipeline from duplicated detection loops
**Confidence:** HIGH

## Summary

Phase 14 is a pure refactoring phase: extracting ~300 lines of character-for-character identical detection logic from `__main__.py` (571 lines) and `tray.py` (515 lines) into a single unified `Pipeline` class with shared data types. No new features, no new dependencies. The existing codebase is 100% Python with well-defined component interfaces (`GestureClassifier`, `GestureSmoother`, `GestureDebouncer`, `SwipeDetector`, `DistanceFilter`, `KeystrokeSender`, `ConfigWatcher`), all of which have `.reset()` methods and clean initialization patterns.

The core challenge is decomposing the monolithic `run_preview_mode()` and `TrayApp._detection_loop()` into a Pipeline class that owns: (1) component initialization, (2) per-frame processing (the detection loop body), (3) config hot-reload, and (4) pipeline reset (hand switch, distance out-of-range, swipe transitions). The wrappers then become thin shells: preview adds FPS/rendering/cv2 window management (~40 lines unique), tray adds threading.Event active/shutdown lifecycle (~50 lines unique).

**Primary recommendation:** Create `gesture_keys/pipeline.py` with a `Pipeline` class that owns all components from camera through keystroke dispatch, exposing `process_frame(frame) -> FrameResult` and `reload_config()`. Move the three `_parse_*_key_mappings()` helpers into pipeline.py (or a `gesture_keys/key_mappings.py` utility). Define `FrameResult` as a `@dataclass` carrying the per-frame outputs needed by preview rendering.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
(None -- all implementation decisions are at Claude's discretion)

### Claude's Discretion
All implementation decisions for this phase are at Claude's discretion. The user trusts the builder to make the right calls across all four gray areas:

**Pipeline class boundary:**
- What goes inside the unified Pipeline class vs. what stays in mode wrappers
- Whether Pipeline owns camera/detector lifecycle or just the detection loop body
- Whether Pipeline owns config hot-reload internally or wrappers drive reload

**Shared type design:**
- How FrameResult and other shared types flow between pipeline stages
- Typed dataclass per frame vs. loose dicts
- What fields FrameResult carries
- How signals propagate from debouncer to keystroke dispatch

**Hot-reload ownership:**
- Where config reload logic lives (currently ~80 lines of inline property patching duplicated in both loops)
- Whether Pipeline.reload_config() rebuilds components or patches them
- How the SWIPE_WINDOW edge case on reload is handled

**Tray active/inactive cycle:**
- How tray mode's active/inactive toggle interacts with the unified Pipeline
- Whether Pipeline uses start()/stop(), pause/resume, or same lifecycle as preview
- Currently tray tears down and recreates all components on reactivate -- can change

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | Shared data types (FrameResult, GestureState, TemporalState enums) used by all pipeline components | Architecture Patterns: FrameResult dataclass design, existing enums (Gesture, DebounceState, SwipeDirection) already in place |
| PIPE-02 | Unified pipeline class that both preview and tray modes call, eliminating duplicated loop logic | Architecture Patterns: Pipeline class design, Code Examples: process_frame() pattern |
| PIPE-03 | Preview mode wrapper using unified pipeline (~80 lines, down from 571) | Architecture Patterns: preview wrapper structure, what stays outside Pipeline |
| PIPE-04 | Tray mode wrapper using unified pipeline (~50 lines, down from 515) | Architecture Patterns: tray wrapper structure, active/inactive lifecycle |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| dataclasses (stdlib) | 3.7+ | FrameResult, shared types | Already used for AppConfig; zero dependency |
| enum (stdlib) | 3.4+ | Gesture, DebounceState, SwipeDirection already exist | Already in codebase |
| typing (stdlib) | 3.5+ | Optional, type annotations | Already in codebase |

### Supporting
No new dependencies. This is a pure refactoring phase using only existing project dependencies (cv2, mediapipe, pystray, pynput, pyyaml, pillow).

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| @dataclass FrameResult | NamedTuple | NamedTuple is immutable (good), but dataclass allows optional fields with defaults (better for incremental adoption) |
| Single Pipeline class | Separate PipelineBuilder + PipelineRunner | Over-engineering for ~300 lines of logic; single class is appropriate |

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
  pipeline.py          # NEW: Pipeline class + FrameResult dataclass
  __main__.py           # SLIMMED: ~80 lines (preview wrapper)
  tray.py               # SLIMMED: ~50 lines (tray wrapper)
  classifier.py         # UNCHANGED
  config.py             # UNCHANGED
  debounce.py           # UNCHANGED
  detector.py           # UNCHANGED
  distance.py           # UNCHANGED
  keystroke.py          # UNCHANGED
  smoother.py           # UNCHANGED
  swipe.py              # UNCHANGED
  preview.py            # UNCHANGED
```

### Pattern 1: Pipeline Class with process_frame()

**What:** A single `Pipeline` class that owns all detection components and exposes a `process_frame(frame) -> FrameResult` method that encapsulates the entire detection logic body (currently duplicated as ~200 lines in each loop).

**When to use:** Both preview and tray modes call `pipeline.process_frame(frame)` each iteration.

**Design:**
```python
@dataclass
class FrameResult:
    """Per-frame output from the detection pipeline."""
    landmarks: list | None = None
    handedness: str | None = None
    gesture: Gesture | None = None
    raw_gesture: Gesture | None = None
    debounce_state: DebounceState = DebounceState.IDLE
    fired_action: str | None = None       # Log message for what fired
    swiping: bool = False

class Pipeline:
    """Unified gesture detection pipeline.

    Owns: camera, detector, classifier, smoother, debouncer,
          swipe_detector, distance_filter, sender, config_watcher,
          key mappings, and all per-frame state variables.
    """

    def __init__(self, config_path: str) -> None: ...
    def start(self) -> None: ...           # Initialize camera + detector
    def stop(self) -> None: ...            # Release camera + detector + held keys
    def process_frame(self) -> FrameResult: ...  # Read frame, run detection, fire keys
    def reload_config(self) -> None: ...   # Hot-reload from config file
    def reset_pipeline(self) -> None: ...  # Reset smoother/debouncer/swipe/hold state
```

**Key insight:** Pipeline owns camera.read() internally so that `process_frame()` is a zero-argument call. This keeps wrappers trivially simple: they just call `pipeline.process_frame()` in a loop and inspect the result for rendering (preview) or do nothing (tray).

### Pattern 2: Preview Wrapper (Target: ~80 lines)

**What:** Thin wrapper that sets up logging, creates Pipeline, runs the frame loop with FPS calculation, renders preview, handles cv2 window events.

**Unique to preview (not in Pipeline):**
- Argument parsing and banner printing (already separate functions)
- FPS calculation from frame delta times
- `draw_hand_landmarks()` and `render_preview()` calls
- `cv2.waitKey()` and window close detection
- Per-frame debug logging (raw/smooth/state) when `--debug` flag set
- `cv2.destroyAllWindows()` on exit

### Pattern 3: Tray Wrapper (Target: ~50 lines)

**What:** `TrayApp` class keeps pystray icon management, menu, active/inactive toggle. Detection loop becomes:

```python
def _detection_loop(self) -> None:
    while not self._shutdown.is_set():
        if not self._active.wait(timeout=0.5):
            continue
        if self._shutdown.is_set():
            break
        pipeline = Pipeline(self._config_path)
        pipeline.start()
        try:
            while self._active.is_set() and not self._shutdown.is_set():
                pipeline.process_frame()
        finally:
            pipeline.stop()
```

**Key insight:** Tray mode tears down and recreates the full pipeline on each active/inactive cycle. This is the existing behavior and should be preserved -- Pipeline.start()/stop() maps directly to the current create/teardown pattern.

### Pattern 4: Key Mapping Parsing (Move to Pipeline)

**What:** The three identical helper functions (`_parse_key_mappings`, `_parse_swipe_key_mappings`, `_parse_compound_swipe_key_mappings`) currently duplicated in both files move into `pipeline.py` as private methods or module-level functions.

### Pattern 5: Internal State Management

**What:** Pipeline owns all the per-frame state variables currently scattered as local variables in the loop:
- `prev_gesture`, `pre_swipe_gesture`, `prev_handedness`
- `hand_was_in_range`, `was_swiping`
- `hold_active`, `hold_modifiers`, `hold_key`, `hold_key_string`, `hold_gesture_name`, `hold_last_repeat`
- `compound_swipe_suppress_until`
- Active key/swipe/compound mapping sets (for current hand)

These become `self._` attributes on Pipeline, initialized in `__init__` or `start()`.

### Anti-Patterns to Avoid
- **Extracting too granularly:** Don't create separate classes for hand-switch logic, distance-gating logic, etc. These are 5-20 line blocks. Keep them as sections within `process_frame()` with clear comments.
- **Changing detection behavior:** This is a move-only refactoring. Every `if/else` branch, every state transition, every edge case must be preserved character-for-character in logic (even if variable names change from locals to self._attributes).
- **Breaking the config hot-reload SWIPE_WINDOW edge case:** When config reloads during SWIPE_WINDOW state, the debouncer fires the static action before resetting. This subtle behavior must be preserved in `reload_config()`.
- **Abstracting away the raw frame:** Pipeline should still expose the frame (via FrameResult or a separate property) so preview mode can render landmarks on it.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Thread synchronization for tray | Custom locking around Pipeline | threading.Event (already used) | Pipeline is single-threaded per active cycle; tray's outer loop handles lifecycle |
| Config change detection | Custom file watcher | ConfigWatcher (already exists) | Proven mtime-based polling with configurable interval |
| Keystroke lifecycle | Manual key press/release tracking | KeystrokeSender.release_all() (already exists) | Already handles modifier + key release correctly |

## Common Pitfalls

### Pitfall 1: Behavioral Regression in Edge Cases
**What goes wrong:** Refactoring changes detection behavior subtly (e.g., swipe suppression timing, hold repeat interval, debouncer state injection on swipe exit).
**Why it happens:** The original code has ~10 subtle edge-case behaviors embedded in specific ordering of operations within the loop body.
**How to avoid:** Extract the loop body as-is, converting local variables to self._ attributes. Do NOT reorder operations. The existing test suite (especially test_compound_gesture.py, test_debounce.py, test_integration.py) must pass without assertion changes.
**Warning signs:** Any test that needs assertion changes is a regression signal.

### Pitfall 2: Config Hot-Reload SWIPE_WINDOW Race
**What goes wrong:** The reload logic has a specific check: if `debouncer.in_swipe_window and debouncer.activating_gesture is not None`, it fires the static action before resetting. Missing this causes gesture drops on config edit.
**Why it happens:** This is ~5 lines buried in ~80 lines of reload logic, easy to overlook.
**How to avoid:** Move the entire reload block as-is into `Pipeline.reload_config()`. Test by verifying the SWIPE_WINDOW fire-before-reset behavior is preserved.

### Pitfall 3: Tray Mode max_hand_size Missing
**What goes wrong:** The tray.py `DistanceFilter` initialization on line 187-190 is missing `max_hand_size=config.max_hand_size` (it only passes `min_hand_size` and `enabled`). The `__main__.py` version on line 194-198 correctly passes all three parameters.
**Why it happens:** This is a pre-existing bug from incomplete copy-paste between the two files.
**How to avoid:** The unified Pipeline will use the complete initialization from `__main__.py`, fixing this bug automatically. Document this as a known fix.

### Pitfall 4: FrameResult Carrying Too Much or Too Little
**What goes wrong:** If FrameResult carries too little (e.g., no landmarks), preview mode can't render. If it carries too much (e.g., all internal state), it becomes a god object.
**Why it happens:** Unclear boundary between pipeline internals and wrapper needs.
**How to avoid:** FrameResult should carry exactly what preview needs to render: `landmarks`, `handedness`, `gesture` (smoothed), `raw_gesture`, `debounce_state` (for overlay), `swiping` flag. The fired action log messages are handled internally by Pipeline via logger calls.

### Pitfall 5: Frame Access for Preview Rendering
**What goes wrong:** If Pipeline.process_frame() reads the camera frame internally and only returns FrameResult, preview mode has no frame to render on.
**Why it happens:** Camera ownership by Pipeline means the raw frame is internal.
**How to avoid:** Two options: (A) Pipeline stores `self._last_frame` and exposes it as a property, or (B) process_frame() returns `(frame, FrameResult)` tuple. Option A is cleaner since it keeps the return type simple. Preview does `frame = pipeline.last_frame; result = pipeline.process_frame(); draw_hand_landmarks(frame, result.landmarks)`.

### Pitfall 6: Hold Repeat Timing
**What goes wrong:** Hold repeat fires keys at `hold_repeat_interval` (default 30ms). If Pipeline.process_frame() doesn't track `current_time` correctly for hold repeat, keys fire at wrong rate.
**Why it happens:** `current_time` is used both for debouncer.update() and hold repeat checks.
**How to avoid:** Pipeline should use `time.perf_counter()` at the start of each process_frame() call, stored as `self._current_time`, used consistently throughout.

## Code Examples

### FrameResult Dataclass
```python
from dataclasses import dataclass, field
from typing import Optional
from gesture_keys.classifier import Gesture
from gesture_keys.debounce import DebounceState

@dataclass
class FrameResult:
    """Per-frame output from the unified detection pipeline."""
    landmarks: list | None = None
    handedness: str | None = None
    gesture: Gesture | None = None         # smoothed gesture
    raw_gesture: Gesture | None = None     # pre-smoothing gesture
    debounce_state: DebounceState = DebounceState.IDLE
    swiping: bool = False
    frame_valid: bool = True               # False if camera.read() failed
```

### Pipeline.__init__ Initialization
```python
class Pipeline:
    def __init__(self, config_path: str) -> None:
        self._config_path = config_path
        self._config = load_config(config_path)
        # Components (created in start())
        self._camera = None
        self._detector = None
        self._classifier = None
        self._smoother = None
        self._debouncer = None
        self._sender = None
        self._distance_filter = None
        self._swipe_detector = None
        self._watcher = None
        # Per-frame state
        self._prev_gesture = None
        self._pre_swipe_gesture = None
        self._prev_handedness = None
        self._hand_was_in_range = True
        self._was_swiping = False
        self._compound_swipe_suppress_until = 0.0
        # Hold state
        self._hold_active = False
        self._hold_modifiers = None
        self._hold_key = None
        self._hold_key_string = None
        self._hold_gesture_name = None
        self._hold_last_repeat = 0.0
        # Frame storage for preview access
        self._last_frame = None
        self._current_time = 0.0
```

### Pipeline.start() / stop()
```python
def start(self) -> None:
    """Initialize camera, detector, and all pipeline components."""
    config = self._config
    self._camera = CameraCapture(config.camera_index).start()
    self._detector = HandDetector(preferred_hand=config.preferred_hand)
    thresholds = {
        name: settings.get("threshold", 0.7)
        for name, settings in config.gestures.items()
        if isinstance(settings, dict)
    }
    self._classifier = GestureClassifier(thresholds)
    self._smoother = GestureSmoother(config.smoothing_window)
    # ... (all component init from current code)
    self._watcher = ConfigWatcher(self._config_path)

def stop(self) -> None:
    """Release all resources: camera, detector, held keys."""
    if self._sender:
        self._sender.release_all()
    if self._camera:
        self._camera.stop()
    if self._detector:
        self._detector.close()
```

### Slim Preview Wrapper
```python
def run_preview_mode(args):
    config = load_config(args.config)
    print_banner(config, args.config)
    setup_logging(args.debug)

    pipeline = Pipeline(args.config)
    pipeline.start()

    prev_time = time.perf_counter()
    fps = 0.0
    try:
        while True:
            current_time = time.perf_counter()
            dt = current_time - prev_time
            if dt > 0:
                fps = 1.0 / dt
            prev_time = current_time

            result = pipeline.process_frame()
            if not result.frame_valid:
                continue

            # Debug logging
            if args.debug and result.landmarks:
                logger.debug("FRAME raw=%s smooth=%s state=%s ...",
                    result.raw_gesture, result.gesture, result.debounce_state)

            # Preview rendering
            frame = pipeline.last_frame
            if result.landmarks:
                draw_hand_landmarks(frame, result.landmarks)
            render_preview(frame, result.gesture, fps,
                debounce_state=result.debounce_state,
                handedness=result.handedness)

            key = cv2.waitKey(1) & 0xFF
            if key == 27:
                break
            try:
                if cv2.getWindowProperty("Gesture Keys", cv2.WND_PROP_VISIBLE) < 1:
                    break
            except cv2.error:
                break
    except KeyboardInterrupt:
        pass
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Duplicated detection loops in __main__.py and tray.py | Unified Pipeline class | Phase 14 (this phase) | Eliminates ~300 lines of duplication, single source of truth for detection logic |

**Deprecated/outdated:**
- None -- this is internal refactoring, no external dependency changes.

## Open Questions

1. **Should Pipeline own config loading or receive a config object?**
   - What we know: Currently both modes call `load_config()` directly. Pipeline could accept either a path string or a pre-loaded AppConfig.
   - What's unclear: Whether accepting a path is simpler (Pipeline can reload internally) vs. accepting AppConfig (more testable).
   - Recommendation: Accept path string. Pipeline loads config internally and handles reload internally. This is simpler and matches the hot-reload pattern where Pipeline needs the path anyway.

2. **Should process_frame() handle camera.read() or should the wrapper pass in frames?**
   - What we know: If Pipeline owns camera, process_frame() can be zero-arg (simplest wrapper). If wrapper owns camera, Pipeline becomes more testable (can inject test frames).
   - What's unclear: Test implications.
   - Recommendation: Pipeline owns camera (matching current behavior). For testing, either: (a) mock CameraCapture, or (b) add an optional `process_frame(frame=None)` that uses self._camera.read() when frame is None. Option (a) is simpler and matches existing test patterns.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (stdlib) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -q` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PIPE-01 | FrameResult dataclass fields, Gesture/DebounceState/SwipeDirection enums accessible | unit | `python -m pytest tests/test_pipeline.py::TestFrameResult -x` | No -- Wave 0 |
| PIPE-02 | Pipeline.process_frame() produces correct FrameResult for known landmark input | unit | `python -m pytest tests/test_pipeline.py::TestPipelineProcessFrame -x` | No -- Wave 0 |
| PIPE-02 | Pipeline.reload_config() updates components without crash | unit | `python -m pytest tests/test_pipeline.py::TestPipelineReload -x` | No -- Wave 0 |
| PIPE-02 | Pipeline.reset_pipeline() resets all component state | unit | `python -m pytest tests/test_pipeline.py::TestPipelineReset -x` | No -- Wave 0 |
| PIPE-03 | All existing tests pass (preview behavior preserved) | regression | `python -m pytest tests/test_integration.py -x` | Yes |
| PIPE-04 | All existing tests pass (tray behavior preserved) | regression | `python -m pytest tests/test_tray.py -x` | Yes |
| PIPE-03 | Preview wrapper is under 80 lines | manual-only | Line count check after implementation | N/A |
| PIPE-04 | Tray wrapper is under 50 lines | manual-only | Line count check after implementation | N/A |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_pipeline.py` -- covers PIPE-01, PIPE-02 (FrameResult, Pipeline.process_frame, reload, reset)
- [ ] Framework install: None needed -- pytest already configured

## Sources

### Primary (HIGH confidence)
- Source code analysis of `gesture_keys/__main__.py` (571 lines) -- full detection loop structure
- Source code analysis of `gesture_keys/tray.py` (515 lines) -- full detection loop structure
- Source code analysis of all pipeline components: classifier.py, smoother.py, debounce.py, swipe.py, distance.py, detector.py, keystroke.py, config.py
- Existing test suite: 14 test files covering all individual components

### Secondary (MEDIUM confidence)
- N/A (pure refactoring, no external research needed)

### Tertiary (LOW confidence)
- N/A

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, pure stdlib dataclasses
- Architecture: HIGH -- based on line-by-line analysis of both source files identifying exact duplication boundaries
- Pitfalls: HIGH -- identified from actual code diff between __main__.py and tray.py (including the max_hand_size bug)

**Research date:** 2026-03-24
**Valid until:** Indefinite (internal refactoring, no external dependency concerns)
