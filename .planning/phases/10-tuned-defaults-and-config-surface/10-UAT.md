---
status: diagnosed
phase: 10-tuned-defaults-and-config-surface
source: [10-01-SUMMARY.md, 10-02-SUMMARY.md, 10-03-SUMMARY.md]
started: 2026-03-23T10:30:00Z
updated: 2026-03-23T11:15:00Z
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
note: passed in prior session

### 2. Gesture Detection Responsiveness (re-test after fix)
expected: Run the app. Perform static gestures (open palm, fist, pinch). Gestures should activate quickly (~0.15s delay) without swipe interference. Moving your hand into position to form a static gesture should NOT trigger a swipe first. Static gesture should fire cleanly.
result: issue
reported: "swipe still gets fired first before static gesture"
severity: major

### 3. Settling Frames Configurable
expected: In config.yaml under `swipe:`, the `settling_frames: 3` setting is present. Change it to a different value (e.g., 5), save the file. The app should pick up the new value on hot-reload without restart.
result: pass
note: passed in prior session

### 4. Per-Gesture Cooldown Override
expected: Under `pinch:` in config.yaml, there is a commented example `# cooldown: 0.6`. Uncomment it (set `cooldown: 0.6`), save, and hot-reload. Pinch gesture should now have a noticeably longer cooldown (~0.6s) than other gestures (~0.3s global default). Re-comment to restore default behavior.
result: pass
note: passed in prior session

### 5. Global Cooldown Fallback
expected: With no per-gesture cooldown overrides active (all commented out), all gestures use the global cooldown_duration (0.3s). Performing any gesture rapidly should show the global cooldown gating repeat fires consistently.
result: pass
note: passed in prior session

### 6. Swipe Still Works (regression check)
expected: With no static gesture being formed, perform deliberate swipe motions (move hand left/right/up/down quickly). Swipes should still detect and fire their mapped keys correctly. The priority fix should not break swipe detection.
result: pass

## Summary

total: 6
passed: 5
issues: 1
pending: 0
skipped: 0

## Gaps

- truth: "Static gestures fire without swipe interference — moving hand into position should not trigger swipe first"
  status: failed
  reason: "User reported: swipe still gets fired first before static gesture"
  severity: major
  test: 2
  root_cause: "Three interacting problems: (1) TIMING GAP - is_activating is reactive, only True after smoother outputs consistent gesture (2+ frames). Hand approach motion triggers swipe BEFORE any gesture is classified, so is_activating is False and swipe arms freely. (2) EXTREME THRESHOLD SENSITIVITY - user config has min_velocity=0.15, min_displacement=0.03 (~2.5x more sensitive than defaults), making natural approach motion indistinguishable from swipe. (3) PIPELINE RESET - smoother.reset() and debouncer.reset() called on swipe arm, destroying any in-progress static classification."
  artifacts:
    - path: "gesture_keys/swipe.py"
      issue: "IDLE->ARMED fires on very low thresholds, no hand-entry settling period"
    - path: "gesture_keys/tray.py"
      issue: "smoother.reset()/debouncer.reset() on swipe arm destroys static gesture progress"
    - path: "gesture_keys/__main__.py"
      issue: "Same reset issue as tray.py"
    - path: "config.yaml"
      issue: "Swipe thresholds (0.15/0.03) too sensitive for approach motion"
  missing:
    - "Hand entry settling period — suppress swipe for N frames when landmarks first appear"
    - "Stop resetting smoother/debouncer on swipe arm"
    - "Require static gesture classified at least once before swipe can arm"
  debug_session: ".planning/debug/swipe-preempts-static.md"
