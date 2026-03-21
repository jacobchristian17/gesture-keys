# Stack Research

**Domain:** Real-time gesture state machine refactoring (v1.2 -- seamless transitions)
**Researched:** 2026-03-22
**Confidence:** HIGH

## Verdict: No New Dependencies

The v1.2 features (gesture-to-gesture firing, faster swipe/static transitions, tuned defaults) are **pure state machine refactors** of existing code. No new libraries are needed. The existing stack is sufficient and adding dependencies would be counter-productive for a ~3K LOC synchronous-loop app running at 30+ FPS.

## Recommended Stack

### Core Technologies

No additions. Existing stack unchanged.

| Technology | Version | Purpose | Status for v1.2 |
|------------|---------|---------|-----------------|
| mediapipe | >=0.10.33 | Hand landmark detection | Unchanged -- classification layer not touched |
| opencv-python | >=4.8.0 | Camera capture, preview | Unchanged |
| pynput | >=1.7.6 | Keystroke simulation | Unchanged |
| PyYAML | >=6.0 | Config loading/hot-reload | Schema additions only (settling_frames) |
| pystray | >=0.19.5 | System tray app | Unchanged |
| Pillow | >=10.0 | Tray icon rendering | Unchanged |
| Python stdlib `enum`, `collections.deque`, `time` | stdlib | State machine states, buffers, timestamps | Already used; no changes |

### Supporting Libraries

No new supporting libraries needed.

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| pytest | >=8.0 | Unit/integration testing | Test the refactored state machines -- new test cases for gesture-to-gesture transitions |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| `--preview` flag | Visual debugging of transitions | Already exists; useful for verifying gesture-to-gesture flow |
| DEBUG logging | Trace state machine transitions | Already instrumented in debounce.py and swipe.py |

## What Actually Changes (Code, Not Dependencies)

### 1. GestureDebouncer -- Gesture-to-Gesture Transitions

**Current flow:** `IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE`. The `_handle_cooldown` method (line 127-134 of debounce.py) requires `gesture is None` before transitioning back to IDLE. This forces users to drop their hand to "none" between every gesture.

**New flow:** After COOLDOWN expires, if a *different* gesture is being held, transition directly to ACTIVATING for the new gesture. Only require None if the *same* gesture is still held (prevents re-fire of held pose). This requires:

1. Add `_last_fired_gesture: Optional[Gesture]` field to track what fired
2. Set it in `_handle_fired` when transitioning to COOLDOWN
3. Modify `_handle_cooldown`: when cooldown expires AND gesture is not None AND gesture differs from `_last_fired_gesture`, go to ACTIVATING with the new gesture instead of staying in COOLDOWN

**Implementation size:** ~15 lines changed in a 134-line file. No new classes, no new imports.

**Pattern:** This is a standard "transition-on-different-input" guard condition. No library needed -- it is a conditional check on a stored value.

### 2. SwipeDetector -- Faster Swipe/Static Transitions

**Current issue:** `settling_frames=10` (hardcoded default in swipe.py line 61) blocks static gesture detection for ~333ms at 30fps after swipe cooldown ends. The `settling_frames_remaining` counter (line 219) burns frames in IDLE state before allowing re-arm. Combined with 0.5s cooldown, total swipe-to-static dead time is ~833ms.

**Fix:**
- Reduce `settling_frames` default from 10 to 4 (~133ms at 30fps)
- Wire `settling_frames` to YAML config (property setter already exists at line 125, just not connected to config loading)
- Add to config schema in `config.py` and to hot-reload path in `__main__.py`

**Static-to-swipe direction:** Currently works well. The `is_swiping` flag (line 129-134) suppresses static detection during swipes, and `smoother.reset()` + `debouncer.reset()` are called on swipe entry (main loop lines 229-231). No changes needed for static-to-swipe.

### 3. Tuned Defaults

The user has already tuned values in config.yaml through real-world usage. Code defaults should match proven values so new users get good defaults.

| Parameter | Code Default | User config.yaml | New Code Default | Rationale |
|-----------|-------------|-----------------|-----------------|-----------|
| `activation_delay` | 0.4s | 0.1s | 0.15s | User proved 0.1s works; 0.15s adds minimal safety margin for new users |
| `cooldown_duration` | 0.8s | 0.5s | 0.3s | With gesture-to-gesture support, cooldown can be much shorter since same-gesture re-fire is separately guarded |
| `smoothing_window` | 3 | 1 | 1 | Window=1 effectively disables smoothing; user proved classifier output is stable enough without it |
| `swipe.cooldown` | 0.5s | 0.5s | 0.3s | Reduce dead time after swipe; user may want to adjust |
| `swipe.settling_frames` | 10 | (not exposed) | 4 | Reduce post-swipe settling from ~333ms to ~133ms; newly exposed in config |
| `swipe.min_velocity` | 0.4 | 0.15 | 0.15 | User's real-world tuning is validated |
| `swipe.min_displacement` | 0.08 | 0.03 | 0.03 | User's real-world tuning is validated |

