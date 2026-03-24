# Feature Research

**Domain:** Structured gesture architecture with activation gating, temporal states, and fire modes
**Researched:** 2026-03-24
**Confidence:** HIGH (domain well-understood from codebase analysis, QMK/ZMK fire mode patterns, and gesture state machine literature)

## Feature Landscape

### Table Stakes (Users Expect These)

Features that must work for v2.0 to feel like a coherent upgrade over v1.3.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Activation gate (arm/disarm) | Prevents false fires when not intending to use gestures; single biggest UX complaint with always-on gesture systems | MEDIUM | Already have `ActivationGate` class with timer-based arm/expire. Needs integration into orchestrator pipeline so activation gesture is consumed (not forwarded to action dispatch). Config: `activation.gesture`, `activation.duration`, `activation.enabled`. |
| Static gesture base layer | 6 gestures already classified; must remain the foundation of the new hierarchy | LOW | Existing `GestureClassifier` unchanged. Orchestrator receives classified gesture as base input. No new detection code needed. |
| Hold as temporal state modifier | "Fist held" vs "fist tapped" must produce different outputs. Users already have `mode: hold` in v1.3 config -- this generalizes it | HIGH | Currently debouncer handles hold mode per-gesture. v2.0 promotes "holding" to a temporal state that any static gesture can enter. Requires: hold detection timer, hold-start/hold-end signals, key press/release lifecycle. Depends on: Orchestrator, Action Dispatch, Hold-Key Fire Mode. |
| Swiping as temporal state modifier | "Open palm + swipe left" already works as compound gesture. v2.0 formalizes swipe as a temporal modifier on the static base | HIGH | Replaces the current `SWIPE_WINDOW` debounce state and `COMPOUND_FIRE` action. Swipe becomes a temporal state that modifies the static gesture rather than a separate compound concept. Must preserve deceleration-based fire timing from `SwipeDetector`. Depends on: Orchestrator, Action Dispatch, SwipeDetector (existing). |
| Action dispatch (static x temporal -> key) | The core lookup: given a base gesture and temporal state, resolve to a keyboard action. Without this the hierarchy is pointless | MEDIUM | New component. Lookup table: `(gesture, temporal_state) -> (key_string, fire_mode)`. Falls back to `(gesture, NONE) -> (key_string, fire_mode)` when no temporal modifier. Config drives the table. Depends on: Config Schema. |
| Tap fire mode (press+release) | Default behavior: gesture activates, key combo taps once. This is what v1.3 does for non-hold gestures | LOW | Already implemented in `KeystrokeSender.send()`. Orchestrator calls it when fire mode is "tap". No new code needed. |
| Hold-key fire mode (sustained keypress) | Key stays pressed while gesture is held, releases when gesture ends. Already exists as `mode: hold` in v1.3 | MEDIUM | Already implemented in `KeystrokeSender.press_and_hold()` / `release_held()`. Needs clean lifecycle: orchestrator emits hold-start -> sender presses, orchestrator emits hold-end -> sender releases. Must handle edge cases (hand lost, gesture changed, activation gate expires mid-hold). |
| Config schema for structured gestures | Users need to express `gesture + temporal -> action` in YAML. Must be intuitive and not wildly different from v1.3 config | MEDIUM | New config structure. Temporal modifiers nest under gestures. Fire mode specified per-action. See Config Schema section below. Depends on: nothing (define first, drives Action Dispatch). |
| Orchestrator / gesture pipeline coordinator | Single component that owns the gesture lifecycle: gate check -> classify -> temporal state -> action resolve -> fire | HIGH | Replaces the current ad-hoc pipeline in `tray.py`/`__main__.py` main loop. Must manage: activation gate, static classification, temporal state tracking, action resolution, fire mode execution. This is the architectural centerpiece. Depends on: all other table-stakes features. |

### Differentiators (Competitive Advantage)

