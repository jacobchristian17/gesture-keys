"""Unit tests for ActionResolver and ActionDispatcher.

Covers: resolver lookup (static, holding, moving, sequence), hand switching,
tap dispatch, hold_key dispatch, hold-to-hold transition ordering,
release_all idempotency, unmapped gesture safety, MOVING_FIRE and
SEQUENCE_FIRE dispatch.
"""

from unittest.mock import MagicMock, call

import pytest

from gesture_keys.action import Action, ActionDispatcher, ActionResolver, FireMode
from gesture_keys.classifier import Gesture
from gesture_keys.keystroke import Key
from gesture_keys.orchestrator import OrchestratorAction, OrchestratorSignal
from gesture_keys.trigger import Direction


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
def right_static() -> dict[str, Action]:
    return {
        "fist": _make_action("space", FireMode.TAP, "fist", key=Key.space),
        "peace": _make_action("enter", FireMode.TAP, "peace", key=Key.enter),
    }


@pytest.fixture
def left_static() -> dict[str, Action]:
    return {
        "fist": _make_action("tab", FireMode.TAP, "fist", key=Key.tab),
    }


@pytest.fixture
def right_holding() -> dict[str, Action]:
    return {
        "open_palm": _make_action("ctrl+z", FireMode.HOLD_KEY, "open_palm",
                                  modifiers=[Key.ctrl], key="z"),
    }


@pytest.fixture
def left_holding() -> dict[str, Action]:
    return {
        "open_palm": _make_action("ctrl+y", FireMode.HOLD_KEY, "open_palm",
                                  modifiers=[Key.ctrl], key="y"),
    }


@pytest.fixture
def right_moving() -> dict[tuple[str, str], Action]:
    return {
        ("open_palm", "left"): _make_action(
            "1", FireMode.TAP, "open_palm+left", key="1"
        ),
        ("open_palm", "right"): _make_action(
            "2", FireMode.TAP, "open_palm+right", key="2"
        ),
    }


@pytest.fixture
def left_moving() -> dict[tuple[str, str], Action]:
    return {}


@pytest.fixture
def right_sequence() -> dict[tuple[str, str], Action]:
    return {
        ("fist", "open_palm"): _make_action(
            "ctrl+s", FireMode.TAP, "fist->open_palm",
            modifiers=[Key.ctrl], key="s",
        ),
    }


@pytest.fixture
def left_sequence() -> dict[tuple[str, str], Action]:
    return {}


@pytest.fixture
def resolver(right_static, left_static, right_holding, left_holding,
             right_moving, left_moving, right_sequence, left_sequence):
    return ActionResolver(
        right_static=right_static,
        left_static=left_static,
        right_holding=right_holding,
        left_holding=left_holding,
        right_moving=right_moving,
        left_moving=left_moving,
        right_sequence=right_sequence,
        left_sequence=left_sequence,
    )


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
# TestResolveStatic
# ===========================================================================

class TestResolveStatic:
    """resolve_static maps gesture name to static Action."""

    def test_resolve_static_mapped_gesture(self, resolver):
        """resolve_static('fist') returns the right-hand fist Action."""
        action = resolver.resolve_static("fist")
        assert action is not None
        assert action.key_string == "space"
        assert action.fire_mode == FireMode.TAP

    def test_resolve_static_unmapped_returns_none(self, resolver):
        """resolve_static('unmapped') returns None."""
        assert resolver.resolve_static("thumbs_up") is None

    def test_resolve_static_left_hand(self, resolver):
        """set_hand('Left') then resolve_static uses left static map."""
        resolver.set_hand("Left")
        action = resolver.resolve_static("fist")
        assert action is not None
        assert action.key_string == "tab"

    def test_resolve_static_switch_back_to_right(self, resolver):
        """set_hand('Right') switches back to right static map."""
        resolver.set_hand("Left")
        resolver.set_hand("Right")
        action = resolver.resolve_static("fist")
        assert action is not None
        assert action.key_string == "space"


