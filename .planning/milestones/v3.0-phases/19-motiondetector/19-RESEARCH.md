# Phase 19: MotionDetector - Research

**Researched:** 2026-03-26
**Domain:** Per-frame motion detection from hand landmarks with hysteresis
**Confidence:** HIGH

## Summary

MotionDetector is a continuous per-frame motion reporter that replaces SwipeDetector's event-based fire model. Instead of detecting discrete swipe events via a 3-state machine (IDLE/ARMED/COOLDOWN), MotionDetector reports a boolean `moving` flag and cardinal `direction` on every frame. The existing SwipeDetector in `swipe.py` provides a proven reference for wrist tracking, rolling deque buffers, direction classification, settling frames, and MediaPipe Y-axis handling -- all of which MotionDetector can adapt.

The core design difference is that SwipeDetector fires once per swipe (event), while MotionDetector continuously reports motion state (signal). This eliminates the ARMED/COOLDOWN state machine in favor of a simpler hysteresis model: arm threshold to transition to moving=True, lower disarm threshold to transition back to moving=False. Direction classification reuses the same axis-dominant approach from SwipeDetector but outputs the `Direction` enum from `trigger.py` instead of `SwipeDirection`.

**Primary recommendation:** Build a stateful `MotionDetector` class with `update()` method following the established detector pattern (SwipeDetector, DistanceFilter, GestureSmoother). Use velocity as the hysteresis metric (displacement is too frame-rate dependent). Output a frozen dataclass `MotionState` with `moving: bool` and `direction: Optional[Direction]` fields.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Reuse the existing `Direction` enum from `trigger.py` (LEFT/RIGHT/UP/DOWN) -- single source of truth from Phase 18
- New `motion:` section in config.yaml -- clean break from old `swipe:` section
- Expose arm/disarm thresholds as configurable parameters (motion_arm_threshold, motion_disarm_threshold)
- Settling frames configurable in the `motion:` section
- Current phase: 4-way cardinal only (matching Direction enum)
- Design direction classification to be extensible for diagonal support later (ETRIG-01)
- Moderate hysteresis gap: arm threshold ~1.5-2x the disarm threshold

### Claude's Discretion
- Output dataclass shape (what fields beyond moving + direction)
- Reference landmark for position tracking
- Class design (stateful with internal buffer vs pure function)
- Velocity vs displacement as hysteresis metric
- Direction hold vs immediate clear on motion stop
- Direction change handling (immediate vs require pause)
- Default threshold values for arm/disarm
- Buffer size for rolling position window
- Default settling frame count

### Deferred Ideas (OUT OF SCOPE)
- Diagonal direction support (up-left, up-right, etc.) -- future requirement ETRIG-01
- Velocity-sensitive triggers (fast vs slow motion) -- future requirement ETRIG-03
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MOTN-01 | System detects continuous per-frame motion state (moving/not moving) from hand landmarks | Hysteresis model with arm/disarm velocity thresholds on rolling buffer; `MotionState` dataclass returned each frame |
| MOTN-02 | System classifies motion direction as one of 4 cardinal directions (left, right, up, down) | Direction classification adapted from SwipeDetector with axis_ratio, using `Direction` enum from `trigger.py`; MediaPipe Y-axis inversion handled |
| MOTN-03 | System uses hysteresis (separate arm/disarm thresholds) to prevent motion state flicker | Two-threshold model: arm velocity > disarm velocity (ratio ~1.5-2x); only transitions logged |
| MOTN-04 | System applies settling frames on hand entry to prevent false motion detection | Settling counter pattern proven in SwipeDetector; suppresses motion during initial frames after hand appears |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| collections.deque | stdlib | Rolling position buffer | Proven in SwipeDetector and GestureSmoother; O(1) append with maxlen |
| dataclasses | stdlib | MotionState output type | Frozen dataclass matches Trigger/SequenceTrigger pattern from Phase 18 |
| enum (Direction) | trigger.py | Cardinal directions | Locked decision: reuse Phase 18 Direction enum |
| math | stdlib | Velocity calculation | sqrt for Euclidean distance, same as SwipeDetector |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| typing | stdlib | Type hints (Optional, Any) | All public API signatures |
| logging | stdlib | Transition logging | State changes only (not every frame) |

