# Architecture: v2.0 Structured Gesture Pipeline

**Domain:** Real-time gesture-to-keystroke pipeline -- clean rewrite with activation gating, gesture hierarchy, and fire modes
**Researched:** 2026-03-24
**Confidence:** HIGH (direct analysis of existing 7,549 LOC codebase + domain patterns from v1.0-v1.3 iterations)

## Problem Statement

The v1.0-v1.3 pipeline grew organically: classifier, smoother, debouncer, swipe detector, compound gestures, hand switching, and activation gate were layered incrementally. The result is a 570-line `__main__.py` and 515-line `tray.py` with near-identical main loops, ad-hoc state coordination (e.g., `compound_swipe_suppress_until`, `pre_swipe_gesture`, `was_swiping`), and direct internal state mutations (`debouncer._state = DebounceState.COOLDOWN`).

v2.0 replaces this with a structured pipeline where each component has a clear single responsibility, typed data flows between components via well-defined interfaces, and the orchestrator coordinates without reaching into component internals.

## Recommended Architecture

### High-Level Pipeline

```
CameraCapture (thread)
    |
    v  BGR frame
HandDetector (MediaPipe, num_hands=2)
    |
    v  (landmarks: list[21], handedness: str | None)
HandSelector (preferred_hand, sticky tracking)
    |
    v  (landmarks, handedness) for active hand only
DistanceFilter
    |
    v  landmarks | None (gated)
ActivationGate                          <--- NEW role in pipeline
    |  consumes activation gesture
    |  gates all downstream processing
    v  landmarks | None (gated when disarmed)
GestureClassifier
    |
    v  StaticGesture | None
GestureSmoother
    |
    v  StaticGesture | None (majority-vote filtered)
         |
         +--- passed to GestureOrchestrator --->
         |                                      |
    SwipeDetector                               |
         |                                      |
         v  SwipeDirection | None               |
         +--- passed to GestureOrchestrator --->+
                                                |
                                    GestureOrchestrator     <--- NEW
                                        |  combines static + temporal
                                        |  manages state machine
                                        v  OrchestratorSignal | None
                                    ActionResolver           <--- NEW
                                        |  maps signal to action
                                        v  ResolvedAction | None
                                    FireModeExecutor          <--- NEW
                                        |  executes tap / hold_key
                                        v  KeystrokeSender
```

### Component Boundaries

| Component | Responsibility | Input | Output | State |
|-----------|---------------|-------|--------|-------|
| **CameraCapture** | Threaded frame acquisition | camera index | (ret, frame) | Internal thread, frame buffer |
| **HandDetector** | MediaPipe landmark extraction | BGR frame, timestamp_ms | (landmarks[], handedness[]) per hand | MediaPipe internal, last_timestamp |
| **HandSelector** | Active hand tracking, sticky selection | all detected hands | single (landmarks, handedness) | active_hand, preferred_hand |
| **DistanceFilter** | Palm-span range gating | landmarks | bool (in_range) | Stateless (logging only) |
| **ActivationGate** | Arm/disarm system via gesture | StaticGesture, timestamp | bool (is_armed) | armed_at, armed state |
| **GestureClassifier** | Rule-based pose classification | landmarks | StaticGesture or None | Stateless |
| **GestureSmoother** | Majority-vote flicker filter | StaticGesture or None | StaticGesture or None | Sliding window buffer |
| **SwipeDetector** | Velocity-based directional swipe | landmarks, timestamp | SwipeDirection or None | Wrist buffer, state machine (IDLE/ARMED/COOLDOWN) |
| **GestureOrchestrator** | Combine static + temporal, debounce, emit signals | smoothed gesture, swipe direction, timestamp | OrchestratorSignal or None | Unified state machine |
| **ActionResolver** | Map orchestrator signals to concrete actions | OrchestratorSignal, config mappings | ResolvedAction or None | Pre-parsed key mappings (per-hand) |
| **FireModeExecutor** | Execute tap or hold_key fire modes | ResolvedAction | keystroke side effects | Hold state (active_key, repeat timer) |
| **KeystrokeSender** | pynput press/release | modifiers, key | OS keystroke | Controller instance |

