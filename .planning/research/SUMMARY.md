# Project Research Summary

**Project:** gesture-keys v2.0 — Structured Gesture Architecture
**Domain:** Real-time webcam gesture-to-keystroke pipeline
**Researched:** 2026-03-24
**Confidence:** HIGH

## Executive Summary

gesture-keys v2.0 is a structured architectural rewrite of an existing, working gesture-to-keystroke system. The current v1.3 codebase (7,549 LOC) has accumulated organically: a 570-line `__main__.py` and 515-line `tray.py` with nearly-identical detection loops, a 338-line `debounce.py` monolith, and 20+ bare state variables scattered across the main loop. The rewrite goal is to decompose this into a clean pipeline — GestureOrchestrator, ActionResolver, FireModeExecutor, Pipeline — with activation gating and a gesture hierarchy (static base + hold/swipe temporal modifiers). No new dependencies are needed; the entire architecture is implementable with the existing stack plus Python stdlib enums, NamedTuples, and dataclasses.

The recommended approach is an incremental refactor — not a from-scratch rewrite. The critical first move is building a behavior inventory and regression test suite from the existing code, then extracting a unified `Pipeline` class that both preview and tray modes share, eliminating the duplication risk before adding any new features. Once a single pipeline exists, new components (GestureOrchestrator replacing GestureDebouncer, ActionResolver extracting scattered dispatch logic, FireModeExecutor encapsulating hold state) can be introduced one layer at a time with the system remaining functional and testable after each step. The feature hierarchy — static gesture as base, hold and swipe as temporal modifiers, tap and hold_key as fire modes — is well-understood and maps cleanly to a 6-state orchestrator FSM that subsumes the current debouncer and main-loop coordination code.

The dominant risks are: (1) stuck keys from incomplete hold-key lifecycle management, which must be addressed in the very first phase that implements FireModeExecutor; (2) behavioral regressions from dropping the ~10 subtle edge-case behaviors accumulated across v1.0-v1.3, which requires a behavior inventory and regression test suite before any refactoring begins; and (3) the rewrite killing the active feedback loop if the system becomes non-functional for extended periods. All three risks are mitigated by the incremental approach and a hard feature-parity checkpoint before any new user-facing behavior is introduced.

## Key Findings

### Recommended Stack

No new dependencies. The v2.0 architecture is a clean decomposition of existing code, not an expansion of the tech stack. All components use Python stdlib: `enum.Enum` for state machines (already the established pattern in debounce.py and classifier.py), `typing.NamedTuple` for typed signals between components (already used for `DebounceSignal`), `dataclasses.dataclass` for config objects (already used for `AppConfig`), and `time.perf_counter` for timing (already used throughout). State machine libraries were evaluated and rejected — the new machines each have 2-4 states, and library DSL overhead exceeds the cost of the boilerplate they would replace. The existing requirements.txt is unchanged.

**Core technologies:**
- mediapipe >=0.10.33: hand landmark detection — unchanged, detector.py untouched
- opencv-python >=4.8.0: camera capture and preview — unchanged
- pynput >=1.7.6: keystroke simulation — unchanged; `send()`, `press_and_hold()`, `release_held()` already fully implemented
- PyYAML >=6.0: config loading and hot-reload — additive schema changes only (new `activation` section)
- pytest >=8.0: unit testing — each new component gets isolated tests with deterministic timestamps

### Expected Features

**Must have (v2.0 core — build in dependency order):**
- Config schema for structured gestures — define first; drives all downstream components; new `activation` section, temporal modifiers nested under gesture keys
- Action dispatch resolver — `(gesture, temporal_state) -> (key, fire_mode)` lookup table extracted from scattered main-loop if/elif chains
- Fire mode executor — thin wrapper over existing KeystrokeSender; dispatches tap (press+release) vs hold_key (sustained keypress with lifecycle tracking)
- Activation gate integration — consumes activation gesture, arms/disarms system; default bypass (disabled) to preserve v1.x behavior
- Hold temporal state — gesture held past configurable threshold changes action; emits hold-start/hold-end signals; highest-risk feature due to lifecycle edge cases
- Swiping temporal state — swipe as modifier on static gesture, replacing current COMPOUND_FIRE/SWIPE_WINDOW debounce states
- GestureOrchestrator — unified state machine replacing GestureDebouncer and ~100 lines of main-loop coordination
- Pipeline class — single shared class eliminating duplication between preview and tray mode detection loops

