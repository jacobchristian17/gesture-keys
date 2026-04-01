# Pitfalls Research

**Domain:** Adding mouse scroll gesture support to existing gesture-keys app
**Researched:** 2026-04-01
**Confidence:** HIGH (codebase analysis of all affected modules + pynput Windows backend source + Windows API documentation)

## Critical Pitfalls

### Pitfall 1: pynput scroll() Multiplies by WHEEL_DELTA (120) -- Passing Velocity Directly Creates Catastrophic Scroll Speed

**What goes wrong:**
pynput's Windows `_scroll()` implementation multiplies `dy` by `WHEEL_DELTA` (120) before passing to `SendInput`. If you map MotionDetector velocity (e.g., 0.5 normalized coords/sec) directly as the scroll amount, you get `0.5 * 120 = 60` wheel units per call. At 30 FPS with no throttling, that is 1800 wheel units/sec -- roughly 15 full mouse wheel clicks per second. Documents fly past. If you naively scale velocity higher (say `dy=5`), you get `5 * 120 = 600` units per call, which is unusable.

The `scroll(dx, dy)` API looks like it takes "number of lines" but it actually takes "number of wheel notches." One notch (`dy=1`) scrolls 3 lines by default (Windows `SPI_GETWHEELSCROLLLINES` setting). So `scroll(0, 1)` = 3 lines, not 1 line.

**Why it happens:**
The WHEEL_DELTA multiplication is hidden inside pynput's platform backend (`pynput/mouse/_win32.py`). The API docs say "the units of scrolling is undefined" which is technically true cross-platform but misleading on Windows where the behavior is well-defined. Developers test with small values like `scroll(0, 2)` and see 6 lines scroll, which "seems fine" until combined with 30 FPS continuous dispatch.

**How to avoid:**
- Use only small integer values: `scroll(0, 1)` = one wheel notch (3 lines), `scroll(0, -1)` = one notch backward
- Map velocity to scroll amount with aggressive clamping: `clamp(round(velocity * scale), -3, 3)` where max is 2-3 notches
- Start conservative: `scroll(0, 1)` per dispatch at a throttled rate is already substantial
- Test in multiple apps (VS Code, browser, Excel, File Explorer) -- each interprets wheel units differently

**Warning signs:**
- Content "teleports" rather than scrolling smoothly
- Scroll moves more than ~10 lines per gesture update
- Testing only in one app and missing different scroll behaviors

**Phase to address:**
Phase 1 (core scroll implementation) -- velocity-to-scroll mapping must be designed with WHEEL_DELTA awareness from the start.

---

### Pitfall 2: MOVING_FIRE Fires Every Frame -- 30 Scroll Events/Sec Without Throttling

**What goes wrong:**
The orchestrator's `_maybe_emit_moving_fire()` emits a MOVING_FIRE signal on every frame where motion is detected. At 30 FPS, even with `scroll(0, 1)` per dispatch, that is 30 wheel notches/sec = 90 lines/sec -- far too fast for usable scrolling. The existing `dispatch_interval` throttling in `ActionDispatcher._handle_moving_fire()` works, but the global default (0.4s from config) means only ~2.5 scroll events/sec, which is sluggish. Scroll needs a sweet spot between 30/sec (too fast) and 2.5/sec (too slow).

**Why it happens:**
`dispatch_interval` was designed for keystroke throttling (arrow keys), where 0.4s gaps between presses feel responsive. Scroll has different ergonomics -- it needs higher frequency with smaller increments for smooth output. Applying the keystroke interval to scroll makes it visibly jerky (scroll-pause-scroll-pause).

**How to avoid:**
- Set a scroll-specific `dispatch_interval` in config (e.g., 0.05-0.1s = 10-20 scroll events/sec)
- The per-action `dispatch_interval` override already exists in the config system -- use it for scroll actions
- Alternatively, accumulate fractional scroll amounts per frame and dispatch only when accumulated >= 1 notch
- Consider velocity-proportional dispatch: slow motion -> longer interval, fast motion -> shorter interval

**Warning signs:**
- Scroll feels either too fast (no throttling) or stuttery (keystroke interval applied)
- Testing with the global `dispatch_interval: 0.4` and not setting a per-action override for scroll