## New Components (Detailed Design)

### 1. HandSelector (extracted from HandDetector + main loop)

Currently, hand selection logic is split between `HandDetector.detect()` (sticky tracking, preferred hand) and the main loop (hand-switch reset, mapping swap). This should be extracted into a dedicated component.

```python
@dataclass
class HandFrame:
    """Single-hand data for one frame."""
    landmarks: list        # 21 MediaPipe landmarks
    handedness: str        # "Left" or "Right"

class HandSelector:
    """Selects which hand to process from multi-hand detection results.

    Handles sticky tracking (keep current hand when both visible),
    preferred hand selection on startup, and hand-switch detection.
    """

    def __init__(self, preferred_hand: str = "left") -> None: ...

    def update(self, detected_hands: dict[str, list]) -> HandFrame | None:
        """Select active hand from detected hands.

        Returns:
            HandFrame for the active hand, or None if no hand detected.
            Sets self.hand_changed if hand switched this frame.
        """

    @property
    def hand_changed(self) -> bool:
        """True if active hand changed on the last update() call."""

    @property
    def active_handedness(self) -> str | None:
        """Current active hand label, or None."""

    def reset(self) -> None: ...
```

**Why extract:** The main loop currently has 20+ lines of hand-switch boilerplate duplicated in both `__main__.py` and `tray.py`. HandSelector encapsulates this, and exposes `hand_changed` so the pipeline controller can react (reset state machines, swap mappings).

### 2. GestureOrchestrator (replaces GestureDebouncer + main loop coordination)

The orchestrator is the core architectural change. It replaces:
- GestureDebouncer (6 states, 7 methods, ~280 lines)
- Main loop swipe/static coordination (~100 lines of `was_swiping`, `pre_swipe_gesture`, `compound_swipe_suppress_until`, `debouncer._state = ...` hacks)

The orchestrator owns a single unified state machine that understands both static gestures and temporal modifiers (hold duration, swiping).

```python
class TemporalState(Enum):
    """Temporal modifier on a static gesture."""
    TAP = "tap"           # brief activation
    HOLD = "hold"         # sustained beyond hold threshold
    SWIPE = "swipe"       # gesture + directional motion

class OrchestratorSignal(NamedTuple):
    """Signal emitted by the orchestrator."""
    action: SignalAction          # FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE
    gesture: StaticGesture        # which static gesture
    temporal: TemporalState       # tap, hold, or swipe
    direction: SwipeDirection | None  # only for SWIPE temporal state

class SignalAction(Enum):
    FIRE = "fire"                 # one-shot: press+release
    HOLD_START = "hold_start"     # key down begins
    HOLD_END = "hold_end"         # key up
    COMPOUND_FIRE = "compound_fire"  # gesture+swipe combo fires

class GestureOrchestrator:
    """Unified state machine for gesture detection and temporal states.

    Combines static gesture debouncing with temporal state resolution
    (tap vs hold vs swipe). Replaces GestureDebouncer + main loop
    coordination logic.
    """

    def __init__(self, config: OrchestratorConfig) -> None: ...

    def update(
        self,
        gesture: StaticGesture | None,
        timestamp: float,
        *,
        swipe_direction: SwipeDirection | None = None,
    ) -> OrchestratorSignal | None:
        """Process one frame of input, return signal if action needed."""

    def reset(self) -> None:
        """Full reset (hand switch, distance gate exit, config reload)."""

    @property
    def state(self) -> OrchestratorState:
        """Current state for preview display."""

    @property
    def is_activating(self) -> bool:
        """True during activation delay. Used by swipe suppression."""
```

**State machine:**

