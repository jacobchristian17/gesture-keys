"""Scroll sending via pynput mouse controller.

Converts hand direction and velocity into mouse scroll events with
velocity-proportional ticks, nonlinear acceleration, EMA jitter
smoothing, and tick clamping.
"""

import logging
import math
from typing import Optional

from pynput.mouse import Controller

from gesture_keys.trigger import Direction

logger = logging.getLogger("gesture_keys")


class ScrollSender:
    """Sends scroll events to the foreground application via pynput.

    Creates a single mouse Controller instance and reuses it for all
    scroll calls. Applies EMA smoothing to velocity input and a
    nonlinear acceleration curve to map velocity to scroll ticks.

    Args:
        scroll_speed: Multiplier for velocity before curve application.
        max_ticks: Maximum ticks per scroll call (clamp ceiling).
        ema_alpha: EMA smoothing factor (0-1). Higher = more reactive.
    """

    def __init__(
        self,
        scroll_speed: float = 3.0,
        max_ticks: int = 10,
        ema_alpha: float = 0.3,
    ) -> None:
        self._controller = Controller()
        self._scroll_speed = scroll_speed
        self._max_ticks = max_ticks
        self._ema_alpha = ema_alpha
        self._smoothed_velocity: float = 0.0
        self._has_prev: bool = False

    def scroll(
        self,
        direction: Direction,
        velocity: float,
        *,
        scroll_speed: Optional[float] = None,
        min_ticks: Optional[int] = None,
        max_ticks: Optional[int] = None,
    ) -> None:
        """Scroll in the given direction at velocity-proportional speed.

        Applies EMA smoothing to the velocity, then converts to ticks
        via a nonlinear acceleration curve (power 1.5). Ticks are
        clamped to [min_ticks, max_ticks].

        Args:
            direction: Cardinal direction to scroll.
            velocity: Raw velocity magnitude (0.0+).
            scroll_speed: Per-call speed multiplier override (None = use instance default).
            min_ticks: Per-call minimum ticks override (None = use default of 1).
            max_ticks: Per-call maximum ticks override (None = use instance default).
        """
        # EMA smoothing
        if not self._has_prev:
            self._smoothed_velocity = velocity
            self._has_prev = True
        else:
            self._smoothed_velocity = (
                self._ema_alpha * velocity
                + (1 - self._ema_alpha) * self._smoothed_velocity
            )

        # Resolve per-call overrides vs instance defaults
        effective_speed = scroll_speed if scroll_speed is not None else self._scroll_speed
        effective_min = min_ticks if min_ticks is not None else 1
        effective_max = max_ticks if max_ticks is not None else self._max_ticks

        # Nonlinear acceleration curve
        raw = self._smoothed_velocity * effective_speed
        curved = math.pow(raw, 1.5)
        ticks = max(effective_min, min(effective_max, round(curved)))

        # Route direction to scroll axis
        if direction == Direction.UP:
            self._controller.scroll(0, ticks)
        elif direction == Direction.DOWN:
            self._controller.scroll(0, -ticks)
        elif direction == Direction.LEFT:
            self._controller.scroll(-ticks, 0)
        elif direction == Direction.RIGHT:
            self._controller.scroll(ticks, 0)

        logger.debug(
            "scroll %s: velocity=%.3f smoothed=%.3f ticks=%d",
            direction.value,
            velocity,
            self._smoothed_velocity,
            ticks,
        )

    def reset(self) -> None:
        """Clear EMA state. Call when gesture tracking is lost."""
        self._smoothed_velocity = 0.0
        self._has_prev = False
