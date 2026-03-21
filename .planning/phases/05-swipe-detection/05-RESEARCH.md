# Phase 5: Swipe Detection - Research

**Researched:** 2026-03-21
**Domain:** Wrist velocity tracking, directional swipe classification, rolling buffer algorithms
**Confidence:** HIGH

## Summary

Swipe detection requires tracking wrist position across frames in a rolling buffer, computing velocity vectors, and classifying direction when velocity/displacement thresholds are exceeded. The implementation follows established project patterns -- `collections.deque` for the rolling buffer (like `GestureSmoother`), a state machine for cooldown (like `GestureDebouncer`), and dataclass fields plus `load_config()` parsing for configuration (like `DistanceFilter`).

No new dependencies are needed. All computation uses stdlib `math`, `collections.deque`, and `enum`. The SwipeDetector class runs as a parallel pipeline path alongside the static gesture pipeline, receiving raw landmarks (not smoothed gestures) and producing swipe events that feed directly into `KeystrokeSender`.

**Primary recommendation:** Build a `SwipeDetector` class in `swipe.py` that tracks WRIST landmark position in a rolling deque, computes velocity on each frame, and fires a directional swipe event when displacement and velocity thresholds are met with sufficient axis dominance. Use deceleration-based fire timing (fire when velocity drops after exceeding threshold) to prevent premature fires during acceleration.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Swipe cooldown is configurable in config.yaml (user sets their preferred duration)
- After cooldown expires, the next swipe motion fires immediately -- no "return to rest" requirement
- Cooldown-only re-arm: allows rapid back-and-forth swiping once cooldown elapses
- Individual thresholds exposed in config.yaml: min_velocity, min_displacement, axis_ratio
- Global thresholds apply to all four swipe directions (no per-direction overrides)

### Claude's Discretion
- Fire timing: whether to fire on peak velocity or deceleration -- optimize for preventing false fires
- Diagonal handling: axis ratio threshold and whether to snap-to-dominant-axis or reject ambiguous swipes
- Default threshold values for min_velocity, min_displacement, axis_ratio -- bias toward what satisfies SWIPE-05 (no false fires from repositioning/jitter)
- Whether swipe section missing from config disables swipes or enables with defaults -- follow whichever pattern is most consistent with existing config behavior
- Rolling buffer size (5-8 frames per Phase 4 research)
- Swipe cooldown default value

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| SWIPE-01 | Detect swipe left, right, up, down as distinct gesture types | Velocity vector decomposition into x/y components with axis_ratio dominance check; SwipeDirection enum with four values |
| SWIPE-02 | Map each swipe direction to keyboard command in config.yaml | New `swipes:` config section with `swipe_left:`, `swipe_right:`, etc. sub-keys containing `key:` field, parsed by existing `parse_key_string()` |
| SWIPE-03 | Wrist velocity in rolling buffer, fire once per swipe with cooldown | `collections.deque(maxlen=N)` storing (x, y, timestamp) tuples; state machine IDLE->ARMED->FIRED->COOLDOWN with configurable cooldown_duration |
| SWIPE-04 | Works with any hand pose (no pose gating) | SwipeDetector receives raw landmarks and only reads WRIST position; completely independent of classifier/smoother/debouncer pipeline |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| collections.deque | stdlib | Rolling position buffer | Already used by GestureSmoother; maxlen auto-eviction |
| math | stdlib | sqrt for velocity magnitude | Already used by DistanceFilter |
| enum.Enum | stdlib | SwipeDirection enum | Already used by Gesture and DebounceState |
| dataclasses | stdlib | Config fields | Already used by AppConfig |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| time.perf_counter | stdlib | Frame timestamps for velocity | Already used in both detection loops |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Frame-to-frame delta | Rolling buffer velocity | Buffer is jitter-resistant; frame-to-frame is noisy |
| ML swipe classifier | Threshold-based rules | Rules are transparent, tunable, zero training data needed |

**Installation:**
```bash
# No new packages required -- all stdlib
```

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
    swipe.py           # SwipeDetector class, SwipeDirection enum
    config.py          # +swipe config fields in AppConfig, +parsing in load_config()
    classifier.py      # +SwipeDirection values added to support key mapping lookup
    __main__.py        # +SwipeDetector in preview loop (parallel to static pipeline)
    tray.py            # +SwipeDetector in tray loop (identical changes)
