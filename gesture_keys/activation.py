"""Activation gate: a gesture arms the system for a timed window.

When enabled, keystrokes only fire during the armed window.
The activation gesture itself does not fire a keystroke.
"""

import logging
from typing import Optional

from gesture_keys.classifier import Gesture

logger = logging.getLogger("gesture_keys")


class ActivationGate:
    """Gates keystroke firing behind an activation gesture.

    Args:
        gesture: The gesture that arms the system.
        duration: Seconds the system stays armed after activation.
    """

    def __init__(self, gesture: Gesture, duration: float = 3.0) -> None:
        self._gesture = gesture
        self._duration = duration
        self._armed_at: Optional[float] = None
        self._armed: bool = False

    @property
    def gesture(self) -> Gesture:
        """The gesture that activates the gate."""
        return self._gesture

    @property
    def duration(self) -> float:
        """Duration in seconds the gate stays armed."""
        return self._duration

    @duration.setter
    def duration(self, value: float) -> None:
        self._duration = value

    def is_armed(self) -> bool:
        """Check if the gate is currently armed."""
        return self._armed

    def tick(self, timestamp: float) -> None:
        """Called every frame. Detects and logs expiry."""
        if not self._armed:
            return
        if (timestamp - self._armed_at) >= self._duration:
            self._armed = False
            elapsed = timestamp - self._armed_at
            self._armed_at = None
            logger.info("Activation gate EXPIRED after %.1fs", elapsed)

    def arm(self, timestamp: float) -> None:
        """Arm the gate, starting the activation window."""
        self._armed_at = timestamp
        self._armed = True
        logger.info("Activation gate ARMED for %.1fs", self._duration)

    def keep_alive(self, timestamp: float) -> None:
        """Reset the expiry timer without changing armed state.

        Called when an action fires to ensure the gate only expires
        after continuous idle time.
        """
        if self._armed:
            self._armed_at = timestamp

    def reset(self) -> None:
        """Reset the gate to disarmed state."""
        self._armed_at = None
        self._armed = False
