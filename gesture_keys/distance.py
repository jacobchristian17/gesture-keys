"""Distance gating filter for gesture-keys.

Filters hand landmarks based on palm span (wrist-to-MCP distance)
to suppress gestures when the hand is too far from the camera.
"""

import logging
import math
from typing import Any

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
            logger.debug(
                "Hand in range: palm span %.3f >= threshold %.3f",
                palm_span,
                self._min_hand_size,
            )
        elif not in_range and self._was_in_range:
            logger.debug(
                "Hand filtered: palm span %.3f < threshold %.3f",
                palm_span,
                self._min_hand_size,
            )

        self._was_in_range = in_range
        return in_range

    def _compute_palm_span(self, landmarks: list[Any]) -> float:
        """Euclidean distance between wrist and middle MCP in normalized coords."""
        dx = landmarks[WRIST].x - landmarks[MIDDLE_MCP].x
        dy = landmarks[WRIST].y - landmarks[MIDDLE_MCP].y
        return math.sqrt(dx * dx + dy * dy)
