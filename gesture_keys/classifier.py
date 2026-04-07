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
    OK = "ok"
    SCOUT = "scout"


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

# Finger tip, PIP, and MCP joint groups (index, middle, ring, pinky)
FINGER_TIPS = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
FINGER_PIPS = [INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP]
FINGER_MCPS = [INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]


class GestureClassifier:
    """Classify hand gestures from MediaPipe landmark positions.

    Uses rule-based finger state detection (extended/curled) with
    hysteresis to prevent boundary flicker, and priority-ordered
    classification:
    OK > PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM > SCOUT > None
    """

    def __init__(
        self,
        thresholds: Optional[dict[str, float]] = None,
        hysteresis_margin: float = 0.02,
    ):
        """Initialize classifier with optional per-gesture thresholds.

        Args:
            thresholds: Dict mapping gesture name to threshold value.
                        For pinch, this is the max distance between
                        thumb tip and index tip (default 0.05).
            hysteresis_margin: Y-coordinate margin for finger/thumb
                               extension hysteresis. Higher = more stable
                               but less responsive.
        """
        self._thresholds = thresholds or {}
        self._pinch_threshold = self._thresholds.get("pinch", 0.05)
        self._hysteresis_margin = hysteresis_margin

        # Hysteresis state
        self._prev_finger_states = [False, False, False, False]
        self._prev_thumb_extended = False
        self._prev_pinch = False

    def reset(self) -> None:
        """Reset hysteresis state. Call on hand switch or config reload."""
        self._prev_finger_states = [False, False, False, False]
        self._prev_thumb_extended = False
        self._prev_pinch = False

    def classify(self, landmarks: list[Any]) -> Optional[Gesture]:
        """Classify a gesture from 21 hand landmarks.

        Args:
            landmarks: List of 21 landmark objects with .x, .y, .z attributes.

        Returns:
            Gesture enum value, or None if no gesture matches.
        """
        # Compute all states once (hysteresis is applied per-call)
        finger_states = self._get_finger_states(landmarks)
        thumb_extended = self._is_thumb_extended(landmarks)
        pinch_detected = self._is_pinch(landmarks, thumb_extended)

        # finger_states: [index, middle, ring, pinky] True = extended
        index_ext, middle_ext, ring_ext, pinky_ext = finger_states

        # Priority order: OK > PINCH > FIST > THUMBS_UP > POINTING > PEACE > OPEN_PALM > SCOUT

        # OK: pinch (thumb+index touching) + middle+ring+pinky extended
        if pinch_detected and middle_ext and ring_ext and pinky_ext:
            return Gesture.OK

        # PINCH: thumb+index touching, remaining fingers not all extended
        if pinch_detected:
            return Gesture.PINCH

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

        # SCOUT: index + middle + ring extended, pinky curled
        if index_ext and middle_ext and ring_ext and not pinky_ext:
            return Gesture.SCOUT

        return None

    def _is_finger_extended(
        self,
        landmarks: list,
        tip_idx: int,
        pip_idx: int,
        mcp_idx: int,
        finger_index: int,
    ) -> bool:
        """Check if a finger is extended with hysteresis.

        Uses arm/disarm margins around the extension boundary to prevent
        flicker from borderline finger positions.
        """
        margin = self._hysteresis_margin
        was_extended = self._prev_finger_states[finger_index]

        if was_extended:
            # Already extended: stays extended unless clearly curled (relaxed check)
            extended = (landmarks[tip_idx].y < landmarks[pip_idx].y + margin and
                        landmarks[pip_idx].y < landmarks[mcp_idx].y + margin)
        else:
            # Currently curled: needs clear extension to switch (strict check)
            extended = (landmarks[tip_idx].y < landmarks[pip_idx].y - margin and
                        landmarks[pip_idx].y < landmarks[mcp_idx].y - margin)

        self._prev_finger_states[finger_index] = extended
        return extended

    def _is_thumb_extended(self, landmarks: list) -> bool:
        """Check if thumb is extended with hysteresis."""
        tip_dist = abs(landmarks[THUMB_TIP].x - landmarks[WRIST].x)
        ip_dist = abs(landmarks[THUMB_IP].x - landmarks[WRIST].x)
        margin = self._hysteresis_margin

        if self._prev_thumb_extended:
            extended = tip_dist > ip_dist - margin
        else:
            extended = tip_dist > ip_dist + margin

        self._prev_thumb_extended = extended
        return extended

    def _is_pinch(self, landmarks: list, thumb_extended: bool) -> bool:
        """Check for pinch gesture with hysteresis on distance threshold.

        Uses tighter threshold to enter pinch, looser to exit, preventing
        flicker at the boundary. Excludes fist poses via thumb_extended guard.
        """
        dx = landmarks[THUMB_TIP].x - landmarks[INDEX_TIP].x
        dy = landmarks[THUMB_TIP].y - landmarks[INDEX_TIP].y
        dz = landmarks[THUMB_TIP].z - landmarks[INDEX_TIP].z
        distance = math.sqrt(dx * dx + dy * dy + dz * dz)

        if self._prev_pinch:
            # Was pinching: need larger distance to release
            threshold = self._pinch_threshold * 1.3
        else:
            # Not pinching: need smaller distance to trigger
            threshold = self._pinch_threshold * 0.85

        if distance >= threshold:
            self._prev_pinch = False
            return False

        self._prev_pinch = thumb_extended
        return thumb_extended

    def _get_finger_states(self, landmarks: list) -> list[bool]:
        """Get extended/curled state for index, middle, ring, pinky with hysteresis."""
        return [
            self._is_finger_extended(landmarks, tip, pip, mcp, i)
            for i, (tip, pip, mcp) in enumerate(zip(FINGER_TIPS, FINGER_PIPS, FINGER_MCPS))
        ]
