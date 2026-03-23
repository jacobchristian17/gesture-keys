# Phase 11: Left Hand Detection and Classification - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Detect left hand via MediaPipe and classify all 6 static gestures + 4 swipe directions with right-hand parity. One hand active at a time. This phase covers detection, classification, and hand-switching logic. Config mappings and preview updates are separate phases.

</domain>

<decisions>
## Implementation Decisions

### Hand Switch Behavior
- Instant switch when hands change — no transition delay
- Hold gestures release immediately on hand switch
- Stick with current active hand while both are visible — only switch when current hand disappears
- Debounce state handling on switch: Claude's discretion (reset vs carry over, whichever avoids false fires best)

### Hand Priority
- Preferred hand defaults to **left** — configurable via `preferred_hand: left` in config.yaml
- When both hands appear simultaneously at startup, preferred hand is selected
- When active hand disappears while other hand is still visible: **wait for clean single-hand detection** before switching (don't immediately jump to the other hand)

### Gesture Verification
- All 6 static gestures must classify with **exact parity** on left hand — not "close enough"
- All 4 swipe directions must work identically (absolute directions, no mirroring)
- Expand unit test suite with left-hand landmark fixtures to verify classification parity
- Approach to thumb/pinch geometry adjustment: Claude's discretion (test first vs proactive mirroring)

### Claude's Discretion
- Debounce state reset vs carry-over on hand switch — pick whichever avoids false fires
- Whether to proactively mirror classifier geometry for left hand or test-first and fix what breaks
- Internal implementation of hand tracking state (new class vs extending HandDetector)

</decisions>

<specifics>
## Specific Ideas

- The user's primary use case is left-hand gestures — left hand is the preferred default, not right
- "Wait for clean" on hand disappearance means the app should not jitter between hands during transitions

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `HandDetector` (detector.py) — already uses `num_hands=2`, just filters to "Right" at line 149. Widening the filter is the core change.
- `GestureClassifier` (classifier.py) — uses `abs()` for thumb x-distance and y-position for fingers. Likely hand-agnostic already, but thumb logic at line 130 needs verification with left-hand landmarks.
- `SwipeDetector` (swipe.py) — tracks wrist position deltas. Should be hand-agnostic since it uses landmark positions directly.
- Existing test fixtures in `tests/conftest.py` — can be mirrored to create left-hand variants.

### Established Patterns
- Pipeline: camera → detector → classifier → smoother → debouncer → keystroke sender
- All components downstream of detector are hand-unaware — they just take landmarks
- State resets on context changes (swipe exit, distance out-of-range) use `smoother.reset()` + `debouncer.reset()` — same pattern applies to hand switches

### Integration Points
- `HandDetector.detect()` return value needs to include handedness info (currently returns just landmarks list)
- Main loop in `__main__.py` and `tray.py` both call `detector.detect()` — both need updating
- Config loading (`load_config`) needs `preferred_hand` field in `AppConfig`

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 11-left-hand-detection-and-classification*
*Context gathered: 2026-03-24*
