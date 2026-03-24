# Domain Pitfalls

**Domain:** Structured gesture architecture with activation gating, temporal states, and fire modes
**Researched:** 2026-03-24
**Focus:** Clean rewrite of gesture pipeline -- adding activation gate, gesture hierarchy (static + temporal modifiers like hold/swiping), action dispatch with fire modes (tap/hold_key), and orchestrator managing state transitions
**Confidence:** HIGH -- all findings from direct analysis of 7,549 LOC existing codebase, state machine design patterns, and rewrite risk analysis

## Critical Pitfalls

Mistakes that cause rewrites, stuck keys, or fundamental architecture failures in the new pipeline.

### Pitfall 1: Stuck Keys from Incomplete hold_key Lifecycle Management

**What goes wrong:** The new `hold_key` fire mode sustains a keypress while a gesture is held. When the activation gate expires, the hand leaves camera range, the app is toggled inactive, or a config hot-reload occurs, the held key is never released. The user has a permanently stuck modifier or key in the OS until they physically press and release it.

**Why it happens:** The current codebase already has this problem in miniature -- `hold_active`, `hold_modifiers`, `hold_key`, and `sender.release_all()` are managed with loose boolean flags across 12+ locations in `__main__.py` (lines 239-244, 299-300, 317-318, 449-450) and `tray.py` (lines 226-238, 253-254, 286-287, 303-310). Every exit path must call `release_all()`. In a rewrite with a proper `hold_key` fire mode, the number of exit paths multiplies: activation gate timeout, distance gate out-of-range, hand switch, app toggle, app quit, config reload, window close, process crash. Missing ANY one path means stuck keys.

**Consequences:** User has a stuck Ctrl, Alt, Win, or Space key in the OS. This is the single most destructive failure mode -- it affects ALL applications, not just gesture-keys, and most users will not know how to diagnose or fix it.

**Prevention:**
- The new fire mode executor must own key lifecycle as a single class with a `release_all()` method called from exactly ONE cleanup path (a `finally` block or context manager `__exit__`), not scattered across 12+ locations.
- Implement a `FireModeExecutor` (or similar) that tracks all held keys internally. Every component that can interrupt the pipeline (activation gate, distance filter, hand switch, app toggle) signals the executor to release, rather than each calling `sender.release_all()` independently.
- Add a watchdog: if `hold_key` has been active for longer than a configurable maximum (e.g., 30 seconds), auto-release and log a warning. This catches missed cleanup paths.
- Use `atexit.register(sender.release_all)` as a last-resort safety net for process crashes.
- Test: toggle app inactive during hold, switch hands during hold, distance gate out-of-range during hold, activation gate expire during hold, config reload during hold. Each must release.

**Detection:** Any user report of "my keyboard is acting weird after using gesture-keys" is this bug.

**Phase:** Address in the FIRST phase that implements the fire mode executor. This is the highest-priority safety requirement of the entire rewrite.

---

### Pitfall 2: Activation Gate Creates Unusable Dead Zones

**What goes wrong:** The activation gate (arm/disarm with scout/peace gesture) swallows the activation gesture so it does not fire a keystroke. But users who previously had scout and peace mapped to useful keys (currently `win+ctrl+right` and `win+ctrl+left`) lose those mappings entirely. Worse, if the gate timeout is too short, users cannot complete their intended gesture sequence before the gate expires, and if too long, accidental gestures during the armed window fire unintended keystrokes.

**Why it happens:** The activation gate is a fundamentally different interaction model from the current "always on" system. The existing `ActivationGate` class (activation.py) has a fixed duration and a single activation gesture. Users must learn a new ritual: make activation gesture -> wait for confirmation -> make action gesture -> system disarms. Any mismatch in timing expectations creates frustration.

**Consequences:** The system feels unreliable -- sometimes gestures work, sometimes they do not (because the gate expired). Users lose muscle memory from v1.x. The bypass mode (gate disabled) becomes the only usable mode, rendering the feature dead code.