**Phase to address:**
Phase 1 -- scroll dispatch rate must be designed alongside the fire mode.

---

### Pitfall 3: No Equivalent of release_all() for Scroll -- Runaway Scroll Has No Safety Stop

**What goes wrong:**
The existing architecture has robust stuck-key prevention: `ActionDispatcher.release_all()` clears `_held_action` and `KeystrokeSender.release_held()` releases all pressed keys on every exit path (hand lost, hand switch, app toggle off, config reload, distance gate). Scroll events are fire-and-forget -- there is no "release" for a scroll event. If the system enters a state where scroll keeps firing after the user intends to stop, there is no cleanup mechanism.

Concrete scenario: user holds pinch and moves down (scrolling). Hand briefly leaves frame. MotionDetector sees `landmarks=None`, resets to not-moving, buffer clears. Hand re-enters frame. Settling period is only 2 frames (~67ms at 30 FPS). If the user's hand is still in motion when it re-enters, the MotionDetector re-arms immediately after settling and fires unwanted scroll events before the user has stabilized.

**Why it happens:**
Fire-and-forget events (scroll, click) are fundamentally different from stateful events (key hold). The architecture was designed around stateful key lifecycle with explicit press/release pairs. Adding fire-and-forget events to the same dispatcher without equivalent safety creates an asymmetry.

**How to avoid:**
- Add a "scroll armed" state flag in ActionDispatcher, set true on HOLD_START for scroll gestures, cleared on HOLD_END and all exit paths
- When "scroll armed" is false, skip scroll dispatches even if MOVING_FIRE arrives
- On every exit path that calls `release_all()`, also clear the scroll-armed flag
- Add a max-scroll-per-second hard cap as an absolute safety limit (e.g., never exceed 20 notches/sec regardless of velocity)
- Require the gesture to be in HOLD state before scroll dispatches are honored -- moving alone is not sufficient

**Warning signs:**
- Scroll continues for 1-2 frames after hand is lost
- Scroll fires during gesture transitions (switching from pinch to fist)
- No test covers "hand lost while scrolling" or "gesture change while scrolling"

**Phase to address:**
Phase 1 -- safety mechanisms must ship with the initial scroll implementation.

---

### Pitfall 4: Three Coordinate Systems Disagree on "Which Way Is Up"

**What goes wrong:**
Three conventions collide:
1. **MediaPipe Y-axis:** Y increases downward (0 = top of frame). Moving hand up = negative dy. The MotionDetector correctly maps `dy < 0` to `Direction.UP`.
2. **pynput scroll():** Positive `dy` = scroll up (content moves down, viewport moves up). This matches physical mouse wheel: roll forward = scroll up.
3. **User's hand motion:** Hand moves up could mean "push content upward" (natural/touchscreen model, scroll DOWN) or "move viewport upward" (traditional/Windows mouse model, scroll UP).

Mapping `Direction.UP` to `scroll(0, +1)` gives traditional scrolling (hand up = scroll up). Mapping `Direction.UP` to `scroll(0, -1)` gives natural scrolling (hand up = content goes up = scroll down). Both are "correct" depending on user expectation.

**Why it happens:**
Developers pick whichever convention matches their own muscle memory, test it, and ship it. Half of users expect the opposite. macOS defaults to natural scrolling; Windows defaults to traditional for mice. Hand gesture control is closer to touchscreen interaction (natural model) but the user lives in Windows (traditional model).

**How to avoid:**
- Default to natural scrolling for gesture control because the physical metaphor of pushing content with your hand is strongest. Hand up = content moves up = `scroll(0, -1)`.
- Add `scroll_direction: natural | traditional` config option
- Document the convention clearly in config.yaml comments
- Test both directions explicitly, not just the default

**Warning signs:**
- "Scrolling feels backward" feedback
- Developer tests only one scroll direction
- No config option for direction inversion

**Phase to address:**
Phase 1 for the default mapping. Config option can be Phase 1 or Phase 2 (but the default must be deliberately chosen in Phase 1).

---

### Pitfall 5: Scroll Fire Mode Conflicts with Existing hold_key on Same Gesture

