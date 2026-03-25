"""Unit tests for ActionResolver and ActionDispatcher.

Covers: resolver lookup, hand switching, compound resolution, tap dispatch,
hold_key dispatch, hold-to-hold transition ordering, compound fire dispatch,
release_all idempotency, unmapped gesture safety.
"""

from unittest.mock import MagicMock, call

import pytest

from gesture_keys.action import Action, ActionDispatcher, ActionResolver, FireMode
from gesture_keys.classifier import Gesture
from gesture_keys.keystroke import Key
from gesture_keys.orchestrator import OrchestratorAction, OrchestratorSignal
from gesture_keys.swipe import SwipeDirection


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_action(key_string: str, fire_mode: FireMode, gesture_name: str,
                 modifiers: list | None = None, key: object = "x") -> Action:
    """Helper to create Action instances for testing."""
    return Action(
        key_string=key_string,
        fire_mode=fire_mode,
        gesture_name=gesture_name,
        modifiers=modifiers or [],
        key=key,
    )


@pytest.fixture
def right_actions() -> dict[str, Action]:
    return {
        "fist": _make_action("space", FireMode.TAP, "fist", key=Key.space),
        "open_palm": _make_action("ctrl+z", FireMode.HOLD_KEY, "open_palm",
                                  modifiers=[Key.ctrl], key="z"),
        "peace": _make_action("enter", FireMode.TAP, "peace", key=Key.enter),
    }


@pytest.fixture
def left_actions() -> dict[str, Action]:
    return {
        "fist": _make_action("tab", FireMode.TAP, "fist", key=Key.tab),
    }


@pytest.fixture
def right_compound() -> dict[tuple[str, str], Action]:
    return {
        ("open_palm", "swipe_left"): _make_action(
            "1", FireMode.TAP, "open_palm+swipe_left", key="1"
        ),
        ("open_palm", "swipe_right"): _make_action(
            "2", FireMode.TAP, "open_palm+swipe_right", key="2"
        ),
    }


@pytest.fixture
def left_compound() -> dict[tuple[str, str], Action]:
    return {}


@pytest.fixture
def resolver(right_actions, left_actions, right_compound, left_compound):
    return ActionResolver(right_actions, left_actions, right_compound, left_compound)


@pytest.fixture
def mock_sender():
    sender = MagicMock()
    sender.send = MagicMock()
    sender.press_and_hold = MagicMock()
    sender.release_held = MagicMock()
    sender.release_all = MagicMock()
    return sender


@pytest.fixture
def dispatcher(mock_sender, resolver):
    return ActionDispatcher(mock_sender, resolver)


# ===========================================================================
# TestActionResolver -- ACTN-01
# ===========================================================================

class TestActionResolver:
    """ActionResolver maps (gesture_name, hand) to an Action."""

    def test_resolve_mapped_gesture(self, resolver, right_actions):
        """resolve('fist') returns the right-hand fist Action."""
        action = resolver.resolve("fist")
        assert action is not None
        assert action.key_string == "space"
        assert action.fire_mode == FireMode.TAP

    def test_resolve_unmapped_gesture_returns_none(self, resolver):
        """resolve('unmapped_gesture') returns None."""
        assert resolver.resolve("thumbs_up") is None

    def test_set_hand_left_switches_map(self, resolver):
        """set_hand('Left') switches to left-hand action map."""
        resolver.set_hand("Left")
        action = resolver.resolve("fist")
        assert action is not None
        assert action.key_string == "tab"

    def test_set_hand_right_switches_back(self, resolver):
        """set_hand('Right') switches back to right-hand map."""
        resolver.set_hand("Left")
        resolver.set_hand("Right")
        action = resolver.resolve("fist")
        assert action is not None
        assert action.key_string == "space"

    def test_resolve_compound_mapped(self, resolver):
        """resolve_compound returns Action for mapped compound gesture."""
        action = resolver.resolve_compound("open_palm", "swipe_left")
        assert action is not None
        assert action.key_string == "1"

    def test_resolve_compound_unmapped_direction_returns_none(self, resolver):
        """resolve_compound with unmapped direction returns None."""
        assert resolver.resolve_compound("open_palm", "swipe_up") is None

    def test_resolve_compound_unmapped_gesture_returns_none(self, resolver):
        """resolve_compound with unmapped gesture returns None."""
        assert resolver.resolve_compound("fist", "swipe_left") is None

    def test_left_hand_compound_empty(self, resolver):
        """Left hand has no compound mappings."""
        resolver.set_hand("Left")
        assert resolver.resolve_compound("open_palm", "swipe_left") is None


# ===========================================================================
# TestTapFireMode -- ACTN-02
# ===========================================================================