**Prevention:**
- Make the gate **optional with bypass as the default**. Users opt in to gating, not out.
- The activation gesture should be one that is NOT commonly used for keystroke mappings. Scout (3 fingers) is a reasonable default because it is the least natural gesture and least likely to be mapped to a critical action.
- Provide clear visual/audio feedback when armed (tray icon color change, preview overlay indicator).
- Allow re-arming: if the user makes the activation gesture again while armed, reset the timer rather than ignoring it.
- Consider a "toggle" mode alternative to "timed window" -- activation gesture arms, same gesture disarms. This eliminates the timeout anxiety.
- Test with real usage: time how long typical gesture sequences take and set the default duration to 2x that.

**Detection:** If users consistently disable the gate in config, the timeout or gesture choice is wrong.

**Phase:** Address when implementing the activation gate. Get the bypass/default behavior right before worrying about the armed window tuning.

---

### Pitfall 3: Clean Rewrite Drops Subtle Behaviors That Took Months to Discover

**What goes wrong:** The current codebase has accumulated ~15 subtle behavioral fixes across v1.0-v1.3 that are encoded in code but not documented as requirements. A clean rewrite starts from the spec and misses these behaviors, reintroducing bugs that were already fixed.

**Why it happens:** The PROJECT.md documents features and decisions but does not list the specific edge-case behaviors. Examples of subtle behaviors in the current code that a rewrite must preserve:

1. **Swipe-exit reset** (debouncer + smoother reset when `was_swiping` goes False, __main__.py lines 320-334): Prevents stale gesture data from causing a false fire after a swipe. This was explicitly identified as a latent bug in v1.2 research and subsequently fixed.
2. **Pre-swipe gesture suppression** (debouncer forced into COOLDOWN with the pre-swipe gesture after swipe ends, __main__.py lines 326-333): Prevents the gesture that was held before the swipe from immediately re-firing after the swipe.
3. **Static-first priority gate** (debouncer `is_activating` suppresses swipe detector, __main__.py line 364): Prevents swipe detection from preempting a static gesture that is being confirmed.
4. **Distance gate full pipeline reset** (hold release + sender release + smoother/debouncer/swipe reset, __main__.py lines 296-304): All state machines must flush when the hand leaves range.
5. **Hand switch full pipeline reset** (same as distance but triggered by handedness change, __main__.py lines 263-279): Must release holds and swap key mappings atomically.
6. **Compound swipe suppression timing** (`compound_swipe_suppress_until`, __main__.py lines 428-433): Prevents standalone swipe fires during and immediately after a compound gesture window.
7. **Unmapped swipe direction reset** (swipe detector reset when unmapped direction detected during swipe window, __main__.py lines 374-379): Prevents unmapped swipes from consuming the detector's cooldown.
8. **COOLDOWN -> ACTIVATING for different gesture** (debounce.py lines 264-279): Direct gesture transitions without returning to None.
9. **Hold release delay** (debounce.py lines 317-324): Absorbs momentary gesture loss during hold without prematurely releasing.
10. **Sticky active hand during two-hand frames** (detector.py lines 175-177): Prevents hand-switch jitter.

**Consequences:** Each missed behavior is a regression bug. Users who upgraded from v1.x will report "this used to work and now it doesn't." Debugging is slow because the symptoms are intermittent and context-dependent.

**Prevention:**
- Before starting the rewrite, extract a **behavior inventory** from the current code: every `if` branch, every reset call, every special-case handler. Document each as a test case.
- Write integration tests against the CURRENT code that exercise each behavior. These tests become the regression suite for the rewrite -- they must pass against the new code too.
- Do NOT rewrite from the spec alone. The spec describes WHAT the system does; the code describes HOW it handles edge cases. Both are needed.
- Consider an incremental refactor approach for the pipeline internals (extract orchestrator, then extract action resolver, then add activation gate) rather than a from-scratch rewrite, to preserve these behaviors by default.