```

### Pattern 1: Velocity-Based Swipe Detection with Deceleration Firing
**What:** Track WRIST position in a rolling deque. On each frame, compute instantaneous velocity from oldest-to-newest positions. When velocity exceeds min_velocity AND displacement exceeds min_displacement AND axis_ratio confirms directional dominance, enter ARMED state. Fire the swipe when velocity begins to decrease (deceleration) -- this catches the end of intentional movement rather than the start.
**When to use:** Every frame where landmarks are detected and hand is in range.
**Example:**
```python
from collections import deque
from enum import Enum
import math

class SwipeDirection(Enum):
    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"

WRIST = 0

class SwipeDetector:
    def __init__(
        self,
        buffer_size: int = 6,
        min_velocity: float = 0.4,
        min_displacement: float = 0.08,
        axis_ratio: float = 2.0,
        cooldown_duration: float = 0.5,
    ) -> None:
        self._buffer: deque = deque(maxlen=buffer_size)
        self._min_velocity = min_velocity
        self._min_displacement = min_displacement
        self._axis_ratio = axis_ratio
        self._cooldown_duration = cooldown_duration
        self._state = "IDLE"  # IDLE | ARMED | COOLDOWN
        self._armed_direction: SwipeDirection | None = None
        self._cooldown_start: float = 0.0
        self._prev_speed: float = 0.0

    def update(self, landmarks, timestamp: float) -> SwipeDirection | None:
        if landmarks is None:
            self._buffer.clear()
            self._state = "IDLE"
            return None

        wrist = landmarks[WRIST]
        self._buffer.append((wrist.x, wrist.y, timestamp))

        if len(self._buffer) < 3:
            return None

        # Cooldown check
        if self._state == "COOLDOWN":
            if timestamp - self._cooldown_start >= self._cooldown_duration:
                self._state = "IDLE"
            else:
                return None

        # Compute velocity from oldest to newest
        x0, y0, t0 = self._buffer[0]
        x1, y1, t1 = self._buffer[-1]
        dt = t1 - t0
        if dt <= 0:
            return None

        dx = x1 - x0
        dy = y1 - y0
        displacement = math.sqrt(dx * dx + dy * dy)
        speed = displacement / dt

        # Check thresholds
        abs_dx = abs(dx)
        abs_dy = abs(dy)

        if self._state == "IDLE":
            if (speed >= self._min_velocity
                    and displacement >= self._min_displacement):
                direction = self._classify_direction(dx, dy, abs_dx, abs_dy)
                if direction is not None:
                    self._state = "ARMED"
                    self._armed_direction = direction
                    self._prev_speed = speed
                    return None

        elif self._state == "ARMED":
            # Fire on deceleration
            if speed < self._prev_speed:
                fired = self._armed_direction
                self._state = "COOLDOWN"
                self._cooldown_start = timestamp
                self._armed_direction = None
                self._buffer.clear()
                return fired
            self._prev_speed = speed

        return None

    def _classify_direction(self, dx, dy, abs_dx, abs_dy):
        # Axis dominance check
        if abs_dx > abs_dy:
            if abs_dx < self._axis_ratio * abs_dy:
                return None  # Too diagonal
            return SwipeDirection.SWIPE_RIGHT if dx > 0 else SwipeDirection.SWIPE_LEFT
        else:
            if abs_dy < self._axis_ratio * abs_dx:
                return None  # Too diagonal
            # MediaPipe: lower y = higher on screen
            return SwipeDirection.SWIPE_UP if dy < 0 else SwipeDirection.SWIPE_DOWN
```

### Pattern 2: Config Section Following Distance Pattern
**What:** Add `swipe:` top-level YAML section with `enabled`, threshold params, cooldown, and sub-mappings. Missing section = swipes disabled (follows `distance:` pattern where missing section = disabled).
**When to use:** Config loading and hot-reload.
**Example:**
```yaml
swipe:
  cooldown: 0.5
  min_velocity: 0.4
  min_displacement: 0.08
  axis_ratio: 2.0

  swipe_left:
    key: alt+left
  swipe_right:
    key: alt+right
  swipe_up:
    key: page_up
  swipe_down:
    key: page_down
