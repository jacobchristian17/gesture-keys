# Phase 13: Preview and Polish - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Add a hand indicator to the preview overlay so users can visually confirm which hand (left or right) is currently active. Switching hands updates the indicator in real time. This phase covers PRV-01 only — no new detection, classification, or config features.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
- Hand indicator placement in the preview window (bottom bar vs frame overlay vs separate element)
- Visual style of the hand indicator (text label, icon, colored dot, etc.)
- How prominent the indicator should be relative to existing gesture label and debounce state
- Visual feedback on hand switch (instant change, flash, color transition, etc.)
- Whether to differentiate left/right with color coding or just text

</decisions>

<specifics>
## Specific Ideas

- User's primary hand is left — left hand is the preferred default
- Keep it simple and functional; this is a developer tool, not a consumer UI

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `preview.py` — `render_preview(frame, gesture_name, fps, debounce_state)` renders a dark gray bottom bar with gesture label (left), debounce state (center), FPS (right). Adding a hand label fits naturally into this bar.
- `draw_hand_landmarks(frame, hand_landmarks)` — draws skeleton on frame. Color could be varied by hand if desired.
- `handedness` variable is already available in both `__main__.py` and `tray.py` detection loops at render time.

### Established Patterns
- Bottom bar layout: left=gesture label, center=debounce state, right=FPS. Hand indicator needs a slot that doesn't conflict.
- Color coding already used: debounce states are color-coded (gray/yellow/orange/green). Same approach could work for hand indicator.
- Preview only runs in `--preview` mode (`__main__.py`), not in tray mode — tray has no preview window.

### Integration Points
- `render_preview()` signature needs `handedness` parameter added
- Call site in `__main__.py` line ~409: `render_preview(frame, gesture_label, fps, debounce_state=debouncer.state.value)` — add handedness arg
- `prev_handedness` variable is already tracked in the main loop and available at render time

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 13-preview-and-polish*
*Context gathered: 2026-03-24*