```
IDLE
  |--[gesture appears, has swipe mappings]--> SWIPE_WINDOW
  |--[gesture appears, no swipe mappings]--> ACTIVATING

ACTIVATING
  |--[held >= activation_delay, mode=tap]--> FIRED
  |--[held >= activation_delay, mode=hold]--> HOLDING
  |--[gesture lost (None)]--> IDLE
  |--[different gesture]--> restart ACTIVATING with new gesture

SWIPE_WINDOW
  |--[swipe detected, mapped direction]--> emit COMPOUND_FIRE --> COOLDOWN
  |--[window expired, gesture still held]--> FIRED (or HOLDING per mode)
  |--[window expired, gesture lost]--> IDLE

FIRED
  |--[immediate]--> COOLDOWN (emit FIRE signal on entry to FIRED)

HOLDING
  |--[same gesture held]--> stay (emit nothing)
  |--[gesture lost, release delay expired]--> COOLDOWN (emit HOLD_END)
  |--[different gesture]--> COOLDOWN (emit HOLD_END) --> ACTIVATING new

COOLDOWN
  |--[time elapsed + None]--> IDLE
  |--[time elapsed + different gesture]--> ACTIVATING (or SWIPE_WINDOW)
  |--[time elapsed + same gesture]--> stay (re-fire prevention)
```

This is the same state machine as the current debouncer, but with SWIPE_WINDOW integrated directly rather than bolted on. The main loop coordination logic (swipe suppression, compound gesture tracking, pre-swipe gesture stashing) is absorbed into the orchestrator.

**Key simplification:** The current codebase has the main loop checking `debouncer.is_activating` to suppress swipe detection, and `debouncer.in_swipe_window` to route swipe results. In v2.0, the orchestrator receives both inputs and handles the coordination internally:

```python
def update(self, gesture, timestamp, *, swipe_direction=None):
    # Orchestrator decides internally whether swipe_direction matters
    # based on its own state. No external coordination needed.
    if self._state == OrchestratorState.SWIPE_WINDOW:
        return self._handle_swipe_window(gesture, timestamp, swipe_direction)
    # ... swipe_direction ignored in other states
```

### 3. ActionResolver (extracted from main loop)

Currently, the main loop has ~50 lines of signal-to-keystroke resolution: checking `DebounceAction`, looking up key mappings, handling compound vs static vs swipe lookups. This should be a separate component.

```python
@dataclass
class ResolvedAction:
    """A concrete action to execute."""
    fire_mode: FireMode         # TAP or HOLD_KEY
    signal_action: SignalAction # FIRE, HOLD_START, HOLD_END, COMPOUND_FIRE
    modifiers: list[Key]        # pynput modifier keys
    key: Key | str              # pynput key
    label: str                  # human-readable label for logging

class FireMode(Enum):
    TAP = "tap"           # press + release
    HOLD_KEY = "hold_key" # sustained keypress

class ActionResolver:
    """Maps orchestrator signals to concrete keystroke actions.

    Pre-parses key mappings at init. Supports per-hand mapping sets
    with hot-swap on hand change.
    """

    def __init__(self, config: AppConfig) -> None:
        self._right_mappings = self._parse_all_mappings(config, "Right")
        self._left_mappings = self._parse_all_mappings(config, "Left")
        self._active_mappings = self._right_mappings

    def resolve(self, signal: OrchestratorSignal) -> ResolvedAction | None:
        """Look up the action for an orchestrator signal.

        Returns None if the gesture/direction has no mapping.
        """

    def set_hand(self, handedness: str) -> None:
        """Swap active mappings for hand switch."""

    def reload(self, config: AppConfig) -> None:
        """Re-parse all mappings from new config."""
```

**Why extract:** The current main loop has three separate `_parse_key_mappings`, `_parse_swipe_key_mappings`, and `_parse_compound_swipe_key_mappings` functions duplicated in both `__main__.py` and `tray.py`. ActionResolver consolidates all mapping logic and provides a single `resolve()` method.

### 4. FireModeExecutor (extracted from main loop hold management)

Currently, hold mode state is managed via 6 bare variables in the main loop (`hold_active`, `hold_modifiers`, `hold_key`, `hold_key_string`, `hold_gesture_name`, `hold_last_repeat`). This should be a component.

