# Phase 4: Distance Gating - Research

**Researched:** 2026-03-21
**Domain:** Palm span distance filtering in MediaPipe hand landmark pipeline
**Confidence:** HIGH

## Summary

Phase 4 adds a distance gating filter to the existing gesture detection pipeline. The filter computes the Euclidean distance between the wrist (landmark 0) and middle finger MCP (landmark 9) in normalized x,y coordinates, comparing it against a user-configured threshold. When the palm span is below the threshold, the hand is considered "too far" and gestures are suppressed. This is a pure per-frame math operation with no state beyond a transition flag for logging.

The implementation touches four files: `config.py` (new fields), a new `distance.py` module (DistanceFilter class), and both detection loops (`__main__.py` and `tray.py`). No new dependencies are needed -- only `math.sqrt` from stdlib. The WRIST-to-MIDDLE_MCP pair is specifically chosen because it is pose-invariant (skeletal joints unaffected by finger articulation), unlike fingertip-based spans that change with every gesture.

**Primary recommendation:** Create a `DistanceFilter` class in `distance.py` that takes landmarks and returns pass/fail, insert it between `detector.detect()` and `classifier.classify()` in both loops, and treat a filtered hand identically to "no hand detected" (feed `None` to smoother, reset smoother/debouncer on transition).

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions
- New top-level `distance:` section in config.yaml with `enabled` (bool) and `min_hand_size` (float) keys
- When the `distance:` section is missing entirely, distance gating is disabled -- v1.0 configs work with zero changes
- Users opt in by adding the `distance:` section to their config
- DEBUG-level log when hand is filtered by distance (e.g., "Hand filtered: palm span 0.08 < threshold 0.15")
- Log on transitions only -- once when hand goes out of range, once when it returns -- not every frame
- Reset smoother buffer and debouncer state when hand is gated out of range, preventing stale gestures from firing when hand returns
- Distance gating settings (`enabled`, `min_hand_size`) hot-reload when config.yaml is edited, consistent with existing detection setting hot-reload

