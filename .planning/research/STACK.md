# Technology Stack

**Project:** gesture-keys v2.0 -- Structured Gesture Architecture
**Researched:** 2026-03-24
**Overall confidence:** HIGH

## Verdict: No New Dependencies

The v2.0 structured gesture architecture (activation gate, gesture orchestrator, temporal state machine, action resolver, fire mode executor) is a **clean architectural decomposition** of the existing 572-line `__main__.py` monolith and 338-line `debounce.py`. All required patterns are implementable with Python stdlib. Adding a state machine library would cost more in integration overhead than it saves in boilerplate for this specific use case.

**Rationale:** The existing codebase already hand-rolls a 6-state machine with hold mode, compound gestures, and swipe windows -- all running per-frame at 30+ FPS in a synchronous loop. The v2.0 rewrite decomposes this into smaller, focused state machines, each with 2-4 states. State machine libraries optimize for declarative transition definitions and introspection, but impose overhead (import time, stack trace depth, learning curve) that is not justified for machines this small running in a real-time loop.

## Recommended Stack

### Core Technologies

No additions. Existing stack unchanged for v2.0.

| Technology | Version | Purpose | v2.0 Status |
|------------|---------|---------|-------------|
| mediapipe | >=0.10.33 | Hand landmark detection | Unchanged -- detector.py untouched |
| opencv-python | >=4.8.0 | Camera capture, preview | Unchanged |
| pynput | >=1.7.6 | Keystroke simulation (tap + hold) | Unchanged -- KeystrokeSender already has `send()`, `press_and_hold()`, `release_held()` |
| PyYAML | >=6.0 | Config loading/hot-reload | Schema changes for activation gate + fire modes |
| pystray | >=0.19.5 | System tray app | Unchanged |
| Pillow | >=10.0 | Tray icon rendering | Unchanged |

### Python Stdlib Used for New Architecture

| Module | Purpose | Why Sufficient |
|--------|---------|----------------|
| `enum.Enum` | States for activation gate, temporal states, fire modes | Already used in debounce.py and classifier.py. Enum states with `match`/`if-elif` handlers is the established pattern. |
| `typing.NamedTuple` | Action descriptors from resolver (gesture, temporal state, fire mode, key mapping) | Already used for `DebounceSignal`. Immutable, typed, lightweight. |
| `dataclasses.dataclass` | Orchestrator config, component state bundles | Already used for `AppConfig`. |
| `time.perf_counter` | Timestamp-based transitions (hold duration, activation window) | Already used throughout. Microsecond resolution, monotonic. |
| `collections.abc.Callable` | Callback-based fire mode executors (tap callback, hold start/end callbacks) | Avoids needing an event bus. Direct function references. |
| `logging` | State transition tracing | Already instrumented. Each new component gets its own logger. |

### Supporting Libraries

No new supporting libraries needed.

| Library | Version | Purpose | v2.0 Notes |
|---------|---------|---------|------------|
| pytest | >=8.0 | Unit testing for each new component | Each component (gate, orchestrator, resolver, executor) gets isolated tests with deterministic timestamps |

## What Changes (Architecture, Not Dependencies)

### Component Mapping: Old to New

| Old (v1.x) | New (v2.0) | What Changes |
|-------------|-----------|--------------|
| `ActivationGate` (activation.py) | **ActivationGate** (refined) | Already exists. Needs: configurable activation gesture, bypass mode (always-armed), integration with orchestrator |
| `GestureDebouncer` (debounce.py, 338 lines) | **GestureOrchestrator** + **TemporalStateMachine** | Decomposed. Debouncer's activation/cooldown logic becomes orchestrator. Hold/swipe-window logic becomes temporal states. |
| Procedural dispatch in `__main__.py` (lines 396-438) | **ActionResolver** | Lookup table: (gesture, temporal_state) -> Action. Replaces scattered if/elif chains. |
| `KeystrokeSender` direct calls in `__main__.py` | **FireModeExecutor** | Wraps KeystrokeSender with fire mode logic (tap = send, hold_key = press_and_hold / release_held). Replaces hold_active/hold_modifiers/hold_key local variables. |
| 20+ local variables in `run_preview_mode()` | Encapsulated in component state | `hold_active`, `hold_modifiers`, `hold_key`, `hold_gesture_name`, `was_swiping`, `pre_swipe_gesture`, `compound_swipe_suppress_until`, etc. all move into components. |

### New Enums (Python stdlib `enum`)

```python
# Temporal states -- modifier on top of static gesture
class TemporalState(Enum):
    INSTANT = "instant"      # Static gesture just confirmed (tap fire)
    HOLDING = "holding"      # Static gesture held beyond threshold
    SWIPING = "swiping"      # Swipe detected during gesture

# Fire modes -- how an action executes
class FireMode(Enum):
    TAP = "tap"              # press + release (existing send())
    HOLD_KEY = "hold_key"    # press on start, release on end (existing press_and_hold/release_held)

# Action descriptor -- output of resolver
class Action(NamedTuple):
    gesture: Gesture
    temporal: TemporalState
    fire_mode: FireMode
    modifiers: list  # pynput Key objects
    key: object      # pynput Key or str
    key_string: str  # original config string for logging
```

### Integration Points with Existing Code