```

### Pattern 3: Parallel Pipeline Integration
**What:** SwipeDetector runs after `detector.detect()` in parallel with the static gesture path. It does NOT pass through smoother or debouncer. Both `__main__.py` and `tray.py` loops get identical integration.
**When to use:** Main detection loops.
**Example:**
```python
# After landmarks = detector.detect(frame, timestamp_ms)
# After distance_filter.check(landmarks) passes

# Static gesture path (existing)
raw_gesture = classifier.classify(landmarks)
gesture = smoother.update(raw_gesture)
fire_gesture = debouncer.update(gesture, current_time)

# Swipe path (new, parallel)
swipe_result = swipe_detector.update(landmarks, current_time)
if swipe_result is not None:
    swipe_name = swipe_result.value  # e.g. "swipe_left"
    if swipe_name in key_mappings:
        modifiers, key, key_string = key_mappings[swipe_name]
        sender.send(modifiers, key)
        logger.info("FIRED: %s -> %s", swipe_name, key_string)
```

### Anti-Patterns to Avoid
- **Frame-to-frame deltas for velocity:** Single-frame deltas are dominated by MediaPipe jitter. Always compute velocity across the full buffer window (oldest to newest).
- **Firing on threshold crossing (acceleration):** This fires at the START of motion before direction is confirmed. Deceleration firing waits for the swipe to commit to a direction.
- **Sharing smoother/debouncer with static gestures:** Swipes are transient motion events, not held poses. They need their own independent state machine.
- **Per-direction threshold overrides:** Adds config complexity with minimal benefit. Keep thresholds global per CONTEXT.md decision.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Rolling buffer | Custom array slicing | collections.deque(maxlen=N) | Auto-eviction, O(1) append, already used in project |
| State machine | Ad-hoc boolean flags | Explicit state enum (IDLE/ARMED/COOLDOWN) | Follows debouncer pattern, debuggable, logged transitions |
| Key parsing for swipes | New parser | Existing parse_key_string() | Swipe key strings use identical format to static gestures |
| Config hot-reload | Custom file watching | Existing ConfigWatcher + property setters | Follow DistanceFilter.enabled/min_hand_size pattern |

**Key insight:** The entire swipe detection pipeline reuses existing patterns (deque, state machine, config parsing, KeystrokeSender). The only novel code is the velocity computation and direction classification algorithm.

## Common Pitfalls

### Pitfall 1: MediaPipe Coordinate System Confusion
**What goes wrong:** Y-axis is inverted -- lower Y = higher on screen. Swipe "up" means decreasing Y values.
**Why it happens:** Intuition says "up = positive Y" but MediaPipe normalizes from top-left corner.
**How to avoid:** Explicitly comment: `dy < 0` means upward movement. Test with known coordinate sequences.
**Warning signs:** Up and down swipes are reversed in testing.

### Pitfall 2: Jitter Triggering False Swipes
**What goes wrong:** MediaPipe landmark jitter (1-3 pixel noise) causes small but rapid position changes that register as high velocity over very short time windows.
**Why it happens:** Velocity = displacement/time. If dt is very small but non-zero, even tiny displacements yield high velocity.
**How to avoid:** Require BOTH min_velocity AND min_displacement thresholds. The displacement requirement means jitter (small absolute movement) cannot trigger a swipe regardless of computed velocity.
**Warning signs:** Swipes fire when hand is stationary.

### Pitfall 3: Duplicate Loop Drift
**What goes wrong:** Changes in `__main__.py` preview loop are not identically applied to `tray.py` detection loop, causing behavioral differences.
**Why it happens:** The two loops are copy-pasted with slight variations. Easy to update one and forget the other.
**How to avoid:** Make changes to both loops in the same plan task. Verify both files have identical swipe integration code.
**Warning signs:** Swipes work in preview mode but not tray mode (or vice versa).

### Pitfall 4: Buffer Not Cleared on Hand Loss
**What goes wrong:** Hand disappears for a few frames then reappears in a different position. The buffer contains old positions, making it look like the hand teleported (false swipe).
**Why it happens:** Buffer persists across hand detection gaps.
**How to avoid:** Clear the buffer whenever `landmarks` is None. Reset state to IDLE.
**Warning signs:** False swipes when hand re-enters frame.

### Pitfall 5: Cooldown Not Blocking Swipe Accumulation
**What goes wrong:** During cooldown, buffer keeps accumulating positions. When cooldown ends, an immediate false fire from stale buffer data.
**Why it happens:** Buffer is only cleared on hand loss, not on state transitions.
**How to avoid:** Clear the buffer when entering COOLDOWN state (after firing). When cooldown ends, buffer starts fresh.
**Warning signs:** Double-fires where a second swipe fires immediately after cooldown.

## Code Examples

### Config Dataclass Extension
```python
# In config.py AppConfig dataclass - add swipe fields
@dataclass
class AppConfig:
    # ... existing fields ...
    swipe_enabled: bool = False
    swipe_cooldown: float = 0.5
    swipe_min_velocity: float = 0.4
    swipe_min_displacement: float = 0.08
    swipe_axis_ratio: float = 2.0
    swipe_mappings: dict[str, str] = field(default_factory=dict)
    # swipe_mappings: {"swipe_left": "alt+left", "swipe_right": "alt+right", ...}
