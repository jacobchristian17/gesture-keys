# Project Research Summary

**Project:** gesture-keys v1.0.1 — Scroll Gesture Support
**Domain:** Mouse scroll event dispatch via hand gesture velocity detection
**Researched:** 2026-04-01
**Confidence:** HIGH

## Executive Summary

This feature adds a `scroll` fire mode to the existing gesture-keys pipeline, enabling continuous mouse scroll events driven by hand movement velocity and direction. The recommended approach requires zero new dependencies: `pynput.mouse.Controller.scroll(dx, dy)` already exists in the installed pynput 1.8.1 and uses `SendInput` with `MOUSEEVENTF_WHEEL`/`MOUSEEVENTF_HWHEEL` internally. The work is a focused extension of the existing `ActionDispatcher` dispatch path — a new `FireMode.SCROLL` enum value, a `ScrollSender` class mirroring `KeystrokeSender`, velocity-to-scroll-amount mapping, and explicit `fire_mode: scroll` config syntax.

The recommended architecture keeps the `GestureOrchestrator` and `MotionDetector` entirely untouched. Scroll is a fire mode concern, not a signal type concern. The orchestrator already emits `MOVING_FIRE` signals with velocity and direction; the only divergence from the existing keystroke path occurs in `_handle_moving_fire()` after all existing velocity and throttle checks pass. A `ScrollSender` class in `gesture_keys/scroll.py` owns `pynput.mouse.Controller` as a peer to the existing `KeystrokeSender`. Velocity maps linearly to scroll ticks (1–5 notches per dispatch) with a hard cap. Per-action `dispatch_interval` controls event rate. Config requires explicit `fire_mode: scroll` to opt in.

The primary risks are all front-loaded and well-understood: pynput multiplies scroll amounts by WHEEL_DELTA=120 internally (raw velocity passed directly produces catastrophic speed); MOVING_FIRE fires at 30 FPS without throttling (must be set to 10–20 dispatches/sec per scroll action); scroll has no `release_all()` equivalent (a scroll-armed safety flag is required); and `hold_key` fire mode on the same gesture will conflict with scroll dispatch unless explicitly routed away. All six critical pitfalls have clear, low-cost prevention strategies that must be applied during the initial implementation — none require architectural rework to fix later.

## Key Findings

### Recommended Stack

No new packages are needed. The entire feature is built on existing dependencies. `pynput 1.8.1` (already in `requirements.txt`) exposes `pynput.mouse.Controller.scroll(dx, dy)` which sends `SendInput` with `MOUSEEVENTF_WHEEL` (vertical) and `MOUSEEVENTF_HWHEEL` (horizontal) on Windows. Fractional values are accepted — `scroll(0, 0.5)` sends 60 wheel units (half a notch). The effective minimum before int truncation produces a no-op is `1/120 ≈ 0.0083`.

**Core technologies:**
- `pynput 1.8.1` (installed): Mouse scroll via `Controller.scroll(dx, dy)` — already a dependency, scroll support verified from installed source (`pynput/mouse/_win32.py`)
- `gesture_keys/motion.py` `MotionDetector`: Provides per-frame `velocity` and `direction` via `MOVING_FIRE` signals — no changes needed, already the correct data
- `gesture_keys/action.py` `ActionDispatcher._handle_moving_fire()`: Single integration point — add `FireMode.SCROLL` branch after existing velocity/throttle checks, call `scroll_sender` instead of `sender`

### Expected Features

**Must have (table stakes):**
- Vertical scroll (up/down) via `pinch:moving:up` / `pinch:moving:down` — core use case, expected by all scroll users
- Horizontal scroll (left/right) via `pinch:moving:left` / `pinch:moving:right` — expected alongside vertical
- `FireMode.SCROLL` enum value and dispatcher routing — architectural prerequisite for everything else
- Velocity-proportional scroll speed — without this scroll feels robotic; faster hand = more ticks per dispatch
- `scroll_speed` per-action config field (default `3.0`) — users need to tune for their setup
- Continuous scroll via per-action `dispatch_interval` (default `0.05s` = 20 events/sec) — must use per-action override, not the global keystroke default of 0.4s
- Scroll armed/disarmed safety flag — scroll stops cleanly when hand stops, hand is lost, gesture changes, or app toggles off

