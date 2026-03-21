# Project Research Summary

**Project:** gesture-keys v1.2 — Seamless Gesture Transitions
**Domain:** Real-time gesture state machine refactoring
**Researched:** 2026-03-22
**Confidence:** HIGH

## Executive Summary

gesture-keys v1.2 is a targeted state machine refactoring milestone, not a feature expansion. The entire milestone is achievable with zero new dependencies — all four research tracks converge on surgical modifications to existing files (`debounce.py`, `swipe.py`, `config.py`, `__main__.py`, `config.yaml`). The keystone change is modifying `GestureDebouncer._handle_cooldown` to allow COOLDOWN -> ACTIVATING transitions when a *different* gesture appears, breaking the current requirement that users return their hand to "none" between every command. This is approximately 15 lines of code change in a 134-line file.

The recommended approach follows three sequential concerns: (1) implement direct gesture-to-gesture firing in the debouncer with proper safety guards, (2) reduce swipe/static transition latency via settling frame reduction and pipeline reset cleanup, then (3) update timing defaults to match values already proven by real-world usage. The order is load-bearing: the direct transition change alters what "good defaults" look like, so tuning before the structural change would require re-tuning afterward. Phases A and B (debouncer and swipe settling) are independent of each other and could be done in either order or in parallel, but Phase C (defaults and config wiring) and Phase D (integration testing) must follow both.

The primary risk is double-fire on transitional hand poses. When transitioning from gesture A to gesture B, the classifier produces 2-3 frames of intermediate "ghost" gestures (e.g., FIST to PEACE passes through POINTING as the index finger extends). With the current config (`smoothing_window: 1`, `activation_delay: 0.1s`), there is essentially no noise rejection buffer, so any transitional pose lasting 3 frames at 30fps can fire. A latent bug was also identified: `__main__.py` is missing a smoother/debouncer reset on the swipe -> static transition (only the static -> swipe direction currently resets them), which is masked today by the large `settling_frames=10` value. This bug must be fixed before reducing settling frames, or it will cause false static fires after swipes.

## Key Findings

### Recommended Stack

No new dependencies. This milestone is a pure code change within the existing stack. The existing synchronous 30fps pipeline (`mediapipe`, `opencv-python`, `pynput`, `PyYAML`, `pystray`, `Pillow`) is sufficient. Adding a state machine library (`transitions`, `python-statemachine`) was explicitly evaluated and rejected — these libraries add import overhead and DSL complexity that exceeds the cost of the 15-line modification needed. The `pytest` test suite is the only tooling addition, and it already exists in the project.

**Core technologies (unchanged):**
- `mediapipe >= 0.10.33`: hand landmark detection — classification layer not touched
- `pynput >= 1.7.6`: keystroke simulation — fires what it is told, no changes
- `PyYAML >= 6.0`: config loading/hot-reload — schema additions only (`settling_frames`)
- `pytest >= 8.0`: test runner — new test cases for gesture-to-gesture transitions

### Expected Features

**Must have (v1.2 table stakes):**
- Direct gesture-to-gesture firing — users expect fist -> peace to fire peace without dropping hand; this is the core behavioral change
- Reduced swipe -> static transition latency — current ~1s delay (settling + smoother refill + activation) is perceptible and frustrating
- Removal of unnecessary smoother/debouncer resets on swipe -> static transition — this is a latent bug fix that enables safe settling reduction
- Tuned timing defaults — code defaults (0.4s activate, 0.8s cooldown) are conservative first guesses; real usage proves faster values work

**Should have (v1.2.x after validation):**
- Configurable transition mode (flag for "require_none" legacy vs. "direct_transition" new) — for users who prefer conservative behavior
- Transition preview feedback — show debounce state (IDLE/ACTIVATING/COOLDOWN) in overlay for debugging

**Defer (v2+):**
- Adaptive activation delay (shorter for gesture-to-gesture, longer for first appearance) — adds state-dependent timing complexity
- Held-key mode (hold gesture = hold key down) — separate state machine with press/release tracking, edge cases with OS key repeat
- Swipe-during-static (allow swipe to interrupt ACTIVATING state) — complex pipeline interaction with mutual exclusion

### Architecture Approach

The pipeline is a linear chain (camera -> detect -> classify -> smooth -> debounce -> fire) with a parallel swipe path coordinated by the main loop. No structural changes to component boundaries are needed for v1.2. All changes are internal to existing components and do not affect inter-component interfaces. The main loop's `is_swiping` flag remains the sole coordinator for mutual exclusion between the swipe and static paths.

