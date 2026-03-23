---
status: investigating
trigger: "Swipe detection still fires before static gesture detection at runtime despite 10-03 fix"
created: 2026-03-23T00:00:00Z
updated: 2026-03-23T00:00:00Z
---

## Current Focus

hypothesis: The fundamental timing problem is that swipe arms BEFORE any static gesture enters ACTIVATING state, because the hand approach motion itself exceeds swipe thresholds before the hand has formed a recognizable gesture
test: Analyze the threshold values and the temporal sequence of events during hand entry
expecting: Swipe thresholds are so low that hand approach motion triggers arming before classifier can even see a gesture
next_action: Document root cause analysis

## Symptoms

expected: Static gestures should be detected and given priority before swipe detection can arm
actual: Swipe fires on hand approach motion before any static gesture is classified
errors: N/A (behavioral, not crash)
reproduction: Move hand into camera view - swipe triggers before static gesture can be recognized
started: Persistent despite 10-03 fix attempt

## Eliminated

- hypothesis: "tray.py loop is different from __main__.py loop (fix not applied to running code path)"
  evidence: Both loops are structurally identical - same detection order, same is_activating gate, same is_swiping check. The fix WAS applied to both code paths correctly.
  timestamp: 2026-03-23

- hypothesis: "is_swiping still includes COOLDOWN state"
  evidence: swipe.py line 129-134 confirms is_swiping returns True only for ARMED state, not COOLDOWN. This part of the 10-03 fix is correct.
  timestamp: 2026-03-23

- hypothesis: "is_activating property is broken"
  evidence: debounce.py line 64-69 correctly returns True when state == ACTIVATING. Implementation is correct.
  timestamp: 2026-03-23

## Evidence

- timestamp: 2026-03-23
  checked: Code path routing (__main__.py lines 327-337)
  found: Without --preview flag, main() calls run_tray_mode() which creates TrayApp. With --preview, it calls run_preview_mode(). User runs via tray, so TrayApp._detection_loop is the active code path.
  implication: The tray loop IS the running code. Fix was applied there.

- timestamp: 2026-03-23
  checked: Both detection loops (tray.py 217-257, __main__.py 217-264)
  found: Loops are structurally identical. Both run static classification first (line 217-232), then debounce (line 234-243), then swipe with is_activating gate (line 246-257).
  implication: The 10-03 restructuring was applied correctly to both loops.

- timestamp: 2026-03-23
  checked: Swipe thresholds in config.yaml (lines 52-54)
  found: min_velocity=0.15, min_displacement=0.03, axis_ratio=1.5. These are EXTREMELY low. Default code values are min_velocity=0.4, min_displacement=0.08, axis_ratio=2.0. User config is ~2.5x more sensitive than defaults.
  implication: With these thresholds, even casual hand movement into the camera frame will exceed them.

- timestamp: 2026-03-23
  checked: Temporal sequence of events during hand entry
  found: |
    Frame-by-frame timeline when hand enters camera view:
    1. Hand appears in frame -> landmarks detected
    2. SwipeDetector buffer starts filling (needs 3 samples minimum)
    3. Classifier.classify() runs but hand may still be in motion/forming gesture
    4. Smoother needs window_size=2 frames of consistent gesture to output non-None
    5. Debouncer needs activation_delay=0.15s of held gesture to reach ACTIVATING

    Meanwhile for swipe:
    - Buffer fills in ~3 frames (~100ms at 30fps)
    - With min_velocity=0.15 and min_displacement=0.03, hand approach motion easily exceeds thresholds
    - Swipe enters ARMED state
    - Next frame with ANY deceleration -> swipe FIRES

    The is_activating gate only suppresses swipe when debouncer is in ACTIVATING state.
    But debouncer reaches ACTIVATING only AFTER: smoother outputs gesture (2 frames) + debouncer transitions IDLE->ACTIVATING (1 frame).
    That's at minimum 3 frames (~100ms). Swipe can arm and fire in 4 frames (~133ms).

    CRITICAL: The approach motion of the hand ITSELF triggers the swipe. The hand hasn't even formed the gesture yet. Classifier may output None or a transient gesture. The smoother may output None. The debouncer stays IDLE. is_activating is False. Swipe arming is NOT suppressed.
  implication: The is_activating gate is fundamentally insufficient because it can only suppress swipe AFTER a gesture has been consistently classified for multiple frames. But swipe triggers on the approach motion BEFORE any gesture is formed.

