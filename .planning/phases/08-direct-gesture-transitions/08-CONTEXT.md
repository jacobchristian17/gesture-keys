# Phase 8: Direct Gesture Transitions - Context

**Gathered:** 2026-03-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can switch between static gestures fluidly -- each new gesture fires immediately without dropping the hand to neutral first. Covers TRANS-01 (direct transition firing), TRANS-02 (no re-fire on sustained hold), and TRANS-03 (debounce state preview). Does NOT change timing defaults (Phase 10) or swipe/static transition latency (Phase 9).

</domain>

<decisions>
## Implementation Decisions

### Transition firing rules
- Cooldown is interruptible by a DIFFERENT gesture: when a new gesture appears during COOLDOWN, immediately transition to ACTIVATING for that gesture (COOLDOWN->ACTIVATING)
- Activation timer runs concurrently with remaining cooldown -- no need to wait for cooldown to finish before starting the new gesture's activation delay
- Same gesture held through cooldown stays blocked -- must release to None before same gesture can re-arm (preserves TRANS-02, matches current behavior)
- Keep current 0.4s activation delay -- defer default tuning to Phase 10

### Transitional pose filtering
- Rely on existing activation delay (0.4s) + smoother majority-vote (window=3) as primary protection against transitional poses firing spuriously
- No special transition logic, smoother reset, or lockout window needed -- transitional poses last ~100-200ms, well under the 0.4s activation threshold
- When activating gesture changes (e.g., POINTING->PEACE during ACTIVATING), reset activation timer fully -- new gesture must be held for full activation_delay from scratch (already the current debouncer behavior at debounce.py lines 105-108)
- No special handling for confusable gesture pairs (PEACE<->POINTING, FIST<->THUMBS_UP) -- trust priority-ordered classifier + smoother + activation delay

### Claude's Discretion
- Debounce state preview (TRANS-03): placement, styling, color-coding, and format of IDLE/ACTIVATING/COOLDOWN indicator in preview overlay
- Internal state tracking for the new COOLDOWN->ACTIVATING transition (e.g., whether to track the fired gesture in cooldown for same-gesture blocking)
- Any additional logging for transition events

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `debounce.py:GestureDebouncer`: Core change target -- `_handle_cooldown` (line 127-133) needs modification to detect different gesture and transition to ACTIVATING
- `debounce.py:DebounceState`: Enum already has all needed states (IDLE, ACTIVATING, FIRED, COOLDOWN)
- `smoother.py:GestureSmoother`: Majority-vote buffer unchanged -- provides transitional pose filtering as-is
- `preview.py`: Existing overlay rendering -- add debounce state indicator

### Established Patterns
- Debouncer state machine: IDLE -> ACTIVATING -> FIRED -> COOLDOWN -> IDLE (adding COOLDOWN -> ACTIVATING path for different gesture)
- Pipeline: camera -> detector -> distance_filter -> classifier -> smoother -> debouncer -> keystroke sender
- Both `__main__.py` and `tray.py` have duplicated detection loops -- must modify both identically
- Config hot-reload resets debouncer (debouncer.reset()) but not smoother -- existing pattern

### Integration Points
- `debounce.py:_handle_cooldown`: Must now track the fired gesture to distinguish same vs different gesture during cooldown
- `preview.py`: Needs access to debouncer state for overlay display
- Both `__main__.py:run_preview_mode()` and `tray.py:TrayApp._detection_loop()` pass debounce state to preview

</code_context>

<specifics>
## Specific Ideas

No specific requirements -- open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None -- discussion stayed within phase scope

</deferred>

---

*Phase: 08-direct-gesture-transitions*
*Context gathered: 2026-03-22*