```

### Config Loading Extension
```python
# In load_config() - parse swipe section
swipe = raw.get("swipe", {})
swipe_enabled = bool(swipe) and any(
    k.startswith("swipe_") for k in swipe
)

swipe_mappings = {}
for direction in ("swipe_left", "swipe_right", "swipe_up", "swipe_down"):
    if direction in swipe and isinstance(swipe[direction], dict):
        key_str = swipe[direction].get("key")
        if key_str:
            swipe_mappings[direction] = key_str
```

### Key Mapping Parsing (Unified)
```python
# _parse_key_mappings needs to handle both static gestures and swipe mappings
# Swipe mappings can be parsed separately and merged into key_mappings dict
def _parse_swipe_key_mappings(swipe_mappings: dict[str, str]) -> dict:
    mappings = {}
    for direction_name, key_string in swipe_mappings.items():
        modifiers, key = parse_key_string(key_string)
        mappings[direction_name] = (modifiers, key, key_string)
    return mappings
```

### Hot-Reload for Swipe Settings
```python
# In config hot-reload section of both loops
swipe_detector.cooldown_duration = new_config.swipe_cooldown
swipe_detector.min_velocity = new_config.swipe_min_velocity
swipe_detector.min_displacement = new_config.swipe_min_displacement
swipe_detector.axis_ratio = new_config.swipe_axis_ratio
swipe_detector.enabled = new_config.swipe_enabled
# Also re-parse swipe key mappings
swipe_key_mappings = _parse_swipe_key_mappings(new_config.swipe_mappings)
```

## Discretion Recommendations

Based on research and codebase analysis, here are recommendations for Claude's Discretion areas:

### Fire Timing: Deceleration (recommended)
Fire when velocity decreases after crossing thresholds. This prevents premature fires during hand acceleration and ensures the swipe has committed to a direction. Peak velocity firing risks catching the wrong direction if the hand curves.

### Diagonal Handling: Reject ambiguous (recommended)
Use axis_ratio to require one axis to dominate. If neither axis is dominant enough (ratio < threshold), reject the swipe entirely rather than snapping to a direction. This prevents false directional fires when the user moves diagonally or at ambiguous angles.

### Default Threshold Values (recommended, needs empirical validation)
- **min_velocity: 0.4** (normalized coords per second) -- MediaPipe jitter is ~0.01-0.03 per frame; at 30fps, jitter velocity is ~0.3-0.9/s, but displacement will be tiny. Combined with min_displacement, 0.4 is safe.
- **min_displacement: 0.08** (normalized coords) -- A deliberate swipe moves the wrist 0.1-0.3 in normalized space. 0.08 catches moderate swipes. Jitter rarely exceeds 0.02-0.03 total displacement over a buffer window.
- **axis_ratio: 2.0** -- Dominant axis must be 2x the minor axis. This rejects ~45-degree diagonals while accepting moderate off-axis swipes (~25 degrees from cardinal).
- **cooldown: 0.5s** -- Matches existing gesture cooldown_duration default (0.8s) but shorter since swipes are faster actions. Long enough to prevent double-fire on a single swipe motion.

### Missing Config Section: Disable swipes (recommended)
The `distance:` section pattern already establishes "missing section = feature disabled." Follow this for consistency. When `swipe:` section is absent, `swipe_enabled=False`.

### Rolling Buffer Size: 6 frames (recommended)
At 30fps, 6 frames = 200ms window. This captures the middle of a typical swipe (200-500ms total duration) while being short enough to react quickly. Within the 5-8 frame range from Phase 4 research.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| ML-based swipe classifiers | Threshold-based velocity tracking | Always valid for simple 4-direction | No training data needed, transparent tuning |
| Frame-to-frame deltas | Rolling buffer velocity | Standard practice | Jitter-resistant, more reliable |
| Fire on threshold crossing | Fire on deceleration | Community best practice | Prevents premature fires |

**Deprecated/outdated:**
- Single-frame velocity: Too noisy for MediaPipe landmarks; always use multi-frame window

## Open Questions

1. **Exact threshold values need empirical tuning**
   - What we know: Recommended defaults are based on MediaPipe coordinate space analysis and community patterns
   - What's unclear: Exact values depend on webcam FPS, user hand speed, and distance from camera
   - Recommendation: Ship with recommended defaults, expose all thresholds in config.yaml for user tuning

2. **Distance filter interaction with swipe buffer**
   - What we know: When distance filter rejects a frame (hand too far), landmarks are set to None
   - What's unclear: Whether to clear the swipe buffer on distance-filtered frames or preserve it
   - Recommendation: Clear buffer when landmarks is None (consistent with hand-loss clearing). Distance-filtered frames mean hand is too far to reliably track, so buffer should reset.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 9.0.2 (Python 3.13) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_swipe.py -x` |
