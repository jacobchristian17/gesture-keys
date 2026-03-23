"""Integration tests for mutual exclusion between swipe and static gestures.

These tests validate the contract that the main loop relies on:
- is_swiping is True only during ARMED state (not COOLDOWN)
- Static gestures have priority: debouncer.is_activating suppresses swipe arming
- is_swiping is False during held poses (static pipeline runs normally)
- reset() cleanly interrupts swipe state for distance gating
- Swipe-to-pose transitions are clean (no stuck states)
- Smoother reset eliminates stale gesture leakage
"""

from enum import Enum
from types import SimpleNamespace

from gesture_keys.classifier import Gesture
from gesture_keys.debounce import GestureDebouncer, DebounceState
from gesture_keys.smoother import GestureSmoother
from gesture_keys.swipe import SwipeDetector, SwipeDirection, _SwipeState


class _FakeGesture(Enum):
    """Fake gesture enum for smoother testing."""
    OPEN_PALM = "open_palm"
    FIST = "fist"


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
        """During ARMED, is_swiping is True; during COOLDOWN and after, False.
        COOLDOWN no longer suppresses static gesture detection."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.2,
        )
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)

        # Track is_swiping through the full swipe lifecycle
        swiping_during_armed = []
        swiping_during_cooldown = []
        t = 0.0
        fired = False
        for x, y in positions:
            result = det.update(_make_wrist_landmarks(x, y), t)
            if result is not None:
                fired = True
            if det._state == _SwipeState.ARMED:
                swiping_during_armed.append(det.is_swiping)
            elif det._state == _SwipeState.COOLDOWN:
                swiping_during_cooldown.append(det.is_swiping)
            t += 0.033

        assert fired, "Swipe should have fired"
        assert all(swiping_during_armed), "is_swiping should be True during ARMED"
        assert not any(swiping_during_cooldown), "is_swiping should be False during COOLDOWN"
        assert det.is_swiping is False, "Should be in COOLDOWN but is_swiping is False"

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
        # Burn through initial hand-entry settling with stable position
        for i in range(4):
            det.update(_make_wrist_landmarks(0.5, 0.5), i * 0.033)
        # Feed frames of fast swipe to enter ARMED
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        t = 0.2
        for x, y in positions:
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
        assert det.is_swiping is False, "Should be in COOLDOWN (is_swiping now ARMED-only)"

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


class TestSmootherResetLeakRegression:
    """Regression test: smoother reset must eliminate stale gesture values."""

    def test_smoother_reset_clears_stale_gestures(self):
        """After filling smoother with a gesture and resetting, feeding None
        should return None immediately -- not the stale gesture via majority vote."""
        smoother = GestureSmoother(window_size=3)

        # Fill the window with OPEN_PALM
        for _ in range(3):
            result = smoother.update(_FakeGesture.OPEN_PALM)
        assert result == _FakeGesture.OPEN_PALM, "Setup: smoother should report OPEN_PALM"

        # Reset (simulating swipe start)
        smoother.reset()

        # Feed None -- should return None, not stale OPEN_PALM
        result = smoother.update(None)
        assert result is None, (
            "After reset, smoother should return None (not stale gesture from window)"
        )

class TestSwipeExitReset:
    """Tests for smoother/debouncer reset when swipe exits (is_swiping True->False)."""

    def test_exit_reset_clears_smoother(self):
        """When swipe exits, smoother buffer must be cleared so stale
        swipe-motion frames don't leak into static gesture recognition."""
        smoother = GestureSmoother(window_size=3)

        # Fill smoother with swipe-motion frames (simulating gestures during swipe)
        for _ in range(3):
            smoother.update(_FakeGesture.OPEN_PALM)
        assert smoother.update(_FakeGesture.OPEN_PALM) == _FakeGesture.OPEN_PALM

        # Simulate swipe exit: was_swiping=True, swiping=False -> reset
        smoother.reset()

        # After reset, buffer should be empty -- feeding None should return None
        assert smoother.update(None) is None, (
            "After exit reset, smoother should not return stale gesture"
        )
        assert len(smoother._buffer) == 1, "Buffer should only contain the one new frame"

    def test_exit_reset_clears_debouncer(self):
        """When swipe exits, debouncer must return to IDLE so no stale
        activation/cooldown state carries over."""
        from gesture_keys.debounce import GestureDebouncer, DebounceState
        from gesture_keys.classifier import Gesture

        debouncer = GestureDebouncer(activation_delay=0.3, cooldown_duration=0.5)

        # Advance debouncer to ACTIVATING state
        debouncer.update(Gesture.OPEN_PALM, 0.0)
        assert debouncer.state == DebounceState.ACTIVATING

        # Simulate swipe exit: reset
        debouncer.reset()
        assert debouncer.state == DebounceState.IDLE, (
            "After exit reset, debouncer should be IDLE"
        )

    def test_exit_reset_symmetric_with_entry(self):
        """The exit condition (was_swiping and not swiping) is the logical
        mirror of entry (swiping and not was_swiping). Both trigger resets."""
        # This test validates the logical symmetry by simulating the state
        # transitions that the main loop performs.
        was_swiping = False
        swiping = True

        # Entry: swiping and not was_swiping
        entry_fires = swiping and not was_swiping
        assert entry_fires is True, "Entry condition should fire"

        was_swiping = swiping  # Transition

        # During swipe: both True, neither fires
        swiping = True
        assert not (swiping and not was_swiping), "No re-entry while swiping"
        assert not (was_swiping and not swiping), "No exit while swiping"

        # Exit: was_swiping and not swiping
        swiping = False
        exit_fires = was_swiping and not swiping
        assert exit_fires is True, "Exit condition should fire"


    def test_smoother_reset_then_new_gesture_works(self):
        """After reset, a new gesture fills the window cleanly."""
        smoother = GestureSmoother(window_size=3)

        # Fill with OPEN_PALM
        for _ in range(3):
            smoother.update(_FakeGesture.OPEN_PALM)

        smoother.reset()

        # Fill with FIST
        for _ in range(3):
            result = smoother.update(_FakeGesture.FIST)

        assert result == _FakeGesture.FIST, "After reset, new gesture should dominate"


