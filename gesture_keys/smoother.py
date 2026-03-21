"""Majority-vote gesture smoothing to prevent single-frame flicker."""

from collections import Counter, deque
from typing import Any, Optional


class GestureSmoother:
    """Buffer recent gesture classifications and return majority vote.

    Prevents single-frame misclassifications from causing gesture flicker
    by requiring a gesture to be the majority in a sliding window before
    it is reported.
    """

    def __init__(self, window_size: int = 3):
        """Initialize smoother with a given window size.

        Args:
            window_size: Number of frames in the smoothing buffer.
        """
        self._window_size = window_size
        self._buffer: deque = deque(maxlen=window_size)

    def update(self, gesture: Any) -> Optional[Any]:
        """Add a gesture to the buffer and return the smoothed result.

        Args:
            gesture: Gesture enum value or None.

        Returns:
            The majority gesture if the buffer is full and there is a
            clear majority (count > window_size / 2). Returns None if
            the buffer is not yet full or there is no clear majority.
        """
        self._buffer.append(gesture)

        if len(self._buffer) < self._window_size:
            return None

        counts = Counter(self._buffer)
        most_common_value, most_common_count = counts.most_common(1)[0]

        # Require strict majority: count must be more than half the window
        if most_common_count <= self._window_size / 2:
            return None

        return most_common_value

    def reset(self) -> None:
        """Clear the smoothing buffer."""
        self._buffer.clear()