No external dependencies needed. This is pure Python computation on landmark coordinates.

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
    motion.py          # MotionDetector class + MotionState dataclass
    trigger.py          # Direction enum (existing, imported)
tests/
    test_motion.py      # Unit tests for MotionDetector
```

### Pattern 1: Stateful Detector with update() Method
**What:** Class that receives per-frame landmarks via `update()`, maintains internal rolling buffer, returns result each frame.
**When to use:** All frame-by-frame detectors in this codebase (SwipeDetector, DistanceFilter, GestureSmoother).
**Example:**
```python
# Follows established codebase pattern from swipe.py, smoother.py
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from gesture_keys.trigger import Direction

WRIST = 0  # Landmark index for wrist tracking

@dataclass(frozen=True)
class MotionState:
    """Per-frame motion detection result."""
    moving: bool
    direction: Optional[Direction] = None

# Singleton for "not moving" to avoid allocation per frame
_NOT_MOVING = MotionState(moving=False)

class MotionDetector:
    def __init__(
        self,
        buffer_size: int = 5,
        arm_threshold: float = 0.25,
        disarm_threshold: float = 0.15,
        axis_ratio: float = 2.0,
        settling_frames: int = 3,
    ) -> None:
        self._buffer: deque[tuple[float, float, float]] = deque(maxlen=buffer_size)
        self._arm_threshold = arm_threshold
        self._disarm_threshold = disarm_threshold
        self._axis_ratio = axis_ratio
        self._settling_frames = settling_frames
        self._moving = False
        self._direction: Optional[Direction] = None
        self._hand_present = False
        self._settling_remaining = 0

    def update(
        self, landmarks: Optional[list[Any]], timestamp: float
    ) -> MotionState:
        """Process one frame, return current motion state."""
        ...
```

### Pattern 2: Hysteresis with Separate Arm/Disarm Thresholds
**What:** Two velocity thresholds prevent rapid toggling. `moving` becomes True when velocity exceeds `arm_threshold`, becomes False only when velocity drops below `disarm_threshold` (which is lower).
**When to use:** Any binary signal derived from a noisy continuous measurement.
**Design:**
```
velocity
  ^
  |  ----arm_threshold---- (0.25)    -> transitions to moving=True
  |
  |  ----disarm_threshold-- (0.15)   -> transitions to moving=False
  |
  0 --------------------------> time
```
The gap between thresholds creates a "dead zone" where the current state is maintained, preventing flicker.

### Pattern 3: Property Setters for Hot-Reload
**What:** Config parameters exposed as properties with setters so pipeline can update them at runtime without recreating the detector.
**When to use:** All configurable parameters (arm_threshold, disarm_threshold, settling_frames, axis_ratio).
**Example:**
```python
@property
def arm_threshold(self) -> float:
    return self._arm_threshold

@arm_threshold.setter
def arm_threshold(self, value: float) -> None:
    self._arm_threshold = value
