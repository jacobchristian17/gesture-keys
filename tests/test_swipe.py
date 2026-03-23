"""Tests for gesture_keys.swipe module."""

from types import SimpleNamespace

import pytest

from gesture_keys.swipe import SwipeDetector, SwipeDirection, _SwipeState


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
            cooldown_duration=0.3, settling_frames=0,
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


class TestSwipeIsSwiping:
    """Tests for the is_swiping read-only property."""

    def test_idle_not_swiping(self):
        """Fresh detector should not be swiping."""
        det = SwipeDetector()
        assert det.is_swiping is False

    def test_armed_is_swiping(self):
        """After entering ARMED state, is_swiping should be True."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        # Feed first 5 positions of a fast swipe to enter ARMED (before deceleration)
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        t = 0.0
        for x, y in positions[:5]:
            det.update(_make_wrist_landmarks(x, y), t)
            t += 0.033
            if det._state == _SwipeState.ARMED:
                break
        assert det._state == _SwipeState.ARMED, "Setup failed: detector not in ARMED state"
        assert det.is_swiping is True

    def test_cooldown_not_swiping(self):
        """After a swipe fires (COOLDOWN), is_swiping should be False.
        COOLDOWN no longer suppresses static gesture detection."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        assert any(r is not None for r in results), "Setup failed: swipe did not fire"
        assert det._state == _SwipeState.COOLDOWN
        assert det.is_swiping is False

    def test_back_to_idle_not_swiping(self):
        """After cooldown expires, is_swiping should be False."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.1,
        )
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        _swipe_sequence(det, positions, start_time=0.0, dt=0.033)
        # Advance past cooldown
        det.update(_make_wrist_landmarks(0.3, 0.5), 1.0)
        assert det._state == _SwipeState.IDLE
        assert det.is_swiping is False


class TestSwipeReset:
    """Tests for the reset() method."""

    def test_reset_clears_buffer(self):
        """After reset, buffer is empty so next updates return None (< 3 entries)."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        # Build buffer
        for i in range(4):
            det.update(_make_wrist_landmarks(0.5, 0.5), i * 0.033)
        det.reset()
        # Only 1 entry after reset -- should return None
        result = det.update(_make_wrist_landmarks(0.5, 0.5), 1.0)
        assert result is None

    def test_reset_returns_to_idle(self):
        """When in ARMED state, reset() transitions to IDLE."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        t = 0.0
        for x, y in positions[:5]:
            det.update(_make_wrist_landmarks(x, y), t)
            t += 0.033
            if det._state == _SwipeState.ARMED:
                break
        assert det._state == _SwipeState.ARMED, "Setup failed"
        det.reset()
        assert det._state == _SwipeState.IDLE

    def test_reset_preserves_cooldown(self):
        """When in COOLDOWN, reset() does NOT change state to IDLE."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        assert any(r is not None for r in results), "Setup failed"
        assert det._state == _SwipeState.COOLDOWN
        det.reset()
        assert det._state == _SwipeState.COOLDOWN

    def test_reset_clears_armed_direction(self):
        """After entering ARMED, reset() clears _armed_direction to None."""
        det = SwipeDetector(buffer_size=6, min_velocity=0.3, min_displacement=0.05)
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        t = 0.0
        for x, y in positions[:5]:
            det.update(_make_wrist_landmarks(x, y), t)
            t += 0.033
            if det._state == _SwipeState.ARMED:
                break
        assert det._armed_direction is not None, "Setup failed"
        det.reset()
        assert det._armed_direction is None