**Detection:** Run the existing test suite against the new code at every phase. Any failure is a regression.

**Phase:** Address BEFORE starting the rewrite. The behavior inventory and regression test suite must exist first. This gates all other phases.

---

### Pitfall 4: Gesture Hierarchy State Explosion

**What goes wrong:** The gesture hierarchy (static gesture x temporal state -> action) creates a combinatorial state space. With 7 static gestures, 3 temporal states (none/hold/swiping), and 4 swipe directions, the full matrix is 7 x (1 + 1 + 4) = 42 possible actions. The orchestrator must handle transitions between ALL of these states, not just the ones that have key mappings. Unmapped state combinations still need defined behavior (do nothing, or block, or pass through).

**Why it happens:** The current system has two parallel pipelines (static and swipe) with ad-hoc mutual exclusion. The rewrite aims to unify them into a hierarchy, but the hierarchy is inherently more complex than two independent pipelines. Developers underestimate the number of transition edges in the state graph.

**Consequences:** Unmapped state combinations cause undefined behavior (could fire nothing, fire the wrong thing, or get stuck). States that "should not happen" happen because MediaPipe classification is noisy. Example: user is in `FIST + holding` (hold mode), hand shifts slightly, classifier flickers to `THUMBS_UP` for 1 frame -- does the system release the hold? Start a new hold? Fire a tap?

**Prevention:**
- Define explicit behavior for EVERY cell in the gesture x temporal-state matrix, even if that behavior is "ignore" or "pass through to static-only handler."
- The orchestrator should have a default fallback for unmapped combinations, not crash or silently do nothing.
- Test with the confusable gesture pairs (PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP) in each temporal state. These are the pairs most likely to cause unexpected transitions.
- Keep the temporal state model simple: a gesture's temporal state should be a property of the gesture, not a separate axis. I.e., `open_palm` has a `hold_duration` that determines if it is in "tap" or "hold" state, rather than tracking temporal state independently of gesture identity.

**Detection:** Log every orchestrator state transition. If you see state combinations not in the matrix, the state space has a gap.

**Phase:** Address in the orchestrator design phase. The matrix must be fully specified before implementation.

---

### Pitfall 5: Duplicated Loop Code Diverges During Rewrite

**What goes wrong:** The current codebase has two nearly-identical detection loops: `run_preview_mode()` in `__main__.py` (lines 132-554, ~420 lines) and `_detection_loop()` in `tray.py` (lines 138-488, ~350 lines). These share ~90% of their logic but with subtle differences (preview has FPS calculation, debug logging, window management; tray has active/shutdown threading). A rewrite that does not unify them first will either: (a) diverge further as new features are added to one but not the other, or (b) require implementing every change twice with the risk of inconsistency.