```

### Anti-Patterns to Avoid
- **Event-based output:** MotionDetector must NOT fire once and go silent. It reports state every frame. This is the fundamental difference from SwipeDetector.
- **Gesture-level state:** No ARMED/COOLDOWN states. MotionDetector is not a gesture recognizer -- it is a continuous signal source. The orchestrator (Phase 21) consumes the signal.
- **Frame-by-frame logging:** Log only state transitions (moving->not_moving, direction changes), not every frame. At 30 FPS, per-frame logging is 30 lines/second.
- **Using displacement alone for thresholds:** Displacement depends on buffer size and frame rate. Velocity (displacement/time) is frame-rate-independent.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rolling buffer | Custom ring buffer | `collections.deque(maxlen=N)` | Proven, O(1), handles overflow automatically |
| Direction enum | New direction enum | `trigger.Direction` | Locked decision; single source of truth |
| Y-axis correction | Custom coordinate transform | Comment-documented inversion in `_classify_direction` | MediaPipe Y-axis is inverted (lower Y = physically higher). SwipeDetector documents this clearly. |

**Key insight:** The SwipeDetector has already solved the low-level problems (wrist tracking, rolling buffer, direction classification, settling frames). MotionDetector adapts these solutions with a different output model (continuous state vs discrete events).

## Common Pitfalls

### Pitfall 1: MediaPipe Y-Axis Inversion
**What goes wrong:** Direction classification reports UP when hand moves down (and vice versa).
**Why it happens:** MediaPipe landmark coordinates have Y=0 at top, Y=1 at bottom. dy < 0 means physically upward movement.
**How to avoid:** Copy the Y-axis handling from SwipeDetector._classify_direction: `dy < 0` = UP, `dy > 0` = DOWN.
**Warning signs:** Test with known up/down movements returns wrong direction.

### Pitfall 2: First-Frame Velocity Spike
**What goes wrong:** Hand appears in frame, first velocity calculation uses stale/zero previous position, produces garbage velocity.
**Why it happens:** Buffer has only 1-2 entries; displacement/time from single frame can be huge if hand appears far from last known position.
**How to avoid:** Require minimum buffer fill (at least 2-3 entries) before computing velocity. Settling frames guard provides additional protection.
**Warning signs:** `moving=True` immediately on hand entry.

### Pitfall 3: Division by Zero in Velocity
**What goes wrong:** Two consecutive frames have identical timestamps (dt=0), causing division by zero.
**Why it happens:** Duplicate timestamps from camera driver, or test code using identical timestamps.
**How to avoid:** Guard `if dt <= 0: return _NOT_MOVING` early in update loop. SwipeDetector has this guard.
**Warning signs:** ZeroDivisionError in production.

### Pitfall 4: Hysteresis Threshold Order
**What goes wrong:** Setting arm_threshold < disarm_threshold creates inverted hysteresis (always moving or never moving).
**Why it happens:** Configuration error or swapped parameter names.
**How to avoid:** Assert or document that `arm_threshold > disarm_threshold`. Optionally validate in setter.
**Warning signs:** Motion state never transitions, or transitions every frame.

### Pitfall 5: Direction Flickering Near Axis Boundary
**What goes wrong:** Hand moving at ~45 degrees rapidly alternates between horizontal and vertical direction.
**Why it happens:** Small noise in dx/dy flips which axis is dominant.
**How to avoid:** Use axis_ratio (require dominant axis to be N times larger than minor axis). When ratio not met, hold previous direction or report no direction.
**Warning signs:** Rapid LEFT/UP/LEFT/UP alternation in logs.

### Pitfall 6: Buffer Size vs Responsiveness Tradeoff
**What goes wrong:** Large buffer makes motion detection sluggish; small buffer makes it jittery.
**Why it happens:** Velocity computed from buffer endpoints. Larger window = more averaging = more lag.
**How to avoid:** Use buffer_size=5 (about 150ms at 30FPS). This balances smoothing with responsiveness. SwipeDetector uses 6.
**Warning signs:** Noticeable delay between hand movement and moving=True, or flickering with small movements.

## Code Examples

### Direction Classification (adapted from SwipeDetector)
```python
# Source: gesture_keys/swipe.py lines 287-320, adapted for Direction enum
def _classify_direction(
    self, dx: float, dy: float
) -> Optional[Direction]:
    """Classify displacement into a cardinal direction.

    Returns None if movement is too diagonal (axis_ratio not met).
    MediaPipe Y-axis is inverted: lower Y = physically higher.
    """
    abs_dx = abs(dx)
    abs_dy = abs(dy)

    minor = min(abs_dx, abs_dy)
    major = max(abs_dx, abs_dy)

    if minor > 0 and major / minor < self._axis_ratio:
        return None  # Too diagonal

    if abs_dx >= abs_dy:
        return Direction.RIGHT if dx > 0 else Direction.LEFT
    else:
        return Direction.UP if dy < 0 else Direction.DOWN