class TestSwipeSettlingGuard:
    """Tests for post-cooldown settling guard preventing false re-arming."""

    def test_no_rearm_during_settling_period(self):
        """After COOLDOWN->IDLE, swipe does not re-arm for settling_frames frames
        even if velocity/displacement thresholds are met."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.1, settling_frames=5,
        )
        # Complete a swipe
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(det, positions, start_time=0.0, dt=0.033)
        assert any(r is not None for r in results), "Setup: swipe should fire"
        assert det._state == _SwipeState.COOLDOWN

        # Advance past cooldown to trigger COOLDOWN->IDLE
        det.update(_make_wrist_landmarks(0.3, 0.5), 1.0)
        assert det._state == _SwipeState.IDLE

        # Now feed a fast swipe during settling period -- should NOT arm
        fast_positions = _generate_swipe_positions((0.3, 0.5), (0.8, 0.5), steps=5)
        t = 1.033
        for x, y in fast_positions:
            result = det.update(_make_wrist_landmarks(x, y), t)
            assert result is None, "Should not fire during settling period"
            t += 0.033

        # Should still be IDLE (not ARMED) due to settling guard
        assert det._state == _SwipeState.IDLE

    def test_swipe_arms_after_settling_expires(self):
        """After settling period expires, swipe can arm normally on genuine motion."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.1, settling_frames=3,
        )
        # Complete a swipe
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        _swipe_sequence(det, positions, start_time=0.0, dt=0.033)

        # Advance past cooldown
        det.update(_make_wrist_landmarks(0.3, 0.5), 1.0)
        assert det._state == _SwipeState.IDLE

        # Burn through settling frames with stable position
        t = 1.033
        for _ in range(3):
            det.update(_make_wrist_landmarks(0.3, 0.5), t)
            t += 0.033

        # Now a genuine swipe should be able to fire
        fast_positions = _generate_swipe_positions((0.3, 0.5), (0.8, 0.5), steps=8)
        results = []
        for x, y in fast_positions:
            results.append(det.update(_make_wrist_landmarks(x, y), t))
            t += 0.033

        fired = [r for r in results if r is not None]
        assert len(fired) >= 1, "After settling expires, swipe should fire"

    def test_settling_counter_resets_on_each_cooldown_transition(self):
        """Each COOLDOWN->IDLE transition resets the settling counter."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.1, settling_frames=3,
        )
        # First swipe cycle
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        _swipe_sequence(det, positions, start_time=0.0, dt=0.033)
        det.update(_make_wrist_landmarks(0.3, 0.5), 1.0)  # COOLDOWN->IDLE
        assert det._settling_frames_remaining == 3

        # Burn settling: need buffer refill (2 frames for <3 entries) + 3 settling frames
        t = 1.033
        for _ in range(6):
            det.update(_make_wrist_landmarks(0.3, 0.5), t)
            t += 0.033
        assert det._settling_frames_remaining == 0

        # Second swipe cycle
        positions2 = _generate_swipe_positions((0.3, 0.5), (0.8, 0.5), steps=8)
        results2 = _swipe_sequence(det, positions2, start_time=t, dt=0.033)
        assert any(r is not None for r in results2), "Second swipe should fire"

        # Advance past cooldown again
        det.update(_make_wrist_landmarks(0.6, 0.5), t + 1.0)
        # Settling counter should be reset to 3 again
        assert det._settling_frames_remaining == 3

    def test_default_settling_frames_is_3(self):
        """Default settling_frames should be 3 (not 10) for fast transitions."""
        detector = SwipeDetector()
        assert detector._settling_frames == 3

    def test_no_settling_without_recent_cooldown(self):
        """Settling guard does not affect normal IDLE->ARMED when no recent cooldown."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.5, settling_frames=10,
        )
        # Fresh detector: settling_frames_remaining should be 0
        assert det._settling_frames_remaining == 0

        # Normal swipe should arm and fire without settling interference
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(det, positions, dt=0.033)
        fired = [r for r in results if r is not None]
        assert len(fired) >= 1, "Normal swipe should fire without settling guard"


