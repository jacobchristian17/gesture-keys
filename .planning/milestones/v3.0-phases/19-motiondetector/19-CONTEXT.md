# Phase 19: MotionDetector - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Continuous per-frame motion state and direction from hand landmarks, replacing SwipeDetector's event-based model. MotionDetector reports moving=True/False with a cardinal direction each frame without maintaining gesture-level state. Pipeline integration (swapping SwipeDetector for MotionDetector) is Phase 23. Config section changes are Phase 20. Orchestrator changes are Phase 21.

</domain>

<decisions>
## Implementation Decisions

### Motion signal output
- Reuse the existing `Direction` enum from `trigger.py` (LEFT/RIGHT/UP/DOWN) — single source of truth from Phase 18
- Output shape and whether to include velocity/confidence is Claude's discretion based on downstream consumer needs (orchestrator MOVING_FIRE signals)
- Landmark tracking point (WRIST vs palm center) is Claude's discretion based on reliability
- Stateful class vs pure function is Claude's discretion based on codebase consistency

### Hysteresis behavior
- Moderate hysteresis gap: arm threshold ~1.5-2x the disarm threshold — prevents jitter without sluggish onset/offset
- Whether direction clears immediately or holds briefly after motion stops is Claude's discretion based on orchestrator needs
- Metric for thresholds (velocity vs displacement) is Claude's discretion — optimize for preventing false triggers at 30 FPS
- Direction change behavior (immediate flip vs require pause) is Claude's discretion

### Config surface
- New `motion:` section in config.yaml — clean break from old `swipe:` section
- Expose arm/disarm thresholds as configurable parameters (motion_arm_threshold, motion_disarm_threshold)
- Settling frames configurable in the `motion:` section

### Diagonal handling
- Current phase: 4-way cardinal only (matching Direction enum)
- Design the direction classification to be extensible for diagonal support later (ETRIG-01 in future requirements)
- Axis ratio concept from SwipeDetector is Claude's discretion — pick whatever approach makes diagonal extension straightforward

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

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `trigger.py:Direction` enum: LEFT/RIGHT/UP/DOWN — MotionDetector reuses this directly
- `swipe.py:SwipeDetector`: Reference implementation for WRIST tracking, rolling buffer, velocity/displacement calculation, settling frames, axis_ratio direction classification — MotionDetector can borrow proven algorithms
- `swipe.py:WRIST = 0`: Landmark index constant

### Established Patterns
- Stateful detector classes: SwipeDetector, DistanceFilter, GestureSmoother all use `update()` method called per frame
- Property setters for hot-reload: SwipeDetector exposes config params as properties
- Rolling deque buffer: SwipeDetector and GestureSmoother both use `collections.deque(maxlen=N)`
- Transition-only logging: log state changes, not every frame
- Config pattern: top-level YAML section -> AppConfig dataclass fields -> load_config() parser with defaults
- MediaPipe Y-axis is inverted: lower Y = physically higher. SwipeDetector._classify_direction documents this.

### Integration Points
- `pipeline.py`: Creates SwipeDetector at line 228, calls update() at line 388 — MotionDetector will eventually replace this (Phase 23)
- `config.py:AppConfig`: Will need new motion config fields (Phase 20)
- `orchestrator.py`: Will consume motion_state parameter (Phase 21, ORCH-01)

</code_context>

<specifics>
## Specific Ideas

- Design direction classification to be extensible for diagonal support (future ETRIG-01)
- MotionDetector is a standalone foundation — no dependencies on other v3.0 phases (parallel with Phase 18)

</specifics>

<deferred>
## Deferred Ideas

- Diagonal direction support (up-left, up-right, etc.) — future requirement ETRIG-01
- Velocity-sensitive triggers (fast vs slow motion) — future requirement ETRIG-03

</deferred>

---

*Phase: 19-motiondetector*
*Context gathered: 2026-03-26*
