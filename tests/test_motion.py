"""Tests for gesture_keys.motion module."""

from types import SimpleNamespace

import pytest

from gesture_keys.motion import MotionDetector, MotionState
from gesture_keys.trigger import Direction


# --- Helpers ---

def _make_wrist_landmarks(x, y):
    """Create a minimal landmarks list with only WRIST (index 0) populated."""
    lm = SimpleNamespace(x=x, y=y)
    return [lm]


def _feed_positions(detector, positions, start_time=0.0, dt=0.033):
    """Feed a sequence of (x, y) wrist positions into the detector.

    Returns list of MotionState results from each update call.
    """
    results = []
    t = start_time
    for x, y in positions:
        lm = _make_wrist_landmarks(x, y)
        results.append(detector.update(lm, t))
        t += dt
    return results


def _generate_linear_positions(start, end, steps):
    """Generate evenly spaced (x, y) tuples from start to end."""
    sx, sy = start
    ex, ey = end
    positions = []
    for i in range(steps):
        frac = i / (steps - 1) if steps > 1 else 0.0
        x = sx + (ex - sx) * frac
        y = sy + (ey - sy) * frac
        positions.append((x, y))
    return positions


class TestMotionDetection:
    """MOTN-01: Basic motion detection."""

    def test_stationary_hand_reports_not_moving(self):
        """Feed identical positions -> moving=False, direction=None."""
        det = MotionDetector(settling_frames=0)
        positions = [(0.5, 0.5)] * 10
        results = _feed_positions(det, positions)
        for state in results:
            assert state.moving is False
            assert state.direction is None

    def test_moving_hand_reports_moving_with_direction(self):
        """Feed positions with clear rightward velocity -> moving=True, direction=RIGHT."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.25, settling_frames=0,
        )
        # Large rightward motion to exceed arm_threshold
        positions = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 10)
        results = _feed_positions(det, positions, dt=0.033)
        moving_states = [s for s in results if s.moving]
        assert len(moving_states) >= 1, "Should detect motion"
        for s in moving_states:
            assert s.direction == Direction.RIGHT

    def test_returns_motion_state_every_frame(self):
        """Every update() call returns a MotionState instance (never None)."""
        det = MotionDetector(settling_frames=0)
        positions = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 8)
        results = _feed_positions(det, positions)
        for state in results:
            assert isinstance(state, MotionState)

    def test_no_landmarks_reports_not_moving(self):
        """update(None, t) -> moving=False."""
        det = MotionDetector()
        state = det.update(None, 0.0)
        assert state.moving is False
        assert state.direction is None


class TestDirectionClassification:
    """MOTN-02: Direction classification."""

    def test_left_motion(self):
        """Decreasing x, stable y -> Direction.LEFT."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.2, settling_frames=0,
        )
        positions = _generate_linear_positions((0.8, 0.5), (0.2, 0.5), 10)
        results = _feed_positions(det, positions, dt=0.033)
        moving_states = [s for s in results if s.moving]
        assert len(moving_states) >= 1
        for s in moving_states:
            assert s.direction == Direction.LEFT

    def test_right_motion(self):
        """Increasing x, stable y -> Direction.RIGHT."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.2, settling_frames=0,
        )
        positions = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 10)
        results = _feed_positions(det, positions, dt=0.033)
        moving_states = [s for s in results if s.moving]
        assert len(moving_states) >= 1
        for s in moving_states:
            assert s.direction == Direction.RIGHT

    def test_up_motion(self):
        """Decreasing y (MediaPipe inverted), stable x -> Direction.UP."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.2, settling_frames=0,
        )
        positions = _generate_linear_positions((0.5, 0.8), (0.5, 0.2), 10)
        results = _feed_positions(det, positions, dt=0.033)
        moving_states = [s for s in results if s.moving]
        assert len(moving_states) >= 1
        for s in moving_states:
            assert s.direction == Direction.UP

    def test_down_motion(self):
        """Increasing y, stable x -> Direction.DOWN."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.2, settling_frames=0,
        )
        positions = _generate_linear_positions((0.5, 0.2), (0.5, 0.8), 10)
        results = _feed_positions(det, positions, dt=0.033)
        moving_states = [s for s in results if s.moving]
        assert len(moving_states) >= 1
        for s in moving_states:
            assert s.direction == Direction.DOWN

    def test_diagonal_rejected(self):
        """Movement at ~45 degrees (axis_ratio not met) -> direction holds previous or None."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.2, axis_ratio=2.0,
            settling_frames=0,
        )
        # Equal dx and dy -- diagonal
        positions = _generate_linear_positions((0.2, 0.2), (0.8, 0.8), 10)
        results = _feed_positions(det, positions, dt=0.033)
        # Should never transition to moving because direction is always None (diagonal)
        for s in results:
            assert s.moving is False