Features that make v2.0 meaningfully better than "gesture -> key" systems.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Gesture hierarchy (base + temporal modifiers) | Multiplicative gesture vocabulary: 6 static x (none + hold + 4 swipe dirs) = up to 36 distinct actions from 6 hand shapes. No other webcam gesture app does this | HIGH | The core innovation. Static gesture is the "what", temporal state is the "how". This is the reason for the rewrite. Depends on: hold detection, swipe detection, action dispatch. |
| Activation bypass for specific gestures | Some gestures (e.g., scout, peace) can bypass the activation gate, acting as "always available" shortcuts even when system is disarmed | LOW | Simple allowlist in config: `activation.bypass: [scout, peace]`. Gate check skips these gestures. Prevents the "I have to activate just to do the one thing I do most" frustration. Depends on: Activation Gate. |
| Per-action fire mode | Different temporal states on the same gesture can have different fire modes: "fist tap -> space, fist hold -> hold space". Inspired by QMK/ZMK dual-role keys | LOW | Config-driven. Each action entry specifies `mode: tap` (default) or `mode: hold_key`. Action resolver passes mode to fire executor. No new detection logic needed. Depends on: Action Dispatch, Config Schema. |
| Hold-to-hold temporal chaining | When holding gesture A and switching to gesture B (both in hold mode), A releases and B starts without returning to idle. Fluid sustained-key transitions | MEDIUM | Already partially exists: debouncer's `HOLDING -> ACTIVATING` transition emits `HOLD_END`. Orchestrator must chain: release A's keys, then start B's hold. Requires careful ordering to avoid stuck keys. Depends on: Orchestrator, Hold-Key Fire Mode. |
| Activation gate visual feedback | Preview overlay shows armed/disarmed state, remaining armed duration as countdown or progress bar | LOW | Purely visual. Overlay already exists for distance and swipe. Add armed-state indicator. Depends on: Activation Gate, Preview (existing). |
| Configurable activation duration | Different users want different armed windows. Power users want longer (10s), cautious users want shorter (2s) | LOW | Already implemented: `ActivationGate.duration` setter. Just needs config exposure: `activation.duration: 3.0`. Depends on: Activation Gate. |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems in this domain.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Simultaneous two-hand gestures | "Left fist + right swipe = special action" | Doubles state space, MediaPipe multi-hand tracking is jittery, hand ID assignment unstable across frames. Massive complexity for marginal vocabulary gain | Keep one-hand-at-a-time. 36 single-hand actions is already more than users can memorize |
| Gesture recording / custom gesture training | "I want to define my own gestures" | Requires ML training pipeline, dataset collection UI, model management. Completely different product. MediaPipe landmarks + rules give 6 reliable gestures | Add more rule-based gestures if needed (e.g., "hang loose", "OK sign"). Each is ~10 LOC in classifier |
| Sequence gestures (gesture A then B = action) | "Fist then open palm = undo" | Temporal ordering adds exponential state space. Users can not remember sequences. Error recovery is nightmare (what if you do A then wrong gesture?) | Temporal modifiers (hold, swipe) on static gestures achieve the same vocabulary expansion with spatial intuition |
| Per-application gesture profiles | "Different gestures for Photoshop vs browser" | Requires foreground window detection (fragile on Windows), profile switching UI, config explosion. Users confused about which profile is active | Single global config. Users can use activation gate to mentally "switch modes" |
| Continuous gesture tracking (mouse cursor) | "Move my hand to move the cursor" | Completely different interaction model. Jitter makes it unusable without heavy smoothing. Latency feels laggy. Not what this tool is for | This tool fires discrete keyboard commands. Cursor control is a different product |
| Auto-calibration / adaptive thresholds | "System should learn my gestures over time" | Unpredictable behavior drift. "It worked yesterday" debugging nightmare. Users lose trust when the system changes under them | Expose tunable thresholds in config. User adjusts once, behavior is deterministic forever |
| Double-tap temporal modifier | "Double-tap fist = different action" | Adds timing ambiguity: every single tap must wait the double-tap window before firing, adding latency to all taps. QMK/ZMK community consensus is that double-tap is the least-liked tap-hold variant | Hold and swipe already provide sufficient vocabulary multiplication without timing penalties |

## Feature Dependencies

```
Config Schema (define first)
    └──drives──> Action Dispatch

Activation Gate (existing, standalone)
    └──integrates into──> Orchestrator

Action Dispatch
    └──requires──> Config Schema
    └──requires──> Static Gesture Base Layer (existing, input)

Hold Temporal State
    └──requires──> Orchestrator (lifecycle management)
    └──requires──> Action Dispatch (resolve hold actions)
    └──requires──> Hold-Key Fire Mode (execute sustained keypresses)

Swiping Temporal State
    └──requires──> Orchestrator (lifecycle management)
    └──requires──> Action Dispatch (resolve swipe-modified actions)
    └──requires──> SwipeDetector (existing, interface may change)

Orchestrator
    └──requires──> Activation Gate
    └──requires──> Action Dispatch
    └──requires──> Hold Temporal State
    └──requires──> Swiping Temporal State
    └──requires──> Fire Mode Executor (tap + hold_key)

Fire Mode Executor
    └──wraps──> KeystrokeSender (existing, already supports tap + hold)

Activation Bypass
    └──requires──> Activation Gate
    └──enhances──> Orchestrator (gate check logic)

Activation Gate Visual Feedback
    └──requires──> Activation Gate
    └──enhances──> Preview Overlay (existing)
```

### Dependency Notes

