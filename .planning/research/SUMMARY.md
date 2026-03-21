# Project Research Summary

**Project:** gesture-keys v1.1 — Distance Threshold and Swipe Gestures
**Domain:** Real-time hand gesture recognition pipeline extension (MediaPipe, Python)
**Researched:** 2026-03-21
**Confidence:** HIGH

## Executive Summary

gesture-keys v1.1 adds two distinct capabilities to an existing static gesture pipeline: distance-based hand gating and directional swipe detection. Research confirms both features can be implemented entirely within the existing dependency footprint — no new packages required. The correct approach for distance gating is to use the Euclidean distance between wrist (landmark 0) and middle finger MCP (landmark 9) as a pose-invariant proxy for hand proximity, not the MediaPipe z-coordinate (which is relative to the wrist, not the camera). Swipe detection requires a new parallel pipeline path that tracks wrist trajectory in a rolling time window and applies velocity thresholding — it must not be fed through the existing GestureSmoother or GestureDebouncer, which are designed for held static poses and are architecturally incompatible with transient motion events.

The two features are independent of each other and can be built in either order, but distance gating is simpler and lower risk so it should be built first. The most dangerous architectural trap is routing swipes through the existing debounce state machine: swipes will either never fire (activation delay requirement) or cause mutual interference with static gestures. This must be treated as a parallel output path from the start, not a retrofit. Both features require all thresholds to be user-configurable in config.yaml with live preview overlays for calibration, since normalized MediaPipe coordinates vary across webcams and hand sizes.

The existing pipeline (camera -> HandDetector -> GestureClassifier -> GestureSmoother -> GestureDebouncer -> KeystrokeSender) gains two new components: DistanceFilter (inserted before GestureClassifier) and SwipeDetector (parallel path receiving raw landmarks, bypassing smoother and debouncer, with its own cooldown). The Gesture enum, AppConfig, and both pipeline loop files (__main__.py and tray.py) need minor additive changes. Per-frame computation overhead is negligible — all new logic is pure math on 21 landmark coordinates.

## Key Findings

### Recommended Stack

No new dependencies are required. All implementation uses MediaPipe HandLandmarkerResult output (already available), stdlib `math` for Euclidean distance calculations, and `collections.deque` for the swipe position ring buffer. Specifically: do not add numpy (overkill for 2-point distance math), scipy (smoothing is already handled), OpenCV optical flow (landmarks are a better signal than pixel motion), or any ML model (4-direction swipe from a velocity vector is solved by atan2 + axis dominance check).

**Core techniques (not new libraries):**
- `math.sqrt` on WRIST-to-MIDDLE_MCP landmark pair — distance proxy, pose-invariant because these are skeletal joints unaffected by finger articulation
- `collections.deque(maxlen=30)` for wrist position history — ring buffer for velocity computation, stdlib, no dependency
- Velocity threshold (`displacement / elapsed_time`) — distinguishes intentional swipes from casual hand repositioning; frame-rate independent unlike raw displacement
- Dominant axis classification (`abs(dx) > abs(dy) * 1.5`) — rejects diagonal noise, maps displacement vector to one of four cardinal directions

### Expected Features

**Must have (v1.1 table stakes):**
- Distance gating filter — reject gestures when hand is below minimum palm span threshold; configurable `min_hand_size` float in config.yaml
- Distance toggle — `enabled: true/false` in config without touching threshold values
- Distance indicator in preview — numeric overlay showing live hand size value for threshold calibration
- Four cardinal swipe gestures — `swipe_left`, `swipe_right`, `swipe_up`, `swipe_down` as new Gesture enum members
- Swipe config entries — same gesture-name-to-key structure as static gestures in config.yaml
- Swipe cooldown — independent of static gesture debouncer, prevents double-fire after a swipe

**Should have (v1.x, add after validation):**
- Per-gesture distance thresholds — some gestures (pinch) need closer range than others
- Swipe visual feedback in preview — directional arrow overlay when swipe fires
- Swipe sensitivity config — `min_velocity`, `min_displacement`, `cooldown` under a `swipe` section