```

### Hysteresis State Transition
```python
# Core hysteresis logic in update()
velocity = displacement / dt

if not self._moving:
    # Not moving -> check arm threshold
    if velocity >= self._arm_threshold:
        direction = self._classify_direction(dx, dy)
        if direction is not None:
            self._moving = True
            self._direction = direction
            logger.debug("Motion armed: %s (vel=%.3f)", direction.value, velocity)
else:
    # Moving -> check disarm threshold
    if velocity < self._disarm_threshold:
        logger.debug("Motion disarmed (vel=%.3f)", velocity)
        self._moving = False
        self._direction = None
    else:
        # Still moving: update direction if changed
        new_direction = self._classify_direction(dx, dy)
        if new_direction is not None and new_direction != self._direction:
            logger.debug("Motion direction: %s -> %s", self._direction.value, new_direction.value)
            self._direction = new_direction
```

### Settling Frames Guard
```python
# Source: gesture_keys/swipe.py lines 188-193, adapted
if not self._hand_present:
    self._hand_present = True
    self._settling_remaining = self._settling_frames
    self._buffer.clear()
    logger.debug("Hand entry: settling for %d frames", self._settling_frames)

if self._settling_remaining > 0:
    self._settling_remaining -= 1
    # Still accumulate buffer but don't evaluate motion
    return _NOT_MOVING
```

### Output Dataclass
```python
@dataclass(frozen=True)
class MotionState:
    """Per-frame motion detection result.

    Attributes:
        moving: True if hand velocity exceeds arm threshold (or remains above disarm threshold).
        direction: Cardinal direction of motion when moving, None when stationary.
    """
    moving: bool
    direction: Optional[Direction] = None
