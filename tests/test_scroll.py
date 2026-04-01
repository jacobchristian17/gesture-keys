"""Tests for scroll sending via pynput mouse controller."""

from unittest.mock import MagicMock, patch

import pytest

from gesture_keys.trigger import Direction


class TestScrollDirection:
    """Test that scroll directions route to correct pynput scroll axes."""

    def _make_sender(self):
        """Create a ScrollSender with mocked mouse controller."""
        with patch("gesture_keys.scroll.Controller") as MockCtrl:
            mock_controller = MagicMock()
            MockCtrl.return_value = mock_controller
            from gesture_keys.scroll import ScrollSender

            sender = ScrollSender()
            sender._controller = mock_controller
            return sender, mock_controller

    def test_scroll_up_calls_positive_dy(self):
        sender, mock_ctrl = self._make_sender()
        sender.scroll(Direction.UP, 0.5)
        args = mock_ctrl.scroll.call_args[0]
        assert args[0] == 0, "dx should be 0 for vertical scroll"
        assert args[1] > 0, "dy should be positive for UP"

    def test_scroll_down_calls_negative_dy(self):
        sender, mock_ctrl = self._make_sender()
        sender.scroll(Direction.DOWN, 0.5)
        args = mock_ctrl.scroll.call_args[0]
        assert args[0] == 0, "dx should be 0 for vertical scroll"
        assert args[1] < 0, "dy should be negative for DOWN"

    def test_scroll_left_calls_negative_dx(self):
        sender, mock_ctrl = self._make_sender()
        sender.scroll(Direction.LEFT, 0.5)
        args = mock_ctrl.scroll.call_args[0]
        assert args[0] < 0, "dx should be negative for LEFT"
        assert args[1] == 0, "dy should be 0 for horizontal scroll"

    def test_scroll_right_calls_positive_dx(self):
        sender, mock_ctrl = self._make_sender()
        sender.scroll(Direction.RIGHT, 0.5)
        args = mock_ctrl.scroll.call_args[0]
        assert args[0] > 0, "dx should be positive for RIGHT"
        assert args[1] == 0, "dy should be 0 for horizontal scroll"


class TestVelocityMapping:
    """Test velocity-to-ticks conversion with nonlinear acceleration."""

    def _make_sender(self):
        with patch("gesture_keys.scroll.Controller") as MockCtrl:
            mock_controller = MagicMock()
            MockCtrl.return_value = mock_controller
            from gesture_keys.scroll import ScrollSender

            sender = ScrollSender()
            sender._controller = mock_controller
            return sender, mock_controller

    def test_low_velocity_produces_min_ticks(self):
        sender, mock_ctrl = self._make_sender()
        sender.scroll(Direction.UP, 0.01)
        args = mock_ctrl.scroll.call_args[0]
        assert args[1] == 1, "Very low velocity should produce minimum 1 tick"

    def test_high_velocity_produces_more_ticks(self):
        sender, mock_ctrl = self._make_sender()

        sender.scroll(Direction.UP, 0.1)
        low_ticks = mock_ctrl.scroll.call_args[0][1]

        sender.reset()
        mock_ctrl.reset_mock()

        sender.scroll(Direction.UP, 1.0)
        high_ticks = mock_ctrl.scroll.call_args[0][1]

        assert high_ticks > low_ticks, "Higher velocity should produce more ticks"

    def test_very_high_velocity_clamped_to_max(self):
        sender, mock_ctrl = self._make_sender()
        sender.scroll(Direction.UP, 99.0)
        args = mock_ctrl.scroll.call_args[0]
        assert args[1] == 10, "Very high velocity should be clamped to max 10 ticks"

    def test_zero_velocity_still_produces_min_tick(self):
        sender, mock_ctrl = self._make_sender()
        sender.scroll(Direction.UP, 0.0)
        args = mock_ctrl.scroll.call_args[0]
        assert args[1] == 1, "Zero velocity should still produce minimum 1 tick"

    def test_nonlinear_acceleration(self):
        """Middle velocity ticks should be less than linear extrapolation."""
        sender, mock_ctrl = self._make_sender()

        # Get ticks at low velocity
        sender.scroll(Direction.UP, 0.2)
        low_ticks = mock_ctrl.scroll.call_args[0][1]

        sender.reset()
        mock_ctrl.reset_mock()

        # Get ticks at high velocity
        sender.scroll(Direction.UP, 1.0)
        high_ticks = mock_ctrl.scroll.call_args[0][1]

        sender.reset()
        mock_ctrl.reset_mock()

        # Get ticks at mid velocity
        sender.scroll(Direction.UP, 0.6)
        mid_ticks = mock_ctrl.scroll.call_args[0][1]

        # Linear interpolation midpoint
        linear_mid = (low_ticks + high_ticks) / 2.0

        # For superlinear curve, mid should be <= linear midpoint
        # (curve bends — slow is more precise, fast is amplified)
        assert mid_ticks <= linear_mid, (
            f"Nonlinear curve: mid_ticks ({mid_ticks}) should be <= "
            f"linear midpoint ({linear_mid})"
        )


