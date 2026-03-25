---
status: complete
phase: 16-action-dispatch-and-fire-modes
source: [16-01-SUMMARY.md, 16-02-SUMMARY.md]
started: 2026-03-25T10:00:00Z
updated: 2026-03-25T10:30:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Tap fire mode presses and releases key once
expected: Configure a gesture with fire_mode: tap (or default). Make the gesture. A single key press+release occurs — one character in a text editor, not a repeating stream.
result: pass

### 2. Hold_key fire mode holds key while gesture sustained
expected: Configure a gesture (e.g., fist) with fire_mode: hold_key. Make the gesture and sustain it. The mapped key should be held down continuously (visible in a text editor as repeating characters from OS key repeat). Change to a different gesture or open hand — the key should release immediately and characters stop.
result: issue
reported: "Holding status is detected, but no continuous firing"
severity: major

### 3. Config backward compatibility (mode: hold)
expected: In config.yaml, use the v1.x syntax `mode: hold` on a gesture instead of `fire_mode: hold_key`. The app should load without errors and the gesture should behave as hold_key (sustained keypress while gesture is active).
result: issue
reported: "same exact case with thumbs_up"
severity: major

### 4. Per-hand action mappings
expected: Configure left_hand and right_hand with different key mappings for the same gesture (e.g., peace → 'x' for right, peace → 'z' for left). Make the peace gesture with each hand separately. Right hand triggers 'x', left hand triggers 'z'.
result: pass

### 5. Stuck key prevention on gesture change
expected: Configure a gesture with fire_mode: hold_key. Make the gesture (key held down). Switch to a different gesture. The held key releases immediately — no stuck keys.
result: pass

### 6. Stuck key prevention on app toggle off
expected: Configure a gesture with fire_mode: hold_key. Make the gesture (key held down). Toggle the app off via system tray. The held key releases immediately — no stuck key remains after app deactivation.
result: skipped

## Summary

total: 6
passed: 3
issues: 2
pending: 0
skipped: 1

## Gaps

- truth: "Hold_key fire mode holds key down continuously while gesture sustained"
  status: failed
  reason: "User reported: Holding status is detected, but no continuous firing"
  severity: major
  test: 2
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
- truth: "Legacy mode: hold syntax produces hold_key behavior (sustained keypress)"
  status: failed
  reason: "User reported: same exact case with thumbs_up"
  severity: major
  test: 3
  root_cause: ""
  artifacts: []
  missing: []
  debug_session: ""
