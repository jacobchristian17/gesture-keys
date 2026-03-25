# Project Retrospective

*A living document updated after each milestone. Lessons feed forward into future planning.*

## Milestone: v1.0 — MVP

**Shipped:** 2026-03-21
**Phases:** 3 | **Plans:** 7

### What Was Built
- 6-gesture hand classifier from MediaPipe landmarks with configurable thresholds
- Full detection pipeline: camera → landmarks → classifier → smoother → debouncer → keystroke sender
- Preview window with landmark skeleton overlay, gesture label, and FPS counter
- System tray app with active toggle, config editing, and clean shutdown
- Config hot-reload without restart

### What Worked
- Bottom-up pipeline architecture (detection → keystroke → tray) let each phase be independently testable
- TDD approach caught issues early — tests written before implementation
- Human verification checkpoints caught real issues (tray icon invisible with RGB on Windows 11)
- Priority-ordered gesture classification eliminated ambiguity without complex logic

### What Was Inefficient
- Tray icon RGB vs RGBA issue required debugging cycle during checkpoint — could have been caught by research noting Windows tray icon requirements
- `_parse_key_mappings` was duplicated between `__main__.py` and `tray.py` — should be extracted to a shared utility
- Integration tests needed updating when `main()` was rewired to tray mode — test coupling to entry point behavior

### Patterns Established
- RGBA with transparent background for Windows system tray icons
- `icon.visible = True` + startup notification for reliable pystray display
- Lazy imports for optional heavy dependencies (pystray/Pillow in tray mode only)
- threading.Event for clean shutdown signaling between threads

### Key Lessons
1. Windows tray icons require RGBA format — RGB renders invisible on some configurations
2. pystray setup callback should set `icon.visible = True` explicitly for reliable display
3. Human verification checkpoints are essential for platform-specific UI features

### Cost Observations
- Model mix: primarily opus with sonnet for verification
- Entire milestone completed in a single day
- Notable: 7 plans across 3 phases executed efficiently with wave-based parallelization

---

## Milestone: v1.1 — Distance Threshold and Swiping Gestures

**Shipped:** 2026-03-21
**Phases:** 4 | **Plans:** 8

### What Was Built
- Distance-based gesture gating via palm span (wrist-to-MCP) with configurable threshold
- 4-direction swipe detection using wrist velocity tracking in rolling buffer
- Mutual exclusion between swipe and static gesture detection
- Preview overlays for distance value and swipe direction

### What Worked
- Existing pipeline architecture extended cleanly for new detection modes
- Settling frames concept (10 frames) prevented false re-arming after swipe cooldown
- Swipe detection as independent subsystem (SwipeDetector class) kept concerns separated

### What Was Inefficient
- Phase 7 (Preview Overlays and Calibration) had no formal plans — was handled ad-hoc
- Settling frames value (10) was conservative — later required reduction in v1.2

### Patterns Established
- SwipeDetector as stateful class with its own cooldown independent of debouncer
- Rolling buffer approach for velocity-based gesture detection
- `is_swiping` property for mutual exclusion gating

### Key Lessons
1. Conservative initial values (settling frames) are safer to ship and tune later
2. Mutual exclusion between detection modes needs explicit gating — implicit separation leads to race conditions

### Cost Observations
- Entire milestone completed same day as v1.0
- 8 plans across 4 phases, fast execution (~2min/plan average)

---

## Milestone: v1.2 — Continuous and Seamless Commands

**Shipped:** 2026-03-24
**Phases:** 3 | **Plans:** 8

### What Was Built
- Direct gesture-to-gesture transitions (COOLDOWN→ACTIVATING for different gesture)
- Color-coded debounce state indicator in preview window
- Swipe-to-static transition latency reduced from ~1.3s to ~300ms
- Tuned real-world defaults (activation_delay 0.15s, cooldown 0.3s, window 2, settling 3)
- Per-gesture cooldown overrides in config.yaml
- Static-first priority gate preventing swipe from preempting static gestures

### What Worked
- Research phase identified the keystone change (~15 LOC in debounce.py) before planning
- Fixing LAT-02 (swipe-exit reset) before LAT-03 (settling reduction) prevented cascading bugs
- UAT testing after Phase 10 caught the swipe-preempts-static issue, leading to gap closure plans 10-03 and 10-04
- Latency budget test (700ms end-to-end) provided concrete verification of improvement