```python
class FireModeExecutor:
    """Executes resolved actions via the appropriate fire mode.

    Handles:
    - TAP: press+release via KeystrokeSender
    - HOLD_KEY: sustained keypress with repeat interval
    """

    def __init__(self, sender: KeystrokeSender, repeat_interval: float = 0.03) -> None:
        self._sender = sender
        self._repeat_interval = repeat_interval
        self._hold_active = False
        self._hold_modifiers = None
        self._hold_key = None
        self._hold_last_repeat = 0.0

    def execute(self, action: ResolvedAction) -> None:
        """Execute a resolved action."""

    def tick(self, timestamp: float) -> None:
        """Called every frame. Handles hold-key repeat."""

    def release_all(self) -> None:
        """Force-release any held keys. Called on hand switch, distance exit, etc."""

    @property
    def is_holding(self) -> bool:
        """True if a hold-key action is active."""
```

### 5. Pipeline (replaces main loop procedural code)

The 570-line `run_preview_mode` and 515-line `_detection_loop` share ~80% of their logic. A Pipeline class encapsulates the shared detection logic, and the mode-specific code (preview rendering, tray threading) wraps it.

```python
class Pipeline:
    """Gesture detection pipeline from landmarks to keystroke execution.

    Owns all pipeline components and processes one frame at a time.
    The caller (preview mode or tray mode) is responsible for:
    - Acquiring frames (CameraCapture)
    - Detecting hands (HandDetector)
    - Calling pipeline.process_frame() with results
    - Rendering preview (if preview mode)
    - Config hot-reload scheduling
    """

    def __init__(self, config: AppConfig) -> None:
        self.hand_selector = HandSelector(config.preferred_hand)
        self.distance_filter = DistanceFilter(...)
        self.activation_gate = ActivationGate(...)  # None if gate disabled
        self.classifier = GestureClassifier(...)
        self.smoother = GestureSmoother(...)
        self.swipe_detector = SwipeDetector(...)
        self.orchestrator = GestureOrchestrator(...)
        self.action_resolver = ActionResolver(config)
        self.fire_executor = FireModeExecutor(...)

    def process_frame(
        self,
        detected_hands: dict[str, list],
        timestamp: float,
    ) -> FrameResult:
        """Process one frame through the full pipeline.

        Returns FrameResult with gesture, state, action taken -- enough
        for the caller to render preview overlays or log.
        """

    def reload_config(self, config: AppConfig) -> None:
        """Hot-reload all pipeline components from new config."""

    def shutdown(self) -> None:
        """Release all held keys, clean up."""

@dataclass
class FrameResult:
    """Result of processing one frame. Used for preview rendering and logging."""
    handedness: str | None
    gesture: StaticGesture | None
    orchestrator_state: str
    action_label: str | None      # e.g. "FIRED: fist -> space"
    hand_changed: bool
    in_range: bool
    is_armed: bool                # activation gate state
```

**Why extract:** Eliminates the main loop duplication between preview and tray modes. Both modes become thin wrappers:

```python
# Preview mode (simplified)
while True:
    ret, frame = camera.read()
    hands = detector.detect(frame, timestamp_ms)
    result = pipeline.process_frame(hands, current_time)
    render_preview(frame, result)

# Tray mode (simplified)
while active and not shutdown:
    ret, frame = camera.read()
    hands = detector.detect(frame, timestamp_ms)
    pipeline.process_frame(hands, current_time)
```

## Data Flow

### Per-Frame Data Flow

