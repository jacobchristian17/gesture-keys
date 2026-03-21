---
status: diagnosed
phase: 06-integration-and-mutual-exclusion
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md]
started: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:10:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Swipe Suppresses Static Gestures
expected: While performing a swipe gesture (moving hand laterally), no static gesture keystrokes should fire. The swipe motion should be the only thing detected — no accidental keypresses from static gestures during the swipe.
result: issue
reported: "failed, static not suppresed within swipe cooldowns"
severity: major

### 2. Static Gestures Resume After Swipe
expected: After completing a swipe gesture and the cooldown period expires, static gesture detection resumes normally. Holding a static gesture pose should trigger its mapped keystroke as before.
result: pass

### 3. Swipe-Then-Static Transition Is Smooth
expected: When transitioning from a swipe to a static gesture, there should be no spurious keystrokes or delayed recognition. The static gesture should be picked up cleanly once the swipe cooldown ends — no ghost inputs.
result: issue
reported: "no transition made from swipe to static"
severity: major

### 4. Distance Gating Resets Swipe State
expected: Move hand out of detection range (too close or too far), then bring it back. Swipe detection should start fresh — no stuck ARMED state from the previous interaction. Static gestures should also work normally after returning to range.
result: pass

## Summary

total: 4
passed: 2
issues: 2
pending: 0
skipped: 0

## Gaps

- truth: "Swipe motion suppresses static gesture detection during ARMED and COOLDOWN states"
  status: failed
  reason: "User reported: failed, static not suppresed within swipe cooldowns"
  severity: major
  test: 1
  root_cause: "GestureSmoother majority-vote window leaks stale static gestures for (window_size-1) frames after is_swiping becomes True. GestureDebouncer.update() runs unconditionally with no is_swiping guard — if debouncer was in ACTIVATING state, leaked frames can trigger keystroke. Neither smoother.reset() nor debouncer.reset() is called on swipe transition, only during distance-gating."
  artifacts:
    - path: "gesture_keys/__main__.py"
      issue: "debouncer.update() not gated by is_swiping; no smoother/debouncer reset on swipe start"
    - path: "gesture_keys/tray.py"
      issue: "same duplicated detection loop with same missing guards"
    - path: "gesture_keys/smoother.py"
      issue: "majority-vote window leaks stale gestures when fed None"
  missing:
    - "Call smoother.reset() and debouncer.reset() when is_swiping transitions False→True"
    - "Gate debouncer.update() behind is_swiping check or reset it on swipe start"
    - "Apply fix in both __main__.py and tray.py"
  debug_session: ".planning/debug/swipe-suppression-not-working.md"

- truth: "After swipe cooldown expires, static gesture detection resumes cleanly without ghost inputs"
  status: failed
  reason: "User reported: no transition made from swipe to static"
  severity: major
  test: 3
  root_cause: "After COOLDOWN expires and state returns to IDLE, hand settling/repositioning movement exceeds user's low thresholds (min_velocity=0.15, min_displacement=0.03) within 3-5 frames, causing immediate re-arming (IDLE→ARMED→COOLDOWN cycle). The single-frame skip guard on COOLDOWN→IDLE is insufficient — buffer needs only 3 frames to enable velocity checks again, creating permanent suppression loop."
  artifacts:
    - path: "gesture_keys/swipe.py"
      issue: "COOLDOWN→IDLE transition has only single-frame guard; IDLE threshold checks have no post-cooldown settling period"
  missing:
    - "Add post-cooldown settling guard: require N frames of low velocity before allowing IDLE→ARMED after cooldown"
    - "Or require hand to be stationary (below min_displacement) for several frames before re-enabling swipe arming"
  debug_session: ".planning/debug/swipe-to-static-no-transition.md"
