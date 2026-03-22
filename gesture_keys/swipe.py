"""Velocity-based directional swipe detection for gesture-keys.

Detects left, right, up, down swipes from wrist position sequences.
Uses a rolling buffer of wrist positions with deceleration-based fire timing.

State machine: IDLE -> ARMED -> COOLDOWN -> IDLE (3 states)
- IDLE: Accumulating buffer, checking thresholds
- ARMED: Thresholds met, waiting for deceleration to fire
- COOLDOWN: Recently fired, blocking new swipes
"""

import logging
import math
from collections import deque
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger("gesture_keys")

WRIST = 0


class SwipeDirection(Enum):
    """Cardinal swipe directions. Values match config key names."""

    SWIPE_LEFT = "swipe_left"
    SWIPE_RIGHT = "swipe_right"
    SWIPE_UP = "swipe_up"
    SWIPE_DOWN = "swipe_down"


class _SwipeState(Enum):
    """Internal states of the swipe state machine."""

    IDLE = "IDLE"
    ARMED = "ARMED"
    COOLDOWN = "COOLDOWN"


class SwipeDetector:
    """Detects cardinal swipes from wrist position sequences.

    Uses a rolling deque of wrist positions with velocity and displacement
    thresholds. Fires on deceleration after thresholds are met (ARMED state).

    Args:
        buffer_size: Max number of position samples to keep.
        min_velocity: Minimum speed (normalized coords/sec) to consider a swipe.
        min_displacement: Minimum total displacement to consider a swipe.
        axis_ratio: Required ratio of dominant axis to minor axis (rejects diagonals).
        cooldown_duration: Seconds after firing during which new swipes are blocked.
    """

    def __init__(
        self,
        buffer_size: int = 6,
        min_velocity: float = 0.4,
        min_displacement: float = 0.08,
        axis_ratio: float = 2.0,
        cooldown_duration: float = 0.5,
        settling_frames: int = 3,
    ) -> None:
        self._buffer_size = buffer_size
        self._min_velocity = min_velocity
        self._min_displacement = min_displacement
        self._axis_ratio = axis_ratio
        self._cooldown_duration = cooldown_duration
        self._settling_frames = settling_frames
        self._enabled = True

        self._buffer: deque[tuple[float, float, float]] = deque(maxlen=buffer_size)
        self._state = _SwipeState.IDLE
        self._prev_speed: float = 0.0
        self._cooldown_start: float = 0.0
        self._armed_direction: Optional[SwipeDirection] = None
        self._settling_frames_remaining: int = 0

    # --- Property setters for hot-reload ---

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value

    @property
    def min_velocity(self) -> float:
        return self._min_velocity

    @min_velocity.setter
    def min_velocity(self, value: float) -> None:
        self._min_velocity = value

    @property
    def min_displacement(self) -> float:
        return self._min_displacement

    @min_displacement.setter
    def min_displacement(self, value: float) -> None:
        self._min_displacement = value

    @property
    def axis_ratio(self) -> float:
        return self._axis_ratio

    @axis_ratio.setter
    def axis_ratio(self, value: float) -> None:
        self._axis_ratio = value

    @property
    def cooldown_duration(self) -> float:
        return self._cooldown_duration

    @cooldown_duration.setter
    def cooldown_duration(self, value: float) -> None:
        self._cooldown_duration = value

    @property
    def settling_frames(self) -> int:
        return self._settling_frames

    @settling_frames.setter
    def settling_frames(self, value: int) -> None:
        self._settling_frames = value

    @property
    def is_swiping(self) -> bool:
        """True when a swipe is in progress (ARMED or COOLDOWN state).

        Used by the main loop to suppress static gesture detection during swipes.
        """
        return self._state in (_SwipeState.ARMED, _SwipeState.COOLDOWN)

    def reset(self) -> None:
        """Reset detector state for distance-gating transitions.

        Clears the position buffer and resets tracking fields.
        Preserves COOLDOWN state so active cooldowns expire naturally.
        """
        self._buffer.clear()
        if self._state != _SwipeState.COOLDOWN:
            self._state = _SwipeState.IDLE
        self._prev_speed = 0.0
        self._armed_direction = None

    def update(
        self, landmarks: Optional[list[Any]], timestamp: float
    ) -> Optional[SwipeDirection]:
        """Process a frame of landmarks and return swipe direction if fired.

        Args:
            landmarks: Hand landmarks list (only index 0 / WRIST is read),
                       or None if hand is lost.
            timestamp: Current time in seconds.

        Returns:
            SwipeDirection if a swipe fires this frame, None otherwise.
        """
        if not self._enabled:
            return None

        # Hand lost: clear buffer, reset to IDLE
        if landmarks is None:
            self._buffer.clear()
            if self._state != _SwipeState.COOLDOWN:
                if self._state != _SwipeState.IDLE:
                    logger.debug("Swipe %s -> IDLE: hand lost", self._state.value)
                self._state = _SwipeState.IDLE
            self._prev_speed = 0.0
            self._armed_direction = None
            return None

        # Extract wrist position
        wrist = landmarks[WRIST]
        self._buffer.append((wrist.x, wrist.y, timestamp))

        # Need at least 3 samples for velocity calculation
        if len(self._buffer) < 3:
            return None

        # Handle cooldown
        if self._state == _SwipeState.COOLDOWN:
            if timestamp - self._cooldown_start >= self._cooldown_duration:
                self._state = _SwipeState.IDLE
                self._buffer.clear()
                self._prev_speed = 0.0
                self._settling_frames_remaining = self._settling_frames
                logger.debug("Swipe COOLDOWN -> IDLE")
                return None  # Skip this frame to avoid re-arming on stale motion
            else:
                return None

        # Compute displacement and velocity from buffer endpoints
        oldest = self._buffer[0]
        newest = self._buffer[-1]
        dx = newest[0] - oldest[0]
        dy = newest[1] - oldest[1]
        dt = newest[2] - oldest[2]

        if dt <= 0:
            return None

        abs_dx = abs(dx)
        abs_dy = abs(dy)
        displacement = math.sqrt(dx * dx + dy * dy)
        speed = displacement / dt

        # Compute frame-to-frame speed for deceleration detection
        prev = self._buffer[-2]
        frame_dx = newest[0] - prev[0]
        frame_dy = newest[1] - prev[1]
        frame_dt = newest[2] - prev[2]
        frame_speed = math.sqrt(frame_dx * frame_dx + frame_dy * frame_dy) / frame_dt if frame_dt > 0 else 0.0

        if self._state == _SwipeState.IDLE:
            # Post-cooldown settling guard: prevent re-arming while hand settles
            if self._settling_frames_remaining > 0:
                self._settling_frames_remaining -= 1
                return None

            # Check if thresholds are met to arm
            if (
                displacement >= self._min_displacement
                and speed >= self._min_velocity
            ):
                direction = self._classify_direction(dx, dy, abs_dx, abs_dy)
                if direction is not None:
                    self._state = _SwipeState.ARMED
                    self._armed_direction = direction
                    self._prev_speed = frame_speed
                    logger.debug(
                        "Swipe IDLE -> ARMED: %s (vel=%.2f, disp=%.3f)",
                        direction.value, speed, displacement,
                    )
                    return None

        elif self._state == _SwipeState.ARMED:
            # Check for deceleration: fire when speed drops
            if frame_speed < self._prev_speed:
                # Fire!
                direction = self._armed_direction
                logger.debug(
                    "Swipe ARMED -> COOLDOWN: fired %s",
                    direction.value if direction else "None",
                )
                self._state = _SwipeState.COOLDOWN
                self._cooldown_start = timestamp
                self._buffer.clear()
                self._prev_speed = 0.0
                self._armed_direction = None
                return direction

            # Update tracking
            self._prev_speed = frame_speed

            # Re-check thresholds (hand may have stopped)
            if displacement < self._min_displacement * 0.5:
                self._state = _SwipeState.IDLE
                self._armed_direction = None
                self._prev_speed = 0.0

        self._prev_speed = frame_speed
        return None

    def _classify_direction(
        self, dx: float, dy: float, abs_dx: float, abs_dy: float
    ) -> Optional[SwipeDirection]:
        """Classify displacement into a cardinal direction.

        Rejects diagonal movement where the axis ratio is not met.

        Note: MediaPipe Y-axis is inverted -- lower Y values are physically
        higher on screen. So dy < 0 means upward movement.

        Args:
            dx: Total x displacement (positive = rightward).
            dy: Total y displacement (positive = downward in MediaPipe).
            abs_dx: Absolute x displacement.
            abs_dy: Absolute y displacement.

        Returns:
            SwipeDirection or None if diagonal (axis ratio not met).
        """
        # Prevent division by zero
        minor = min(abs_dx, abs_dy)
        major = max(abs_dx, abs_dy)

        if minor > 0 and major / minor < self._axis_ratio:
            return None  # Too diagonal

        # If minor is 0, it's perfectly along one axis -- allow it
        if abs_dx >= abs_dy:
            # Horizontal swipe
            return SwipeDirection.SWIPE_RIGHT if dx > 0 else SwipeDirection.SWIPE_LEFT
        else:
            # Vertical swipe
            # MediaPipe Y inverted: dy < 0 = upward movement
            return SwipeDirection.SWIPE_UP if dy < 0 else SwipeDirection.SWIPE_DOWN