**Should have (v2.x — after core is validated):**
- Activation bypass for specific gestures — allowlist of gestures that skip the gate
- Activation gate visual feedback — preview overlay armed/disarmed indicator
- Hold-to-hold temporal chaining — fluid transitions between sustained keys without returning to idle
- Per-action fire mode in config — mixed tap/hold_key on same gesture's temporal variants

**Defer (v3+):**
- Additional rule-based gestures (hang loose, OK sign) — expand if 6 proves limiting
- Gesture macros (sequence of keys from single gesture)
- Left/right hand with different gesture hierarchies

**Anti-features to avoid permanently:**
- Two-hand simultaneous gestures — doubles state space, MediaPipe multi-hand tracking is jittery
- Sequence gestures (A then B) — exponential state space, poor UX recall
- Double-tap temporal modifier — timing penalty on ALL single taps (QMK/ZMK community consensus: worst tap-hold variant)
- Per-application profiles — fragile foreground window detection, config explosion

### Architecture Approach

The v2.0 pipeline separates what was a single tangled main loop into five distinct layers with clean data flow: frame acquisition (CameraCapture, HandDetector, HandSelector) feeds into filtering (DistanceFilter, ActivationGate), then classification (GestureClassifier, GestureSmoother, SwipeDetector), then orchestration (GestureOrchestrator emitting typed OrchestratorSignal), then action resolution (ActionResolver mapping signal to ResolvedAction), then execution (FireModeExecutor calling KeystrokeSender). A Pipeline class owns all components and is the only entity that calls reset() on any component — eliminating the current anti-pattern of the main loop mutating debouncer internals directly (`debouncer._state = DebounceState.COOLDOWN`).

**Major components:**
1. **GestureOrchestrator** — replaces GestureDebouncer (338 lines) and ~100 lines of main-loop coordination; unified 6-state FSM (IDLE, ACTIVATING, SWIPE_WINDOW, FIRED, HOLDING, COOLDOWN) that takes both static gesture and swipe direction as inputs and coordinates them internally
2. **ActionResolver** — pre-parsed lookup table `(OrchestratorSignal) -> ResolvedAction`; consolidates three near-identical `_parse_key_mappings` functions currently duplicated in `__main__.py` and `tray.py`; supports per-hand mapping swap and hot-reload
3. **FireModeExecutor** — encapsulates hold state (currently 6 bare variables in main loop); provides single `release_all()` called from one cleanup path, not scattered across 12+ locations
4. **Pipeline** — wires all components; owns reset cascade logic; exposes `process_frame()`, `reload_config()`, `shutdown()`; reduces preview mode to ~50 lines and tray mode to ~30 lines from ~500 lines each
5. **HandSelector** — extracted from HandDetector + main loop hand-switch boilerplate; exposes `hand_changed` flag for pipeline reset coordination

**New files:** `types.py`, `hand_selector.py`, `orchestrator.py`, `action_resolver.py`, `fire_executor.py`, `pipeline.py`
**Removed:** `debounce.py` (replaced by orchestrator.py)
**Unchanged:** `classifier.py`, `smoother.py`, `swipe.py`, `distance.py`, `keystroke.py`

### Critical Pitfalls

1. **Stuck keys from incomplete hold_key lifecycle** — The new FireModeExecutor must have ONE cleanup path (not scattered across 12+ locations as in v1.3). Every exit event (gate expiry, distance exit, hand switch, app toggle, config reload, process crash) must route through `fire_executor.release_all()`. Add `atexit.register(sender.release_all)` as last resort. Add a watchdog: auto-release after 30 seconds maximum hold. Test all 5 exit paths explicitly.

2. **Behavioral regressions from rewrite** — The current code contains ~10 subtle fixes accumulated across v1.0-v1.3 that are encoded in code but not documented as requirements (swipe-exit reset, pre-swipe gesture suppression, static-first priority gate, distance gate full pipeline reset, hand switch atomic reset, compound swipe suppression timing, unmapped swipe reset, COOLDOWN->ACTIVATING direct transition, hold release delay, sticky active hand). Build a behavior inventory and regression test suite BEFORE touching any code.