### What Was Inefficient
- Phase 10 grew from 2 to 4 plans due to UAT-discovered gaps — initial planning underestimated swipe/static interaction complexity
- ROADMAP.md progress table had stale data for phases 8-9 (showed "Planning" despite being complete)
- STATE.md accumulated multiple stale YAML frontmatter blocks instead of being cleaned up between sessions
- Duplicated loop code in __main__.py and tray.py meant every change had to be applied twice

### Patterns Established
- `is_activating` property on debouncer for cross-subsystem priority gating
- `suppressed` parameter pattern for clean subsystem gating without side effects
- UAT → gap closure plan → execute cycle for catching interaction bugs
- Latency budget tests with concrete timing thresholds for performance requirements

### Key Lessons
1. Interaction bugs between subsystems (swipe vs static) are the hardest to predict — UAT testing is essential before milestone completion
2. Fixing prerequisite bugs (exit resets) before optimization (settling reduction) avoids cascading failures
3. Research identifying the minimal keystone change keeps implementation focused
4. When two detection modes interact, explicit priority ordering is more robust than timing-based separation
5. Duplicated loop code (__main__.py + tray.py) is a maintenance burden — refactoring should be prioritized

### Cost Observations
- Model mix: primarily opus for planning/execution
- 108 commits across 3 days
- Notable: Phase 10 gap closure (plans 03-04) added ~40% more work but fixed real user-facing bugs

---

## Milestone: v1.3 — Left Hand Support

**Shipped:** 2026-03-24
**Phases:** 3 | **Plans:** 5

### What Was Built
- Both-hand detection with active hand selection (sticky, preferred, transition jitter prevention)
- Left-hand classification verified hand-agnostic — zero classifier changes needed
- Deep-merge config resolution for per-hand gesture and swipe mappings via left_gestures YAML section
- Hand-aware mapping pre-parsed at startup with instant hand-switch swap and hot-reload
- Preview overlay hand indicator (L/R) with distinct per-hand colors

### What Worked
- Classifier hand-agnosticism was a major win — MediaPipe normalizes hand geometry, so abs()/y-axis-only checks work for both hands without code changes
- Pre-parsing both hand mapping sets at startup gives instant swap on hand switch (no per-frame resolution overhead)
- Transition frame returning ([], None) during hand switches prevents jitter cleanly
- TDD continued to catch issues early — 4 new test files, all passing before integration

### What Was Inefficient
- Duplicated loop code in __main__.py and tray.py remains — hand-switch logic, mapping pre-parse, and hot-reload all had to be applied twice (carried forward from v1.2 lesson)
- 3 pre-existing config test failures persisted throughout all 5 plans due to user-modified config.yaml — should be addressed

### Patterns Established
- `detect()` returns (landmarks, handedness) tuple — all downstream consumers unpack this
- `resolve_hand_*()` functions for per-hand mapping lookup at config layer
- Dual-mapping pre-parse at startup: right_key_mappings + left_key_mappings swapped by handedness
- Preview overlay optional params: add kwarg with None default, render only when not None