```

## Design Decisions (Claude's Discretion)

### Velocity as Hysteresis Metric (not displacement)
**Rationale:** Velocity (displacement/time) is frame-rate independent. Displacement alone varies with buffer size and FPS. At 30 FPS vs 60 FPS, the same physical hand speed produces different per-frame displacements but similar velocities. SwipeDetector already computes velocity this way.

### WRIST (landmark index 0) as Reference Point
**Rationale:** SwipeDetector uses WRIST and it works well. The wrist is the most stable large-motion indicator -- fingers and palm center have more local jitter from finger movements. WRIST = 0 constant already exists in swipe.py; define it in motion.py as well.

### Stateful Class (not pure function)
**Rationale:** Every detector in the codebase (SwipeDetector, DistanceFilter, GestureSmoother) is a stateful class with `update()`. A pure function would require passing state in/out every frame, breaking the pattern. The rolling deque buffer and hysteresis state (moving bool, direction, settling counter) are inherently stateful.

### Direction Clears Immediately on Motion Stop
**Rationale:** When `moving` transitions to False, `direction` should become None. The orchestrator (Phase 21) receives `MotionState(moving=False, direction=None)` and knows motion stopped. Holding the last direction after motion stops would create stale data that the orchestrator must reason about -- simpler to clear it.

### Direction Changes Immediately (no pause required)
**Rationale:** If a hand changes direction (e.g., left to right), the direction field should update immediately. Requiring a pause between directions would add latency to legitimate direction changes. The hysteresis already prevents flicker on the moving/not-moving boundary; direction changes within continuous motion should be responsive.

### Default Threshold Values
- **arm_threshold:** 0.25 normalized coords/sec. At 30 FPS with buffer_size=5, this requires about 0.04 displacement over ~167ms -- clearly intentional movement, not jitter.
- **disarm_threshold:** 0.15 normalized coords/sec. Ratio of 1.67x to arm threshold (within the 1.5-2x guideline). Provides meaningful hysteresis gap.
- **axis_ratio:** 2.0 (same as SwipeDetector default). Dominant axis must be 2x the minor axis for a cardinal classification.
- **buffer_size:** 5. About 167ms at 30 FPS. Smaller than SwipeDetector's 6 for slightly faster response (MotionDetector needs quicker onset since it's continuous, not event-based).
- **settling_frames:** 3 (same as SwipeDetector default). Proven value for suppressing hand-entry false positives.

### Extensibility for Diagonal Support
The `_classify_direction` method returns `Optional[Direction]` and uses axis_ratio to reject diagonals. When ETRIG-01 adds diagonal directions, this method is the single point of change: add diagonal Direction values and modify the ratio logic. No other code needs to change.

## State of the Art

| Old Approach (SwipeDetector) | New Approach (MotionDetector) | Why Changed |
|------------------------------|-------------------------------|-------------|
| Event-based: fires once per swipe | Continuous: reports state every frame | Orchestrator needs per-frame motion signal for MOVING_FIRE |
| 3-state machine (IDLE/ARMED/COOLDOWN) | 2-state (moving/not-moving with hysteresis) | No cooldown needed for continuous signal |
| SwipeDirection enum (swipe_left, etc.) | Direction enum (left, right, etc.) | Phase 18 unified direction names |
| Own SwipeDirection enum in swipe.py | Imports Direction from trigger.py | Single source of truth |

## Open Questions

1. **Suppressed parameter needed?**
   - What we know: SwipeDetector has `suppressed` param for activation gate integration (debouncer is_activating)
   - What's unclear: Whether MotionDetector needs the same -- Phase 23 (pipeline integration) will determine this
   - Recommendation: Do NOT add `suppressed` parameter yet. Phase 23 will add it if needed. YAGNI.

2. **Reset method needed?**
   - What we know: SwipeDetector.reset() is called by pipeline for distance-gating transitions
   - What's unclear: Whether MotionDetector needs reset for the same purpose
   - Recommendation: Include a `reset()` method matching the SwipeDetector pattern (clear buffer, reset state). Low cost, high utility for Phase 23.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (pyproject.toml) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_motion.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MOTN-01 | Reports moving=True/False per frame based on velocity | unit | `python -m pytest tests/test_motion.py::TestMotionDetection -x` | No - Wave 0 |
| MOTN-02 | Classifies direction as LEFT/RIGHT/UP/DOWN | unit | `python -m pytest tests/test_motion.py::TestDirectionClassification -x` | No - Wave 0 |
| MOTN-03 | Hysteresis prevents flicker (arm/disarm thresholds) | unit | `python -m pytest tests/test_motion.py::TestHysteresis -x` | No - Wave 0 |
| MOTN-04 | Settling frames on hand entry prevent false motion | unit | `python -m pytest tests/test_motion.py::TestSettlingFrames -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_motion.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_motion.py` -- covers MOTN-01, MOTN-02, MOTN-03, MOTN-04
- [ ] Test helpers: `_make_wrist_landmarks()` and position sequence generators (can borrow from test_swipe.py)

No framework install needed -- pytest already configured and used extensively.

## Sources

### Primary (HIGH confidence)
- `gesture_keys/swipe.py` -- Reference implementation: rolling buffer, velocity calculation, direction classification, settling frames, MediaPipe Y-axis handling
- `gesture_keys/trigger.py` -- Direction enum (LEFT/RIGHT/UP/DOWN) from Phase 18
- `gesture_keys/config.py` -- AppConfig pattern, property setters, YAML section mapping
- `tests/test_swipe.py` -- Test patterns, helper functions, edge case coverage
- `config.yaml` -- Existing `swipe:` section structure as template for `motion:` section

### Secondary (MEDIUM confidence)
- `.planning/phases/19-motiondetector/19-CONTEXT.md` -- User decisions and constraints

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- stdlib only, all patterns proven in existing codebase
- Architecture: HIGH -- direct adaptation of SwipeDetector pattern with simpler state model
- Pitfalls: HIGH -- observed from SwipeDetector implementation and test edge cases
- Design decisions: MEDIUM -- threshold defaults are educated guesses based on SwipeDetector values; may need tuning

**Research date:** 2026-03-26
**Valid until:** 2026-04-25 (stable domain -- hand tracking fundamentals don't change)