**Major components and their v1.2 changes:**
1. **GestureDebouncer** (`debounce.py`) — add `_fired_gesture` field; modify `_handle_cooldown` to allow COOLDOWN -> ACTIVATING for different gestures; store fired gesture in `_handle_fired` (one line)
2. **SwipeDetector** (`swipe.py`) — add velocity gate after cooldown expiry; reduce default `settling_frames` from 10 to 3-4; update default parameter values
3. **AppConfig** (`config.py`) + `config.yaml` — add `settling_frames` to swipe config schema; update timing defaults to match real-world proven values
4. **Main loop** (`__main__.py`) — add missing smoother/debouncer reset on swipe -> static transition; wire `settling_frames` from config to SwipeDetector; add `smoother.reset()` to hot-reload block

**Unchanged components:** `detector.py`, `classifier.py`, `smoother.py`, `keystroke.py`, `distance.py`, `activation.py`, `preview.py`, `tray.py`, `requirements.txt`

### Critical Pitfalls

1. **Double-fire on transitional poses** — when COOLDOWN -> ACTIVATING for a different gesture is allowed, intermediate hand shapes (e.g., POINTING during FIST -> PEACE transition) become firing candidates. Mitigation: always reset the full activation timer on the new gesture; keep `activation_delay >= 0.15s` minimum for direct transitions; test all 42 gesture-pair combinations and especially confusable pairs (PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP).

2. **Same-gesture repeat-fire on cooldown modification** — modifying COOLDOWN behavior can accidentally allow the held gesture to re-enter ACTIVATING and spam keystrokes. Mitigation: the COOLDOWN -> ACTIVATING guard MUST check `gesture != _fired_gesture`; same gesture still requires returning to None. Write an explicit test: hold gesture A for 10 seconds, verify exactly 1 fire event.

3. **Missing smoother/debouncer reset on swipe -> static transition (latent bug)** — `__main__.py` resets smoother and debouncer when swiping *starts* but NOT when swiping *ends*. This is masked by `settling_frames=10` today but will cause false static fires after reducing settling. Mitigation: add the mirror reset (`if not swiping and was_swiping: smoother.reset(); debouncer.reset()`) before reducing settling frames — this is a prerequisite, not optional cleanup.

4. **Smoother window and activation delay are a coupled system** — `perceived_latency = (window_size / fps) + activation_delay`. Changing one without the other creates unexpected behavior. With direct transitions enabled, the classifier WILL produce transitional noise that `window=1` cannot absorb; a minimum of `window=3` + `delay=0.15s` (~250ms total) is recommended for direct transition robustness.

5. **Hot-reload desynchronizes state machines (latent bug)** — config hot-reload resets the debouncer but not the smoother or swipe detector settling state. With more state machine paths added in v1.2, a stale smoother on reload can immediately push a gesture into the new COOLDOWN -> ACTIVATING path. Mitigation: reset ALL stateful components on config reload.

## Implications for Roadmap

The dependency graph drives a clear 5-phase build order. Phases A and B are independent; Phase C depends on both; Phase D validates all; Phase E is empirical tuning.

### Phase A: Debouncer Direct Transitions

**Rationale:** This is the keystone feature. All other changes are incremental tuning on top of it. Must come first because it defines what "seamless transitions" means and determines what parameter values make sense downstream.
**Delivers:** Direct gesture-to-gesture firing without requiring hand release to neutral; updated test suite for all new transition paths
**Addresses:** "Direct gesture-to-gesture firing" (P1), latent hot-reload desync bug
**Avoids:** Double-fire on transitional poses (Pitfall 1), same-gesture repeat-fire (Pitfall 2), insufficient test coverage (write tests before implementing — TDD)
**Key tasks:** Add `_fired_gesture` field to `GestureDebouncer`; modify `_handle_cooldown`; update `_handle_fired` (one line); write 7 test scenarios before implementation; add debouncer state to preview overlay for visibility during development

### Phase B: Swipe/Static Transition Latency Reduction

