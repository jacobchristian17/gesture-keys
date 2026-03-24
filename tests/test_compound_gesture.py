"""Tests for static-to-swipe compound gesture integration."""

from gesture_keys.classifier import Gesture
from gesture_keys.orchestrator import (
    GestureOrchestrator,
    LifecycleState,
    OrchestratorAction,
)
from gesture_keys.swipe import SwipeDirection


class TestCompoundGestureIntegration:
    def test_full_compound_flow(self):
        o = GestureOrchestrator(
            swipe_gesture_directions={"peace": {"swipe_left", "swipe_right"}},
            swipe_window=0.2,
        )
        result = o.update(Gesture.PEACE, 0.0)
        assert result.outer_state == LifecycleState.SWIPE_WINDOW
        result = o.update(Gesture.PEACE, 0.1, swipe_direction=SwipeDirection.SWIPE_LEFT)
        assert len(result.signals) == 1
        assert result.signals[0].action == OrchestratorAction.COMPOUND_FIRE
        assert result.signals[0].gesture == Gesture.PEACE
        assert result.signals[0].direction == SwipeDirection.SWIPE_LEFT

    def test_static_fallback(self):
        o = GestureOrchestrator(
            swipe_gesture_directions={"peace": {"swipe_left"}},
            swipe_window=0.2,
        )
        o.update(Gesture.PEACE, 0.0)
        result = o.update(Gesture.PEACE, 0.25)
        assert len(result.signals) == 1
        assert result.signals[0].action == OrchestratorAction.FIRE

    def test_non_swipe_gesture_unaffected(self):
        o = GestureOrchestrator(
            activation_delay=0.15,
            swipe_gesture_directions={"peace": {"swipe_left"}},
        )
        result = o.update(Gesture.FIST, 0.0)
        assert result.outer_state == LifecycleState.ACTIVATING
        result = o.update(Gesture.FIST, 0.2)
        assert len(result.signals) == 1
        assert result.signals[0].action == OrchestratorAction.FIRE

    def test_swipe_not_double_fired(self):
        """COMPOUND_FIRE consumes the swipe -- it should not also be standalone."""
        o = GestureOrchestrator(
            swipe_gesture_directions={"peace": {"swipe_left"}},
            swipe_window=0.2,
        )
        o.update(Gesture.PEACE, 0.0)
        result = o.update(Gesture.PEACE, 0.1, swipe_direction=SwipeDirection.SWIPE_LEFT)
        assert len(result.signals) == 1
        assert result.signals[0].action == OrchestratorAction.COMPOUND_FIRE
        result2 = o.update(None, 0.15)
        assert len(result2.signals) == 0
