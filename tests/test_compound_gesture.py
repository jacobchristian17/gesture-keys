"""Tests for static-to-swipe compound gesture integration."""

from gesture_keys.classifier import Gesture
from gesture_keys.debounce import DebounceAction, DebounceState, GestureDebouncer
from gesture_keys.swipe import SwipeDirection


class TestCompoundGestureIntegration:
    def test_full_compound_flow(self):
        d = GestureDebouncer(
            swipe_gesture_directions={"peace": {"swipe_left", "swipe_right"}},
            swipe_window=0.2,
        )
        d.update(Gesture.PEACE, 0.0)
        assert d.state == DebounceState.SWIPE_WINDOW
        result = d.update(Gesture.PEACE, 0.1, swipe_direction=SwipeDirection.SWIPE_LEFT)
        assert result.action == DebounceAction.COMPOUND_FIRE
        assert result.gesture == Gesture.PEACE
        assert result.direction == SwipeDirection.SWIPE_LEFT

    def test_static_fallback(self):
        d = GestureDebouncer(
            swipe_gesture_directions={"peace": {"swipe_left"}},
            swipe_window=0.2,
        )
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.25)
        assert result.action == DebounceAction.FIRE

    def test_non_swipe_gesture_unaffected(self):
        d = GestureDebouncer(
            activation_delay=0.15,
            swipe_gesture_directions={"peace": {"swipe_left"}},
        )
        d.update(Gesture.FIST, 0.0)
        assert d.state == DebounceState.ACTIVATING
        result = d.update(Gesture.FIST, 0.2)
        assert result.action == DebounceAction.FIRE

    def test_swipe_not_double_fired(self):
        """COMPOUND_FIRE consumes the swipe — it should not also be standalone."""
        d = GestureDebouncer(
            swipe_gesture_directions={"peace": {"swipe_left"}},
            swipe_window=0.2,
        )
        d.update(Gesture.PEACE, 0.0)
        result = d.update(Gesture.PEACE, 0.1, swipe_direction=SwipeDirection.SWIPE_LEFT)
        assert result.action == DebounceAction.COMPOUND_FIRE
        result2 = d.update(None, 0.15)
        assert result2 is None