class TestHysteresis:
    """MOTN-03: Hysteresis prevents flicker."""

    def test_arm_threshold_triggers_moving(self):
        """Velocity crosses arm_threshold -> moving=True."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.2, disarm_threshold=0.1,
            settling_frames=0,
        )
        # Fast motion to exceed arm_threshold
        positions = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 6)
        results = _feed_positions(det, positions, dt=0.033)
        assert any(s.moving for s in results), "Should arm when velocity exceeds arm_threshold"

    def test_disarm_threshold_clears_moving(self):
        """Velocity drops below disarm_threshold -> moving=False."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.2, disarm_threshold=0.1,
            settling_frames=0,
        )
        # Fast motion to arm
        fast = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 6)
        results = _feed_positions(det, fast, dt=0.033)
        assert any(s.moving for s in results), "Setup: should arm"

        # Slow/stationary to disarm
        slow = [(0.8, 0.5)] * 6
        results2 = _feed_positions(det, slow, start_time=0.2, dt=0.033)
        # Last state should be not-moving
        assert results2[-1].moving is False, "Should disarm below disarm_threshold"

    def test_velocity_between_thresholds_holds_state(self):
        """Velocity between disarm and arm thresholds -> state unchanged (dead zone)."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.5, disarm_threshold=0.1,
            settling_frames=0,
        )
        # First, arm with high velocity
        fast = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 4)
        _feed_positions(det, fast, dt=0.020)

        # Now feed moderate motion (velocity between 0.1 and 0.5)
        # Buffer size 3, so we need positions that produce velocity ~0.3
        moderate = _generate_linear_positions((0.8, 0.5), (0.83, 0.5), 4)
        results = _feed_positions(det, moderate, start_time=0.1, dt=0.033)
        # State should remain moving (dead zone holds)
        assert results[-1].moving is True, "Dead zone should hold moving state"

    def test_jitter_around_arm_threshold_no_flicker(self):
        """Velocity oscillates near arm_threshold -> does not rapidly toggle."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.3, disarm_threshold=0.1,
            settling_frames=0,
        )
        # Alternate between slightly above and below arm_threshold
        # Start not-moving, oscillate near threshold
        positions = []
        x = 0.5
        for i in range(20):
            # Alternate tiny and medium steps
            if i % 2 == 0:
                x += 0.012  # small step -> low velocity
            else:
                x += 0.015  # slightly larger step
            positions.append((x, 0.5))

        results = _feed_positions(det, positions, dt=0.033)
        transitions = 0
        prev_moving = False
        for s in results:
            if s.moving != prev_moving:
                transitions += 1
                prev_moving = s.moving
        # Hysteresis should prevent rapid toggling
        assert transitions <= 2, f"Too many transitions ({transitions}), hysteresis should prevent flicker"


class TestSettlingFrames:
    """MOTN-04: Settling frames on hand entry."""

    def test_hand_entry_settling(self):
        """First N frames after hand appears -> moving=False regardless of velocity."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.1, settling_frames=3,
        )
        # Fast motion from first frame
        positions = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 6)
        results = _feed_positions(det, positions, dt=0.033)
        # First 3 frames must be not-moving (settling)
        for i in range(3):
            assert results[i].moving is False, f"Frame {i} should be suppressed by settling"

    def test_motion_detected_after_settling(self):
        """After settling frames pass, normal detection resumes."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.1, settling_frames=3,
        )
        # Fast motion sustained beyond settling period
        positions = _generate_linear_positions((0.2, 0.5), (0.9, 0.5), 12)
        results = _feed_positions(det, positions, dt=0.033)
        # After settling (first 3 frames), motion should eventually be detected
        post_settling = results[3:]
        assert any(s.moving for s in post_settling), "Motion should be detected after settling"

    def test_hand_exit_and_reentry_resets_settling(self):
        """Hand disappears then reappears -> settling restarts."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.1, settling_frames=3,
        )
        # Establish hand presence and burn through settling
        positions = [(0.5, 0.5)] * 5
        _feed_positions(det, positions)

        # Hand disappears
        det.update(None, 0.2)

        # Hand reappears with fast motion
        fast = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 6)
        results = _feed_positions(det, fast, start_time=0.3, dt=0.033)
        # First 3 frames after reentry should be not-moving
        for i in range(3):
            assert results[i].moving is False, f"Frame {i} after reentry should be settling"

    def test_settling_counter_configurable(self):
        """settling_frames=5 -> 5 frames suppressed."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.1, settling_frames=5,
        )
        positions = _generate_linear_positions((0.2, 0.5), (0.9, 0.5), 10)
        results = _feed_positions(det, positions, dt=0.033)
        # First 5 frames must be not-moving
        for i in range(5):
            assert results[i].moving is False, f"Frame {i} should be suppressed (settling=5)"