**Defer to v2+:**
- Diagonal swipe support (8 directions) — adds ambiguity, 4 directions already double the input vocabulary
- Swipe + static gesture combos (e.g., "pointing + swipe right") — high state machine complexity
- Distance-based confidence scaling — couples two independent systems

### Architecture Approach

v1.1 adds two new modules (`distance.py` and `swipe.py`) that slot into the existing linear pipeline with minimal changes to existing components. The pipeline gains a filter-in-pipeline stage (DistanceFilter converts "too far" to "no hand" so downstream code sees no change) and a parallel temporal detector (SwipeDetector accumulates wrist trajectory evidence across frames and emits discrete swipe events that bypass the smoother, going directly to the debouncer or keystroke sender). The Gesture enum is expanded additively. AppConfig gains new fields with backwards-compatible defaults. Both pipeline loop files (__main__.py and tray.py) contain duplicated loop code and both must be modified identically — this technical debt is accepted for v1.1 and flagged for future refactoring.

**Major components:**
1. `DistanceFilter` (`distance.py`) — computes palm span (WRIST-to-MIDDLE_MCP Euclidean distance in normalized coords), returns pass/fail; `last_size` property for preview overlay; O(1) per frame
2. `SwipeDetector` (`swipe.py`) — maintains wrist position deque with timestamps, computes displacement vector and velocity over rolling window, classifies cardinal direction on threshold crossing, includes settling period (5-8 frames) to suppress false detections on hand entry
3. `Gesture` enum additions — `SWIPE_LEFT`, `SWIPE_RIGHT`, `SWIPE_UP`, `SWIPE_DOWN` as new members; additive, no downstream breakage
4. `AppConfig` additions — `min_hand_size`, `swipe_min_distance`, `swipe_max_duration`, `swipe_min_speed` with sensible defaults; backwards-compatible

### Critical Pitfalls

1. **Using MediaPipe z-coordinate as camera distance** — z is relative to the wrist origin (inter-landmark depth), not absolute camera distance. Avoid entirely. Use WRIST-to-MIDDLE_MCP Euclidean distance in normalized x,y as the proxy; it is gesture-invariant and requires no calibration.

2. **Routing swipes through GestureSmoother / GestureDebouncer** — the smoother requires majority vote across N frames (votes out single-frame swipe events); the debouncer requires hold-to-activate (swipes are transient 200-400ms events). Both are architecturally incompatible with swipes. SwipeDetector must be a parallel component with its own cooldown and a direct output path to KeystrokeSender.

3. **Swipe detection from frame-to-frame landmark deltas** — MediaPipe landmarks jitter 1-3% of normalized coordinates even on a stationary hand. Frame-to-frame deltas produce phantom micro-movements. Use a rolling deque (5-8 frames, ~0.3s window), compute displacement from oldest to newest entry, and require velocity (not raw displacement) to be frame-rate independent.

4. **Swipe/static gesture cross-firing** — during a swipe the hand passes through static gesture poses, triggering unintended keystrokes. During quick pose transitions the wrist moves, triggering false swipes. Implement mutual exclusion: suppress static classification when wrist velocity exceeds "hand is moving" threshold; suppress swipe detection when static gesture is in ACTIVATING or FIRED state.

5. **Hardcoded thresholds that break across cameras and users** — MediaPipe normalized coordinates vary with webcam FOV and hand size. Every threshold must be in config.yaml. The preview overlay must display live distance proxy value and wrist velocity so users can calibrate to their setup.

6. **False swipes on hand entry/exit** — hand entering the frame from an edge produces an artificial large displacement jump. Implement a settling period: require N consecutive frames of continuous hand presence before SwipeDetector begins tracking. Clear position buffer entirely on hand loss.

## Implications for Roadmap

Based on research, the natural build order is driven by the dependency graph: enum and config changes are foundational, distance gating is simpler and independent, swipe detection depends on the enum but not on distance gating, and pipeline integration wires everything together last.