| Full suite command | `python -m pytest tests/ -x` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| SWIPE-01 | Four distinct swipe directions detected | unit | `python -m pytest tests/test_swipe.py::TestSwipeDirectionClassification -x` | No - Wave 0 |
| SWIPE-02 | Swipe directions map to keyboard commands in config | unit | `python -m pytest tests/test_config.py::TestSwipeConfig -x` | No - Wave 0 |
| SWIPE-03 | Rolling buffer velocity, fire once with cooldown | unit | `python -m pytest tests/test_swipe.py::TestSwipeCooldown -x` | No - Wave 0 |
| SWIPE-04 | Works regardless of hand pose | unit | `python -m pytest tests/test_swipe.py::TestSwipePoseIndependence -x` | No - Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_swipe.py -x`
- **Per wave merge:** `python -m pytest tests/ -x`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_swipe.py` -- covers SWIPE-01, SWIPE-03, SWIPE-04
- [ ] `tests/test_config.py::TestSwipeConfig` -- covers SWIPE-02 (add to existing file)
- [ ] Conftest fixture: `mock_swipe_landmarks_sequence` helper for generating position sequences with known velocities

## Sources

### Primary (HIGH confidence)
- Project source code: `gesture_keys/distance.py`, `gesture_keys/debounce.py`, `gesture_keys/smoother.py`, `gesture_keys/config.py` -- established patterns for buffers, state machines, config
- Project source code: `gesture_keys/__main__.py`, `gesture_keys/tray.py` -- integration points for parallel pipeline
- MediaPipe Hand Landmark documentation -- 21 landmarks, normalized [0,1] coordinates, WRIST=index 0

### Secondary (MEDIUM confidence)
- [MediaPipe Hands documentation](https://mediapipe.readthedocs.io/en/latest/solutions/hands.html) -- landmark structure and coordinate system
- [Android gesture detection patterns](https://developer.android.com/develop/ui/views/touch-and-input/gestures/detector) -- velocity threshold and distance threshold patterns for swipe detection
- [TinyGesture library](https://www.npmjs.com/package/tinygesture?activeTab=readme) -- escape velocity and threshold-based swipe detection patterns

### Tertiary (LOW confidence)
- Default threshold values (0.4 velocity, 0.08 displacement, 2.0 axis_ratio) -- derived from analysis of MediaPipe coordinate space but not empirically tested on this specific application

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- all stdlib, no new dependencies, patterns directly from existing codebase
- Architecture: HIGH -- parallel pipeline path established in Phase 4 research, config/state-machine patterns proven
- Pitfalls: HIGH -- identified from direct codebase analysis (coordinate system, duplicate loops, buffer lifecycle)
- Default thresholds: LOW -- analytically reasonable but need empirical tuning

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (stable -- stdlib only, no version dependencies)