```
Frame arrives (BGR ndarray)
    |
    v
HandDetector.detect(frame, ts) -> dict[str, list]  {label: landmarks}
    |
    v
HandSelector.update(detected_hands) -> HandFrame | None
    |  (emits hand_changed flag)
    |  if hand_changed: pipeline resets orchestrator, fire_executor, smoother
    |
    v
DistanceFilter.check(landmarks) -> bool
    |  if not in_range: pipeline resets orchestrator, fire_executor
    |  if not in_range: landmarks = None for downstream
    |
    v
ActivationGate.check(gesture, timestamp) -> bool
    |  if gate enabled and gesture == activation_gesture:
    |      gate.arm(timestamp), consume gesture (return None downstream)
    |  if not gate.is_armed: skip downstream processing
    |
    v (landmarks, active hand only, in range, gate armed)
    |
    +------> GestureClassifier.classify(landmarks) -> StaticGesture | None
    |             |
    |             v
    |         GestureSmoother.update(gesture) -> StaticGesture | None
    |             |
    +------> SwipeDetector.update(landmarks, ts) -> SwipeDirection | None
    |             |  (suppressed when orchestrator.is_activating)
    |             |
    +-------> GestureOrchestrator.update(
    |             smoothed_gesture,
    |             timestamp,
    |             swipe_direction=swipe_result
    |         ) -> OrchestratorSignal | None
    |             |
    |             v
    |         ActionResolver.resolve(signal) -> ResolvedAction | None
    |             |
    |             v
    |         FireModeExecutor.execute(action)
    |             |
    |             v
    |         KeystrokeSender.send(modifiers, key)
    |
    v
FireModeExecutor.tick(timestamp)  # hold-key repeat, every frame
    |
    v
FrameResult (for preview / logging)
```

### Reset Cascade

Events that trigger resets and what gets reset:

| Trigger | What Resets | Why |
|---------|-------------|-----|
| Hand switch | smoother, orchestrator, swipe_detector, fire_executor.release_all() | Stale state from previous hand would cause false fires |
| Distance out-of-range | smoother, orchestrator, swipe_detector, fire_executor.release_all() | Hand too far, all state invalid |
| Config reload | smoother, orchestrator, swipe_detector, fire_executor.release_all(), action_resolver.reload() | Mappings and timing may have changed |
| Activation gate disarm | orchestrator, fire_executor.release_all() | System no longer active |

**Key design rule:** Resets always flow through the Pipeline. No component reaches into another component's internals. The current `debouncer._state = DebounceState.COOLDOWN` hack in the main loop is eliminated.

## Activation Gate Integration

The activation gate has two modes based on config:

1. **Disabled (default, bypass):** Gate always returns True. The pipeline processes all gestures normally. This is the current v1.3 behavior.

2. **Enabled:** A specific gesture (configurable, e.g., "scout" or "peace") arms the system for a timed window. During this window, all other gestures are processed normally. When the window expires, the system disarms and ignores all gestures until the activation gesture is seen again.

**Integration point:** The gate sits between DistanceFilter and the classifier/orchestrator. It consumes the activation gesture (does not pass it downstream) and gates all subsequent processing.

```python
# In Pipeline.process_frame():
if self.activation_gate is not None:
    if gesture == self.activation_gate.gesture:
        if not self.activation_gate.is_armed():
            self.activation_gate.arm(timestamp)
        # Activation gesture is consumed, not passed to orchestrator
        gesture = None

    self.activation_gate.tick(timestamp)

    if not self.activation_gate.is_armed():
        return FrameResult(is_armed=False, ...)  # skip processing
```

**Important:** The gate must be checked AFTER classification and smoothing, not before. The classifier needs to see the activation gesture to identify it. The gate then decides whether to pass the gesture downstream or consume it.

Revised position in pipeline:

```
landmarks -> classifier -> smoother -> ActivationGate -> orchestrator
```

The gate receives the smoothed gesture. If it is the activation gesture, the gate arms and returns None (consumed). If the gate is armed, it passes the gesture through. If the gate is not armed (and not bypassed), it returns None.

## Patterns to Follow

### Pattern 1: Signal-Based Component Communication

**What:** Components communicate via typed signals (NamedTuple or dataclass), not by reading each other's internal state.

**When:** Between any two pipeline stages.

**Example:**
```python
# GOOD: Orchestrator emits a signal, ActionResolver consumes it
signal = orchestrator.update(gesture, timestamp, swipe_direction=swipe)
if signal is not None:
    action = resolver.resolve(signal)

# BAD (current codebase): Main loop reads debouncer internals
if debouncer.in_swipe_window and swipe_result is not None:
    gesture_name = debouncer.activating_gesture.value  # reaching into internals
```

### Pattern 2: Pipeline Reset via Coordinator

**What:** Only the Pipeline class calls reset() on components. Components never reset each other.

**When:** Hand switch, distance exit, config reload, gate disarm.