class TestHandEntrySettling:
    """Tests for hand-entry settling guard that suppresses swipe on hand appearance."""

    def test_hand_entry_settling_suppresses_swipe(self):
        """When hand appears after absence, swipe is suppressed for settling_frames frames."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            settling_frames=3,
        )
        # Hand absent for a frame
        det.update(None, 0.0)

        # Hand appears with fast motion -- should be suppressed during settling
        fast_positions = _generate_swipe_positions((0.2, 0.5), (0.7, 0.5), steps=8)
        t = 0.033
        results = []
        for x, y in fast_positions:
            results.append(det.update(_make_wrist_landmarks(x, y), t))
            t += 0.033

        # First 3 frames should all be None (settling guard)
        # After settling, swipe CAN fire
        assert results[0] is None, "Frame 1 should be suppressed by settling"
        assert results[1] is None, "Frame 2 should be suppressed by settling"
        assert results[2] is None, "Frame 3 should be suppressed by settling"

    def test_hand_continuously_present_no_settling(self):
        """Hand continuously present (never lost) does NOT trigger settling after initial entry."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            settling_frames=3,
        )
        # First call establishes hand presence -- triggers initial settling
        det.update(_make_wrist_landmarks(0.5, 0.5), 0.0)
        det.update(_make_wrist_landmarks(0.5, 0.5), 0.033)
        det.update(_make_wrist_landmarks(0.5, 0.5), 0.066)
        # Settling should be expired by now (3 frames consumed)
        det.update(_make_wrist_landmarks(0.5, 0.5), 0.099)

        # Now a real swipe should fire without settling interference
        fast_positions = _generate_swipe_positions((0.5, 0.5), (0.1, 0.5), steps=8)
        t = 0.132
        results = []
        for x, y in fast_positions:
            results.append(det.update(_make_wrist_landmarks(x, y), t))
            t += 0.033
        fired = [r for r in results if r is not None]
        assert len(fired) >= 1, "Continuous hand presence should not re-trigger settling"

    def test_hand_reentry_triggers_settling(self):
        """Hand lost briefly then returns triggers settling guard again."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            settling_frames=3,
        )
        # Establish hand presence and burn through initial settling
        for i in range(5):
            det.update(_make_wrist_landmarks(0.5, 0.5), i * 0.033)

        # Hand lost
        det.update(None, 0.2)

        # Hand reappears -- should trigger settling again
        assert det._hand_present is False
        det.update(_make_wrist_landmarks(0.5, 0.5), 0.233)
        assert det._settling_frames_remaining == 3, "Re-entry should trigger settling"

    def test_suppressed_preserves_hand_present(self):
        """suppressed=True preserves _hand_present -- no false settling on resume."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            settling_frames=3,
        )
        # Establish hand presence and burn through initial settling
        for i in range(5):
            det.update(_make_wrist_landmarks(0.5, 0.5), i * 0.033)
        assert det._hand_present is True

        # Simulate is_activating gate: suppressed=True with None landmarks
        t = 0.2
        for _ in range(5):
            det.update(None, t, suppressed=True)
            t += 0.033
        # _hand_present should still be True (suppressed preserves it)
        assert det._hand_present is True

        # Now resume with real landmarks, suppressed=False
        # Should NOT trigger settling (hand was never truly absent)
        result = det.update(_make_wrist_landmarks(0.5, 0.5), t)
        assert det._settling_frames_remaining == 0, (
            "Settling should NOT trigger after suppressed period"
        )

    def test_suppressed_prevents_arming(self):
        """suppressed=True prevents arming even with buffer pre-loaded."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            settling_frames=0,  # No settling to isolate suppressed behavior
        )
        # Build up buffer with fast motion
        fast_positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=6)
        t = 0.0
        for x, y in fast_positions[:4]:
            det.update(_make_wrist_landmarks(x, y), t)
            t += 0.033

        # Now call with suppressed=True -- should not arm or fire
        for x, y in fast_positions[4:]:
            result = det.update(_make_wrist_landmarks(x, y), t, suppressed=True)
            assert result is None, "suppressed=True should prevent arming/firing"
            t += 0.033
        assert det._state != _SwipeState.ARMED, "Should not be ARMED during suppression"
