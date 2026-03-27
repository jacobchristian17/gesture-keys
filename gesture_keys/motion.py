"""Continuous per-frame motion state reporter for gesture-keys.

Detects hand movement direction from MediaPipe wrist landmarks using
velocity-based hysteresis. Reports moving/not-moving with cardinal
direction every frame -- feeds the orchestrator's MOVING_FIRE signal.

Unlike SwipeDetector (event-based, fires once per swipe), MotionDetector
is a continuous signal source that reports state every frame.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass
from typing import Any, Optional

from gesture_keys.trigger import Direction

logger = logging.getLogger("gesture_keys")

WRIST = 0


@dataclass(frozen=True)
class MotionState:
    """Immutable per-frame motion report.

    Attributes:
        moving: True if hand velocity exceeds hysteresis arm threshold.
        direction: Cardinal direction of movement, or None if not moving.
        velocity: Computed velocity in normalized coords/sec, 0.0 when not moving.
    """

    moving: bool
    direction: Optional[Direction] = None
    velocity: float = 0.0


# Singleton for not-moving state to avoid per-frame allocation.
_NOT_MOVING = MotionState(moving=False, velocity=0.0)


class MotionDetector:
    """Continuous motion detector using velocity hysteresis.

    Reports moving/not-moving with cardinal direction every frame.
    Uses a rolling buffer of wrist positions with arm/disarm thresholds
    to prevent flicker near the motion boundary.

    Args:
        buffer_size: Max number of position samples to keep.
        arm_threshold: Velocity (normalized coords/sec) to transition to moving.
        disarm_threshold: Velocity to transition back to not-moving.
        axis_ratio: Required ratio of dominant to minor axis (rejects diagonals).
        settling_frames: Frames to suppress after hand first appears.
    """

    def __init__(
        self,
        buffer_size: int = 5,
        arm_threshold: float = 0.25,
        disarm_threshold: float = 0.15,
        axis_ratio: float = 2.0,
        settling_frames: int = 3,
    ) -> None:
        self._buffer_size = buffer_size
        self._arm_threshold = arm_threshold
        self._disarm_threshold = disarm_threshold
        self._axis_ratio = axis_ratio
        self._settling_frames = settling_frames

        self._buffer: deque[tuple[float, float, float]] = deque(
            maxlen=buffer_size,
        )
        self._moving: bool = False
        self._direction: Optional[Direction] = None
        self._velocity: float = 0.0
        self._hand_present: bool = False
        self._settling_remaining: int = 0

    # --- Property setters for hot-reload ---

    @property
    def buffer_size(self) -> int:
        return self._buffer_size

    @buffer_size.setter
    def buffer_size(self, value: int) -> None:
        self._buffer_size = value
        self._buffer = deque(self._buffer, maxlen=value)

    @property
    def arm_threshold(self) -> float:
        return self._arm_threshold

    @arm_threshold.setter
    def arm_threshold(self, value: float) -> None:
        self._arm_threshold = value

    @property
    def disarm_threshold(self) -> float:
        return self._disarm_threshold

    @disarm_threshold.setter
    def disarm_threshold(self, value: float) -> None:
        self._disarm_threshold = value

    @property
    def axis_ratio(self) -> float:
        return self._axis_ratio

    @axis_ratio.setter
    def axis_ratio(self, value: float) -> None:
        self._axis_ratio = value

    @property
    def settling_frames(self) -> int:
        return self._settling_frames

    @settling_frames.setter
    def settling_frames(self, value: int) -> None:
        self._settling_frames = value

    def reset(self) -> None:
        """Reset detector state, clearing buffer and motion flags.

        After reset, the next hand appearance triggers settling frames.
        """
        self._buffer.clear()
        self._moving = False
        self._direction = None
        self._velocity = 0.0
        self._hand_present = False
        self._settling_remaining = 0

    def update(
        self, landmarks: Optional[list[Any]], timestamp: float,
    ) -> MotionState:
        """Process a frame of landmarks and return motion state.

        Args:
            landmarks: Hand landmarks list (only index 0 / WRIST is read),
                       or None if hand is lost.
            timestamp: Current time in seconds.

        Returns:
            MotionState with moving flag and optional direction.
        """
        # Hand lost: reset motion state
        if landmarks is None:
            self._hand_present = False
            self._moving = False
            self._direction = None
            self._velocity = 0.0
            self._buffer.clear()
            return _NOT_MOVING

        # Hand entry detection
        if not self._hand_present:
            self._hand_present = True
            self._settling_remaining = self._settling_frames
            self._buffer.clear()
            self._moving = False
            self._direction = None
            self._velocity = 0.0

        # Extract wrist position
        wrist = landmarks[WRIST]
        self._buffer.append((wrist.x, wrist.y, timestamp))

        # Settling guard: suppress motion during settling period
        if self._settling_remaining > 0:
            self._settling_remaining -= 1
            return _NOT_MOVING

        # Need at least 2 entries to compute velocity
        if len(self._buffer) < 2:
            return self._current_state()

        # Compute velocity from oldest to newest buffer entry
        oldest = self._buffer[0]
        newest = self._buffer[-1]
        dx = newest[0] - oldest[0]
        dy = newest[1] - oldest[1]
        dt = newest[2] - oldest[2]

        # Guard against zero or negative dt
        if dt <= 0:
            return _NOT_MOVING

        displacement = math.sqrt(dx * dx + dy * dy)
        velocity = displacement / dt

        # Store velocity for _current_state()
        self._velocity = velocity

        # Hysteresis state transitions
        if not self._moving:
            # Not moving -> check if velocity crosses arm threshold
            if velocity >= self._arm_threshold:
                direction = self._classify_direction(dx, dy)
                if direction is not None:
                    self._moving = True
                    self._direction = direction
                    logger.debug(
                        "Motion armed: %s (vel=%.3f)",
                        direction.value, velocity,
                    )
        else:
            # Moving -> check if velocity drops below disarm threshold
            if velocity < self._disarm_threshold:
                self._moving = False
                self._direction = None
                self._velocity = 0.0
                logger.debug("Motion disarmed (vel=%.3f)", velocity)
            elif velocity >= self._disarm_threshold:
                # Still moving: update direction if changed
                direction = self._classify_direction(dx, dy)
                if direction is not None and direction != self._direction:
                    logger.debug(
                        "Motion direction change: %s -> %s",
                        self._direction.value if self._direction else "None",
                        direction.value,
                    )
                    self._direction = direction

        return self._current_state()

    def _classify_direction(self, dx: float, dy: float) -> Optional[Direction]:
        """Classify displacement vector into a cardinal direction.

        Rejects diagonal movement where the axis ratio is not met.

        Note: MediaPipe Y-axis is inverted -- lower Y values are physically
        higher on screen. So dy < 0 means upward movement.

        Args:
            dx: X displacement (positive = rightward).
            dy: Y displacement (positive = downward in MediaPipe).

        Returns:
            Direction or None if too diagonal.
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
            # MediaPipe Y inverted: dy < 0 = upward movement
            return Direction.UP if dy < 0 else Direction.DOWN

    def _current_state(self) -> MotionState:
        """Return current motion state, using singleton for not-moving."""
        if not self._moving:
            return _NOT_MOVING
        return MotionState(moving=True, direction=self._direction, velocity=self._velocity)