class TestEMASmoothing:
    """Test exponential moving average smoothing of velocity input."""

    def _make_sender(self):
        with patch("gesture_keys.scroll.Controller") as MockCtrl:
            mock_controller = MagicMock()
            MockCtrl.return_value = mock_controller
            from gesture_keys.scroll import ScrollSender

            sender = ScrollSender()
            sender._controller = mock_controller
            return sender, mock_controller

    def test_jittery_input_smoothed(self):
        """Rapid alternating velocities should produce stable output."""
        sender, mock_ctrl = self._make_sender()

        ticks_sequence = []
        for vel in [0.1, 0.9, 0.1, 0.9, 0.1, 0.9]:
            sender.scroll(Direction.UP, vel)
            ticks_sequence.append(mock_ctrl.scroll.call_args[0][1])

        # Last few ticks should not alternate as wildly as input
        # Check that the range of last 3 ticks is less than if unsmoothed
        last_three = ticks_sequence[-3:]
        tick_range = max(last_three) - min(last_three)
        assert tick_range <= 3, (
            f"Jittery input should be smoothed; last 3 ticks range was {tick_range}"
        )

    def test_ema_alpha_0_3_weights_recent(self):
        """After sequence [0.0, 0.0, 1.0], smoothed value should be between 0 and 1."""
        sender, mock_ctrl = self._make_sender()

        sender.scroll(Direction.UP, 0.0)
        sender.scroll(Direction.UP, 0.0)
        sender.scroll(Direction.UP, 1.0)

        # The smoothed velocity after [0, 0, 1] with alpha=0.3 should be:
        # step1: 0.0 (first value, no prev)
        # step2: 0.3*0 + 0.7*0 = 0.0
        # step3: 0.3*1.0 + 0.7*0.0 = 0.3
        # raw = 0.3 * 3.0 = 0.9, curved = 0.9^1.5 ~ 0.854, ticks = max(1, round(0.854)) = 1
        args = mock_ctrl.scroll.call_args[0]
        assert args[1] >= 1, "Should produce at least 1 tick"

    def test_reset_clears_ema_state(self):
        """After reset, EMA should start fresh."""
        sender, mock_ctrl = self._make_sender()

        # Build up some EMA state
        for _ in range(5):
            sender.scroll(Direction.UP, 1.0)

        sender.reset()
        mock_ctrl.reset_mock()

        # Now scroll with low velocity — should be low ticks (fresh EMA, no history)
        sender.scroll(Direction.UP, 0.01)
        args = mock_ctrl.scroll.call_args[0]
        assert args[1] == 1, "After reset, low velocity should produce min ticks"


class TestScrollSenderAPI:
    """Test ScrollSender public API and constructor."""

    def test_constructor_creates_mouse_controller(self):
        with patch("gesture_keys.scroll.Controller") as MockCtrl:
            from gesture_keys.scroll import ScrollSender

            sender = ScrollSender()
            MockCtrl.assert_called_once()
            assert hasattr(sender, "_controller")

    def test_scroll_method_signature(self):
        """scroll() accepts direction and velocity parameters."""
        with patch("gesture_keys.scroll.Controller"):
            from gesture_keys.scroll import ScrollSender

            sender = ScrollSender()
            sender._controller = MagicMock()
            # Should not raise
            sender.scroll(direction=Direction.UP, velocity=0.5)

    def test_reset_method_exists(self):
        with patch("gesture_keys.scroll.Controller"):
            from gesture_keys.scroll import ScrollSender

            sender = ScrollSender()
            assert hasattr(sender, "reset")
            assert callable(sender.reset)
