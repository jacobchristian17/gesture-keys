---
status: diagnosed
trigger: "Static gestures are not suppressed within swipe cooldowns"
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:01:00Z
---

## Current Focus

hypothesis: CONFIRMED - smoother leaks stale gesture values into debouncer during swipe
test: Traced code path through smoother and debouncer during is_swiping=True
expecting: smoother.update(None) still returns non-None gesture for up to (window_size - 1) frames due to majority vote
next_action: Return diagnosis

## Symptoms

expected: Swipe motion suppresses static gesture detection during ARMED and COOLDOWN states. No static gesture keystrokes should fire during a swipe.
actual: Static gestures still fire during swipe cooldowns
errors: None
reproduction: UAT Test 1
started: Discovered during UAT

## Eliminated

## Evidence

- timestamp: 2026-03-22T00:00:30Z
  checked: is_swiping property in SwipeDetector (swipe.py line 118-123)
  found: Returns True when state is ARMED or COOLDOWN -- this is correct
  implication: The is_swiping flag itself works properly

- timestamp: 2026-03-22T00:00:35Z
  checked: Static gesture gating in __main__.py (lines 226-231) and tray.py (lines 227-232)
  found: When swiping=True, classifier.classify() is skipped and smoother.update(None) is called
  implication: Classification is correctly gated, but smoother receives None instead of being reset

- timestamp: 2026-03-22T00:00:40Z
  checked: GestureSmoother.update() behavior with None input (smoother.py lines 24-47)
  found: Majority vote over sliding window. If buffer was [FIST, FIST, FIST] and one None is added, buffer becomes [FIST, FIST, None]. Majority is still FIST (2/3 > 1.5). Returns FIST for up to (window_size - 1) more frames.
  implication: Stale gesture values LEAK THROUGH the smoother for multiple frames after swipe starts

- timestamp: 2026-03-22T00:00:45Z
  checked: Debouncer behavior during swiping (__main__.py lines 240-246, tray.py lines 234-240)
  found: debouncer.update() is called unconditionally with whatever smoother returns. No is_swiping check before debouncer.
  implication: Debouncer receives non-None gestures during early swipe frames and can fire keystroke

- timestamp: 2026-03-22T00:00:50Z
  checked: Whether smoother.reset() or debouncer.reset() are called on swipe start
  found: Both are ONLY called during distance-gating (hand out of range) and config reload. Neither is called when is_swiping transitions to True.
  implication: No mechanism exists to flush stale state when swipe begins

## Resolution

root_cause: When a swipe begins (is_swiping becomes True), the detection loops correctly skip classifier.classify() and feed None to smoother.update(). However, the GestureSmoother uses a majority-vote sliding window, so it continues returning the previous static gesture for up to (window_size - 1) frames until enough Nones accumulate. The GestureDebouncer receives these leaked gesture values unconditionally (no is_swiping guard on debouncer.update()) and can fire a keystroke if the activation delay is met. Neither smoother.reset() nor debouncer.reset() is called when swiping starts -- they are only called during distance-gating transitions.
fix:
verification:
files_changed: []
