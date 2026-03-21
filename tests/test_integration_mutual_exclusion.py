"""Integration tests for mutual exclusion between swipe and static gestures.

These tests validate the contract that the main loop relies on:
- is_swiping is True during active swipes (suppresses static pipeline)
- is_swiping is False during held poses (static pipeline runs normally)
- reset() cleanly interrupts swipe state for distance gating
- Swipe-to-pose transitions are clean (no stuck states)
"""

from types import SimpleNamespace

from gesture_keys.swipe import SwipeDetector, SwipeDirection, _SwipeState


# --- Helpers (duplicated from test_swipe to keep test file independent) ---

def _make_wrist_landmarks(x, y):
    """Create a minimal landmarks list with only WRIST (index 0) populated."""
    lm = SimpleNamespace(x=x, y=y)
    return [lm]


def _generate_swipe_positions(start, end, steps=8):
    """Generate evenly-spaced positions with natural accel/decel pattern."""
    import math
    sx, sy = start
    ex, ey = end
    positions = []
    for i in range(steps):
        frac = (1 - math.cos(math.pi * i / (steps - 1))) / 2
        x = sx + (ex - sx) * frac
        y = sy + (ey - sy) * frac
        positions.append((x, y))
    return positions


def _swipe_sequence(detector, positions, start_time=0.0, dt=0.033):
    """Feed a sequence of (x, y) wrist positions into the detector."""
    results = []
    t = start_time
    for x, y in positions:
        lm = _make_wrist_landmarks(x, y)
        results.append(detector.update(lm, t))
        t += dt
    return results


class TestMutualExclusionIntegration:
    """Integration tests for swipe/static gesture mutual exclusion."""

    def test_swipe_suppresses_static(self):
        """During ARMED/COOLDOWN, is_swiping is True; after cooldown, False."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.2,
        )
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)

        # Track is_swiping through the full swipe lifecycle
        swiping_during_motion = []
        t = 0.0
        fired = False
        for x, y in positions:
            result = det.update(_make_wrist_landmarks(x, y), t)
            if result is not None:
                fired = True
            if det._state in (_SwipeState.ARMED, _SwipeState.COOLDOWN):
                swiping_during_motion.append(det.is_swiping)
            t += 0.033

        assert fired, "Swipe should have fired"
        assert all(swiping_during_motion), "is_swiping should be True during ARMED/COOLDOWN"
        assert det.is_swiping is True, "Should still be in COOLDOWN"

        # Advance past cooldown
        det.update(_make_wrist_landmarks(0.3, 0.5), 5.0)
        assert det.is_swiping is False, "After cooldown expires, is_swiping should be False"

    def test_held_pose_does_not_trigger_swipe(self):
        """20 frames of identical position: no fire, is_swiping stays False."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        t = 0.0
        for _ in range(20):
            result = det.update(_make_wrist_landmarks(0.5, 0.5), t)
            assert result is None, "Held pose should not fire swipe"
            assert det.is_swiping is False, "Held pose should not activate is_swiping"
            t += 0.033

    def test_distance_reset_clears_swipe(self):
        """reset() clears ARMED state; subsequent frames don't false-fire."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        # Feed 5 frames of fast swipe to enter ARMED
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        t = 0.0
        for x, y in positions[:5]:
            det.update(_make_wrist_landmarks(x, y), t)
            t += 0.033
            if det._state == _SwipeState.ARMED:
                break

        assert det._state == _SwipeState.ARMED, "Setup: should be ARMED"
        det.reset()
        assert det._state == _SwipeState.IDLE, "reset() should return to IDLE"
        assert det.is_swiping is False

        # Feed 2 frames of a new position -- insufficient buffer, should not fire
        result1 = det.update(_make_wrist_landmarks(0.4, 0.5), t + 0.1)
        result2 = det.update(_make_wrist_landmarks(0.4, 0.5), t + 0.133)
        assert result1 is None, "Should not fire with insufficient buffer after reset"
        assert result2 is None, "Should not fire with insufficient buffer after reset"

    def test_swipe_to_pose_transition(self):
        """After swipe cooldown expires, is_swiping transitions cleanly to False."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.2,
        )
        # Complete a swipe
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(det, positions, start_time=0.0, dt=0.033)
        assert any(r is not None for r in results), "Swipe should fire"
        assert det.is_swiping is True, "Should be in COOLDOWN (swiping)"

        # Advance past cooldown with stable position (simulating held pose)
        det.update(_make_wrist_landmarks(0.3, 0.5), 5.0)
        assert det.is_swiping is False, "After cooldown, is_swiping should be False"

        # Feed several stable frames -- should stay not-swiping
        t = 5.033
        for _ in range(5):
            result = det.update(_make_wrist_landmarks(0.3, 0.5), t)
            assert result is None
            assert det.is_swiping is False
            t += 0.033