- **Config Schema must be defined first.** Action Dispatch needs to know the lookup structure before it can be built. Everything downstream depends on the schema.
- **Orchestrator is the integration point -- build last.** It depends on all other components being ready. Build components bottom-up, orchestrator top-down.
- **Activation Gate is standalone and already exists.** Integration into orchestrator is a gate check at pipeline entry. Lowest-risk component.
- **Fire Mode Executor reuses existing code.** `KeystrokeSender` already has `send()` (tap) and `press_and_hold()` / `release_held()` (hold). Wrapper adds mode dispatch, no new keystroke code.
- **Hold Temporal State is the highest-risk feature.** Hold lifecycle (start, sustain, end) has edge cases: hand lost mid-hold (must release keys), gesture changed mid-hold (must release then re-evaluate), activation gate expires mid-hold (must release). Every edge case is a potential stuck-key bug.
- **Swiping Temporal State replaces compound gestures.** The existing `COMPOUND_FIRE` / `SWIPE_WINDOW` debounce states are subsumed. SwipeDetector itself is preserved, but its output is routed through the orchestrator instead of the debouncer.

## MVP Definition

### Launch With (v2.0 Core)

Minimum viable structured gesture architecture. Build order follows dependencies.

- [ ] **Config schema for structured gestures** -- define first, drives everything else
- [ ] **Action dispatch resolver** -- the `(gesture, temporal_state) -> (key, mode)` lookup
- [ ] **Fire mode executor** -- thin wrapper over KeystrokeSender dispatching tap vs hold_key
- [ ] **Activation gate integration** -- consume activation gesture, arm/disarm, gate all other actions
- [ ] **Hold temporal state** -- hold detection, hold-start/hold-end signals, hold_key fire mode lifecycle
- [ ] **Swiping temporal state** -- swipe-as-modifier on static gestures, replacing compound gesture concept
- [ ] **Orchestrator** -- ties everything together: gate -> classify -> temporal -> dispatch -> fire

### Add After Validation (v2.x)

Features to add once core pipeline is stable and tested.

- [ ] **Activation bypass gestures** -- when users find the gate too restrictive for frequent actions
- [ ] **Activation gate visual feedback** -- when users report not knowing if system is armed
- [ ] **Hold-to-hold temporal chaining** -- when users want fluid transitions between held keys
- [ ] **Per-action fire mode in config** -- when users want mixed tap/hold on same gesture's temporal variants

### Future Consideration (v3+)

Features to defer until v2.0 is validated in real usage.

- [ ] **Additional rule-based gestures** (hang loose, OK sign) -- expand vocabulary if 6 proves limiting
- [ ] **Gesture macros** (fire sequence of keys from single gesture) -- different from single key fire
- [ ] **Left/right hand different gesture hierarchies** -- config complexity, unclear user demand

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Config schema for structured gestures | HIGH | MEDIUM | P1 |
| Action dispatch resolver | HIGH | MEDIUM | P1 |
| Orchestrator pipeline | HIGH | HIGH | P1 |
| Activation gate integration | HIGH | LOW | P1 |
| Hold temporal state | HIGH | HIGH | P1 |
| Swiping temporal state | HIGH | HIGH | P1 |
| Tap fire mode | HIGH | LOW (existing) | P1 |
| Hold-key fire mode | HIGH | LOW (existing) | P1 |
| Fire mode executor | HIGH | LOW | P1 |
| Activation bypass gestures | MEDIUM | LOW | P2 |
| Activation gate visual feedback | MEDIUM | LOW | P2 |
| Hold-to-hold chaining | MEDIUM | MEDIUM | P2 |
| Per-action fire mode config | MEDIUM | LOW | P2 |

**Priority key:**
- P1: Must have for v2.0 launch -- the structured gesture architecture requires all of these
- P2: Should have, add in v2.x -- improve usability once core is working
- P3: Nice to have, future consideration

## Config Schema Recommendation

The v2.0 config should nest temporal modifiers under each gesture, with fire mode per-action:

```yaml
activation:
  enabled: true
  gesture: scout        # gesture that arms the system
  duration: 3.0         # seconds armed window lasts
  bypass: [peace]       # gestures that skip the gate

gestures:
  fist:
    threshold: 0.7
    tap:                 # temporal state: NONE (quick gesture, fires on activation)
      key: space
      mode: tap          # press+release (default, can omit)
    hold:                # temporal state: HOLD (fires when held past threshold)
      key: space
      mode: hold_key     # sustained keypress, mirrors gesture hold state
  open_palm:
    threshold: 0.7
    tap:
      key: win+tab
    swipe_left:          # temporal state: SWIPE_LEFT
      key: "1"
    swipe_right:         # temporal state: SWIPE_RIGHT
      key: "2"
  pointing:
    threshold: 0.7
    tap:
      key: alt+tab
    hold:
      key: alt+tab
      mode: hold_key     # hold alt+tab while pointing is held
```

