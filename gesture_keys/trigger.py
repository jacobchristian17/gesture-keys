"""Trigger string data model and parser for the action library.

Trigger strings are compact representations of when an action fires:
- Static:   "fist:static"           -> detected gesture, no motion
- Holding:  "fist:holding"          -> gesture held for duration
- Moving:   "open_palm:moving:left" -> gesture with directional motion
- Sequence: "fist > open_palm"      -> gesture transition
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Union

from gesture_keys.classifier import Gesture


class TriggerState(Enum):
    """Trigger activation states."""

    STATIC = "static"
    HOLDING = "holding"
    MOVING = "moving"


class Direction(Enum):
    """Cardinal movement directions for moving triggers."""

    LEFT = "left"
    RIGHT = "right"
    UP = "up"
    DOWN = "down"


@dataclass(frozen=True)
class Trigger:
    """A single gesture trigger with state and optional direction."""

    gesture: Gesture
    state: TriggerState
    direction: Optional[Direction] = None


@dataclass(frozen=True)
class SequenceTrigger:
    """A two-gesture sequence trigger (gesture A -> gesture B)."""

    first: Trigger
    second: Trigger


class TriggerParseError(ValueError):
    """Raised when a trigger string cannot be parsed."""


# Pre-compute valid value sets for fast lookup
_VALID_GESTURES = {g.value for g in Gesture}
_VALID_STATES = {s.value for s in TriggerState}
_VALID_DIRECTIONS = {d.value for d in Direction}


def _parse_single(part: str, allow_bare: bool = False) -> Trigger:
    """Parse a single trigger part (not a sequence).

    Args:
        part: Trigger string like "fist:static" or "fist:moving:left".
        allow_bare: If True, allow bare gesture name without state
                    (defaults to STATIC). Used for sequence parts.

    Returns:
        Trigger instance.

    Raises:
        TriggerParseError: If the trigger string is invalid.
    """
    part = part.strip()
    if not part:
        raise TriggerParseError("empty trigger string")

    tokens = part.split(":")

    if len(tokens) == 1:
        if allow_bare:
            gesture_str = tokens[0]
            if gesture_str not in _VALID_GESTURES:
                raise TriggerParseError(
                    f"unknown gesture '{gesture_str}', "
                    f"expected one of: {sorted(_VALID_GESTURES)}"
                )
            return Trigger(
                gesture=Gesture(gesture_str),
                state=TriggerState.STATIC,
            )
        raise TriggerParseError(
            "state required, use gesture:static or gesture:holding"
        )

    if len(tokens) == 2:
        gesture_str, state_str = tokens
        if gesture_str not in _VALID_GESTURES:
            raise TriggerParseError(
                f"unknown gesture '{gesture_str}', "
                f"expected one of: {sorted(_VALID_GESTURES)}"
            )
        if state_str not in _VALID_STATES:
            raise TriggerParseError(
                f"invalid state '{state_str}', "
                f"expected one of: {sorted(_VALID_STATES)}"
            )
        state = TriggerState(state_str)
        if state == TriggerState.MOVING:
            raise TriggerParseError(
                "direction required for moving trigger, "
                "use gesture:moving:direction"
            )
        return Trigger(gesture=Gesture(gesture_str), state=state)

    if len(tokens) == 3:
        gesture_str, state_str, direction_str = tokens
        if gesture_str not in _VALID_GESTURES:
            raise TriggerParseError(
                f"unknown gesture '{gesture_str}', "
                f"expected one of: {sorted(_VALID_GESTURES)}"
            )
        if state_str not in _VALID_STATES:
            raise TriggerParseError(
                f"invalid state '{state_str}', "
                f"expected one of: {sorted(_VALID_STATES)}"
            )
        state = TriggerState(state_str)
        if state != TriggerState.MOVING:
            raise TriggerParseError(
                "direction only valid for moving triggers"
            )
        if direction_str not in _VALID_DIRECTIONS:
            raise TriggerParseError(
                f"invalid direction '{direction_str}', "
                f"expected one of: {sorted(_VALID_DIRECTIONS)}"
            )
        return Trigger(
            gesture=Gesture(gesture_str),
            state=state,
            direction=Direction(direction_str),
        )

    raise TriggerParseError(
        f"too many ':' separators in '{part}', "
        "expected gesture:state or gesture:state:direction"
    )


def parse_trigger(trigger_string: str) -> Union[Trigger, SequenceTrigger]:
    """Parse a trigger string into a Trigger or SequenceTrigger.

    Supported formats:
        "fist:static"              -> Trigger (static)
        "fist:holding"             -> Trigger (holding)
        "fist:moving:left"         -> Trigger (moving with direction)
        "fist > open_palm"         -> SequenceTrigger

    Args:
        trigger_string: The trigger string to parse.

    Returns:
        Trigger or SequenceTrigger instance.

    Raises:
        TriggerParseError: If the trigger string is invalid.
    """
    trigger_string = trigger_string.strip()
    if not trigger_string:
        raise TriggerParseError("empty trigger string")

    # Sequence trigger: contains ">"
    if ">" in trigger_string:
        parts = [p.strip() for p in trigger_string.split(">")]
        if len(parts) != 2:
            raise TriggerParseError(
                "sequence trigger must have exactly two parts "
                "separated by ' > '"
            )
        first_str, second_str = parts
        if not first_str.strip() or not second_str.strip():
            raise TriggerParseError(
                "incomplete sequence trigger, both parts required"
            )
        first = _parse_single(first_str, allow_bare=True)
        second = _parse_single(second_str, allow_bare=True)
        return SequenceTrigger(first=first, second=second)

    # Single trigger
    return _parse_single(trigger_string)