3. **Activation gate creating unusable dead zones** — Make the gate optional with bypass as the default (preserving v1.x behavior). Users opt in to gating. Provide clear visual feedback when armed. Allow re-arming by making the activation gesture again to reset the timer.

4. **Rewrite killing the active feedback loop** — The system must remain functional at every step. Incremental refactor with a feature parity checkpoint before any new user-facing behavior is added. Do NOT start with the activation gate. Start with pipeline unification.

5. **"Hold" naming collision** — `mode: hold` in the current config means "sustained keypress fire mode." The v2.0 spec introduces "hold" as a temporal state modifier (gesture held N seconds selects a different action). These are different concepts. Use `hold_key` for fire mode and `hold` (or `long_press`) for temporal state. Clarify before any implementation.

## Implications for Roadmap

Based on research, the dependency graph and pitfall mitigations constrain the build order tightly. The architecture research provides an explicit 6-phase build order that should be followed directly.

### Phase 1: Behavior Inventory and Regression Test Suite

**Rationale:** Prerequisite for all other work. Pitfall 2 (behavioral regressions) gates all subsequent phases. The behavior inventory documents all ~10 subtle edge-case behaviors from v1.0-v1.3. Regression tests must pass against the new code at every phase. Without this, the rewrite has no safety net.

**Delivers:** Documented behavior inventory; integration test suite covering all edge cases; `GestureSequencePlayer` test utility for feeding pre-recorded gesture sequences through the full pipeline.

**Addresses:** Pitfall 2 (behavioral regressions), Pitfall 13 (test suite cannot test real sequences).

**Avoids:** The classic rewrite failure mode where months of subtle fixes are discarded.

### Phase 2: Shared Types and Pipeline Unification

**Rationale:** The 90% code duplication between `__main__.py` and `tray.py` is the structural root of all divergence risk. Every subsequent feature would have to be implemented twice. The Pipeline class must exist before any new components are built. Config schema must be defined before ActionResolver is built (it drives the lookup structure). This phase also defines the shared data types (`HandFrame`, `OrchestratorSignal`, `ResolvedAction`, `FrameResult`) that all downstream components depend on.

**Delivers:** `types.py` with all shared data types; `Pipeline` class as thin wrapper around existing components (no behavioral change); preview and tray modes reduced to thin callers of `Pipeline.process_frame()`; all regression tests passing (feature parity checkpoint).

**Implements:** types.py, pipeline.py (initial), HandSelector extraction.

**Addresses:** Pitfall 5 (duplicated loop divergence), Pitfall 9 (config backwards compatibility — new activation section added with defaults that reproduce v1.x behavior).

### Phase 3: GestureOrchestrator

**Rationale:** The orchestrator is the most complex new component and the architectural centerpiece. Building it after shared types and Pipeline exist allows thorough isolated testing before integration. All existing `test_debounce.py` tests must be ported and pass against the new orchestrator before integration.

**Delivers:** `orchestrator.py` implementing the 6-state unified FSM; swipe coordination absorbed from main loop; all debouncer tests ported and passing; compound gesture integration tests added.

**Implements:** GestureOrchestrator replacing GestureDebouncer.

**Uses:** `enum.Enum`, `typing.NamedTuple`, `time.perf_counter` (all stdlib, existing patterns).

**Addresses:** The core architectural goal — replacing the GestureDebouncer monolith and ad-hoc main-loop coordination.

**Avoids:** Pitfall 4 (state explosion — requires fully specifying the gesture x temporal-state matrix before implementation); Pitfall 14 (hold naming collision — terminology finalized before implementation).

**Research flag:** The full gesture x temporal-state matrix (7 gestures x 6 temporal states = 42 cells) needs explicit specification before implementation, including defined behavior for unmapped cells. The confusable gesture pairs (PEACE<->SCOUT, POINTING<->PEACE, FIST<->THUMBS_UP) need hysteresis design. This phase may benefit from a targeted research-phase pass.

### Phase 4: ActionResolver and FireModeExecutor