| Existing Component | Integration | Direction |
|-------------------|-------------|-----------|
| `HandDetector.detect()` | Feeds landmarks + handedness to orchestrator | Unchanged, orchestrator consumes output |
| `GestureClassifier.classify()` | Feeds static gesture to orchestrator | Unchanged |
| `SwipeDetector.update()` | Feeds swipe direction to orchestrator | Unchanged, orchestrator decides priority |
| `GestureSmoother.update()` | Feeds smoothed gesture to orchestrator | Unchanged |
| `DistanceFilter.check()` | Gates orchestrator input | Unchanged |
| `KeystrokeSender` | FireModeExecutor wraps it | KeystrokeSender unchanged, executor owns the instance |
| `ConfigWatcher` | Triggers orchestrator.reset() on config change | Unchanged mechanism |
| `config.load_config()` | Schema additions for activation + fire modes | Additive changes only |

## Alternatives Considered

### State Machine Libraries

| Library | Version | Stars | Why NOT for v2.0 |
|---------|---------|-------|-----------------|
| `transitions` | 0.9.2 | 5.6k | Adds ~50ms import overhead per startup. HierarchicalMachine requires learning its DSL (states-as-dicts, trigger strings). Stack traces go through library internals. The v2.0 machines have 2-4 states each -- the DSL overhead exceeds the boilerplate it replaces. |
| `python-statemachine` | 3.0.0 | 900+ | Class decorator DSL with `State.Compound` for hierarchy. More structured than `transitions`, but requires all transitions declared upfront. Real-time per-frame usage pattern (call `update()` 30x/sec) is not its design target. |
| `hsm-py` | 0.3.0 | ~50 | Small library for hierarchical states. Low adoption, unclear maintenance. Not worth the dependency risk for 2-4 state machines. |

**When a state machine library WOULD be justified:** If v2.0 grew beyond ~8 states per machine with complex guard conditions, or if state diagram visualization/export was required for documentation. Neither applies here.

### Event Bus / Pub-Sub

| Pattern | Why NOT |
|---------|---------|
| `blinker` / `pymitter` event bus | Pipeline is linear: camera -> detect -> classify -> smooth -> orchestrate -> resolve -> fire. No fan-out, no dynamic subscribers, no cross-cutting concerns. Direct method calls are simpler and debuggable. |
| Observer pattern (manual) | Same reasoning. The orchestrator calls the resolver which calls the executor. Chain of responsibility, not pub-sub. |
| RxPY reactive streams | Synchronous 30fps loop. Reactive operators add indirection and async complexity for zero benefit. |

### Dependency Injection

| Pattern | Why NOT |
|---------|---------|
| `inject` / `dependency-injector` | 7 components with clear constructor dependencies. Manual wiring in `__main__.py` is ~20 lines. DI framework overhead not justified. |

## What NOT to Add

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Any state machine library | 2-4 state machines, each 2-4 states. Library DSL learning curve exceeds hand-rolled boilerplate. Import overhead matters at 30fps startup. | `enum.Enum` states + `if/elif` handlers (existing pattern from debounce.py) |
| Event bus / pub-sub library | Linear pipeline, no fan-out. Adds indirection that obscures data flow. | Direct method calls between components |
| `asyncio` | Synchronous loop works. Camera capture is already threaded. No I/O-bound operations in the gesture pipeline. | Keep synchronous `while True` loop with `time.perf_counter()` |
| `attrs` | `dataclasses` already used and sufficient. `attrs` adds marginal benefit (validators, converters) for this use case. | `dataclasses.dataclass` |
| Type-checking runtime (pydantic) | Config validation is simple type coercion from YAML scalars. Pydantic model overhead not justified. | Manual validation in `load_config()` (existing pattern) |
| Abstract base classes (`abc.ABC`) | Components have concrete implementations, no polymorphism needed. Orchestrator, resolver, executor are each one class. | Concrete classes with clear interfaces via type hints |

## Installation

```bash
# No changes to installation:
pip install -r requirements.txt

# requirements.txt remains unchanged:
# mediapipe>=0.10.33
# opencv-python>=4.8.0
# PyYAML>=6.0
# pytest>=8.0
# pynput>=1.7.6
# pystray>=0.19.5
# Pillow>=10.0
```

## Sources

- Codebase analysis of `debounce.py` (338 lines, 6-state machine with hold mode), `__main__.py` (572 lines, 20+ state variables in main loop), `activation.py` (67 lines, simple arm/disarm gate), `keystroke.py` (send + press_and_hold + release_held already implemented) -- primary source for all recommendations (HIGH confidence)
- [pytransitions/transitions GitHub](https://github.com/pytransitions/transitions) -- evaluated for hierarchical state machine support, rejected for real-time per-frame use case (HIGH confidence)
- [python-statemachine 3.0.0 docs](https://python-statemachine.readthedocs.io/en/latest/) -- evaluated for declarative state machine DSL, rejected (HIGH confidence)
- [hsm-py GitHub](https://github.com/artcom/hsm-py) -- evaluated for lightweight HSM, rejected due to low adoption (MEDIUM confidence)
- [Top 10 State Machine Frameworks for Python](https://statemachine.events/article/Top_10_State_Machine_Frameworks_for_Python.html) -- landscape survey (MEDIUM confidence)

---
*Stack research for: gesture-keys v2.0 structured gesture architecture*
*Researched: 2026-03-24*