**What goes wrong:**
Currently, `pinch:holding` maps to `hold_key` mode (tap-repeat a keystroke while held). The new scroll feature needs `holding + moving` state. If a user configures both `pinch:holding` (hold_key, key repeat) and `pinch:moving:up` (scroll), both HOLD_START (triggering key repeat via `tick()`) and MOVING_FIRE (triggering scroll) fire simultaneously. The user gets key repeats AND scroll events at the same time.

Looking at the orchestrator code: MOVING_FIRE is emitted at the top-level `update()` (line ~188), independently from the HOLD state handling that emits HOLD_START. Both signal paths are active in the same frame. This is by design for keystrokes (hold a key while also firing a directional keystroke), but for scroll it creates an unwanted conflict.

**Why it happens:**
The trigger type system (`static`, `holding`, `moving`) was designed so a single gesture can have actions in multiple trigger types simultaneously. Scroll breaks this assumption because scroll IS the holding+moving behavior -- it should replace, not coexist with, a holding action.

**How to avoid:**
- Design `scroll` as a new fire_mode value that replaces `hold_key` semantics for the scroll gesture
- When a moving action has `fire_mode: scroll`, the ActionDispatcher should NOT process HOLD_START as key repeat for that gesture. Instead, HOLD_START only "arms" the scroll dispatcher.
- The cleanest approach: scroll actions live in the moving trigger map (trigger syntax `pinch:moving:up`). They are resolved via `resolve_moving()`. The fire_mode field on the Action determines whether `_handle_moving_fire()` sends a keystroke or a scroll event.
- If the gesture has ONLY scroll-mode moving actions and no explicit holding action, HOLD_START should be a no-op (no key repeat).

**Warning signs:**
- Both keystrokes and scroll events fire during the same gesture
- Existing hold_key tests break when scroll is added
- The `_held_action` field tracks a keyboard action while scroll has no equivalent state

**Phase to address:**
Phase 1 -- fire mode routing is foundational architecture.

---

### Pitfall 6: MotionDetector Velocity Jitter Causes Scroll Stutter at Low Speeds

**What goes wrong:**
The MotionDetector computes velocity from a rolling buffer of 5 wrist positions over ~167ms (5 frames at 30 FPS). At low hand speeds near the arm/disarm threshold (0.25/0.15), velocity oscillates across the threshold, causing rapid arm/disarm cycles. For keystrokes this is tolerable (dispatch_interval masks it). For scroll, this creates visible stutter: scroll-stop-scroll-stop every few frames.

Additionally, the direction can flip between adjacent frames. The `axis_ratio` filter (1.5) rejects pure diagonals but allows near-diagonal movement to alternate between UP and LEFT frame-to-frame. For scroll, direction flipping means content bounces between vertical and horizontal scroll.

**Why it happens:**
MediaPipe wrist tracking has ~2-5px noise at 30 FPS. At low velocities, noise is a significant fraction of displacement, causing both velocity and direction instability. The hysteresis gap (arm=0.25, disarm=0.15) helps but was tuned for keystroke triggers, not smooth continuous output.

**How to avoid:**
- Add velocity smoothing before mapping to scroll amount: exponential moving average `smoothed = alpha * raw + (1-alpha) * prev` with alpha ~0.3
- Use wider hysteresis for scroll (arm=0.30, disarm=0.10) to reduce threshold flicker
- Lock scroll direction once armed until motion disarms -- do not change direction mid-scroll (or require direction stability for N frames before switching)
- Add a dead zone at very low velocities where scroll amount is 0 even though motion is technically detected

**Warning signs:**
- Scroll oscillates (forward-backward-forward) when hand is nearly still
- Content shifts horizontally during intended vertical scroll
- Scroll stutters at slow speeds but works fine at fast speeds

