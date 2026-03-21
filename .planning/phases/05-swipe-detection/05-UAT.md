---
status: complete
phase: 05-swipe-detection
source: [05-01-SUMMARY.md, 05-02-SUMMARY.md]
started: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:05:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Cardinal Swipe Fires Keystroke
expected: Make a clear left, right, up, or down swipe gesture with your hand. The mapped keystroke for that direction fires (check console/log output for "SWIPE" prefix). Each cardinal direction triggers its configured key.
result: issue
reported: "failed, no swiping gestures registered"
severity: blocker

### 2. Diagonal Swipe Rejected
expected: Make a diagonal swipe gesture (e.g., upper-left). No keystroke should fire — the axis ratio filter rejects non-cardinal movement.
result: issue
reported: "failed, no swiping gestures registered"
severity: blocker

### 3. Cooldown Prevents Double-Fire
expected: Make a quick swipe, then immediately swipe again in the same direction. Only the first swipe fires a keystroke; the second is suppressed until the cooldown period elapses.
result: issue
reported: "blocked, no swiping gestures registered"
severity: blocker

### 4. Swipe Config in YAML
expected: Open config.yaml. A "swipe" section exists with fields for enabled, cooldown_ms, velocity_threshold, min_displacement, axis_ratio, and direction-to-key mappings. Missing section means swipe is disabled by default.
result: issue
reported: "no swipe config on config.yaml"
severity: major

### 5. Hot-Reload Swipe Config
expected: While the app is running, edit config.yaml to change a swipe mapping or threshold. The app picks up the change without restart (log shows updated config). New swipe behavior reflects the edit.
result: skipped
reason: user requested skip

### 6. Swipe Works in Tray Mode
expected: Run the app in tray (headless) mode. Swipe gestures still detect and fire keystrokes identically to preview mode.
result: skipped
reason: user requested skip

## Summary

total: 6
passed: 0
issues: 4
pending: 0
skipped: 2

## Gaps

- truth: "Cardinal swipe fires mapped keystroke"
  status: failed
  reason: "User reported: failed, no swiping gestures registered"
  severity: blocker
  test: 1
  artifacts: []
  missing: []

- truth: "Diagonal swipe rejected by axis ratio filter"
  status: failed
  reason: "User reported: failed, no swiping gestures registered"
  severity: blocker
  test: 2
  artifacts: []
  missing: []

- truth: "Cooldown prevents double-fire on rapid swipes"
  status: failed
  reason: "User reported: blocked, no swiping gestures registered"
  severity: blocker
  test: 3
  artifacts: []
  missing: []

- truth: "Swipe config section exists in config.yaml"
  status: failed
  reason: "User reported: no swipe config on config.yaml"
  severity: major
  test: 4
  artifacts: []
  missing: []