class TestEdgeCases:
    """Additional edge cases."""

    def test_zero_dt_no_crash(self):
        """Two frames with identical timestamps -> returns not moving, no ZeroDivisionError."""
        det = MotionDetector(settling_frames=0)
        lm1 = _make_wrist_landmarks(0.2, 0.5)
        lm2 = _make_wrist_landmarks(0.8, 0.5)
        det.update(lm1, 1.0)
        state = det.update(lm2, 1.0)  # same timestamp
        assert isinstance(state, MotionState)
        assert state.moving is False

    def test_reset_clears_state(self):
        """reset() -> buffer cleared, moving=False, settling restarted on next hand entry."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.1, settling_frames=3,
        )
        # Establish motion
        positions = [(0.5, 0.5)] * 5
        _feed_positions(det, positions)

        det.reset()

        # After reset, next update should trigger settling
        lm = _make_wrist_landmarks(0.5, 0.5)
        state = det.update(lm, 1.0)
        assert state.moving is False

    def test_direction_clears_on_motion_stop(self):
        """When moving transitions to False -> direction=None."""
        det = MotionDetector(
            buffer_size=3, arm_threshold=0.2, disarm_threshold=0.1,
            settling_frames=0,
        )
        # Fast motion to arm
        fast = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 6)
        results = _feed_positions(det, fast, dt=0.033)
        assert any(s.moving for s in results), "Setup: should arm"

        # Stationary to disarm
        slow = [(0.8, 0.5)] * 6
        results2 = _feed_positions(det, slow, start_time=0.3, dt=0.033)
        # Find the first not-moving state
        not_moving = [s for s in results2 if not s.moving]
        assert len(not_moving) >= 1
        for s in not_moving:
            assert s.direction is None, "Direction should be None when not moving"


class TestMotionStateVelocity:
    """Tests for MotionState.velocity field."""

    def test_motion_state_has_velocity_field(self):
        """MotionState(moving=True, direction=Direction.RIGHT).velocity returns a float."""
        state = MotionState(moving=True, direction=Direction.RIGHT, velocity=0.35)
        assert state.velocity == 0.35

    def test_motion_state_not_moving_velocity_zero(self):
        """MotionState(moving=False).velocity returns 0.0."""
        state = MotionState(moving=False)
        assert state.velocity == 0.0

    def test_motion_state_velocity_default_is_zero(self):
        """MotionState velocity defaults to 0.0 when not specified."""
        state = MotionState(moving=True, direction=Direction.LEFT)
        assert state.velocity == 0.0

    def test_not_moving_singleton_velocity_zero(self):
        """The _NOT_MOVING singleton has velocity=0.0."""
        from gesture_keys.motion import _NOT_MOVING
        assert _NOT_MOVING.velocity == 0.0

    def test_moving_detector_reports_velocity(self):
        """MotionDetector.update() returns MotionState with non-zero velocity when moving."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.2, settling_frames=0,
        )
        # Large rightward motion
        positions = _generate_linear_positions((0.2, 0.5), (0.8, 0.5), 10)
        results = _feed_positions(det, positions, dt=0.033)
        moving_states = [s for s in results if s.moving]
        assert len(moving_states) >= 1
        for s in moving_states:
            assert s.velocity > 0.0, "Moving state should have positive velocity"

    def test_custom_arm_threshold_in_constructor(self):
        """MotionDetector initialized with arm_threshold=0.5 arms at 0.5."""
        det = MotionDetector(
            buffer_size=5, arm_threshold=0.5, settling_frames=0,
        )
        # Moderate motion that exceeds 0.25 but not 0.5
        moderate_positions = _generate_linear_positions((0.5, 0.5), (0.55, 0.5), 10)
        results = _feed_positions(det, moderate_positions, dt=0.033)
        # With threshold 0.5, moderate motion should NOT arm
        assert all(not s.moving for s in results), "Should NOT arm with velocity below 0.5"