**Why it happens:** The duplication was originally a pragmatic choice (tray mode has threading constraints from pystray's main-thread requirement). Over v1.0-v1.3, both loops accumulated the same fixes independently: hand switching, distance gating, swipe detection, compound gestures, hold mode. Each addition required careful mirroring.

**Consequences:** During the rewrite, a behavioral fix applied to the orchestrator in preview mode is forgotten in tray mode (or vice versa). Users in tray mode (the default) hit bugs that were already fixed in preview mode. Testing doubles in scope.

**Prevention:**
- The FIRST action of the rewrite should be extracting the shared pipeline into a single `GesturePipeline` class (or similar) that both preview and tray modes call. This class owns: camera read -> detect -> classify -> smooth -> debounce -> fire. Preview mode adds rendering; tray mode adds threading/active toggle.
- The pipeline class should expose a single `process_frame(frame, timestamp) -> list[Action]` method. The caller handles frame acquisition and action execution (preview renders; tray logs).
- This unification is a prerequisite for all other rewrite phases. Adding activation gating, temporal states, or fire modes to a unified pipeline is one change. Adding them to two duplicated loops is two changes with divergence risk.

**Detection:** `diff __main__.py tray.py` should show ONLY caller-specific code (preview rendering, tray threading). Any shared logic appearing in both files is duplication.

**Phase:** Address as Phase 1 of the rewrite. All subsequent phases build on the unified pipeline.

---

## Moderate Pitfalls

### Pitfall 6: Activation Gate Interacts Badly with Hold Mode

**What goes wrong:** User arms the system with the activation gesture, then performs a `hold_key` gesture (e.g., fist for sustained space). The activation gate timer counts down during the hold. When the gate expires, the hold should release -- but the user is still holding the gesture. If the system releases the key but does not inform the user, they continue holding fist expecting space to be pressed, not knowing the gate expired.

**Prevention:**
- When the activation gate expires during a hold, the fire mode executor must: (a) release the held key, (b) provide feedback (preview overlay flash, tray notification), and (c) transition the pipeline to a "gated" state where gestures are detected but not acted upon.
- Consider extending the gate duration automatically while a hold is active ("hold extends gate"). The gate should not expire while a key is being held.
- Test: arm gate -> fist hold -> gate expires -> verify key released and no stuck key.

**Phase:** Address when implementing activation gate + fire mode integration. This is a cross-cutting concern between the two features.

### Pitfall 7: Temporal State Transitions During Gesture Flicker

**What goes wrong:** The temporal state model (static -> hold after N seconds, static -> swiping on velocity threshold) assumes stable gesture classification. In practice, the classifier flickers between confusable gestures (PEACE<->SCOUT) 2-5 times per second near the decision boundary. Each flicker resets the hold timer or interrupts a swipe detection, making both temporal states unreachable for gestures near the confusion boundary.

**Prevention:**
- The temporal state timer should be scoped to the gesture BASE, not the exact gesture identity. If the gesture changes between confusable neighbors but the temporal state is unchanged (still holding), the timer should not reset.
- Alternatively, apply hysteresis: once a gesture has been classified for N frames, only allow transition to a DIFFERENT gesture after M frames of the new gesture (where M > the typical flicker duration of 2-3 frames).
- The smoother already provides some of this, but window=2 (current config) absorbs at most 1 frame of flicker. For temporal states that depend on multi-second holds, the smoother window is insufficient.
- Test with confusable pairs: hold PEACE near the SCOUT boundary for 5 seconds, verify hold mode activates without interruption.

**Phase:** Address in temporal state implementation. Must be designed before the hold timer is built.

### Pitfall 8: Action Resolver Becomes a God Object

**What goes wrong:** The action resolver (static gesture x temporal state -> key mapping lookup) absorbs responsibility for: config lookup, key parsing, fire mode selection, per-gesture cooldown/threshold override, left/right hand mapping swap, compound gesture resolution. It becomes a 500+ line class that is hard to test and harder to modify.

**Prevention:**
- Separate concerns: (a) a `GestureState` class that knows the current gesture + temporal state, (b) a `MappingResolver` that looks up key bindings from config, (c) a `FireModeExecutor` that handles tap vs hold_key execution. The action resolver is just the glue between these three.
- Each component should be independently testable with mock inputs. The `MappingResolver` should take a gesture state and return a key binding; it should not know about the fire mode. The `FireModeExecutor` should take a key binding and a mode; it should not know about gestures.
- The current code's `_parse_key_mappings()` + `_parse_swipe_key_mappings()` + `_parse_compound_swipe_key_mappings()` (three near-identical functions in both __main__.py and tray.py) is a preview of what happens when resolution logic is not unified.

**Phase:** Address during architecture design. Get the component boundaries right before implementing.

### Pitfall 9: Config Schema Backwards Compatibility Break

**What goes wrong:** The v2.0 config schema needs new fields (activation gate settings, fire mode per gesture, temporal state parameters). If the schema changes are not backwards-compatible with v1.x configs, users upgrading lose their customized settings and must re-create their config from scratch.

**Prevention:**
- New fields must have sensible defaults that reproduce v1.x behavior when absent. The activation gate should default to `enabled: false`. Fire modes should default to `tap` (current behavior). Temporal states should default to the current behavior (hold only for `mode: hold` gestures).
- Add config migration: detect v1.x schema (no activation section, no fire_mode field) and apply defaults silently, with a log message noting the upgrade.
- The existing `AppConfig` dataclass with defaults (config.py) already follows this pattern -- extend it, do not replace it.
- Test: load the CURRENT config.yaml with the new code and verify identical behavior to v1.3.

**Phase:** Address in the config/schema design phase. Must be validated before any feature implementation.

### Pitfall 10: Rewrite Kills the Feedback Loop

**What goes wrong:** The current system works. Users (the developer) have tuned config values over months of real usage. A clean rewrite that takes multiple weeks to reach feature parity means weeks without a working system, during which: (a) real-world usage feedback stops, (b) accumulated config tuning knowledge is lost, (c) motivation drops because the "new thing" does not work yet.

**Prevention:**
- Implement the rewrite incrementally behind feature flags. Each new component (activation gate, orchestrator, fire modes) should be independently toggleable so the old pipeline remains functional.
- Alternatively, implement as a refactor: extract unified pipeline first (preserving all behavior), then add new features one at a time. At every step, the system is usable.
- Set a "feature parity checkpoint" early: the refactored code must pass all existing tests and reproduce all v1.3 behavior before any new features are added.
- Do NOT start with the activation gate (the most disruptive change to UX). Start with the pipeline unification (Pitfall 5) and the orchestrator extraction (structural, not behavioral).

**Detection:** If the developer stops using gesture-keys during the rewrite, the rewrite has killed the feedback loop.

**Phase:** Affects phase ordering. Pipeline unification and feature parity must come before any new user-facing features.

## Minor Pitfalls

### Pitfall 11: Orchestrator Priority Logic Conflicts with Activation Gate

**What goes wrong:** The orchestrator determines which gesture type has priority (static > swipe, per the current static-first priority gate). The activation gate adds another layer: gated gestures should not even reach priority resolution. If the activation gate check happens after priority resolution, gated gestures may have already suppressed swipe detection or started hold timers, creating stale state when the gate is subsequently found to be disarmed.

**Prevention:**
- The activation gate check must be the FIRST step in the pipeline, before any classification or state tracking. If the gate is disarmed, the frame is a no-op (no state updates, no classification, no swipe tracking).
- Architecture: `frame -> activation gate check -> (if armed) gesture classification -> orchestrator -> action dispatch`.
- Do NOT classify the gesture and then check the gate. Classification has side effects (smoother buffer fills, swipe position buffer fills).

**Phase:** Address in orchestrator architecture design.

### Pitfall 12: pynput hold_key Mode Interacts with OS Key Repeat

**What goes wrong:** The current hold mode uses repeated `sender.send()` calls at `hold_repeat_interval` (30ms) to simulate key repeat. The new `hold_key` fire mode (sustained keypress) uses `press_and_hold()` to keep the key physically pressed. This triggers the OS-level key repeat (Windows default: 250ms delay, then 30/sec repeat), which is different from the app-controlled repeat rate. Some applications handle physical holds differently from rapid taps.

**Prevention:**
- Decide which semantic is needed: OS-level repeat (press and hold, let the OS repeat) or app-level repeat (tap rapidly at a controlled rate). The current implementation uses app-level repeat; the proposed `hold_key` mode implies OS-level.
- If using OS-level hold, the fire mode executor needs only `press()` on start and `release()` on end. But be aware that some applications (games, terminal emulators) consume the first keypress and do not repeat.
- If keeping app-level repeat, `hold_key` mode should be implemented as the current `send()` loop, just wrapped in a cleaner abstraction.
- Test both modes in the actual target applications (alt+tab, win+ctrl+left, etc.) to verify the intended behavior.

**Phase:** Address during fire mode executor implementation.

### Pitfall 13: Test Suite Cannot Test Real Gesture Sequences

**What goes wrong:** The existing tests use mock landmarks and timestamps. They test individual components (classifier, smoother, debouncer, swipe detector) in isolation. They cannot test the actual interaction patterns that cause real-world bugs: "make fist, transition to peace, swipe left, return to rest." The rewrite adds more interaction points (activation gate, temporal states, fire modes) that amplify the gap between unit tests and real behavior.

**Prevention:**
- Create a `GestureSequencePlayer` test utility that feeds pre-recorded landmark sequences through the full pipeline and asserts on the output actions. This bridges the gap between unit tests and manual testing.
- Record 5-10 "golden" gesture sequences from real camera data (just the landmark coordinates and timestamps, not video). These become the regression test inputs.
- At minimum, create synthetic sequences for the critical interaction patterns: arm -> gesture -> fire, arm -> hold -> release, arm -> gesture -> swipe -> return, confusable pair oscillation.

**Phase:** Build the test utility early (alongside pipeline unification). Use it throughout all subsequent phases.

### Pitfall 14: Temporal State "Hold" Conflicts with Existing "mode: hold" Concept

**What goes wrong:** The current codebase already has `mode: hold` (config.py `_extract_gesture_modes`, debounce.py `HOLD_START`/`HOLD_END`) which means "keep key pressed while gesture is held." The v2.0 spec introduces "hold" as a temporal state modifier (gesture held for N seconds changes behavior). These are different concepts with the same name. Developers, documentation, and config keys will confuse them.

**Prevention:**
- Use distinct terminology. The gesture fire mode should remain `mode: hold` (for sustained keypress). The temporal state should be called something different: `hold_modifier`, `sustained`, or `long_press`. Do NOT reuse the word "hold" for both concepts.
- In the gesture hierarchy, a `long_press` temporal state can trigger a DIFFERENT action than a `tap` of the same gesture. This is orthogonal to whether the fired action uses `tap` or `hold_key` fire mode.
- Example: `open_palm` tap fires `win+tab` (tap mode), `open_palm` long_press fires `win+d` (also tap mode). The temporal state selects the action; the fire mode selects how the key is sent.

**Detection:** If anyone asks "wait, does hold mean the key is held or the gesture is held?" the naming is wrong.

**Phase:** Address during architecture/naming design, before any implementation.

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Pipeline unification (extract shared loop) | Dropping subtle edge-case behaviors (Pitfall 3) | Build behavior inventory + regression tests BEFORE refactoring |
| Pipeline unification | Duplicated code diverges further (Pitfall 5) | Extract shared pipeline as Phase 1; all subsequent work builds on it |
| Activation gate | Dead zones / unusable timeout (Pitfall 2) | Default to bypass; make gate opt-in; provide clear feedback |
| Activation gate | Gate expires during hold (Pitfall 6) | Hold extends gate; release key on gate expiry |
| Activation gate | Gate check ordering (Pitfall 11) | Gate check BEFORE classification; disarmed = no-op |
| Gesture hierarchy / orchestrator | State explosion (Pitfall 4) | Define full gesture x temporal-state matrix before implementation |
| Gesture hierarchy / orchestrator | Temporal state flicker (Pitfall 7) | Hysteresis on gesture transitions; timer scoped to gesture base |
| Gesture hierarchy / orchestrator | "Hold" naming collision (Pitfall 14) | Use "long_press" for temporal state; "hold" for fire mode only |
| Fire mode executor | Stuck keys (Pitfall 1) | Single cleanup path; watchdog timer; atexit safety net |
| Fire mode executor | OS key repeat mismatch (Pitfall 12) | Decide tap-repeat vs physical-hold semantic upfront |
| Fire mode executor | God object (Pitfall 8) | Separate GestureState / MappingResolver / FireModeExecutor |
| Config / schema | Backwards compatibility (Pitfall 9) | New fields default to v1.x behavior; test with current config.yaml |
| All phases | Rewrite kills feedback loop (Pitfall 10) | Incremental refactor; feature parity checkpoint before new features |
| Testing | Cannot test real sequences (Pitfall 13) | Build GestureSequencePlayer early; record golden sequences |

## Integration Risk Map

The highest-risk integration point in the v2.0 rewrite is the **activation gate + hold fire mode + temporal state** intersection:

1. User makes scout gesture (activation gate arms)
2. User makes fist gesture (hold_key fire mode, space key held)
3. User holds fist for 3 seconds (temporal state: long_press -- should this change the action?)
4. Activation gate timer expires during the hold
5. System must: release space key, disarm gate, transition to unarmed state, NOT re-fire when user releases fist

Each step individually is straightforward. The combination exercises: gate lifecycle, fire mode key tracking, temporal state transition, and cleanup ordering. Missing any one step produces a stuck key, phantom fire, or silent failure.

The second highest-risk point is **pipeline unification + behavioral preservation** (Pitfall 3 + 5). If the unified pipeline drops any of the 10 subtle behaviors documented in Pitfall 3, the regression will not be caught until real-world usage exposes it.

## Rewrite-Specific "Looks Done But Isn't" Checklist

- [ ] Load current config.yaml with new code -- identical behavior to v1.3
- [ ] All 14 existing tests in test_debounce.py pass against new pipeline
- [ ] All 5 tests in test_integration_mutual_exclusion.py pass against new pipeline
- [ ] Preview mode and tray mode produce identical gesture/fire behavior (no divergence)
- [ ] Hold fist (hold mode) -> toggle app inactive -> verify space key released
- [ ] Hold fist -> hand leaves camera range -> verify space key released
- [ ] Hold fist -> switch hands -> verify space key released
- [ ] Hold fist -> activation gate expires -> verify space key released
- [ ] Hold fist -> config hot-reload -> verify space key released
- [ ] Arm gate -> PEACE gesture -> verify PEACE fires (not swallowed as gate gesture)
- [ ] Arm gate -> wait for expiry -> PEACE gesture -> verify PEACE does NOT fire
- [ ] FIST (hold) 10 seconds -> verify exactly 1 hold_start, 0 extra fires, 1 hold_end on release
- [ ] Confusable pairs (PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP) in each temporal state
- [ ] Swipe during armed window -> verify swipe fires, gate stays armed
- [ ] Config with no activation section -> verify bypass mode (all gestures fire immediately)

## Sources

- Direct analysis of gesture-keys source code v1.3: __main__.py (571 lines, preview pipeline), tray.py (516 lines, tray pipeline), debounce.py (338 lines, 6-state machine), classifier.py (155 lines, 7 gestures), smoother.py (52 lines), swipe.py (321 lines, 3-state machine), keystroke.py (152 lines, hold tracking), activation.py (67 lines, gate prototype), config.py (321 lines, 42 config fields), detector.py (202 lines, hand selection)
- Previous v1.2 pitfalls research (.planning/research/PITFALLS.md, 2026-03-22) -- pitfalls 1-4 from that research remain relevant and are subsumed by this document's broader scope
- Behavioral edge cases extracted from: test_debounce.py (14 tests), test_integration_mutual_exclusion.py (5 tests), test_compound_gesture.py, test_swipe.py
- Key decisions log in PROJECT.md (15 validated decisions documenting rationale for current edge-case handling)
- Rewrite risk analysis based on the "Second System Effect" pattern: rewrites that drop accumulated fixes are a well-documented failure mode in software engineering

---
*Pitfalls research for: gesture-keys v2.0 structured gesture architecture*
*Researched: 2026-03-24*