**Rationale:** Independent of Phase A. Must fix the latent missing-reset bug before reducing settling frames — this ordering is non-negotiable. The reset fix is a prerequisite; only then is it safe to reduce `settling_frames`.
**Delivers:** Swipe -> static transition latency reduced from ~1s to ~0.5s; static -> swipe transition behavior verified; settling converted to time-based duration
**Addresses:** "Reduced swipe -> static transition latency" (P1), "Remove unnecessary pipeline resets" (P1)
**Avoids:** Stale smoother data after swipe ends (Pitfall 3), residual velocity re-arming swipe detector (Pitfall 9), FPS-dependent frame-count settling (Pitfall 6)
**Key tasks:** Add missing `smoother.reset()` + `debouncer.reset()` on swipe -> static in `__main__.py`; add velocity gate in `SwipeDetector` after cooldown; reduce default `settling_frames` from 10 to 3-4; convert settling to time-based `settling_duration`

### Phase C: Config Schema and Wiring

**Rationale:** Thin layer that depends on Phases A and B finalizing parameter names. Adds user-facing config surface and fixes the hot-reload latent bug.
**Delivers:** `settling_frames`/`settling_duration` exposed in `config.yaml`; hot-reload updated to reset all stateful components; updated config defaults
**Addresses:** Hot-reload desynchronization (Pitfall 7)
**Key tasks:** Add `settling_duration` to swipe config schema in `config.py`; wire to `SwipeDetector` in `__main__.py`; add `smoother.reset()` to hot-reload block; update `config.yaml` with new fields

### Phase D: Integration Testing and Validation

**Rationale:** All individual changes must be validated together before tuning. The compound scenario (gesture A -> gesture B -> swipe) is high-risk because it exercises all three changes simultaneously. Do not skip this phase.
**Delivers:** Verified correct behavior across all 42 gesture-pair transitions, swipe-to-static scenarios, and combined flows; updated test suites for `test_debounce.py`, `test_swipe.py`, `test_integration_mutual_exclusion.py`
**Avoids:** The "looks done but isn't" failure mode; compound interaction bugs between direct transition logic and swipe mutual exclusion
**Key tasks:** Run full "looks done but isn't" checklist; test all 42 gesture pairs; specifically test confusable pairs (PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP); test compound A -> B -> swipe scenario; verify no regressions in false-fire prevention; measure total perceived latency (target < 500ms for gesture-to-gesture)

### Phase E: Default Tuning

**Rationale:** Must follow Phase D because the state machine changes alter what "good defaults" look like. Tuning before the structural change would require re-tuning afterward. This phase is empirical — results cannot be fully determined from code analysis alone.
**Delivers:** Updated code defaults matching real-world proven values; new users get good out-of-box experience without needing to edit config.yaml
**Addresses:** "Tuned timing defaults" (P1), smoother/delay coupling documentation (Pitfall 4), activation delay floor for transitions (Pitfall 10)
**Key tasks:** Update defaults: `activation_delay` 0.4s -> 0.15s, `cooldown_duration` 0.8s -> 0.3s, `smoothing_window` 3 -> 1, `settling_duration` ~333ms -> ~133ms, `swipe.cooldown` 0.5s -> 0.3s, `swipe.min_velocity` 0.4 -> 0.15, `swipe.min_displacement` 0.08 -> 0.03; test with both `window=1` (current user config) and `window=3` (default)

### Phase Ordering Rationale

- **A and B are independent**: Can be done in either order or in parallel; each is isolated to a single component with no shared interfaces
- **A before C**: Config schema cannot be finalized until the debouncer's new parameter names (`_fired_gesture`) are established
- **B before C**: Settling parameter wiring depends on Phase B choosing between frame-count vs. time-based settling
- **D before E**: Tuning is empirical; requires the state machines to be in their final structural form before measuring what "good" looks like
- **Pitfall 3 drives B's internal ordering**: The missing reset bug must be fixed before reducing settling frames — this is a hard prerequisite within Phase B

### Research Flags

Phases with well-documented patterns (skip research-phase — implementation is fully specified):
- **Phase A**: Exact code structure documented in all four research files; TDD test cases enumerated (7 specific scenarios); ~15 lines of change in a known file
- **Phase C**: Additive config schema changes following established patterns already present in the codebase; no novel patterns
- **Phase E**: Parameter values fully specified from real-world `config.yaml` analysis with rationale for each