**Should have (competitive):**
- `scroll_direction: natural | traditional` config option — half of users expect the opposite default; natural (hand up = content moves up) should be the default for gesture control
- Acceleration curve — slow movement = precise (1 tick), fast movement = rapid (10 ticks); adds trackpad-like feel
- Scroll indicator in preview overlay — helps users calibrate hand speed

**Defer (v2+):**
- Scroll inertia/momentum — significant state complexity (deceleration timer thread), unreliable with webcam input latency
- Pinch-to-zoom — separate input signal (pinch distance delta vs. hand translation), separate milestone
- Diagonal free-axis scroll — MotionDetector intentionally rejects diagonals; not worth the ambiguity

### Architecture Approach

Scroll integrates as a new fire mode within the existing `MOVING_FIRE` signal path, not as a new signal type. The `GestureOrchestrator` is unchanged. The sole modification point in the dispatch path is `ActionDispatcher._handle_moving_fire()`, which branches on `action.fire_mode == FireMode.SCROLL` after all existing velocity and throttle checks, then calls `scroll_sender.scroll(direction, velocity)` instead of `sender.send()`. A new `ScrollSender` class in `gesture_keys/scroll.py` owns `pynput.mouse.Controller` exclusively and encapsulates velocity-to-ticks mapping and direction-to-axis routing. Config parsing gains explicit `fire_mode: scroll` recognition (overriding the current state-inferred fire mode) and makes `key` optional for scroll actions.

**Major components:**
1. `ScrollSender` (new, `scroll.py`) — wraps `pynput.mouse.Controller`; velocity-to-ticks mapping (`clamp(velocity * scroll_speed, min, max)`); direction-to-axis routing (`UP -> scroll(0, +ticks)`, etc.); peer to `KeystrokeSender`
2. `FireMode.SCROLL` (new enum value, `action.py`) — routes `_handle_moving_fire()` to `scroll_sender` instead of `sender`; no new signal types in the orchestrator
3. Config parsing updates (`config.py`) — explicit `fire_mode` field on `ActionEntry` (overrides state-inferred mode); `key` field optional for scroll actions; `scroll_speed` per-action override

**Components that do NOT change:** `MotionDetector`, `GestureOrchestrator`, `ActionResolver`, `Trigger`/`parse_trigger()`, `KeystrokeSender`, `ActivationGate`, `GestureSmoother`, `DistanceFilter`.

### Critical Pitfalls

1. **WHEEL_DELTA=120 hidden multiplier** — pynput multiplies `dy` by 120 internally before `SendInput`; passing velocity directly (e.g., `dy=0.8`) sends 96 wheel units per call; at 30 FPS with no throttle that is ~1800 wheel units/sec. Map velocity to small integers: `clamp(round(velocity * scroll_speed), 1, 5)`. One notch (`dy=1`) = 3 lines scrolled (Windows default).

2. **30 FPS MOVING_FIRE flooding** — at 30 Hz with `scroll(0, 1)` per call = 90 notches/sec, unusably fast. The global keystroke `dispatch_interval` (0.4s) is too slow (2.5 events/sec = jerky). Set `dispatch_interval: 0.05` per scroll action (20 events/sec with 1–3 notches each = smooth, usable).

3. **No release_all() equivalent** — scroll has no held state, so no cleanup mechanism if scroll continues after intent stops. Implement a scroll-armed flag (set on HOLD_START for scroll gestures, cleared on HOLD_END and all exit paths that call `release_all()`). Add a hard cap of max 20 notches/sec as an absolute safety limit.

4. **hold_key + scroll conflict** — if `pinch:holding` is configured as `hold_key`, HOLD_START fires key repeats while MOVING_FIRE fires scroll simultaneously. The dispatcher must suppress HOLD_START key repeat when the gesture's moving actions are SCROLL mode.

5. **Coordinate system mismatch** — three conventions collide: MediaPipe Y increases downward, pynput positive `dy` = scroll up, and users disagree on natural vs traditional. Deliberately choose a default (natural: hand up = content moves up = `scroll(0, -1)`) and expose `scroll_direction: natural | traditional` config option.