# ===========================================================================
# TestResolveHolding
# ===========================================================================

class TestResolveHolding:
    """resolve_holding maps gesture name to holding Action."""

    def test_resolve_holding_mapped(self, resolver):
        """resolve_holding('open_palm') returns the right-hand holding Action."""
        action = resolver.resolve_holding("open_palm")
        assert action is not None
        assert action.key_string == "ctrl+z"
        assert action.fire_mode == FireMode.HOLD_KEY

    def test_resolve_holding_unmapped_returns_none(self, resolver):
        """resolve_holding('fist') returns None (fist is static, not holding)."""
        assert resolver.resolve_holding("fist") is None

    def test_resolve_holding_left_hand(self, resolver):
        """set_hand('Left') then resolve_holding uses left holding map."""
        resolver.set_hand("Left")
        action = resolver.resolve_holding("open_palm")
        assert action is not None
        assert action.key_string == "ctrl+y"


# ===========================================================================
# TestResolveMoving
# ===========================================================================

class TestResolveMoving:
    """resolve_moving maps (gesture, direction) to moving Action."""

    def test_resolve_moving_mapped(self, resolver):
        """resolve_moving with mapped gesture+direction returns Action."""
        action = resolver.resolve_moving("open_palm", Direction.LEFT)
        assert action is not None
        assert action.key_string == "1"

    def test_resolve_moving_unmapped_direction_returns_none(self, resolver):
        """resolve_moving with unmapped direction returns None."""
        assert resolver.resolve_moving("open_palm", Direction.UP) is None

    def test_resolve_moving_unmapped_gesture_returns_none(self, resolver):
        """resolve_moving with unmapped gesture returns None."""
        assert resolver.resolve_moving("fist", Direction.LEFT) is None

    def test_resolve_moving_left_hand_empty(self, resolver):
        """Left hand has no moving mappings."""
        resolver.set_hand("Left")
        assert resolver.resolve_moving("open_palm", Direction.LEFT) is None


# ===========================================================================
# TestResolveSequence
# ===========================================================================

class TestResolveSequence:
    """resolve_sequence maps (first_gesture, second_gesture) to sequence Action."""

    def test_resolve_sequence_mapped(self, resolver):
        """resolve_sequence with mapped pair returns Action."""
        action = resolver.resolve_sequence(Gesture.FIST, Gesture.OPEN_PALM)
        assert action is not None
        assert action.key_string == "ctrl+s"

    def test_resolve_sequence_unmapped_returns_none(self, resolver):
        """resolve_sequence with unmapped pair returns None."""
        assert resolver.resolve_sequence(Gesture.FIST, Gesture.FIST) is None

    def test_resolve_sequence_left_hand_empty(self, resolver):
        """Left hand has no sequence mappings."""
        resolver.set_hand("Left")
        assert resolver.resolve_sequence(Gesture.FIST, Gesture.OPEN_PALM) is None


# ===========================================================================
# TestResolveCompoundRemoved
# ===========================================================================

class TestResolveCompoundRemoved:
    """resolve_compound method no longer exists."""

    def test_resolve_compound_raises_attribute_error(self, resolver):
        """resolve_compound() raises AttributeError."""
        assert not hasattr(resolver, "resolve_compound")


# ===========================================================================
# TestSetHand
# ===========================================================================