Phases that may benefit from additional investigation during execution:
- **Phase B**: The velocity gate threshold (`min_velocity * 0.3`) needs empirical validation on real hardware; settling floor needs testing across the FPS range of target hardware
- **Phase D**: Scope is well-defined but results will determine whether Phase E parameter values need adjustment; confusable gesture pair behavior with `window=1` has not been tested with direct transitions enabled

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies; conclusion based on full codebase read and explicit evaluation of two alternative libraries; both rejected with clear rationale |
| Features | MEDIUM | Direct codebase analysis is HIGH confidence; "seamless transitions" as a named pattern has no single authoritative external source; feature prioritization derives from code analysis and gesture recognition literature rather than established domain authority |
| Architecture | HIGH | Full codebase read; exact line numbers identified for all changes; two latent bugs identified with specific file/line references and reproduction paths |
| Pitfalls | HIGH | All 12 pitfalls derived from direct code analysis with specific file/line references; no speculation; latent bugs verified against actual code paths |

**Overall confidence:** HIGH

### Gaps to Address

- **Velocity gate threshold**: The recommended `min_velocity * 0.3` for the swipe re-arm gate is a reasonable starting point but needs empirical testing on target hardware. If swipe double-fires appear with reduced settling, the threshold needs increasing. Handle during Phase B execution.
- **Confusable gesture pair transitions with window=1**: The 42-pair transition matrix has not been tested with direct transitions enabled. The classifier's priority ordering helps but does not guarantee clean transitions between adjacent gestures (PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP). Handle during Phase D.
- **Two-delay vs. one-delay architecture decision**: PITFALLS.md raises the option of separate `activation_delay` (from None) and `transition_delay` (from different gesture) since the noise characteristics differ between the two cases. FEATURES.md recommends a single delay at 0.15-0.2s as simpler. This architecture decision should be made explicitly in Phase A rather than deferred to tuning.
- **Settling floor vs. FPS range**: Converting settling to time-based addresses the FPS dependency, but the correct minimum floor (estimated at 150ms based on hand deceleration physics) depends on actual user gesture speed. Validate with real-world testing during Phase B.

## Sources

### Primary (HIGH confidence — direct codebase analysis)
- `debounce.py` lines 76-134 — 4-state IDLE/ACTIVATING/FIRED/COOLDOWN machine; `_handle_cooldown` root cause at lines 130-132
- `swipe.py` lines 148-265 — 3-state machine with settling; default `settling_frames=10` at line 61; `settling_frames_remaining` counter at line 219
- `__main__.py` lines 183-309 — main loop integration; swipe-start reset at lines 229-231; missing swipe-end reset identified
- `classifier.py` — 7 gestures, priority-ordered; confusable pairs identified: PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP, OPEN_PALM<->SCOUT
- `config.yaml` — production values: `activation_delay=0.1s`, `cooldown=0.5s`, `smoothing_window=1`
- `test_debounce.py`, `test_integration_mutual_exclusion.py` — 14 existing debounce tests, 5 mutual exclusion tests; no tests for COOLDOWN -> ACTIVATING path

### Secondary (MEDIUM confidence — gesture recognition literature)
- [Gesture Modeling and Recognition Using Finite State Machines (IEEE 840667)](https://ieeexplore.ieee.org/document/840667/) — foundational FSM-based gesture recognition patterns
- [Gestop: Customizable Gesture Control](https://github.com/ofnote/gestop) — confirms mode-switching latency is a known UX concern in gesture systems
- [React Native Gesture Handler: States and Events](https://docs.swmansion.com/react-native-gesture-handler/docs/fundamentals/states-events/) — gesture state machine transition patterns; transitions without required "none" states
- [Apple Gesture Recognizer State Machine](https://developer.apple.com/documentation/uikit/about-the-gesture-recognizer-state-machine) — platform reference for gesture transitions (Possible->Recognized without explicit None states)
- [MediaPipe Gesture Recognizer Guide](https://ai.google.dev/edge/mediapipe/solutions/vision/gesture_recognizer) — tracking-based detection latency characteristics
- [Continuous Hand Gesture Recognition (ScienceDirect)](https://www.sciencedirect.com/science/article/pii/S1077314225001584) — skeleton-based approaches confirmed as standard for start/end point detection

### Tertiary (evaluated and rejected)
- [pytransitions/transitions](https://github.com/pytransitions/transitions) — evaluated as state machine library; rejected: adds ~50ms import overhead and stack trace complexity for two 3-4 state machines
- [python-statemachine](https://pypi.org/project/python-statemachine/) — evaluated as state machine library; rejected: same reasoning; class decorator DSL adds abstraction without reducing complexity for this use case

---
*Research completed: 2026-03-22*
*Ready for roadmap: yes*