6. **Velocity jitter at low speeds** — MotionDetector rolling buffer produces oscillating velocity near arm/disarm threshold, causing scroll stutter. Add exponential moving average (alpha ~0.3) in `ScrollSender` before velocity-to-ticks mapping. Lock scroll direction once armed until disarm.

## Implications for Roadmap

Based on research, the entire feature fits within a single focused milestone. Architecture research prescribes a 5-phase build order structured by dependency graph. All six critical pitfalls are addressed in Phases 1–3; Phases 4–5 are pure wiring and documentation with no new risk.

### Phase 1: ScrollSender (Pure New Code)

**Rationale:** Leaf node — no existing files change. Zero risk to existing functionality. The velocity-to-ticks mapping and WHEEL_DELTA awareness are baked in from the start, before the dispatcher touches it.
**Delivers:** `gesture_keys/scroll.py` with `ScrollSender` class; velocity-to-ticks mapping with clamp; direction-to-axis routing; full unit tests in `tests/test_scroll.py`
**Addresses:** Vertical + horizontal scroll (table stakes); velocity-proportional speed; scroll direction convention
**Avoids:** WHEEL_DELTA pitfall (Pitfall 1); scroll direction mismatch (Pitfall 4)

### Phase 2: FireMode + Config Changes

**Rationale:** Modifies shared types (`action.py`, `config.py`) but is backward compatible — new enum value and optional field only. Must precede dispatcher changes that consume `FireMode.SCROLL`.
**Delivers:** `FireMode.SCROLL` enum value; `fire_mode` field on `ActionEntry`; updated `derive_from_actions()` that handles `fire_mode: scroll`; `key` field optional for scroll actions; `scroll_speed` per-action config field
**Addresses:** Explicit config syntax (table stakes); `hold_key` conflict prevention via routing at config layer
**Avoids:** Accidental scroll inference from trigger state; `key` field validation error on scroll actions

### Phase 3: ActionDispatcher Integration

**Rationale:** Consumes Phase 1 (ScrollSender) and Phase 2 (FireMode). This is the critical integration point. Mocked `ScrollSender` in tests isolates routing logic from real pynput calls.
**Delivers:** `scroll_sender` parameter in `ActionDispatcher.__init__()`; SCROLL branch in `_handle_moving_fire()` after existing velocity/throttle checks; scroll-armed safety flag cleared on all exit paths
**Addresses:** 30 FPS flooding (Pitfall 2); runaway scroll safety (Pitfall 3); hold_key conflict (Pitfall 4)
**Avoids:** Scroll-fires-after-stop scenario; simultaneous key-repeat + scroll; missing exit path coverage

### Phase 4: Pipeline Wiring

**Rationale:** Consumes Phase 3. Connects `ScrollSender` instantiation into `Pipeline.start()` and `reload_config()`. Enables end-to-end integration tests.
**Delivers:** `ScrollSender` instantiated once in `Pipeline.start()` and injected into `ActionDispatcher`; hot-reload resets scroll state cleanly
**Avoids:** Controller-per-call anti-pattern; stale scroll state after hot-reload

### Phase 5: Config + Documentation

**Rationale:** Final wiring. Validates end-to-end with real YAML config. Documents scroll conventions for users.
**Delivers:** Example scroll actions in `config.yaml` (all four directions with `scroll_speed`, `dispatch_interval`, `scroll_direction` comments); `scroll_direction: natural | traditional` config option; verification of hot-reload with scroll config

### Phase Ordering Rationale

- Phase 1 first because it is pure new code — no existing tests can break, and having `ScrollSender` fully tested before touching the dispatcher dramatically reduces integration risk
- Phase 2 before Phase 3 because `ActionDispatcher` branches on `FireMode.SCROLL` which must exist in the enum first
- Phase 3 before Phase 4 because pipeline wiring requires a tested dispatcher
- Phase 5 last because it validates the full chain end-to-end and requires all prior phases complete
- All six critical pitfalls are addressed in Phases 1–3. By Phase 4 the hard decisions are locked in and safety mechanisms are in place
- The build order matches the ARCHITECTURE.md recommended sequence exactly — no conflicts between research files