**Schema rationale:**
- Temporal states are explicit children of gestures (not a separate section)
- Defaults `mode` to `tap` when omitted (backward-compatible mental model)
- Replaces the v1.3 `swipe:` nesting and `mode: hold` top-level with uniform temporal-state children
- Any gesture can have any combination of temporal actions (no artificial restrictions)
- Human-readable and hand-editable in YAML
- Inspired by QMK/ZMK hold-tap where the same physical key has different behaviors based on duration/context

**Temporal state enum values for Action Dispatch:**
- `TAP` -- gesture activated, no temporal modifier (default)
- `HOLD` -- gesture sustained past hold threshold
- `SWIPE_LEFT`, `SWIPE_RIGHT`, `SWIPE_UP`, `SWIPE_DOWN` -- gesture + swipe direction

## Competitor/Reference Feature Analysis

| Feature | QMK/ZMK Keyboards | Touch Gesture Systems (iOS/Android) | Our Approach |
|---------|-------------------|--------------------------------------|--------------|
| Tap vs hold distinction | Tapping term (200ms default), 4 interrupt flavors (hold-preferred, balanced, tap-preferred, tap-unless-interrupted) | Touch duration threshold, long-press callback after ~500ms | Activation delay (configurable per-gesture). Simpler than QMK because we have no key overlap ambiguity -- gestures are visually distinct |
| Fire mode | Tap sends key A, hold sends key B (mod-tap, layer-tap) | Tap = select, long-press = context menu, drag = move | Tap = press+release, hold_key = sustained press mirroring gesture state. Two modes sufficient; QMK's 4+ flavors address keyboard-specific ambiguities we do not have |
| Activation/gating | N/A (keyboard always active) | N/A (touch always active) | Gesture-based arm/disarm with timed window. Unique to webcam gesture domain where false fires from ambient hand movement are the primary UX problem |
| Gesture hierarchy | Layer system (hold to activate layer, all keys change meaning) | Gesture priority (tap > scroll > drag), recognizer arbitration | Static gesture = base, temporal state = modifier. Conceptually similar to QMK layers but the "layer" is a temporal state, not a held modifier key |
| Temporal modifiers | Hold, double-tap, tap-dance, combo (chords) | Hold, swipe, drag, pinch, rotate | Hold and swipe only. Double-tap deferred (timing penalty on all taps). Drag/pinch/rotate not applicable to webcam hand poses |
| State machine | Per-key FSM with tapping term and interrupt detection | Per-recognizer FSM (Possible -> Began -> Changed -> Ended/Cancelled) | Orchestrator FSM managing gesture lifecycle across activation, classification, temporal resolution, and fire. Single FSM rather than per-gesture (only one hand active at a time) |
| Edge case handling | Retro tapping (hold that was actually a tap), speculative hold (apply early, cancel if tap) | Gesture failure (recognizer -> Failed state), simultaneous recognition delegation | Hold release delay (existing: 100ms grace period for hand flicker), activation gate expiry (must release held keys), gesture-change-during-hold (release and re-evaluate) |

## Sources

- [QMK Firmware Tap-Hold Documentation](https://docs.qmk.fm/tap_hold) -- tap/hold decision logic, tapping term, permissive hold, retro tapping, per-key configuration
- [ZMK Firmware Hold-Tap Behavior](https://zmk.dev/docs/keymaps/behaviors/hold-tap) -- mod-tap, layer-tap, timing configuration, interrupt flavors (hold-preferred, balanced, tap-preferred), positional hold-tap
- [ZSA Tap and Hold Keys Explained](https://blog.zsa.io/tap-hold-explained/) -- user-facing explanation of tap-hold mechanics and common frustrations
- [React Native Gesture Handler States](https://docs.swmansion.com/react-native-gesture-handler/docs/fundamentals/states-events/) -- gesture state machine patterns for touch systems
- [Material Design Gestures (M2)](https://m2.material.io/design/interaction/gestures.html) -- gesture hierarchy, priority, and composition patterns
- [Finite State Machine Gesture Recognition (Glasgow)](https://www.dcs.gla.ac.uk/~jhw/fsm.html) -- FSM approach to gesture modeling in spatial-temporal space
- [Hierarchical State Machines (UPenn)](https://www.cis.upenn.edu/~lee/06cse480/lec-HSM.pdf) -- HSM design patterns applicable to gesture orchestration
- Existing codebase analysis: `debounce.py` (state machine), `activation.py` (gate), `keystroke.py` (fire modes), `swipe.py` (swipe detection), `classifier.py` (6 gestures), `config.yaml` (current schema)

---
*Feature research for: gesture-keys v2.0 structured gesture architecture*
*Researched: 2026-03-24*
