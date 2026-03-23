# Phase 9: Swipe/Static Transition Latency - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Reduce swipe-to-static gesture transition latency from ~1.3s to ~300ms after swipe cooldown ends. Fix the missing smoother/debouncer reset on swipe exit (LAT-02), reduce settling frames (LAT-03), and achieve the ~300ms target (LAT-01). Does NOT change default timing values (Phase 10) or static-to-static transitions (Phase 8, complete).

</domain>

<decisions>
## Implementation Decisions

### Reset behavior on swipe exit (LAT-02)
- When `is_swiping` transitions from true to false, explicitly reset both smoother and debouncer so stale swipe-motion frames don't pollute static gesture recognition
- The current code resets smoother+debouncer on swipe ENTRY (`if swiping and not was_swiping`) but NOT on swipe EXIT -- this is the LAT-02 bug
- Fix: add symmetric reset on exit (`if was_swiping and not swiping`) in both `__main__.py` and `tray.py` detection loops
- This MUST land before settling frame reduction (LAT-03) to avoid false static fires from stale smoother state

### Settling frame target (LAT-03)
- Reduce settling_frames from 10 to 3 (aggressive end of 3-5 range)
- With the smoother/debouncer reset fix (LAT-02), stale state is flushed on swipe exit, so 3 frames is sufficient to let residual hand motion dampen
- 3 frames at ~30fps = ~100ms settling, down from ~330ms
- If false fires occur in practice, user can increase via config (settling_frames is already configurable)

### Latency budget (LAT-01)
- Target breakdown after fixes: settling (3 frames = ~100ms) + smoother refill (3 frames = ~100ms) + activation_delay (0.15s default in Phase 10, currently 0.4s) = ~350ms with current defaults, ~250ms after Phase 10 tuning
- Acceptable: with current 0.4s activation_delay, total will be ~600ms (down from ~1.3s) -- Phase 10's default tuning to ~0.15s activation_delay will bring it to ~300ms target
- Phase 9 focuses on what it can control: reset bug fix + settling frame reduction

### Hot-reload reset scope
- Fix the latent bug: config reload should reset smoother in addition to debouncer
- Also reset swipe settling state (`_settling_frames_remaining = 0`) on config reload to prevent stale settling blocking
- Small fix, directly related to LAT-02's reset theme -- include in this phase rather than deferring

### Claude's Discretion
- Exact placement and ordering of reset calls in the detection loops
- Whether to add a `swipe_exiting` log message for debugging transitions
- Test approach for verifying the latency improvement

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SwipeDetector.is_swiping` (swipe.py:129-134): Already tracks ARMED/COOLDOWN state -- used for mutual exclusion
- `GestureSmoother.reset()` (smoother.py:49-51): Clears buffer -- exactly what's needed on swipe exit
- `GestureDebouncer.reset()` (debounce.py:60-66): Resets to IDLE -- needed on swipe exit
- `SwipeDetector._settling_frames_remaining` (swipe.py:76): Post-cooldown settling counter

### Established Patterns
- Swipe entry reset: `__main__.py:229-231` -- `if swiping and not was_swiping: smoother.reset(); debouncer.reset()` -- mirror this for exit
- Both `__main__.py` and `tray.py` have duplicated detection loops -- must modify both identically
- Config hot-reload in both loops: `debouncer.reset()` called but `smoother.reset()` missing

### Integration Points
- `__main__.py:228-232`: swipe/static mutual exclusion block -- add exit reset here
- `tray.py:228-232`: identical block in tray detection loop
- `__main__.py:262-264` and `tray.py:255-257`: config reload sections -- add smoother reset

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- user deferred all decisions to Claude's discretion ("Go YOLO").

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 09-swipe-static-transition-latency*
*Context gathered: 2026-03-22*