**Phase to address:**
Phase 1 for basic smoothing and direction locking. Phase 2 for tuning after real-world testing.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Using `KeystrokeSender.send()` for scroll dispatch | No new dependency | Conflates keyboard and mouse concerns; `pynput.mouse.Controller` is a separate object with different lifecycle | Never -- scroll requires `pynput.mouse.Controller`, must be a separate component |
| Hardcoding scroll speed instead of config | Faster to ship | Every user has different scroll preferences; no way to tune without code changes | MVP only if config is added in same phase |
| Sharing MotionDetector thresholds between keystroke and scroll | No config changes needed | Keystroke and scroll have different sensitivity requirements | Acceptable if per-action velocity overrides (already supported) are used |
| No separate scroll tests -- relying on existing MOVING_FIRE tests | Faster test writing | Scroll-specific edge cases (direction inversion, capping, runaway, hold_key conflict) go untested | Never -- scroll introduces new failure modes that need dedicated tests |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `pynput.mouse.Controller` instantiation | Creating a new Controller per scroll call | Create one at Pipeline/Dispatcher init time, reuse (same pattern as keyboard Controller in KeystrokeSender) |
| `mouse.Controller` + `keyboard.Controller` coexistence | Assuming they conflict or share state | They are fully independent; both can be active simultaneously |
| MOVING_FIRE + scroll fire_mode | Dispatching scroll via `sender.send()` (keyboard) | Add fire_mode check: if SCROLL, call `mouse_controller.scroll()` instead of `sender.send()` |
| Config parsing for scroll actions | Adding `scroll` to FireMode enum but not updating DerivedConfig inference | DerivedConfig infers fire_mode from trigger state (`moving` -> `tap` currently). Scroll needs explicit `fire_mode: scroll` in config, not inference |
| Hot-reload with scroll state | Rebuilding ActionResolver but not resetting scroll state (smoothed velocity, accumulator, scroll-armed flag) | Reset scroll-specific state during hot-reload alongside existing resolver/dispatcher rebuild |
| `scroll()` argument order | Passing `(dy, dx)` instead of `(dx, dy)` | pynput signature is `scroll(dx, dy)` -- horizontal first, then vertical. For vertical-only scroll: `scroll(0, amount)` |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| `mouse.scroll()` every frame (30 FPS) | System-wide input lag, scroll acceleration overshoot | Throttle to 10-20 dispatches/sec max | Immediately -- Windows input queue backs up |
| Large scroll delta (> 3 notches per call) | Target app skips content, scroll animations break | Cap at 2-3 notches per dispatch | Immediately -- apps that animate scroll choke on large deltas |
| Velocity EMA computation per frame | None at this scale | This is ~1 multiply + 1 add per frame, negligible | Never -- not a real concern at 30 FPS |
| Separate `SendInput` calls for dx and dy | Two system calls when scrolling diagonally | pynput sends vertical and horizontal as separate calls internally. Accept this; diagonal scroll is rare | Only matters if allowing simultaneous H+V scroll |

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Default scroll speed too fast | User overshoots, content flies past target | Default to conservative speed (1 notch per dispatch at ~10 Hz); let user increase via `scroll_speed` config |
| No visual feedback during scroll | User cannot tell scroll is active or which direction | Add scroll indicator to preview overlay (directional arrow or "SCROLL DOWN" text) |
| Scroll activates during gesture transitions | Content jumps when switching between gestures | Require stable HOLD state before scroll dispatches; settling guard on scroll entry |
| Horizontal scroll enabled by default | Most users expect vertical only; accidental horizontal scroll surprises | Default horizontal scroll to off; require explicit config to enable |
| No scroll speed config | Power users want fast, cautious users want slow | Add `scroll_speed` multiplier (default 1.0) in config |
| Scroll direction feels "wrong" | Half of users disagree with any default | Provide `scroll_direction: natural | traditional` config option |

## "Looks Done But Isn't" Checklist