**Example:**
```python
# GOOD: Pipeline coordinates resets
class Pipeline:
    def _handle_hand_switch(self):
        self.smoother.reset()
        self.orchestrator.reset()
        self.swipe_detector.reset()
        self.fire_executor.release_all()

# BAD (current codebase): Main loop mutates debouncer state directly
debouncer._state = DebounceState.COOLDOWN
debouncer._cooldown_gesture = pre_swipe_gesture
```

### Pattern 3: Config as Constructor Argument, Not Runtime Mutation

**What:** Components receive config at construction. Hot-reload creates new config, calls `pipeline.reload_config(new_config)`, which updates components via their public interfaces or recreates them.

**When:** Config hot-reload.

**Example:**
```python
# GOOD: Pipeline reload method
def reload_config(self, config: AppConfig):
    self.orchestrator = GestureOrchestrator(OrchestratorConfig.from_app_config(config))
    self.action_resolver.reload(config)
    self.smoother = GestureSmoother(config.smoothing_window)

# BAD (current codebase): Direct field mutation
debouncer._activation_delay = new_config.activation_delay
debouncer._cooldown_duration = new_config.cooldown_duration
debouncer._gesture_cooldowns = merged_cooldowns
```

### Pattern 4: Single Update Entry Point Per Component

**What:** Each component has one `update()` method that processes one frame of input and returns output. No multi-method protocols.

**When:** All stateful pipeline components.

**Why:** The current SwipeDetector requires the caller to check `is_swiping`, `is_activating`, `in_swipe_window` and route data accordingly. The orchestrator should absorb this routing logic.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Parallel State Machines with External Coordination

**What:** Running separate state machines (debouncer, swipe detector) and coordinating them via flags in the main loop (`was_swiping`, `compound_swipe_suppress_until`).

**Why bad:** The coordination logic grows with each new interaction between state machines. The current codebase has 6 coordination variables and ~100 lines of routing logic in the main loop. Adding a new temporal state (e.g., double-tap) would require touching the main loop coordinator.

**Instead:** Absorb the coordination into the orchestrator. The orchestrator owns one state machine that knows about both static and temporal states. The main loop becomes a simple frame loop.

### Anti-Pattern 2: Mode-Specific Code Duplication

**What:** Having nearly identical main loops in `__main__.py` (preview) and `tray.py` (tray mode).

**Why bad:** Every bug fix and feature addition must be applied to both places. The current codebase has ~500 lines duplicated between the two files, leading to subtle divergences (e.g., `tray.py` references `gesture` before it is defined on line 303).

**Instead:** Extract shared logic into Pipeline. Preview and tray modes become thin wrappers that differ only in frame acquisition and output (preview renders, tray does not).

### Anti-Pattern 3: Consuming Activation Gesture at Classification Time

**What:** Modifying the classifier to skip the activation gesture.

**Why bad:** The classifier should be stateless and classify all poses it sees. The gating decision belongs in the pipeline coordinator, not in classification.

**Instead:** Classify normally, then gate at the pipeline level. The activation gesture is identified by comparing the classified result against the configured activation gesture.

### Anti-Pattern 4: Temporal State as Separate Gesture Enum

**What:** Adding `FIST_HOLD`, `FIST_SWIPE_LEFT`, etc. to the Gesture enum.

**Why bad:** Combinatorial explosion. 7 gestures x 3 temporal states x 4 directions = 84 entries. Unmaintainable.

**Instead:** Keep static gestures as the base layer (7 values). Temporal state is an orthogonal modifier (TAP / HOLD / SWIPE). The orchestrator signal carries both dimensions independently.

## Config Schema (v2.0)

