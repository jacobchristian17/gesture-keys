---
status: diagnosed
phase: 10-tuned-defaults-and-config-surface
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md]
started: 2026-03-23T10:30:00Z
updated: 2026-03-23T10:30:00Z
---

## Current Test
<!-- OVERWRITE each test - shows where we are -->

number: done
name: testing complete
expected: |
  [testing complete]
awaiting: none

## Tests

### 1. Tuned Defaults Ship Out of Box
expected: In config.yaml, detection section shows: smoothing_window: 2, activation_delay: 0.15, cooldown_duration: 0.3. Swipe section shows settling_frames: 3.
result: pass

### 2. Gesture Detection Responsiveness
expected: Run the app. Perform gestures (open palm, fist, pinch). Gestures should activate quickly (~0.15s delay) and have a short cooldown (~0.3s) before the same gesture can re-fire. Overall feel should be snappy and responsive compared to previous defaults.
result: issue
reported: "Swipe fires first, activates the cooldown, theres a delay when static gesture is the main intent. Cooldown works good for others. I'll suggest that static gestures must fire first before detecting any swipes"
severity: major

### 3. Settling Frames Configurable
expected: In config.yaml under `swipe:`, the `settling_frames: 3` setting is present. Change it to a different value (e.g., 5), save the file. The app should pick up the new value on hot-reload without restart.
result: pass

### 4. Per-Gesture Cooldown Override
expected: Under `pinch:` in config.yaml, there is a commented example `# cooldown: 0.6`. Uncomment it (set `cooldown: 0.6`), save, and hot-reload. Pinch gesture should now have a noticeably longer cooldown (~0.6s) than other gestures (~0.3s global default). Re-comment to restore default behavior.
result: pass

### 5. Global Cooldown Fallback
expected: With no per-gesture cooldown overrides active (all commented out), all gestures use the global cooldown_duration (0.3s). Performing any gesture rapidly should show the global cooldown gating repeat fires consistently.
result: pass

## Summary

total: 5
passed: 4
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Gestures activate quickly with snappy responsiveness, no interference between gesture types"
  status: failed
  reason: "User reported: Swipe fires first, activates the cooldown, theres a delay when static gesture is the main intent. Cooldown works good for others. I'll suggest that static gestures must fire first before detecting any swipes"
  severity: major
  test: 2
  root_cause: "Swipe detector runs before static classifier in main loop. Hand approach motion triggers swipe (IDLE->ARMED->COOLDOWN), is_swiping includes COOLDOWN state which resets smoother/debouncer and suppresses static detection for full swipe_cooldown (500ms). Two problems: (A) no priority feedback from debouncer ACTIVATING state to suppress swipe arming, (B) COOLDOWN treated same as ARMED for suppression."
  artifacts:
    - path: "gesture_keys/__main__.py"
      issue: "Swipe detection at line 218 runs before static classifier at line 239, no priority gate"
    - path: "gesture_keys/tray.py"
      issue: "Same ordering issue as __main__.py"
    - path: "gesture_keys/debounce.py"
      issue: "No API to query ACTIVATING state for cross-detector priority"
  missing:
    - "Static gesture priority: check debouncer ACTIVATING state before allowing swipe to arm"
    - "Stop treating swipe COOLDOWN as swiping for static gesture suppression"
