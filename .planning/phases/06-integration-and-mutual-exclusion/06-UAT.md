---
status: diagnosed
phase: 06-integration-and-mutual-exclusion
source: [06-01-SUMMARY.md, 06-02-SUMMARY.md]
started: 2026-03-22T00:15:00Z
updated: 2026-03-22T00:25:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Swipe Suppresses Static Gestures
expected: While performing a swipe gesture (moving hand laterally), no static gesture keystrokes should fire. The swipe motion should be the only thing detected — no accidental keypresses from static gestures during the swipe.
result: pass

### 2. Static Gestures Resume After Swipe
expected: After completing a swipe gesture and the cooldown period expires, static gesture detection resumes normally. Holding a static gesture pose should trigger its mapped keystroke as before.
result: pass

### 3. Swipe-Then-Static Transition Is Smooth
expected: When transitioning from a swipe to a static gesture, there should be no spurious keystrokes or delayed recognition. The static gesture should be picked up cleanly once the swipe cooldown ends — no ghost inputs.
result: pass

### 4. Distance Gating Resets Swipe State
expected: Move hand out of detection range (too close or too far), then bring it back. Swipe detection should start fresh — no stuck ARMED state from the previous interaction. Static gestures should also work normally after returning to range.
result: issue
reported: "distance is not configured on yaml"
severity: major

## Summary

total: 4
passed: 3
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Distance gating resets swipe state and is configurable via config.yaml"
  status: failed
  reason: "User reported: distance is not configured on yaml"
  severity: major
  test: 4
  root_cause: "config.yaml is missing the distance: section entirely. The backend is fully wired — config.py already reads distance.enabled and distance.min_hand_size from YAML, and both detection loops pass these values to DistanceFilter. The only gap is the missing YAML section, so distance defaults to enabled: False with hardcoded min_hand_size: 0.15 invisible to the user."
  artifacts:
    - path: "config.yaml"
      issue: "Missing distance: section — backend support exists but no user-facing config"
  missing:
    - "Add distance: section to config.yaml with enabled: true and min_hand_size: 0.15"
  debug_session: ".planning/debug/distance-config-missing-yaml.md"