### Phase 1: Gesture Enum and Config Expansion
**Rationale:** All other phases depend on the Gesture enum having swipe members and AppConfig having new fields. These are additive, zero-risk changes that unblock everything else. Best done first to avoid merge conflicts during parallel development.
**Delivers:** `Gesture.SWIPE_*` enum values; `min_hand_size`, `swipe_*` AppConfig fields with backwards-compatible defaults; updated config.yaml with commented new keys
**Addresses:** "Hardcoded thresholds" pitfall — all thresholds are in config from day one
**Avoids:** Retrofitting config support after components are already written with magic numbers

### Phase 2: Distance Filter
**Rationale:** Simpler feature, no state management, pure per-frame math. Validates the landmark coordinate approach before tackling the more complex stateful SwipeDetector. Can be built and tested in isolation with no camera required (unit test with synthetic landmark lists).
**Delivers:** `DistanceFilter` class (`distance.py`); distance gate inserted in both pipeline loops before GestureClassifier; `min_hand_size` config wired up; `DistanceFilter.last_size` for preview
**Addresses:** Distance gating filter, distance toggle, "too far" UX feedback (preview overlay)
**Avoids:** Z-coordinate distance pitfall; pose-varying proxy pitfall (using WRIST-MIDDLE_MCP, not bounding box or fingertip span)

### Phase 3: Swipe Detector
**Rationale:** Depends on Gesture enum (Phase 1). Independent of DistanceFilter (Phase 2) but benefits from having config infrastructure ready. The most algorithmically complex component — needs careful implementation of rolling buffer, velocity thresholding, axis dominance, settling period, and cooldown.
**Delivers:** `SwipeDetector` class (`swipe.py`) with wrist position deque, velocity computation, cardinal direction classification, settling period, and internal cooldown; wired as parallel path in both pipeline loops; bypasses GestureSmoother and GestureDebouncer
**Addresses:** Four cardinal swipe gestures, swipe config entries, swipe cooldown
**Avoids:** Frame-to-frame jitter pitfall; hand entry/exit false swipe pitfall; swipe-through-debouncer architectural pitfall

### Phase 4: Integration and Mutual Exclusion
**Rationale:** After both distance filter and swipe detector work independently, their interaction with each other and with static gesture detection must be validated and hardened. Mutual exclusion between swipe and static paths is the highest-risk integration concern identified in research.
**Delivers:** Wrist velocity tracking for mutual exclusion gating; suppression of static classification during active swipe motion; suppression of swipe detection during held static gesture; integration test coverage for cross-firing scenarios
**Addresses:** Swipe/static cross-firing pitfall; distance-filter-interrupts-mid-swipe UX pitfall
**Avoids:** The "looks done but isn't" failure mode where both features work in isolation but interfere in real use

### Phase 5: Preview Overlay and Calibration UX
**Rationale:** Both features are silent without visual feedback. Users cannot tune thresholds without seeing live values. This phase is not blocking for functionality but is blocking for usability.
**Delivers:** Distance proxy value overlay in preview mode; "TOO FAR" indicator when hand detected but filtered; swipe direction arrow overlay on swipe fire; live wrist velocity display for swipe calibration
**Addresses:** Distance indicator in preview, swipe visual feedback, camera/FOV variation pitfall
**Avoids:** User confusion ("gestures stopped working") from silent distance gating

### Phase Ordering Rationale

- Enum and config first because they are zero-risk and unblock all other phases
- Distance filter before swipe because it is simpler, validates the landmark math approach, and has no state to debug
- Swipe detector before integration because it needs to work correctly in isolation before mutual exclusion logic is layered on top
- Integration and mutual exclusion as its own phase because it is the highest-risk area and needs focused attention after both features are working
- Preview overlay last because it is pure polish and does not affect whether features work correctly

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Swipe Detector):** Specific threshold defaults (min_velocity, min_displacement, dominant axis ratio) are educated guesses from research; real values will require empirical calibration. Plan for a tuning pass.
- **Phase 4 (Integration/Mutual Exclusion):** The velocity threshold for "hand is moving vs. stationary" gating has no established default in the literature for this specific setup. Will require testing.

