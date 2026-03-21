"""Rule-based gesture classification from 21 hand landmarks."""

import math
from enum import Enum
from typing import Any, Optional


class Gesture(Enum):
    """Recognized hand gestures."""

    OPEN_PALM = "open_palm"
    FIST = "fist"
    THUMBS_UP = "thumbs_up"
    PEACE = "peace"
    POINTING = "pointing"
    PINCH = "pinch"


# MediaPipe landmark indices
WRIST = 0
THUMB_CMC = 1
THUMB_MCP = 2
THUMB_IP = 3
THUMB_TIP = 4
INDEX_MCP = 5
INDEX_PIP = 6
INDEX_DIP = 7
INDEX_TIP = 8
MIDDLE_MCP = 9
MIDDLE_PIP = 10
MIDDLE_DIP = 11
MIDDLE_TIP = 12
RING_MCP = 13
RING_PIP = 14
RING_DIP = 15
RING_TIP = 16
PINKY_MCP = 17
PINKY_PIP = 18
PINKY_DIP = 19
PINKY_TIP = 20

# Finger tip and PIP joint pairs (index, middle, ring, pinky)
FINGER_TIPS = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
FINGER_PIPS = [INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]


class GestureClassifier:
    """Classify hand gestures from MediaPipe landmark positions.

    Uses rule-based finger state detection (extended/curled) and
    priority-ordered classification:
    PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM > None
    """

    def __init__(self, thresholds: Optional[dict[str, float]] = None):
        """Initialize classifier with optional per-gesture thresholds.

        Args:
            thresholds: Dict mapping gesture name to threshold value.
                        For pinch, this is the max distance between
                        thumb tip and index tip (default 0.05).
                        Other thresholds reserved for future use.
        """
        self._thresholds = thresholds or {}
        self._pinch_threshold = self._thresholds.get("pinch", 0.05)

    def classify(self, landmarks: list[Any]) -> Optional[Gesture]:
        """Classify a gesture from 21 hand landmarks.

        Args:
            landmarks: List of 21 landmark objects with .x, .y, .z attributes.

        Returns:
            Gesture enum value, or None if no gesture matches.
        """
        # Priority order: PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM
        if self._is_pinch(landmarks):
            return Gesture.PINCH

        finger_states = self._get_finger_states(landmarks)
        thumb_extended = self._is_thumb_extended(landmarks)

        # finger_states: [index, middle, ring, pinky] True = extended
        index_ext, middle_ext, ring_ext, pinky_ext = finger_states

        # FIST: all fingers curled + thumb curled
        if not any(finger_states) and not thumb_extended:
            return Gesture.FIST

        # THUMBS_UP: thumb extended + all 4 fingers curled
        if thumb_extended and not any(finger_states):
            return Gesture.THUMBS_UP

        # POINTING: index extended, middle + ring + pinky curled
        if index_ext and not middle_ext and not ring_ext and not pinky_ext:
            return Gesture.POINTING

        # PEACE: index + middle extended, ring + pinky curled
        if index_ext and middle_ext and not ring_ext and not pinky_ext:
            return Gesture.PEACE

        # OPEN_PALM: all 4 fingers extended + thumb extended
        if all(finger_states) and thumb_extended:
            return Gesture.OPEN_PALM

        return None

    def _is_finger_extended(self, landmarks: list, tip_idx: int, pip_idx: int) -> bool:
        """Check if a finger is extended (tip above PIP joint).

        In normalized coordinates, lower Y = higher on screen = extended.
        """
        return landmarks[tip_idx].y < landmarks[pip_idx].y

    def _is_thumb_extended(self, landmarks: list) -> bool:
        """Check if thumb is extended.

        Compare thumb tip x-distance from wrist vs thumb IP x-distance
        from wrist. If tip is further, thumb is extended.
        """
        tip_dist = abs(landmarks[THUMB_TIP].x - landmarks[WRIST].x)
        ip_dist = abs(landmarks[THUMB_IP].x - landmarks[WRIST].x)
        return tip_dist > ip_dist

    def _is_pinch(self, landmarks: list) -> bool:
        """Check if thumb tip is close to index tip (pinch gesture)."""
        dx = landmarks[THUMB_TIP].x - landmarks[INDEX_TIP].x
        dy = landmarks[THUMB_TIP].y - landmarks[INDEX_TIP].y
        dz = landmarks[THUMB_TIP].z - landmarks[INDEX_TIP].z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)
        return distance < self._pinch_threshold

    def _get_finger_states(self, landmarks: list) -> list[bool]:
        """Get extended/curled state for index, middle, ring, pinky."""
        return [
            self._is_finger_extended(landmarks, tip, pip)
            for tip, pip in zip(FINGER_TIPS, FINGER_PIPS)
        ]