### Files That Change

| File | Change |
|------|--------|
| `debounce.py` | Add `_last_fired_gesture` tracking, modify `_handle_cooldown` for gesture-to-gesture |
| `swipe.py` | Update default values |
| `config.py` | Add `settling_frames` to swipe config schema |
| `__main__.py` | Wire `settling_frames` from config to SwipeDetector, update hot-reload path |
| `config.yaml` | Update defaults, add `settling_frames` option |
| `tests/test_debounce.py` | Add gesture-to-gesture transition test cases |

### Files That Do NOT Change

| File | Why Unchanged |
|------|---------------|
| `detector.py` | MediaPipe pipeline untouched |
| `classifier.py` | Gesture classification untouched |
| `smoother.py` | Already effectively disabled at window=1 |
| `keystroke.py` | Keystroke sending untouched |
| `distance.py` | Distance gating untouched |
| `activation.py` | Activation gate untouched |
| `preview.py` | Preview rendering untouched |
| `tray.py` | Tray app untouched |
| `requirements.txt` | No new dependencies |

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| Hand-rolled state machines (keep current) | `transitions` library (v0.9.2, [GitHub](https://github.com/pytransitions/transitions)) | Only if state machines grow beyond ~10 states with complex guard conditions and you need visualization/diagrams. Current machines have 3-4 states. |
| Hand-rolled state machines (keep current) | `python-statemachine` (v3.0.0, [PyPI](https://pypi.org/project/python-statemachine/)) | Only if you need hierarchical states or auto-generated state diagrams. Not applicable here. |
| Modify existing debouncer | New "ContinuousDebouncer" class | Only if the original debouncer needs to remain available for backward compatibility. Since this is the same app, modifying in place is simpler. |
| Raw MediaPipe landmarks + custom classifier | MediaPipe Gesture Recognizer Task API | Only if dropping custom gestures (scout, pinch thresholds). Not applicable for v1.2. |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `transitions` library | Adds import-time overhead (~50ms) and stack trace complexity through library internals for two 50-line state machines. The DSL learning curve and debugging cost exceeds the 15-line modification needed. | Keep hand-rolled state machines with the surgical modifications described above |
| `python-statemachine` | Same reasoning. Class decorator DSL is elegant but the abstraction adds complexity without reducing it for 3-4 state machines. | Keep hand-rolled state machines |
| `asyncio` patterns | Main loop is synchronous `while True` at 30fps with threaded camera capture. Async would require rewriting the entire pipeline for zero benefit. State machine updates are microseconds. | Keep synchronous loop with `time.perf_counter()` |
| Event bus / pub-sub libraries | The pipeline is a linear chain (camera -> detect -> classify -> smooth -> debounce -> fire). There is no fan-out or dynamic subscription. An event bus adds indirection for no benefit. | Keep direct method calls |
| RxPY / reactive streams | Same reasoning as event bus. The pipeline processes one frame at a time, synchronously. Reactive streams are for async/concurrent data flows. | Keep synchronous loop |

## Real-Time Gesture State Machine Patterns (From Research)

No specialized libraries exist for "real-time gesture state machines" as a category. The standard approach across MediaPipe gesture projects is exactly what gesture-keys already does: hand-rolled state machines with enum states, timestamp-based transitions, and cooldown guards. The `transitions` library is the most popular general Python state machine library but is designed for application-level state management (workflows, protocols), not per-frame real-time processing.

**Key pattern for gesture-to-gesture transitions** (used in multiple open-source gesture control projects): Track the "last fired gesture" separately from the "current gesture being held." Allow re-entry to the activation state when the held gesture differs from the last fired one. This is the exact pattern recommended for the debouncer modification above.

## Installation

```bash
# No changes to installation:
pip install -r requirements.txt
```

## Sources

- [pytransitions/transitions GitHub](https://github.com/pytransitions/transitions) -- evaluated as state machine library, rejected for real-time per-frame use case (HIGH confidence)
- [python-statemachine PyPI](https://pypi.org/project/python-statemachine/) -- evaluated as state machine library, rejected (HIGH confidence)
- [MediaPipe Gesture Recognizer Python guide](https://developers.google.com/mediapipe/solutions/vision/gesture_recognizer/python) -- evaluated built-in gesture API, rejected for lacking custom gesture support (HIGH confidence)
- Codebase analysis of `debounce.py`, `swipe.py`, `__main__.py`, `config.yaml`, `smoother.py` -- primary source for all recommendations (HIGH confidence)

---
*Stack research for: gesture-keys v1.2 seamless gesture transitions*
*Researched: 2026-03-22*