class TestSetHand:
    """set_hand switches all four active map pairs."""

    def test_set_hand_left_switches_all_maps(self, resolver):
        """set_hand('Left') switches static, holding, moving, sequence maps."""
        resolver.set_hand("Left")
        # Static switched
        assert resolver.resolve_static("fist") is not None
        assert resolver.resolve_static("fist").key_string == "tab"
        # Holding switched
        assert resolver.resolve_holding("open_palm") is not None
        assert resolver.resolve_holding("open_palm").key_string == "ctrl+y"
        # Moving switched (empty for left)
        assert resolver.resolve_moving("open_palm", Direction.LEFT) is None
        # Sequence switched (empty for left)
        assert resolver.resolve_sequence(Gesture.FIST, Gesture.OPEN_PALM) is None

    def test_set_hand_right_restores_all_maps(self, resolver):
        """set_hand('Right') restores all four maps."""
        resolver.set_hand("Left")
        resolver.set_hand("Right")
        assert resolver.resolve_static("fist").key_string == "space"
        assert resolver.resolve_holding("open_palm").key_string == "ctrl+z"
        assert resolver.resolve_moving("open_palm", Direction.LEFT).key_string == "1"
        assert resolver.resolve_sequence(Gesture.FIST, Gesture.OPEN_PALM).key_string == "ctrl+s"


# ===========================================================================
# TestTapFireMode -- ACTN-02
# ===========================================================================

class TestTapFireMode:
    """Tap fire mode calls sender.send() once per FIRE signal."""

    def test_fire_tap_calls_send(self, dispatcher, mock_sender):
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


# ===========================================================================
# TestHoldKeyFireMode -- ACTN-03
# ===========================================================================

class TestHoldKeyFireMode:
    """Hold_key fire mode sets _held_action for tick-based tap-repeat."""

    def test_hold_start_sets_held_action(self, dispatcher, mock_sender):
        """dispatch(HOLD_START for hold_key gesture) sets _held_action."""
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(signal)
        assert dispatcher._held_action is not None
        assert dispatcher._held_action.key_string == "ctrl+z"
        mock_sender.press_and_hold.assert_not_called()

    def test_hold_start_tap_gesture_ignored(self, dispatcher, mock_sender):
        """dispatch(HOLD_START for tap-mode gesture) does nothing."""
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.FIST)
        dispatcher.dispatch(signal)
        mock_sender.press_and_hold.assert_not_called()
        assert dispatcher._held_action is None

    def test_hold_end_clears_held_action(self, dispatcher, mock_sender):
        """dispatch(HOLD_END) clears _held_action."""
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(start)
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end)
        assert dispatcher._held_action is None
        mock_sender.release_held.assert_not_called()

    def test_hold_end_without_start_does_nothing(self, dispatcher, mock_sender):
        """dispatch(HOLD_END) with no active hold does nothing."""
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end)
        mock_sender.release_held.assert_not_called()

    def test_hold_to_hold_transition_ordering(self, dispatcher, mock_sender):
        """Hold-to-hold: old hold cleared before new hold set."""
        start1 = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(start1)
        end1 = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end1)
        assert dispatcher._held_action is None
        mock_sender.release_held.assert_not_called()


# ===========================================================================
# TestMovingFireDispatch
# ===========================================================================