### Key Lessons
1. Testing hand-agnosticism of existing code before writing new code saves significant effort
2. Sticky active hand selection (don't switch during two-hand frames) prevents jitter better than priority-based selection
3. Deep-merge for gesture overrides + full replacement for swipe directions matches user mental model of config
4. Loop code duplication (__main__.py + tray.py) is now a confirmed pattern — refactor is overdue for next milestone

### Cost Observations
- Model mix: opus for execution, sonnet for verification
- 5 plans across 3 days, ~3-5 min per plan execution
- Notable: Smallest milestone (5 plans) but high impact — doubled the supported input surface

---

## Milestone: v2.0 — Structured Gesture Architecture

**Shipped:** 2026-03-26
**Phases:** 4 | **Plans:** 9

### What Was Built
- Unified Pipeline class with FrameResult dataclass — preview wrapper ~70 lines, tray wrapper ~29 lines (down from ~570 and ~515)
- Hierarchical GestureOrchestrator FSM with outer lifecycle + inner temporal state dispatch
- ActionResolver (pure lookup) + ActionDispatcher (stateful key lifecycle) with tap and hold_key fire modes
- App-controlled tap-repeat at 33Hz fixing Windows SendInput non-repeat behavior
- Activation gate with configurable arm/disarm, bypass mode (default off), gate expiry safety, hot-reload
- 428 tests passing with full TDD red-green coverage across all new subsystems

### What Worked
- Clean architectural break from v1.x — full rewrite enabled rethinking instead of patching
- TDD red-green discipline caught regressions immediately (e.g., MagicMock auto-attributes returning truthy for activation_gate_enabled)
- Resolver-Dispatcher separation made action dispatch independently testable with clear state ownership
- gate=None as bypass mode gives zero overhead when feature is disabled (null-object pattern)
- Wave-based execution with parallel agents kept phase completion fast despite 9 plans
- UAT verified all 6 human-testable activation gate behaviors passed on first try

### What Was Inefficient
- Phase 16 required gap closure (plan 16-03) when Windows SendInput non-repeat behavior wasn't anticipated during planning — research should have flagged OS-level keyboard simulation differences
- 4 pre-existing test failures from v1.x persisted through all v2.0 phases (stale test assertions for removed debouncer fields) — finally fixed in commit 77bf995 after all plans complete
- Plan checkbox state in ROADMAP.md was inconsistent (some checked, some not) for completed plans — cosmetic but caused confusion during verification

### Patterns Established
- Pipeline.process_frame() as zero-arg entry point — all mode wrappers just loop this
- Hierarchical FSM: outer dispatch to handler methods, inner sub-dispatch within _handle_active()
- Resolver-Dispatcher pattern: pure lookup separated from stateful dispatch with single held-action field
- App-controlled tap-repeat for platforms where OS key-hold doesn't auto-repeat programmatic input
- gate=None as null-object bypass — no conditional checks on hot path

### Key Lessons
1. Pipeline unification resolved the persistent v1.x pain point of duplicated loop code — should have been done earlier
2. Windows SendInput keyboard simulation differs from physical keyboard behavior — research should explicitly test OS-level APIs before planning fire modes
3. Pre-existing test failures should be fixed at milestone boundary, not carried forward — they obscure new test regressions
4. TDD with MagicMock requires explicit attribute setup for boolean fields — auto-attributes return truthy MagicMock objects, not False
5. Activation gate UAT passing on first try validates that thorough automated testing (33 tests) makes human verification a confirmation step, not a discovery step

### Cost Observations
- Model mix: opus for execution, sonnet for verification
- 4 phases across 5 days, ~3-6 min per plan execution
- Notable: Major architectural rewrite (9 plans, +8540/-2217 lines) completed efficiently — clean break from v1.x avoided compatibility shim overhead

---

## Cross-Milestone Trends

### Process Evolution

| Milestone | Phases | Plans | Key Change |
|-----------|--------|-------|------------|
| v1.0 | 3 | 7 | Initial project — established TDD + human verification pattern |
| v1.1 | 4 | 8 | Extended pipeline architecture — added SwipeDetector subsystem |
| v1.2 | 3 | 8 | UAT gap closure pattern — plans grew from 2→4 in Phase 10 |
| v1.3 | 3 | 5 | Smallest milestone — hand-agnostic classifier, dual-mapping pre-parse |
| v2.0 | 4 | 9 | Full rewrite — unified pipeline, hierarchical FSM, action dispatch, activation gate |

### Top Lessons (Verified Across Milestones)

1. Human verification / UAT catches issues automated tests miss — confirmed in v1.0 (tray icon), v1.2 (swipe priority), v1.3 (preview indicator)
2. Bottom-up architecture with independently testable phases reduces integration risk
3. Research before planning identifies minimal keystone changes — keeps implementation focused (v1.2)
4. Fix prerequisites before optimizations to avoid cascading failures (v1.1 settling frames → v1.2 reduction)
5. Test existing code assumptions before writing new code — v1.3 classifier was already hand-agnostic, saving significant effort
6. Duplicated loop code (__main__.py + tray.py) is a persistent maintenance burden — flagged in v1.2, confirmed in v1.3, **resolved in v2.0** via unified Pipeline class
7. Full architectural rewrites (v2.0) are more efficient than incremental patching when the fundamental abstraction is wrong — clean break avoids compatibility shim overhead
8. Platform-specific API behavior (Windows SendInput) must be researched before planning — OS-level differences cause gap closure cycles (v2.0 phase 16)