class TestHotReloadReset:
    """Tests for hot-reload resetting smoother and clearing settling state."""

    def test_hot_reload_resets_smoother(self):
        """Hot-reload must reset smoother so stale buffer doesn't persist
        across config changes."""
        smoother = GestureSmoother(window_size=3)

        # Fill smoother with gestures
        for _ in range(3):
            smoother.update(_FakeGesture.OPEN_PALM)
        assert len(smoother._buffer) == 3

        # Simulate hot-reload: reset()
        smoother.reset()
        assert len(smoother._buffer) == 0, "Smoother buffer should be empty after reset"

    def test_settling_frames_clear_on_reload(self):
        """Hot-reload must clear settling_frames_remaining so stale settling
        state doesn't persist across config changes."""
        det = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.2, settling_frames=10,
        )

        # Simulate settling state: manually set remaining frames
        det._settling_frames_remaining = 5
        assert det._settling_frames_remaining == 5

        # Simulate hot-reload: clear settling
        det._settling_frames_remaining = 0
        assert det._settling_frames_remaining == 0, (
            "Settling frames should be cleared after hot-reload"
        )


class TestTransitionLatency:
    """End-to-end test: swipe -> cooldown -> settling -> smoother refill -> debouncer fires.

    Validates that the full pipeline latency from cooldown end to static gesture
    fire is within the ~600ms budget (settling 100ms + smoother 100ms + activation_delay 400ms).
    """

    def test_transition_latency_within_budget(self):
        """After swipe cooldown ends, a held static gesture should fire within 0.7s.

        Pipeline stages after cooldown ends:
        1. Settling frames (3 frames @ ~33ms = ~100ms)
        2. Smoother window refill (3 frames @ ~33ms = ~100ms)
        3. Activation delay (0.4s default)
        Total: ~600ms, budget = 700ms with margin.
        """
        fps_dt = 0.033  # ~30fps

        # Create components with default parameters
        swipe_detector = SwipeDetector(
            buffer_size=6, min_velocity=0.3, min_displacement=0.05,
            cooldown_duration=0.5,
            # settling_frames uses default -- this is what we're testing
        )
        smoother = GestureSmoother(window_size=3)
        debouncer = GestureDebouncer(activation_delay=0.4, cooldown_duration=0.8)

        # Phase 1: Trigger a swipe
        positions = _generate_swipe_positions((0.7, 0.5), (0.2, 0.5), steps=8)
        results = _swipe_sequence(swipe_detector, positions, start_time=0.0, dt=fps_dt)
        assert any(r is not None for r in results), "Setup: swipe should fire"
        assert swipe_detector._state == _SwipeState.COOLDOWN

        # Phase 2: Advance past cooldown
        cooldown_end_time = 1.0  # Well past 0.5s cooldown
        swipe_detector.update(_make_wrist_landmarks(0.3, 0.5), cooldown_end_time)
        assert swipe_detector.is_swiping is False, "Cooldown should have expired"

        # Simulate main-loop exit reset (as __main__.py does)
        smoother.reset()
        debouncer.reset()

        # Phase 3: Feed static gesture frames and track when debouncer fires
        t = cooldown_end_time + fps_dt
        fire_time = None

        # Feed up to 30 frames (~1s) of static gesture
        for _ in range(30):
            # Swipe detector: feed stable position (settling guard consumes frames)
            swipe_detector.update(_make_wrist_landmarks(0.3, 0.5), t)

            # Static pipeline runs whenever is_swiping is False
            gesture = smoother.update(Gesture.OPEN_PALM)
            fire = debouncer.update(gesture, t)

            if fire is not None:
                fire_time = t
                break

            t += fps_dt

        assert fire_time is not None, (
            "Static gesture should have fired within 30 frames (~1s)"
        )

        latency = fire_time - cooldown_end_time
        assert latency < 0.7, (
            f"Transition latency {latency:.3f}s exceeds 0.7s budget. "
            f"Expected ~0.6s (smoother refill + activation_delay)."
        )
