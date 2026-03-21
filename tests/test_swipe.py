"""Tests for gesture_keys.swipe module."""

from types import SimpleNamespace

import pytest

from gesture_keys.swipe import SwipeDetector, SwipeDirection


# --- Helpers ---

def _make_wrist_landmarks(x, y):
    """Create a minimal landmarks list with only WRIST (index 0) populated."""
    lm = SimpleNamespace(x=x, y=y)
    return [lm]


def _swipe_sequence(detector, positions, start_time=0.0, dt=0.033):
    """Feed a sequence of (x, y) wrist positions into the detector.

    Returns list of results from each update call.
    """
    results = []
    t = start_time
    for x, y in positions:
        lm = _make_wrist_landmarks(x, y)
        results.append(detector.update(lm, t))
        t += dt
    return results


def _generate_swipe_positions(start, end, steps=8):
    """Generate evenly-spaced positions from start to end (x,y) tuples.

    Produces a clear acceleration then deceleration pattern:
    first half accelerates, second half decelerates.
    """
    sx, sy = start
    ex, ey = end
    positions = []
    for i in range(steps):
        # Use sine curve for natural accel/decel
        import math
        frac = (1 - math.cos(math.pi * i / (steps - 1))) / 2
        x = sx + (ex - sx) * frac
        y = sy + (ey - sy) * frac
        positions.append((x, y))
    return positions