class TestMovingFireDispatch:
    """MOVING_FIRE signal dispatches via resolve_moving and calls sender.send()."""

    def test_moving_fire_mapped_calls_send(self, dispatcher, mock_sender):
        """MOVING_FIRE for mapped (gesture, direction) calls sender.send()."""
        signal = OrchestratorSignal(
            OrchestratorAction.MOVING_FIRE,
            Gesture.OPEN_PALM,
            direction=Direction.LEFT,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_called_once_with([], "1")

    def test_moving_fire_unmapped_does_nothing(self, dispatcher, mock_sender):
        """MOVING_FIRE for unmapped (gesture, direction) does nothing."""
        signal = OrchestratorSignal(
            OrchestratorAction.MOVING_FIRE,
            Gesture.OPEN_PALM,
            direction=Direction.UP,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_not_called()

    def test_moving_fire_unmapped_gesture_does_nothing(self, dispatcher, mock_sender):
        """MOVING_FIRE for unmapped gesture does nothing."""
        signal = OrchestratorSignal(
            OrchestratorAction.MOVING_FIRE,
            Gesture.FIST,
            direction=Direction.LEFT,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_not_called()


# ===========================================================================
# TestSequenceFireDispatch
# ===========================================================================

class TestSequenceFireDispatch:
    """SEQUENCE_FIRE signal dispatches via resolve_sequence and calls sender.send()."""

    def test_sequence_fire_mapped_calls_send(self, dispatcher, mock_sender):
        """SEQUENCE_FIRE for mapped (first, second) calls sender.send()."""
        signal = OrchestratorSignal(
            OrchestratorAction.SEQUENCE_FIRE,
            Gesture.FIST,
            second_gesture=Gesture.OPEN_PALM,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_called_once_with([Key.ctrl], "s")

    def test_sequence_fire_unmapped_does_nothing(self, dispatcher, mock_sender):
        """SEQUENCE_FIRE for unmapped (first, second) does nothing."""
        signal = OrchestratorSignal(
            OrchestratorAction.SEQUENCE_FIRE,
            Gesture.FIST,
            second_gesture=Gesture.FIST,
        )
        dispatcher.dispatch(signal)
        mock_sender.send.assert_not_called()


# ===========================================================================
# TestHoldKeyTick
# ===========================================================================

class TestHoldKeyTick:
    """tick() sends repeated keystrokes at repeat_interval while _held_action is set."""

    def test_tick_no_held_action_does_nothing(self, mock_sender, resolver):
        """tick() with no held action does not call sender."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        d.tick(1.0)
        mock_sender.send.assert_not_called()

    def test_hold_start_then_tick_sends_first_keystroke(self, mock_sender, resolver):
        """HOLD_START + tick() sends first keystroke immediately."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        d.dispatch(signal)
        mock_sender.send.reset_mock()
        d.tick(1.0)
        mock_sender.send.assert_called_once_with([Key.ctrl], "z")

    def test_tick_sends_when_interval_elapsed(self, mock_sender, resolver):
        """tick() sends when repeat_interval has elapsed since last send."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        d.dispatch(signal)
        d.tick(1.0)
        mock_sender.send.reset_mock()
        d.tick(1.04)
        mock_sender.send.assert_called_once_with([Key.ctrl], "z")

    def test_tick_does_not_send_before_interval(self, mock_sender, resolver):
        """tick() does NOT send when repeat_interval has not elapsed."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        d.dispatch(signal)
        d.tick(1.0)
        mock_sender.send.reset_mock()
        d.tick(1.01)
        mock_sender.send.assert_not_called()

    def test_hold_end_stops_tick(self, mock_sender, resolver):
        """HOLD_END clears held action; subsequent tick() does nothing."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        d.dispatch(start)
        d.tick(1.0)
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        d.dispatch(end)
        mock_sender.send.reset_mock()
        d.tick(1.1)
        mock_sender.send.assert_not_called()

    def test_release_all_stops_tick(self, mock_sender, resolver):
        """release_all() clears held action; subsequent tick() does nothing."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        d.dispatch(start)
        d.tick(1.0)
        d.release_all()
        mock_sender.send.reset_mock()
        d.tick(1.1)
        mock_sender.send.assert_not_called()

    def test_hold_start_never_calls_press_and_hold(self, mock_sender, resolver):
        """HOLD_START no longer calls sender.press_and_hold()."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        signal = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        d.dispatch(signal)
        mock_sender.press_and_hold.assert_not_called()

    def test_hold_end_never_calls_release_held(self, mock_sender, resolver):
        """HOLD_END no longer calls sender.release_held()."""
        d = ActionDispatcher(mock_sender, resolver, repeat_interval=0.03)
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        d.dispatch(start)
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        d.dispatch(end)
        mock_sender.release_held.assert_not_called()


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
        start = OrchestratorSignal(OrchestratorAction.HOLD_START, Gesture.OPEN_PALM)
        dispatcher.dispatch(start)
        dispatcher.release_all()
        mock_sender.release_all.assert_called_once()
        end = OrchestratorSignal(OrchestratorAction.HOLD_END, Gesture.OPEN_PALM)
        dispatcher.dispatch(end)
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