Phases with standard patterns (can skip research-phase):
- **Phase 1 (Enum/Config):** Purely additive Python changes, established patterns already in codebase
- **Phase 2 (Distance Filter):** Landmark math is fully specified in STACK.md with verified formula; implementation is mechanical
- **Phase 5 (Preview Overlay):** OpenCV text/shape drawing, well-documented patterns already used in existing preview.py

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | No new dependencies; MediaPipe landmark coordinate semantics verified against official docs and GitHub issues; existing codebase confirmed sufficient |
| Features | MEDIUM | Core feature set is clear; specific threshold defaults for swipe sensitivity are estimates requiring empirical validation with real hardware |
| Architecture | HIGH | Pipeline integration points fully mapped against actual codebase files; parallel path pattern is architecturally clean with clear component boundaries |
| Pitfalls | HIGH | Z-coordinate confusion and swipe-through-debouncer pitfalls verified against MediaPipe docs, GitHub issues, and codebase analysis; all pitfalls have concrete prevention strategies |

**Overall confidence:** HIGH

### Gaps to Address

- **Swipe threshold defaults:** `min_velocity` (normalized units/second), `min_displacement`, and dominant axis ratio need empirical calibration on representative hardware. Research gives plausible starting ranges (velocity ~0.8-1.5, displacement ~0.15, axis ratio ~1.5x) but these are starting points, not validated defaults. Plan a tuning session during Phase 3 execution.
- **Mirror/flip coordinate mapping:** Whether swipe direction names match user-perceived direction depends on whether the webcam feed is mirrored. ARCHITECTURE.md flags this but does not resolve it. The SwipeDetector should document its coordinate convention and the config or code should include a `mirror_x` flag if needed.
- **Duplicate pipeline code:** Both `__main__.py` and `tray.py` contain the detection loop. Research recommends accepting this duplication for v1.1. Phases 2-4 must modify both files identically. Flag for a dedicated refactoring pass after v1.1 ships.

## Sources

### Primary (HIGH confidence)
- [MediaPipe Hand Landmarker docs (Google AI Edge)](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker) — landmark coordinate system, z-value semantics, HandLandmarkerResult structure
- [MediaPipe Hand Landmarker Python guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python) — confirmed hand_landmarks and hand_world_landmarks fields
- [MediaPipe z-value discussion (Issue #742)](https://github.com/google/mediapipe/issues/742) — z is relative to wrist, not camera distance
- [MediaPipe camera distance discussion (Issue #1153)](https://github.com/google/mediapipe/issues/1153) — bounding box size confirmed as practical proxy
- Existing codebase (`classifier.py`, `detector.py`, `smoother.py`, `debounce.py`) — pipeline architecture, landmark indices, coordinate access patterns

### Secondary (MEDIUM confidence)
- [Hand-Distance-Measurement repo](https://github.com/MohamedAlaouiMhamdi/Hand-Distance-Measurement) — validates landmark distance approach; calibration not required for threshold gating
- [Gestop: Customizable Gesture Control (arXiv:2010.13197)](https://arxiv.org/pdf/2010.13197) — swipe detection using palm base timediff coordinates and velocity thresholds
- [Implementing a Swipe Gesture (Musing Mortoray)](https://mortoray.com/implementing-a-swipe-gesture/) — velocity threshold patterns, distance thresholds, direction classification
- [Dynamic Hand Gesture Recognition Using MediaPipe and Transformer](https://www.mdpi.com/2673-4591/108/1/22) — frame-to-frame landmark delta approach for dynamic gestures; confirms temporal window approach

### Tertiary (LOW confidence)
- [5 Things I Wish I Knew Before Using MediaPipe for Hand Gesture Recognition](https://dev.to/trojanmocx/5-things-i-wish-i-knew-before-using-mediapipe-for-hand-gesture-recognition-41gb) — jitter characteristics, confidence tuning, lighting sensitivity; community source, not official

---
*Research completed: 2026-03-21*
*Ready for roadmap: yes*