```yaml
activation:
  enabled: false              # bypass by default (v1.x behavior)
  gesture: scout              # gesture that arms the system
  duration: 3.0               # seconds gate stays armed

detection:
  smoothing_window: 2
  activation_delay: 0.2
  cooldown_duration: 0.1
  hold_release_delay: 0.1
  hold_repeat_interval: 0.03
  swipe_window: 0.5           # seconds to wait for static-to-swipe compound

gestures:
  fist:
    key: space
    mode: hold_key             # fire mode: tap (default) or hold_key
    threshold: 0.7
  open_palm:
    key: win+tab
    threshold: 0.7
    swipe:                     # temporal swipe modifiers for this gesture
      swipe_left:
        key: "1"
      swipe_right:
        key: "2"
  # ... other gestures

swipe:                         # standalone swipe mappings (no static gesture)
  settling_frames: 2
  cooldown: 0.3
  min_velocity: 0.15
  min_displacement: 0.03
  axis_ratio: 1.5
  swipe_left:
    key: right
  swipe_right:
    key: left
```

No schema changes needed for the gesture/swipe sections -- v2.0 reuses the existing config structure. The only addition is the `activation` section.

## Component Dependency Graph (Build Order)

```
Layer 0 (existing, unchanged):
    CameraCapture, HandDetector, GestureClassifier,
    KeystrokeSender, DistanceFilter, GestureSmoother,
    SwipeDetector

Layer 1 (extract from existing code):
    HandSelector           <-- extract from HandDetector + main loop
    |
    depends on: HandDetector (provides detected_hands dict)

Layer 2 (new components, independent of each other):
    GestureOrchestrator    <-- replaces GestureDebouncer
    |                          absorbs main loop coordination
    |  depends on: StaticGesture enum, SwipeDirection enum
    |
    ActionResolver         <-- extracted from main loop
    |  depends on: OrchestratorSignal, config parsing functions
    |
    FireModeExecutor       <-- extracted from main loop hold state
    |  depends on: ResolvedAction, KeystrokeSender

Layer 3 (integration):
    Pipeline               <-- orchestrates all components
    |  depends on: all Layer 0-2 components
    |
    ActivationGate         <-- existing, integrate into Pipeline
    |  depends on: StaticGesture enum

Layer 4 (entry points):
    run_preview_mode       <-- simplified, uses Pipeline
    TrayApp._detection_loop <-- simplified, uses Pipeline
```

## Suggested Build Order

The build order is constrained by the "clean rewrite" goal: we need to build bottom-up so each layer can be tested before the next is added.

### Phase 1: Data Types and HandSelector

New files: `gesture_keys/types.py`, `gesture_keys/hand_selector.py`

1. Define shared types: `HandFrame`, `OrchestratorSignal`, `SignalAction`, `TemporalState`, `ResolvedAction`, `FireMode`, `FrameResult`
2. Extract `HandSelector` from `HandDetector.detect()` + main loop hand-switch logic
3. Test: HandSelector unit tests (sticky tracking, preferred hand, hand_changed flag)

**Why first:** Types are needed by all downstream components. HandSelector is a straightforward extraction with clear test cases.

### Phase 2: GestureOrchestrator

New file: `gesture_keys/orchestrator.py`

1. Implement unified state machine (IDLE, ACTIVATING, SWIPE_WINDOW, FIRED, HOLDING, COOLDOWN)
2. Port all state transition logic from GestureDebouncer
3. Absorb swipe coordination (is_activating suppression, compound gesture routing)
4. Test: Port and extend all `test_debounce.py` tests. Add compound gesture integration tests.

**Why second:** The orchestrator is the most complex new component. Building it early allows thorough testing before integration.

### Phase 3: ActionResolver + FireModeExecutor

New files: `gesture_keys/action_resolver.py`, `gesture_keys/fire_executor.py`

1. Extract key mapping parsing from main loop into ActionResolver
2. Implement per-hand mapping swap and reload
3. Extract hold-mode state management into FireModeExecutor
4. Test: ActionResolver mapping tests, FireModeExecutor hold/tap tests

**Why third:** These depend on the types from Phase 1 and consume signals from Phase 2's orchestrator.

### Phase 4: Pipeline Integration

New file: `gesture_keys/pipeline.py`

1. Wire all components together in Pipeline class
2. Implement `process_frame()`, `reload_config()`, `shutdown()`
3. Integrate ActivationGate into pipeline flow
4. Test: Integration tests with mocked components

**Why fourth:** Pipeline depends on all components being ready.

### Phase 5: Entry Point Rewrite