### Claude's Discretion
- Default `min_hand_size` threshold value
- Whether `enabled: false` preserves or ignores the threshold value (must satisfy success criteria #2: toggle without removing values)
- Exact position of distance check in the pipeline (before classifier vs after detector)
- Any additional config validation or error messages

### Deferred Ideas (OUT OF SCOPE)
None -- discussion stayed within phase scope

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| DIST-01 | User can configure a minimum hand size threshold in config.yaml to ignore hands too far from the camera | New `distance:` config section with `enabled` and `min_hand_size` fields in AppConfig; `load_config()` parses optional distance section |
| DIST-02 | Gestures are only detected when the hand's palm span (wrist-to-MCP distance) exceeds the configured threshold | DistanceFilter class computes WRIST-to-MIDDLE_MCP Euclidean distance; inserted before classifier in both loops; filtered hand treated as no-hand |

</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| math (stdlib) | n/a | `math.sqrt` for Euclidean distance | Already used in classifier.py for pinch distance; no external dependency needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| yaml (PyYAML) | existing | Config parsing | Already a project dependency; distance section parsed same way as detection section |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| math.sqrt | math.dist (Python 3.8+) | `math.dist` is cleaner but the codebase already uses explicit `dx*dx + dy*dy` pattern in classifier.py -- stay consistent |
| WRIST-to-MIDDLE_MCP | Bounding box area | Bounding box varies with finger articulation; WRIST-to-MIDDLE_MCP is pose-invariant |
| WRIST-to-MIDDLE_MCP | MediaPipe z-coordinate | z is relative to wrist (inter-landmark depth), NOT camera distance -- do not use |

**Installation:**
```bash
# No new packages needed
```

## Architecture Patterns

### Recommended Project Structure
```
gesture_keys/
    distance.py          # NEW: DistanceFilter class
    config.py            # MODIFIED: add distance_enabled, min_hand_size fields
    __main__.py           # MODIFIED: insert distance check in preview loop
    tray.py              # MODIFIED: insert distance check in tray loop
```

### Pattern 1: DistanceFilter Class
**What:** Stateless per-frame filter that computes palm span and returns pass/fail
**When to use:** Every frame after landmarks are detected, before classification
**Example:**
```python
# Source: project v1.1 research + existing classifier.py pattern
import math
import logging
from typing import Any, Optional

logger = logging.getLogger("gesture_keys")

WRIST = 0
MIDDLE_MCP = 9

class DistanceFilter:
    """Filter hands by palm span (wrist-to-MCP distance).

    Args:
        min_hand_size: Minimum palm span in normalized coordinates.
        enabled: Whether distance gating is active.
    """

    def __init__(self, min_hand_size: float = 0.15, enabled: bool = True) -> None:
        self._min_hand_size = min_hand_size
        self._enabled = enabled
        self._was_in_range = True  # Track transitions for logging

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def min_hand_size(self) -> float:
        return self._min_hand_size

    @min_hand_size.setter
    def min_hand_size(self, value: float) -> None:
        self._min_hand_size = value

    def check(self, landmarks: list[Any]) -> bool:
        """Check if hand is within distance range.

        Args:
            landmarks: 21 MediaPipe hand landmarks.

        Returns:
            True if hand passes filter (close enough or gating disabled).
        """
        if not self._enabled:
            return True

        palm_span = self._compute_palm_span(landmarks)
        in_range = palm_span >= self._min_hand_size

        # Log transitions only
        if in_range and not self._was_in_range:
            logger.debug("Hand in range: palm span %.3f >= threshold %.3f",
                        palm_span, self._min_hand_size)
        elif not in_range and self._was_in_range:
            logger.debug("Hand filtered: palm span %.3f < threshold %.3f",
                        palm_span, self._min_hand_size)

        self._was_in_range = in_range
        return in_range

    def _compute_palm_span(self, landmarks: list[Any]) -> float:
        """Euclidean distance between wrist and middle MCP in normalized coords."""
        dx = landmarks[WRIST].x - landmarks[MIDDLE_MCP].x
        dy = landmarks[WRIST].y - landmarks[MIDDLE_MCP].y
        return math.sqrt(dx * dx + dy * dy)
```

### Pattern 2: Config Section Parsing (Optional Section)
**What:** Parse an optional config section with defaults when missing
**When to use:** Adding new optional config sections that must not break existing configs
**Example:**
```python
# In load_config(), after existing parsing:
distance = raw.get("distance", {})
# When section is missing entirely, distance gating is disabled
distance_enabled = bool(distance.get("enabled", False)) if distance else False
min_hand_size = float(distance.get("min_hand_size", 0.15)) if distance else 0.15
```

### Pattern 3: Pipeline Integration Point
**What:** Insert distance check between detector and classifier
**When to use:** Both `__main__.py` and `tray.py` detection loops
**Example:**
```python
# Current pattern:
landmarks = detector.detect(frame, timestamp_ms)
if landmarks:
    raw_gesture = classifier.classify(landmarks)
    gesture = smoother.update(raw_gesture)
else:
    gesture = smoother.update(None)

# New pattern:
landmarks = detector.detect(frame, timestamp_ms)
if landmarks and not distance_filter.check(landmarks):
    # Hand detected but too far -- treat as no hand
    landmarks = None  # or use a flag; key: smoother/debouncer get None
if landmarks:
    raw_gesture = classifier.classify(landmarks)
    gesture = smoother.update(raw_gesture)
else:
    gesture = smoother.update(None)
```

### Pattern 4: Smoother/Debouncer Reset on Transition
**What:** Reset pipeline state when hand transitions out of range
**When to use:** When distance filter rejects a previously-in-range hand
**Example:**
```python
# Track previous in-range state for reset logic
if landmarks_raw and not distance_filter.check(landmarks_raw):
    # Hand went out of range -- reset downstream state
    smoother.reset()
    debouncer.reset()
    landmarks = None
```
Note: The transition tracking in DistanceFilter handles the logging; the loop code handles the reset. This keeps DistanceFilter stateless regarding pipeline concerns.

### Pattern 5: Hot-Reload of Distance Settings
**What:** Update distance filter settings when config is reloaded
**When to use:** In the existing hot-reload blocks in both loops
**Example:**
```python
# In existing hot-reload block, after debouncer updates:
distance_filter.enabled = new_config.distance_enabled
distance_filter.min_hand_size = new_config.min_hand_size
```

### Anti-Patterns to Avoid
- **Using z-coordinate for distance:** MediaPipe z is relative to wrist, not camera. It measures inter-landmark depth, not how far the hand is from the camera. Will produce random values unrelated to hand proximity.
- **Checking distance after classification:** Wastes classification compute and risks race conditions with state in smoother/debouncer. Filter early.
- **Logging every filtered frame:** At 30fps this floods logs. Use transition-only logging.
- **Coupling DistanceFilter to smoother/debouncer directly:** Keep the filter a pure check; let the loop code handle reset logic. This keeps components decoupled and testable.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Euclidean distance | Vector math library | `math.sqrt(dx*dx + dy*dy)` | Two-point 2D distance is a one-liner; adding numpy for this is massive overkill |
| Config file watching | Custom inotify/FSEvents | Existing `ConfigWatcher` class | Already built, tested, and used in both loops |
| YAML parsing | Custom parser | Existing `yaml.safe_load` + `load_config` | Already handles errors, validation, and section extraction |

## Common Pitfalls

### Pitfall 1: Forgetting to modify both detection loops
**What goes wrong:** Distance gating works in preview mode but not in tray mode (or vice versa)
**Why it happens:** `__main__.py:run_preview_mode()` and `tray.py:TrayApp._detection_loop()` have duplicated pipeline code
**How to avoid:** Modify both loops identically. The changes are: (1) create DistanceFilter after config load, (2) insert check between detect and classify, (3) add reset on out-of-range transition, (4) add hot-reload update
**Warning signs:** Manual testing only in preview mode

### Pitfall 2: Stale smoother/debouncer state after distance filter
**What goes wrong:** Hand goes out of range, comes back, and the previous gesture immediately fires without being held again
**Why it happens:** Smoother buffer still has old gesture votes; debouncer may be in ACTIVATING state with accumulated time
**How to avoid:** Call `smoother.reset()` and `debouncer.reset()` when the distance filter transitions from in-range to out-of-range
**Warning signs:** Gestures fire immediately when hand returns to range

### Pitfall 3: Missing config section breaks existing users
**What goes wrong:** v1.0 configs without a `distance:` section raise errors
**Why it happens:** Config parser requires the new section
**How to avoid:** Make the entire `distance:` section optional with `.get("distance", {})`. When missing, `distance_enabled` defaults to `False`, preserving v1.0 behavior exactly
**Warning signs:** `ValueError` or `KeyError` when loading old configs

### Pitfall 4: Not distinguishing "no hand" from "hand too far"
**What goes wrong:** When hand is too far, the system behaves identically to no hand -- but the transition logging and reset behavior should differ
**Why it happens:** Naively setting `landmarks = None` loses the information
**How to avoid:** Check distance before nullifying landmarks; the DistanceFilter tracks transitions internally for logging. The loop only needs to know "should I classify?" (answer: no if filtered)
**Warning signs:** No DEBUG log messages about distance filtering

## Code Examples

### Palm Span Calculation (verified math)
```python
# Source: project v1.1 research STACK.md + MediaPipe landmark docs
# WRIST = landmark 0, MIDDLE_MCP = landmark 9
# These are skeletal joints -- distance between them is pose-invariant
# (unaffected by finger curl/extension)
import math

def palm_span(landmarks):
    dx = landmarks[0].x - landmarks[9].x
    dy = landmarks[0].y - landmarks[9].y
    return math.sqrt(dx * dx + dy * dy)
```

### Config YAML Example
```yaml
# New optional section -- omit entirely for v1.0 behavior
distance:
  enabled: true
  min_hand_size: 0.15  # normalized coordinate units
```

### AppConfig Additions
```python
@dataclass
class AppConfig:
    camera_index: int = 0
    smoothing_window: int = 3
    activation_delay: float = 0.4
    cooldown_duration: float = 0.8
    gestures: dict[str, dict[str, Any]] = field(default_factory=dict)
    # New distance gating fields
    distance_enabled: bool = False
    min_hand_size: float = 0.15
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Bounding box area for distance | Landmark pair distance | Standard practice | Bounding box varies with hand pose; landmark pair is stable |
| MediaPipe z for camera distance | 2D palm span proxy | Documented in MediaPipe issues | z measures depth between landmarks, not camera distance |

## Open Questions

1. **Default min_hand_size value**
   - What we know: Normalized MediaPipe coordinates put typical palm span at 0.10-0.30 depending on distance and webcam FOV
   - What's unclear: Exact default that works across common webcam setups
   - Recommendation: Use 0.15 as default (mid-range). User MUST calibrate via preview overlay (Phase 7). Document that this value varies by webcam and should be tuned. Err on the low side to avoid frustrating "my gestures stopped working" experiences.

2. **enabled: false behavior**
   - What we know: Must satisfy success criteria #2 (toggle without removing values)
   - Recommendation: `enabled: false` preserves `min_hand_size` in config and in AppConfig but the DistanceFilter.check() always returns True. This is the simplest approach and matches how users expect toggle behavior to work.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (existing) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/test_distance.py tests/test_config.py -x -q` |
| Full suite command | `python -m pytest tests/ -x -q` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| DIST-01 | Config loads distance section with enabled + min_hand_size | unit | `python -m pytest tests/test_config.py -x -q -k distance` | No -- Wave 0 |
| DIST-01 | Config without distance section defaults to disabled | unit | `python -m pytest tests/test_config.py -x -q -k distance_missing` | No -- Wave 0 |
| DIST-02 | DistanceFilter passes hand when palm span >= threshold | unit | `python -m pytest tests/test_distance.py -x -q -k passes` | No -- Wave 0 |
| DIST-02 | DistanceFilter rejects hand when palm span < threshold | unit | `python -m pytest tests/test_distance.py -x -q -k rejects` | No -- Wave 0 |
| DIST-02 | DistanceFilter always passes when disabled | unit | `python -m pytest tests/test_distance.py -x -q -k disabled` | No -- Wave 0 |
| DIST-02 | Transition logging fires once per range change | unit | `python -m pytest tests/test_distance.py -x -q -k transition` | No -- Wave 0 |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/test_distance.py tests/test_config.py -x -q`
- **Per wave merge:** `python -m pytest tests/ -x -q`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_distance.py` -- covers DIST-02 (DistanceFilter behavior, pass/fail/disabled/transition)
- [ ] Update `tests/test_config.py` -- covers DIST-01 (distance config section parsing, defaults, missing section)
- [ ] Update `tests/conftest.py` -- add landmark fixtures with known palm span values for distance testing

## Sources

### Primary (HIGH confidence)
- Existing codebase: `classifier.py` (WRIST=0, MIDDLE_MCP=9, Euclidean distance pattern), `config.py` (AppConfig dataclass, load_config, ConfigWatcher), `__main__.py` and `tray.py` (detection loop structure, hot-reload pattern)
- `.planning/research/SUMMARY.md` -- v1.1 research covering distance gating approach, z-coordinate pitfall, WRIST-to-MIDDLE_MCP rationale
- `.planning/phases/04-distance-gating/04-CONTEXT.md` -- user decisions on config structure, logging, hot-reload

### Secondary (MEDIUM confidence)
- [MediaPipe z-value discussion (Issue #742)](https://github.com/google/mediapipe/issues/742) -- z is relative to wrist, not camera distance
- [MediaPipe camera distance discussion (Issue #1153)](https://github.com/google/mediapipe/issues/1153) -- bounding box size as proxy

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH -- no new dependencies, all patterns already in codebase
- Architecture: HIGH -- insertion point clearly identified in both loops, follows existing patterns
- Pitfalls: HIGH -- z-coordinate trap well-documented, dual-loop modification is known tech debt

**Research date:** 2026-03-21
**Valid until:** 2026-04-21 (stable -- no external dependencies or version-sensitive APIs)
