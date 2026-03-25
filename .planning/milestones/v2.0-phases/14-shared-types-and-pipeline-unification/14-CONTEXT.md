# Phase 14: Shared Types and Pipeline Unification - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Both preview and tray modes run through a single unified Pipeline class with shared data types, eliminating ~90% code duplication between `__main__.py` (571 lines) and `tray.py` (515 lines). Preview wrapper targets ~80 lines, tray wrapper ~50 lines. No new features — identical detection behavior to v1.3.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion

All implementation decisions for this phase are at Claude's discretion. The user trusts the builder to make the right calls across all four gray areas:

**Pipeline class boundary:**
- What goes inside the unified Pipeline class vs. what stays in mode wrappers
- Whether Pipeline owns camera/detector lifecycle or just the detection loop body
- Whether Pipeline owns config hot-reload internally or wrappers drive reload

**Shared type design:**
- How FrameResult and other shared types flow between pipeline stages
- Typed dataclass per frame vs. loose dicts
- What fields FrameResult carries
- How signals propagate from debouncer to keystroke dispatch

**Hot-reload ownership:**
- Where config reload logic lives (currently ~80 lines of inline property patching duplicated in both loops)
- Whether Pipeline.reload_config() rebuilds components or patches them
- How the SWIPE_WINDOW edge case on reload is handled

**Tray active/inactive cycle:**
- How tray mode's active/inactive toggle interacts with the unified Pipeline
- Whether Pipeline uses start()/stop(), pause/resume, or same lifecycle as preview
- Currently tray tears down and recreates all components on reactivate — can change

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `_parse_key_mappings()`, `_parse_swipe_key_mappings()`, `_parse_compound_swipe_key_mappings()`: Identical in both files — move to shared location (pipeline or config module)
- `GestureDebouncer`, `GestureSmoother`, `SwipeDetector`, `DistanceFilter`, `GestureClassifier`: All existing pipeline components with `.reset()` methods
- `ConfigWatcher`: Already handles hot-reload mtime polling
- `KeystrokeSender`: Has `.send()` and `.release_all()` for keystroke lifecycle

### Established Patterns
- Pipeline order: camera → detector → distance_filter → classifier → smoother → debouncer → keystroke sender (+ parallel swipe path)
- Hot-reload: ConfigWatcher polls mtime, reloads full config, updates component properties inline
- Hand switch: reset all pipeline components (smoother, debouncer, swipe_detector) + release held keys
- Distance out-of-range: same reset pattern as hand switch
- Swipe exit: reset + suppress pre-swipe gesture re-fire via debouncer state injection

### Integration Points
- `__main__.py:run_preview_mode()` (~440 lines): detection loop + preview rendering + FPS + debug logging
- `tray.py:TrayApp._detection_loop()` (~350 lines): detection loop + active/shutdown event checks
- Both share ~300 lines of character-for-character identical detection logic
- Preview adds: FPS calc, debug per-frame logging, landmark drawing, cv2.waitKey (~40 lines)
- Tray adds: threading.Event checks, component teardown/recreation on toggle (~50 lines)

### Duplication Inventory
- 3 identical helper functions (key mapping parsers)
- Component initialization (~40 lines each)
- Hand switch handling (~20 lines each)
- Distance gating (~15 lines each)
- Static gesture classification + swipe detection (~40 lines each)
- Debounce + fire dispatch (~50 lines each)
- Compound swipe suppression + standalone swipe (~15 lines each)
- Hold repeat (~5 lines each)
- Config hot-reload (~70 lines each)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 14-shared-types-and-pipeline-unification*
*Context gathered: 2026-03-24*