**Rationale:** These components depend on the types from Phase 2 and consume signals from Phase 3's orchestrator. They can be built in parallel. ActionResolver consolidates three duplicated key-mapping parse functions. FireModeExecutor is the safety-critical component for stuck key prevention and must be in place before the activation gate (which triggers key release on expiry) is integrated.

**Delivers:** `action_resolver.py` with consolidated mapping lookup and per-hand swap; `fire_executor.py` with single cleanup path, watchdog timer, and `atexit` safety net; all hold-lifecycle exit paths tested (gate expiry, distance exit, hand switch, app toggle, config reload).

**Implements:** ActionResolver, FireModeExecutor.

**Addresses:** Action dispatch resolver, fire mode executor, tap fire mode (existing), hold-key fire mode (existing, now properly encapsulated).

**Avoids:** Pitfall 1 (stuck keys — single cleanup path, watchdog timer); Pitfall 8 (god object — ActionResolver and FireModeExecutor remain separate concerns); Pitfall 12 (OS key repeat mismatch — decide tap-repeat vs physical-hold semantic before implementation).

**Research flag:** The OS key repeat semantic decision (physical `press_and_hold()` triggers OS-level repeat at 250ms delay + 30/sec; app-level rapid `send()` loop gives controlled repeat rate) needs a brief empirical test against target applications (alt+tab, win+ctrl+left) before implementation.

### Phase 5: Activation Gate Integration

**Rationale:** The activation gate is the most disruptive user-facing change. It must come last among the core components because it requires all other components to be stable — it coordinates with FireModeExecutor for hold release on gate expiry and with the Orchestrator for gate-disarm reset. Making it opt-in by default means this phase does not break existing users.

**Delivers:** Activation gate integrated into Pipeline with bypass default; gate check positioned after classification but before orchestrator (receives smoothed gesture); gate expiry releases held keys via FireModeExecutor; configurable duration; re-arming on repeated activation gesture.

**Implements:** ActivationGate integration into Pipeline.

**Addresses:** Activation gate integration, activation gate visual feedback.

**Avoids:** Pitfall 2 (dead zones — bypass default, clear feedback); Pitfall 6 (gate expires during hold — gate expiry triggers `fire_executor.release_all()`); Pitfall 11 (gate check ordering — after classification, before orchestrator).

### Phase 6: Cleanup and v2.x Features

**Rationale:** Once the core pipeline is validated in real usage, remove dead code and add P2 enhancements. Cleanup includes removing `debounce.py`, removing duplicated `_parse_key_mappings` functions, and verifying hot-reload works through `Pipeline.reload_config()`.

**Delivers:** Removal of debounce.py; elimination of duplicated parse functions; v2.x features: activation bypass gestures, hold-to-hold chaining, per-action fire mode config.

**Addresses:** Activation bypass, hold-to-hold chaining, per-action fire mode.

### Phase Ordering Rationale

- **Behavior inventory first** because regressions are invisible without a test suite and the existing tests do not cover integration patterns.
- **Pipeline unification second** because all subsequent work builds on it — implementing a new feature in duplicated loops is double the work with divergence risk.
- **Orchestrator third** because it is the most complex component and must be thoroughly tested in isolation before Pipeline integration.
- **ActionResolver/FireModeExecutor fourth** because they consume orchestrator signals; FireModeExecutor's safety guarantees must be in place before ActivationGate (which triggers key release on expiry) is integrated.
- **Activation gate fifth** because it is the most disruptive user-facing change and requires all other components to be stable.
- **Incremental approach throughout** preserves the working system at every step and prevents the feedback loop from dying (Pitfall 10).

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (GestureOrchestrator):** The full gesture x temporal-state matrix needs explicit specification before implementation. Hysteresis design for confusable gesture pairs during hold-state detection cannot be determined from code analysis alone.
- **Phase 4 (FireModeExecutor):** OS key repeat semantic decision needs empirical validation against actual target applications before implementation.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Behavior Inventory):** Mechanical extraction from existing code — read the code, document behaviors, write tests. No domain research needed.
- **Phase 2 (Pipeline Unification):** Standard extract-and-delegate refactor with well-established patterns. The existing code provides all the implementation detail.
- **Phase 5 (Activation Gate):** Gate already exists as `activation.py`. Integration is additive. The bypass-first default eliminates most UX risk.
- **Phase 6 (Cleanup + v2.x):** Removal of dead code and additive config features. No research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All recommendations based on direct analysis of 7,549 LOC existing codebase. No new dependencies needed — strongest possible basis for a stack decision. State machine libraries evaluated and rejected with clear rationale. |
| Features | HIGH | Feature set derived from existing working system + QMK/ZMK tap-hold patterns + touch gesture system patterns. Anti-features are well-reasoned from domain constraints. Feature dependency graph is fully specified. |
| Architecture | HIGH | Direct analysis of current codebase identifies exact duplication points, exact components to extract, exact state machine to port. Build order is constrained by verified dependencies. Component interfaces are fully specified. |
| Pitfalls | HIGH | All 14 pitfalls identified from direct codebase analysis, not speculation. Stuck-key paths, behavioral edge cases, and naming collisions are concrete findings from reading the code with specific line references. |