Modified files: `gesture_keys/__main__.py`, `gesture_keys/tray.py`

1. Replace 570-line `run_preview_mode` with ~50 lines using Pipeline
2. Replace 515-line `_detection_loop` with ~30 lines using Pipeline
3. Keep preview rendering in `__main__.py` (reads FrameResult)
4. Keep tray app lifecycle in `tray.py` (threading, menu)
5. Test: End-to-end manual testing, automated smoke tests

**Why last:** Entry points depend on Pipeline being solid.

### Phase 6: Cleanup

1. Remove `gesture_keys/debounce.py` (replaced by orchestrator)
2. Remove duplicated `_parse_key_mappings` functions
3. Update config.py if new `activation` section is needed
4. Verify hot-reload works through Pipeline.reload_config()

## New vs Modified vs Removed Files

| File | Status | Notes |
|------|--------|-------|
| `gesture_keys/types.py` | **NEW** | Shared data types (signals, frames, actions) |
| `gesture_keys/hand_selector.py` | **NEW** | Extracted from HandDetector + main loop |
| `gesture_keys/orchestrator.py` | **NEW** | Replaces debounce.py, absorbs main loop coordination |
| `gesture_keys/action_resolver.py` | **NEW** | Extracted from main loop key mapping logic |
| `gesture_keys/fire_executor.py` | **NEW** | Extracted from main loop hold state management |
| `gesture_keys/pipeline.py` | **NEW** | Wires all components together |
| `gesture_keys/__main__.py` | **REWRITE** | Simplified to thin wrapper over Pipeline |
| `gesture_keys/tray.py` | **REWRITE** | Simplified to thin wrapper over Pipeline |
| `gesture_keys/config.py` | **MODIFY** | Add `activation` section parsing |
| `gesture_keys/activation.py` | **MODIFY** | Minor: integrate with Pipeline (already exists) |
| `gesture_keys/debounce.py` | **REMOVE** | Replaced by orchestrator.py |
| `gesture_keys/classifier.py` | UNCHANGED | Stateless, works as-is |
| `gesture_keys/smoother.py` | UNCHANGED | Stateless, works as-is |
| `gesture_keys/swipe.py` | UNCHANGED | Self-contained state machine, works as-is |
| `gesture_keys/distance.py` | UNCHANGED | Stateless, works as-is |
| `gesture_keys/detector.py` | **MODIFY** | Remove hand selection logic (moved to HandSelector) |
| `gesture_keys/keystroke.py` | UNCHANGED | Thin pynput wrapper, works as-is |
| `gesture_keys/preview.py` | **MODIFY** | Consume FrameResult instead of raw values |

## Scalability Considerations

| Concern | Current (v1.3) | v2.0 | Notes |
|---------|----------------|------|-------|
| Adding a gesture | Add to Gesture enum, classifier, config | Same -- classifier is unchanged | No pipeline changes needed |
| Adding a temporal state | N/A (hardcoded in main loop) | Add to TemporalState enum, add orchestrator transition | Orchestrator is the single touch point |
| Adding a fire mode | Hardcoded hold logic in main loop | Add to FireMode enum, implement in FireModeExecutor | Isolated change |
| Per-app profiles | Would require duplicating config everywhere | Pipeline.reload_config() with new config | Clean swap point |
| Two-hand simultaneous | Would require duplicating entire main loop | Two Pipeline instances, one per hand | Pipeline is self-contained |

## Sources

- Direct analysis of existing codebase: `__main__.py` (570 LOC), `tray.py` (515 LOC), `debounce.py` (338 LOC), `swipe.py` (321 LOC), `classifier.py` (155 LOC), `config.py` (320 LOC), `activation.py` (67 LOC)
- v1.0-v1.3 architecture research (`.planning/research/ARCHITECTURE.md` previous version)
- State machine pattern analysis from v1.2 debouncer evolution (6 states, 7 transition handlers)
- Pipeline/coordinator pattern: standard software architecture (no external source needed -- this is basic decomposition)

---
*Architecture research for: gesture-keys v2.0 structured gesture pipeline*
*Researched: 2026-03-24*