- [ ] **Scroll direction:** Verified in all four cardinal directions (up, down, left, right), not just one
- [ ] **hold_key conflict:** Tested that scroll fire_mode does NOT also trigger key repeats on the same gesture
- [ ] **Hand loss during scroll:** Verified scroll stops within 1 frame when hand leaves camera view
- [ ] **Gesture change during scroll:** Verified scroll stops when user switches from scroll gesture to a different gesture
- [ ] **App toggle off during scroll:** Verified scroll stops when user toggles app off via system tray
- [ ] **Config hot-reload during scroll:** Verified scroll state resets cleanly when config is reloaded while scrolling
- [ ] **Distance gate during scroll:** Verified scroll stops when hand moves out of distance range
- [ ] **Activation gate during scroll:** Verified scroll stops when activation gate expires
- [ ] **Preview overlay:** Scroll direction/speed shown in preview window
- [ ] **Multiple apps tested:** Scroll verified in browser, VS Code, File Explorer, and at least one app with custom scroll (e.g., Excel)
- [ ] **Velocity capping:** Verified that no matter how fast the hand moves, scroll speed is bounded
- [ ] **Low-speed stability:** Verified slow hand movement produces smooth scroll without stutter

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Wrong scroll direction default | LOW | Single config value change; no architectural impact |
| WHEEL_DELTA scaling surprise | LOW | Fix the mapping constant; no architecture change |
| Missing scroll throttling | LOW | Add `dispatch_interval` to scroll action config or scroll-specific throttle |
| Runaway scroll (no safety stop) | MEDIUM | Add scroll-armed flag + exit path hooks; must touch all exit paths (same scope as stuck-key prevention was) |
| Velocity jitter causing stutter | MEDIUM | Add EMA smoothing layer; may need MotionDetector extension if smoothing is per-action |
| Scroll + hold_key firing simultaneously | HIGH | Requires fire_mode routing redesign in ActionDispatcher; may affect orchestrator signal emission |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| WHEEL_DELTA scaling | Phase 1 (core implementation) | Unit test: `scroll(0,1)` produces exactly 1 notch (not 120 lines) |
| Frame-rate scroll flooding | Phase 1 (core implementation) | Unit test: 30 MOVING_FIRE signals produce <= 15 scroll dispatches |
| Runaway scroll safety | Phase 1 (core implementation) | Integration test: hand loss stops scroll within 1 frame; all exit paths clear scroll state |
| Direction convention | Phase 1 (core implementation) | Manual test: hand up = content moves down (natural default) |
| hold_key conflict | Phase 1 (fire mode routing) | Unit test: scroll fire_mode suppresses HOLD_START key repeat |
| Velocity jitter/stutter | Phase 1 (basic smoothing), Phase 2 (tuning) | Manual test: slow hand movement produces smooth scroll |
| Config options (speed, direction) | Phase 1 | Config test: `scroll_speed` and `scroll_direction` parse and apply correctly |
| Horizontal scroll default-off | Phase 1 | Config test: no horizontal scroll without explicit config |
| Preview overlay for scroll | Phase 2 (polish) | Visual test: scroll indicator visible in preview |

## Sources

- [pynput mouse documentation](https://pynput.readthedocs.io/en/latest/mouse.html) -- `scroll(dx, dy)` API reference
- [pynput Windows mouse backend (GitHub source)](https://github.com/moses-palmer/pynput/blob/master/lib/pynput/mouse/_win32.py) -- confirmed `dy * WHEEL_DELTA` multiplication in `_scroll()`
- [WM_MOUSEWHEEL (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/inputdev/wm-mousewheel) -- WHEEL_DELTA = 120, scroll line mapping
- [MOUSEINPUT (Microsoft Learn)](https://learn.microsoft.com/en-us/windows/win32/api/winuser/ns-winuser-mouseinput) -- mouseData field for MOUSEEVENTF_WHEEL / MOUSEEVENTF_HWHEEL
- [Why WHEEL_DELTA is 120 (The Old New Thing / Raymond Chen)](https://devblogs.microsoft.com/oldnewthing/20130123-00/?p=5473) -- divisibility rationale
- [pynput GitHub issue #641](https://github.com/moses-palmer/pynput/issues/641) -- on_scroll dx/dy value accuracy
- [Natural vs reverse scrolling (LogRocket)](https://blog.logrocket.com/ux-design/natural-vs-reverse-scrolling/) -- direction convention analysis
- Codebase analysis: `gesture_keys/motion.py` (MotionDetector velocity/direction), `gesture_keys/action.py` (ActionDispatcher signal routing, release_all()), `gesture_keys/orchestrator.py` (_maybe_emit_moving_fire, HOLD state), `gesture_keys/keystroke.py` (KeystrokeSender lifecycle), `gesture_keys/config.py` (DerivedConfig, FireMode, dispatch_interval)

---
*Pitfalls research for: scroll gesture support in gesture-keys v1.0.1*
*Researched: 2026-04-01*
