---
status: diagnosed
trigger: "No transition from swipe to static gesture detection"
created: 2026-03-22T00:00:00Z
updated: 2026-03-22T00:00:00Z
---

## Current Focus

hypothesis: CONFIRMED - Post-cooldown hand movement causes immediate swipe re-arming due to low thresholds and no post-cooldown settling guard
test: Simulated swipe-to-static with user's config thresholds (min_velocity=0.15, min_displacement=0.03)
expecting: Re-arming during hand settling
next_action: Return root cause diagnosis

## Symptoms

expected: After swipe cooldown expires, static gesture detection resumes cleanly without ghost inputs
actual: No transition from swipe to static gesture detection. Static gestures do not resume after swipe.
errors: None reported
reproduction: Test 3 in UAT (swipe then hold static gesture)
started: Discovered during UAT

## Eliminated

## Evidence

- timestamp: 2026-03-22T00:01:00Z
  checked: swipe.py COOLDOWN->IDLE transition (lines 173-181)
  found: COOLDOWN->IDLE transition works correctly - checks timestamp, clears buffer, resets prev_speed, returns None. The is_swiping property returns False once state is IDLE.
  implication: Swipe state machine itself transitions correctly

- timestamp: 2026-03-22T00:02:00Z
  checked: Main loop suppression logic (__main__.py lines 226-232, tray.py lines 227-232)
  found: "swiping = config.swipe_enabled and swipe_detector.is_swiping" gates static detection. When swiping=True, smoother.update(None) is called instead of classifying. When swiping=False (after cooldown), classifier runs normally.
  implication: Gate logic is correct in principle

- timestamp: 2026-03-22T00:03:00Z
  checked: Smoother behavior (smoother.py) after receiving None during COOLDOWN
  found: During COOLDOWN (say 0.5s at 30fps = ~15 frames), smoother receives None every frame. Buffer fills with None. After COOLDOWN ends and classifier resumes, smoother needs majority of window to be the gesture. With window=1 in current config, this should pass immediately. BUT: smoother returns None if most_common_value is None (line 47 returns None since that IS the majority value... wait, it returns most_common_value which CAN be None).
  implication: With window_size=1, first valid gesture should pass through. But with larger windows, there's inherent delay.

- timestamp: 2026-03-22T00:04:00Z
  checked: Smoother return value when most_common is None
  found: smoother.update() returns most_common_value directly (line 47). If most_common is None, it returns None. This is correct behavior. With window_size=1 (config), buffer has 1 slot - first real gesture immediately becomes majority.
  implication: Smoother is NOT the blocker with current config (window=1)