**Overall confidence:** HIGH

### Gaps to Address

- **OS key repeat semantic decision:** Physical `press_and_hold()` triggers OS-level repeat (250ms delay + 30/sec); app-level rapid `send()` loop gives controlled repeat rate. Both have tradeoffs depending on the target application. Needs a brief empirical test before FireModeExecutor implementation.
- **Hold timer hysteresis parameters:** The smoother window of 2 frames absorbs at most 1 frame of flicker. For gestures near the PEACE<->SCOUT confusion boundary, the hold timer may be unreachable without additional hysteresis. Exact hysteresis parameters need tuning against real camera data — cannot be determined from code analysis alone.
- **Activation gate timeout defaults:** Default duration (3.0 seconds in activation.py) needs validation against real usage timing. The research recommends 2x typical gesture sequence duration, but actual sequence timing is unknown without measurement.

## Sources

### Primary (HIGH confidence)
- gesture-keys v1.3 codebase direct analysis: `__main__.py` (571 lines), `tray.py` (516 lines), `debounce.py` (338 lines), `swipe.py` (321 lines), `config.py` (321 lines), `classifier.py` (155 lines), `keystroke.py` (152 lines), `detector.py` (202 lines), `activation.py` (67 lines), `smoother.py` (52 lines) — primary basis for all stack, architecture, and pitfall findings
- `test_debounce.py` (14 tests), `test_integration_mutual_exclusion.py` (5 tests), `test_compound_gesture.py`, `test_swipe.py` — behavioral edge cases inventory
- `PROJECT.md` — 15 validated decisions documenting rationale for current edge-case handling

### Secondary (MEDIUM confidence)
- [QMK Firmware Tap-Hold Documentation](https://docs.qmk.fm/tap_hold) — tap/hold decision logic, tapping term, permissive hold, retro tapping
- [ZMK Firmware Hold-Tap Behavior](https://zmk.dev/docs/keymaps/behaviors/hold-tap) — interrupt flavors, mod-tap, positional hold-tap
- [ZSA Tap and Hold Keys Explained](https://blog.zsa.io/tap-hold-explained/) — user-facing explanation of tap-hold mechanics and common frustrations
- [React Native Gesture Handler States](https://docs.swmansion.com/react-native-gesture-handler/docs/fundamentals/states-events/) — gesture state machine patterns for touch systems
- [Material Design Gestures M2](https://m2.material.io/design/interaction/gestures.html) — gesture hierarchy, priority, composition patterns
- [pytransitions/transitions GitHub](https://github.com/pytransitions/transitions) — evaluated for HSM support, rejected for real-time per-frame use case
- [python-statemachine 3.0.0 docs](https://python-statemachine.readthedocs.io/en/latest/) — evaluated for declarative state machine DSL, rejected

### Tertiary (LOW confidence)
- [Top 10 State Machine Frameworks for Python](https://statemachine.events/article/Top_10_State_Machine_Frameworks_for_Python.html) — landscape survey used for confirming library evaluation completeness
- [Finite State Machine Gesture Recognition (Glasgow)](https://www.dcs.gla.ac.uk/~jhw/fsm.html) — FSM approach to gesture modeling
- [Hierarchical State Machines (UPenn)](https://www.cis.upenn.edu/~lee/06cse480/lec-HSM.pdf) — HSM design patterns

---
*Research completed: 2026-03-24*
*Ready for roadmap: yes*