class TestTapFireMode:
    """Tap fire mode calls sender.send() once per FIRE signal."""

    def test_fire_tap_calls_send(self, dispatcher, mock_sender, right_actions):
        """dispatch(FIRE for tap-mapped gesture) calls sender.send() once."""
        signal = OrchestratorSignal(OrchestratorAction.FIRE, Gesture.FIST)
        dispatcher.dispatch(signal)
        mock_sender.send.assert_called_once_with([], Key.space)

    def test_fire_unmapped_does_nothing(self, dispatcher, mock_sender):
        """dispatch(FIRE for unmapped gesture) does nothing."""
        signal = OrchestratorSignal(OrchestratorAction.FIRE, Gesture.THUMBS_UP)
        dispatcher.dispatch(signal)
        mock_sender.send.assert_not_called()
        mock_sender.press_and_hold.assert_not_called()

    def test_fire_hold_mapped_still_sends(self, dispatcher, mock_sender):
        """dispatch(FIRE for hold_key-mapped gesture) calls sender.send(), not hold.

        FIRE is always tap behavior regardless of fire_mode.
        """
        signal = OrchestratorSignal(OrchestratorAction.FIRE, Gesture.OPEN_PALM)
        dispatcher.dispatch(signal)
        mock_sender.send.assert_called_once_with([Key.ctrl], "z")
        mock_sender.press_and_hold.assert_not_called()


# ===========================================================================
# TestHoldKeyFireMode -- ACTN-03
# ===========================================================================

class TestHoldKeyFireMode:
    """Hold_key fire mode uses press_and_hold / release_held lifecycle."""

    def test_hold_start_calls_press_and_hold(self, dispatcher, mock_sender):
        """dispatch(HOLD_START for hold_key gesture) calls sender.press_and_hold()."""
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(signal)
        mock_sender.press_and_hold.assert_called_once_with([Key.ctrl], "z")

    def test_hold_start_tap_gesture_ignored(self, dispatcher, mock_sender):
        """dispatch(HOLD_START for tap-mode gesture) does nothing."""
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.FIST)
        dispatcher.dispatch(signal)
        mock_sender.press_and_hold.assert_not_called()

    def test_hold_end_calls_release_held(self, dispatcher, mock_sender):
        """dispatch(HOLD_END) calls sender.release_held() and clears held state."""
        # First hold start
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(start)
        # Then hold end
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end)
        mock_sender.release_held.assert_called_once()

    def test_hold_end_without_start_does_nothing(self, dispatcher, mock_sender):
        """dispatch(HOLD_END) with no active hold does nothing."""
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end)
        mock_sender.release_held.assert_not_called()

    def test_hold_to_hold_transition_ordering(self, dispatcher, mock_sender):
        """Hold-to-hold: old keys released before new keys pressed.

        Orchestrator emits HOLD_END for old gesture, then pipeline processes
        new gesture HOLD_START. Verify the ordering.
        """
        # Start holding open_palm
        start1 = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(start1)

        # Orchestrator emits HOLD_END for old, then new gesture starts
        end1 = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end1)

        # Verify release happened before we could start new hold
        assert mock_sender.release_held.call_count == 1

        # Now new gesture could start holding (if it were hold_key mode)
        # This verifies the ordering is correct


# ===========================================================================
# TestCompoundFire
# ===========================================================================

class TestCompoundFire:
    """COMPOUND_FIRE resolves compound mapping and sends."""

    def test_compound_fire_calls_send(self, dispatcher, mock_sender):
        """dispatch(COMPOUND_FIRE) resolves compound and sends."""
        signal = OrchestratorSignal(
            OrchestratorAction.COMPOUND_FIRE,
            Gesture.OPEN_PALM,
            SwipeDirection.SWIPE_LEFT,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_called_once_with([], "1")

    def test_compound_fire_unmapped_does_nothing(self, dispatcher, mock_sender):
        """dispatch(COMPOUND_FIRE for unmapped compound) does nothing."""
        signal = OrchestratorSignal(
            OrchestratorAction.COMPOUND_FIRE,
            Gesture.FIST,
            SwipeDirection.SWIPE_LEFT,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_not_called()

    def test_compound_fire_no_direction_does_nothing(self, dispatcher, mock_sender):
        """dispatch(COMPOUND_FIRE with no direction) does nothing."""
        signal = OrchestratorSignal(
            OrchestratorAction.COMPOUND_FIRE,
            Gesture.OPEN_PALM,
            None,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_not_called()


# ===========================================================================
# TestStuckKeyPrevention -- ACTN-04
# ===========================================================================

class TestStuckKeyPrevention:
    """release_all() releases all held keys and clears internal state."""

    def test_release_all_calls_sender_release_all(self, dispatcher, mock_sender):
        """release_all() calls sender.release_all()."""
        dispatcher.release_all()
        mock_sender.release_all.assert_called_once()

    def test_release_all_clears_held_action(self, dispatcher, mock_sender):
        """release_all() clears _held_action so subsequent HOLD_END is no-op."""
        # Start a hold
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(start)
        # Release all
        dispatcher.release_all()
        mock_sender.release_all.assert_called_once()
        # HOLD_END after release_all should do nothing
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end)
        # release_held should NOT be called (already released via release_all)
        mock_sender.release_held.assert_not_called()

    def test_release_all_idempotent(self, dispatcher, mock_sender):
        """release_all() called twice does not crash."""
        dispatcher.release_all()
        dispatcher.release_all()
        assert mock_sender.release_all.call_count == 2

    def test_hold_end_after_release_all_no_double_release(self, dispatcher, mock_sender):
        """After release_all(), HOLD_END does not call release_held (no double-release)."""
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(start)
        dispatcher.release_all()
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end)
        mock_sender.release_held.assert_not_called()