class TestSwipeDirectionClassification:
    """Tests for all 4 directions and diagonal rejection."""

    def test_left_swipe_detected(self):
        """Left swipe: decreasing x, stable y."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        fired = [r for r in results if r is not None]
        assert len(fired) >= 1
        assert fired[0] == SwipeDirection.SWIPE_LEFT

    def test_right_swipe_detected(self):
        """Right swipe: increasing x, stable y."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.2, 0.5), (0.7, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        fired = [r for r in results if r is not None]
        assert len(fired) >= 1
        assert fired[0] == SwipeDirection.SWIPE_RIGHT

    def test_up_swipe_detected(self):
        """Up swipe: decreasing y (MediaPipe Y inverted)."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.5, 0.7), (0.5, 0.2), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        fired = [r for r in results if r is not None]
        assert len(fired) >= 1
        assert fired[0] == SwipeDirection.SWIPE_UP

    def test_down_swipe_detected(self):
        """Down swipe: increasing y (MediaPipe Y inverted)."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.5, 0.2), (0.5, 0.7), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        fired = [r for r in results if r is not None]
        assert len(fired) >= 1
        assert fired[0] == SwipeDirection.SWIPE_DOWN

    def test_diagonal_movement_rejected(self):
        """Diagonal movement (abs_dx ~= abs_dy) should not fire."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05, axis_ratio=2.0)
        # Equal dx and dy -- diagonal
        positions = _generate_swipe_positions((0.2, 0.2), (0.7, 0.7), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        fired = [r for r in results if r is not None]
        assert len(fired) == 0


class TestSwipeThresholds:
    """Tests for min_velocity, min_displacement filtering."""

    def test_no_fire_below_min_displacement(self):
        """Jitter-level movement should not fire."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.1, min_displacement=0.2)
        # Tiny movement: 0.05 displacement (below 0.2 threshold)
        positions = _generate_swipe_positions((0.5, 0.5), (0.55, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        fired = [r for r in results if r is not None]
        assert len(fired) == 0

    def test_no_fire_below_min_velocity(self):
        """Slow repositioning should not fire."""
        det = SwipeDetector(buffer_size=6, min_velocity=5.0, min_displacement=0.01)
        # Large displacement but very slow (large dt)
        positions = _generate_swipe_positions((0.2, 0.5), (0.7, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.5)
        fired = [r for r in results if r is not None]
        assert len(fired) == 0


class TestSwipeFireTiming:
    """Tests for deceleration-based firing."""

    def test_fire_on_deceleration(self):
        """Fire should occur when speed drops (deceleration) while ARMED."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        # Generate positions with acceleration then deceleration
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        # Fire should occur in the deceleration phase (latter half)
        fired_indices = [i for i, r in enumerate(results) if r is not None]
        assert len(fired_indices) >= 1
        # Fire should happen after the midpoint (deceleration phase)
        assert fired_indices[0] >= 3


class TestSwipeCooldown:
    """Tests for cooldown blocking and re-arm."""

    def test_cooldown_blocks_new_swipes(self):
        """During cooldown, new swipes should not fire."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=1.0,
        )
        # First swipe
        pos1 = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results1 = _swipe_sequence(det, pos1, start_time=0.0, dt=0.033)
        assert any(r is not None for r in results1)

        # Second swipe immediately (within cooldown)
        pos2 = _generate_swipe_positions((0.2, 0.5), (0.7, 0.5), steps=8)
        results2 = _swipe_sequence(det, pos2, start_time=0.3, dt=0.033)
        assert all(r is None for r in results2)

    def test_swipe_fires_after_cooldown_expires(self):
        """After cooldown expires, next swipe fires immediately (no return-to-rest needed)."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.3,
        )
        # First swipe
        pos1 = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        _swipe_sequence(det, pos1, start_time=0.0, dt=0.033)

        # Second swipe after cooldown
        pos2 = _generate_swipe_positions((0.2, 0.5), (0.7, 0.5), steps=8)
        results2 = _swipe_sequence(det, pos2, start_time=1.0, dt=0.033)
        fired = [r for r in results2 if r is not None]
        assert len(fired) >= 1
        assert fired[0] == SwipeDirection.SWIPE_RIGHT


class TestSwipeBufferLifecycle:
    """Tests for buffer clear on None landmarks and on fire."""

    def test_buffer_clears_on_none_landmarks(self):
        """When landmarks is None (hand lost), buffer clears and state resets."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        # Build up some buffer entries
        lm = _make_wrist_landmarks(0.5, 0.5)
        det.update(lm, 0.0)
        det.update(lm, 0.033)
        det.update(lm, 0.066)
        # Hand lost
        result = det.update(None, 0.1)
        assert result is None
        # Buffer should be empty -- next updates should not have stale data
        # Feed insufficient data (< 3 entries)
        result2 = det.update(_make_wrist_landmarks(0.5, 0.5), 0.2)
        assert result2 is None

    def test_buffer_clears_on_fire(self):
        """Buffer clears on fire to prevent stale data after cooldown."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.1,
        )
        # Complete a swipe
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        _swipe_sequence(det, positions, start_time=0.0, dt=0.033)

        # After cooldown, buffer should be empty
        # Fewer than 3 entries should return None
        result = det.update(_make_wrist_landmarks(0.3, 0.5), 1.0)
        assert result is None

    def test_fewer_than_3_entries_returns_none(self):
        """Insufficient data should return None."""
        det = SwipeDetector(buffer_size=6)
        lm = _make_wrist_landmarks(0.5, 0.5)
        assert det.update(lm, 0.0) is None
        assert det.update(lm, 0.033) is None


class TestSwipePoseIndependence:
    """Test that only WRIST (index 0) is accessed."""

    def test_only_reads_index_zero(self):
        """SwipeDetector should only access landmarks[0] (WRIST)."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)

        class TrackedList(list):
            """List that tracks which indices are accessed."""
            def __init__(self, *args):
                super().__init__(*args)
                self.accessed_indices = set()

            def __getitem__(self, idx):
                self.accessed_indices.add(idx)
                return super().__getitem__(idx)

        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        for x, y in positions:
            lm = SimpleNamespace(x=x, y=y)
            tracked = TrackedList([lm])
            det.update(tracked, 0.0)
            assert tracked.accessed_indices <= {0}, (
                f"Accessed indices {tracked.accessed_indices}, expected only {{0}}"
            )


class TestSwipeDirectionValues:
    """Test SwipeDirection enum values match config key names."""

    def test_swipe_left_value(self):
        assert SwipeDirection.SWIPE_LEFT.value == "swipe_left"

    def test_swipe_right_value(self):
        assert SwipeDirection.SWIPE_RIGHT.value == "swipe_right"

    def test_swipe_up_value(self):
        assert SwipeDirection.SWIPE_UP.value == "swipe_up"

    def test_swipe_down_value(self):
        assert SwipeDirection.SWIPE_DOWN.value == "swipe_down"