- timestamp: 2026-03-23
  checked: SwipeDetector armed-to-fire timing (swipe.py lines 239-256)
  found: Once ARMED, swipe fires on the very first frame where frame_speed < prev_speed (any deceleration). With natural hand motion, deceleration happens within 1-2 frames of peak velocity.
  implication: The window between swipe ARMED and swipe FIRED is extremely small (1-2 frames). Even if is_activating kicked in, the swipe would likely fire before the suppression takes effect.

- timestamp: 2026-03-23
  checked: What happens when swipe enters ARMED (is_swiping becomes True)
  found: Lines 219-227 in both loops - when swiping transitions from False to True, smoother.reset() and debouncer.reset() are called. This DESTROYS any in-progress static gesture classification. Even if the classifier was starting to see a gesture, the smoother buffer is cleared and debouncer goes back to IDLE.
  implication: Double whammy - not only does swipe arm before static can activate, but swipe arming actively resets the static detection pipeline.

## Resolution

root_cause: |
  THREE interacting problems make the 10-03 fix ineffective:

  1. TIMING GAP: The is_activating gate cannot protect against approach-motion swipes because
     the debouncer only reaches ACTIVATING state after smoother (2 frames) + classifier consistency.
     Swipe can arm and fire in 3-4 frames on approach motion BEFORE any gesture is formed.
     The hand is still moving into position - no static gesture exists yet to activate.

  2. THRESHOLD SENSITIVITY: User config has min_velocity=0.15 (default 0.4) and
     min_displacement=0.03 (default 0.08). These are so sensitive that normal hand
     approach/positioning motion exceeds them. The approach vector of bringing a hand
     into frame is indistinguishable from an intentional swipe at these thresholds.

  3. PIPELINE RESET ON ARM: When swipe enters ARMED state, the loop resets smoother and
     debouncer (lines 220-222). This destroys any in-progress static gesture classification,
     making it impossible for static to "catch up" even if the hand has formed a gesture.

  The 10-03 fix correctly restructured the code order and added the is_activating gate,
  but the fundamental problem is that is_activating is a reactive guard (requires static
  gesture to already be detected) trying to prevent a proactive event (swipe arming on
  raw motion that occurs before any gesture exists).

fix: |
  Not applied (research only). Suggested directions:

  A. SETTLING GUARD ON HAND ENTRY: When landmarks first appear (hand enters frame),
     suppress swipe detection for N frames or T seconds to let the hand settle and
     a static gesture to be classified first. Similar to the existing post-cooldown
     settling_frames but applied to initial hand detection.

  B. RAISE SWIPE THRESHOLDS: The user's thresholds (0.15 vel, 0.03 disp) are too
     sensitive. Recommend min_velocity >= 0.3, min_displacement >= 0.06. This alone
     would significantly reduce false swipe triggers on approach motion.

  C. REQUIRE GESTURE-THEN-SWIPE: Instead of the is_activating gate (which requires
     debouncer state), require that a static gesture has been classified at least once
     before swipe can arm. A simple flag: "hand_has_gesture = True" once classifier
     returns non-None. Reset when hand is lost. Swipe only processes landmarks when
     hand_has_gesture is True.

  D. DO NOT RESET PIPELINE ON SWIPE ARM: Remove the smoother.reset()/debouncer.reset()
     calls when swiping transitions to True. This prevents swipe arming from destroying
     in-progress static detection.

verification:
files_changed: []