### Research Flags

Phases with standard patterns (no additional research needed):
- **Phase 1:** `ScrollSender` pattern directly mirrors existing `KeystrokeSender`. pynput mouse API verified from installed source. Implementation path is fully specified.
- **Phase 2:** Enum and config extension patterns are already established in the codebase. Backward compatible change.
- **Phase 3:** Dispatcher routing branching pattern already exists for `hold_key`. Scroll-armed flag mirrors `_held_action` lifecycle.
- **Phase 4:** Pipeline wiring follows existing `KeystrokeSender` instantiation pattern exactly.
- **Phase 5:** Config documentation — no research needed.

No phases require `/gsd:research-phase`. All technical unknowns were resolved during initial research.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | pynput scroll API verified from installed source (`pynput/mouse/_win32.py`). WHEEL_DELTA=120 confirmed. No new dependencies needed. All claims traceable to installed code. |
| Features | HIGH | Based on direct codebase analysis of all affected modules plus established gesture UX patterns. Table stakes list is minimal and focused. Anti-features list prevents over-engineering. |
| Architecture | HIGH | All integration points identified from direct code reading (action.py, config.py, pipeline.py, orchestrator.py). Component boundary decisions follow existing codebase patterns. Six unchanged components explicitly confirmed. |
| Pitfalls | HIGH | Six critical pitfalls with concrete prevention strategies, recovery costs, and phase assignments. All sourced from installed pynput source, Windows API docs, and direct codebase analysis. |

**Overall confidence:** HIGH

### Gaps to Address

- **Scroll direction default:** Research recommends natural scrolling (hand up = content moves up = `scroll(0, -1)`) but this is a UX preference that should be validated with real usage. A single config value flips it. Not a blocker — implement the default and document the override.
- **Velocity-to-ticks tuning:** The `scroll_speed: 3.0` default and MIN/MAX bounds are derived from velocity range analysis, not user testing. Expect to tune these values after first real-world use. The config system supports this without code changes.
- **EMA smoothing alpha:** The recommended alpha ~0.3 for velocity smoothing needs empirical tuning. Architecture accommodates adding smoothing inside `ScrollSender` without touching `MotionDetector`. Validate during Phase 1 implementation.

## Sources

### Primary (HIGH confidence)
- `pynput/mouse/_win32.py` (installed pynput 1.8.1 source) — verified `_scroll()` implementation, WHEEL_DELTA=120, fractional value support, HWHEEL for horizontal scroll
- [Microsoft WM_MOUSEWHEEL](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-mousewheel) — WHEEL_DELTA=120 standard, sub-notch scrolling design
- [Microsoft WM_MOUSEHWHEEL](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-mousehwheel) — horizontal scroll message and HWHEEL flag
- [Raymond Chen: Why WHEEL_DELTA is 120](https://devblogs.microsoft.com/oldnewthing/20130123-00/?p=5473) — divisibility rationale and sub-notch intent
- Codebase: `gesture_keys/action.py`, `gesture_keys/motion.py`, `gesture_keys/keystroke.py`, `gesture_keys/config.py`, `gesture_keys/pipeline.py`, `gesture_keys/orchestrator.py` — all integration points verified via direct code reading

### Secondary (MEDIUM confidence)
- [BetterTouchTool Scroll Modifiers](https://docs.folivora.ai/docs/4001_scroll_modifiers.html) — acceleration formula (`output = input * (1 + strength * sqrt(abs(input)/4))`), proven UX patterns (different platform)
- [Android fling/scroll gesture docs](https://developer.android.com/develop/ui/views/touch-and-input/gestures/scroll) — velocity-based scroll mapping patterns (mobile context, but velocity math is transferable)
- [Natural vs reverse scrolling (LogRocket)](https://blog.logrocket.com/ux-design/natural-vs-reverse-scrolling/) — direction convention analysis and user expectation data
- [pynput GitHub issue #641](https://github.com/moses-palmer/pynput/issues/641) — on_scroll dx/dy value accuracy confirmation

---
*Research completed: 2026-04-01*
*Ready for roadmap: yes*