- timestamp: 2026-03-22T00:05:00Z
  checked: Debouncer behavior after swipe cooldown period
  found: CRITICAL - During swipe COOLDOWN, smoother outputs None, so debouncer receives None every frame. If debouncer was in IDLE, it stays IDLE. If it was ACTIVATING, it resets to IDLE. If in COOLDOWN (debouncer's own cooldown), it may get stuck. The key issue: debouncer COOLDOWN->IDLE requires gesture==None (line 131). But after swipe cooldown ends, the user is HOLDING a static gesture, so gesture is non-None. The debouncer cooldown check only transitions to IDLE if the gesture is None. If the debouncer happened to be in its own COOLDOWN state when the swipe started, it would require a None gesture to exit COOLDOWN, but after swipe cooldown the user's hand is showing a gesture.
  implication: Need to check if debouncer gets stuck in its own COOLDOWN state

- timestamp: 2026-03-22T00:06:00Z
  checked: Full timeline of debouncer state during swipe scenario
  found: Scenario: User is holding static gesture -> fires -> debouncer enters COOLDOWN -> user starts swiping -> swipe suppression feeds None to smoother -> debouncer sees None -> debouncer COOLDOWN expires and sees gesture==None -> transitions to IDLE. So debouncer exits cleanly. HOWEVER: Consider the opposite scenario: debouncer is in IDLE or just activated, swipe happens, swipe cooldown feeds None to debouncer for ~15 frames, debouncer stays IDLE. After swipe cooldown, debouncer is IDLE and starts ACTIVATING on first gesture. This should work.
  implication: Debouncer state is not the primary issue for the "no transition" symptom

- timestamp: 2026-03-22T00:07:00Z
  checked: COOLDOWN->IDLE timing and the "return None / skip frame" behavior (swipe.py line 179)
  found: On the frame where COOLDOWN expires, swipe.py returns None AND clears the buffer. But is_swiping returns False (state is now IDLE). On this SAME frame, the main loop checks is_swiping AFTER calling swipe_detector.update(). So: (1) swipe_detector.update() transitions COOLDOWN->IDLE, (2) swiping check sees is_swiping=False, (3) classifier runs on landmarks. This is correct sequencing.
  implication: Frame-level sequencing is correct

- timestamp: 2026-03-22T00:08:00Z
  checked: Whether swipe COOLDOWN->IDLE clears the buffer causing the NEXT update to have < 3 samples
  found: CRITICAL FINDING. When COOLDOWN->IDLE happens (line 176), buffer is cleared. Next frame: landmarks are appended to buffer, buffer has 1 sample, line 169 check "if len < 3: return None" triggers. So for 2 more frames, update() returns None without checking cooldown state. But state IS IDLE now, so is_swiping returns False. The static pipeline runs correctly on these frames because is_swiping is checked separately from swipe_detector.update(). This is fine.
  implication: Buffer clearing doesn't affect static gesture pipeline

- timestamp: 2026-03-22T00:09:00Z
  checked: Re-examine the EXACT sequencing more carefully - swipe fires THEN is_swiping checked
  found: In __main__.py lines 214-232 and tray.py lines 214-232: swipe_detector.update() is called FIRST (line 215-223). THEN is_swiping is checked (line 226-227). After update transitions from COOLDOWN->IDLE, is_swiping returns False. classifier.classify runs. smoother.update gets real gesture. This produces correct output on the very first frame after cooldown expires. Pipeline IS correct.
  implication: The code logic appears sound for normal operation

- timestamp: 2026-03-22T00:10:00Z
  checked: Test 1 vs Test 3 cross-reference from UAT
  found: Test 1 ALSO failed - "static not suppressed within swipe cooldowns". This means is_swiping is NOT returning True during COOLDOWN as expected, OR the gate check isn't working. If Test 1 fails (static fires during cooldown), it means swiping flag is False during cooldown. If swiping is False during cooldown, then after cooldown ends, static would work fine. But Test 3 says "no transition made" - which could mean the USER never saw the transition work cleanly because Test 1's failure (static firing during swipe) created confusion about what's happening.
  implication: Test 1 and Test 3 may share the same root cause - the is_swiping flag not working correctly during COOLDOWN

- timestamp: 2026-03-22T00:11:00Z
  checked: Simulated swipe-to-static with user config thresholds (min_velocity=0.15, min_displacement=0.03)
  found: With moderate hand repositioning (~0.01 normalized coords/frame), swipe re-arms at t=0.831 (165ms after cooldown expires at t=0.666) and re-fires at t=0.897. This creates an indefinite cycle preventing static detection.
  implication: ROOT CAUSE CONFIRMED - post-cooldown hand movement causes false swipe re-detection

- timestamp: 2026-03-22T00:12:00Z
  checked: Brief IDLE gap between COOLDOWN->IDLE and re-ARMED
  found: During the ~4 frame window (132ms) where state=IDLE after cooldown, static gestures are enabled. With smoothing_window=1 and activation_delay=0.05s, a static gesture can fire in 2 frames during this gap.
  implication: Explains Test 1 failure (static fires during what user perceives as swipe period)

- timestamp: 2026-03-22T00:13:00Z
  checked: swipe.py line 179 "skip this frame" guard
  found: Only skips 1 frame after COOLDOWN->IDLE transition. Buffer rebuilds to 3 samples in 3 frames, then velocity/displacement checks resume. Insufficient protection against post-cooldown settling movement.
  implication: The existing guard acknowledges the problem but is too narrow (1 frame vs needed ~10-15 frames)

## Resolution

root_cause: After swipe COOLDOWN expires and state returns to IDLE, the swipe detector immediately begins accumulating new buffer samples. With the user's low thresholds (min_velocity=0.15, min_displacement=0.03), natural hand repositioning or settling movement after a swipe exceeds these thresholds within 3-5 frames (~100-165ms), causing the detector to re-arm (IDLE->ARMED) and re-fire (ARMED->COOLDOWN). This creates an indefinite COOLDOWN->IDLE->ARMED->COOLDOWN cycle that prevents static gesture detection from ever resuming. The single-frame skip on COOLDOWN->IDLE (line 179) is insufficient; the code needs a post-cooldown settling period where swipe arming is suppressed to allow the hand to stabilize before re-enabling swipe detection. This same root cause also explains Test 1's failure: during the brief IDLE gap between cooldown expiry and re-arming (~4 frames), static gestures are momentarily enabled and can fire spuriously.
fix:
verification:
files_changed: []
