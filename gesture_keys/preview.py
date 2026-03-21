"""OpenCV preview window rendering with bottom bar for gesture-keys."""

import cv2
import numpy as np

BAR_HEIGHT = 40

# MediaPipe hand connections: pairs of landmark indices that should be connected.
# Mirrors mediapipe.solutions.hands.HAND_CONNECTIONS for environments where
# the solutions subpackage is not available (e.g., mediapipe 0.10.33 on Python 3.13).
HAND_CONNECTIONS = [
    (0, 1), (1, 2), (2, 3), (3, 4),       # Thumb
    (0, 5), (5, 6), (6, 7), (7, 8),       # Index
    (0, 9), (9, 10), (10, 11), (11, 12),  # Middle (via wrist)
    (0, 13), (13, 14), (14, 15), (15, 16),  # Ring (via wrist)
    (0, 17), (17, 18), (18, 19), (19, 20),  # Pinky (via wrist)
    (5, 9), (9, 13), (13, 17),             # Palm connections
]

# Colors for finger groups (BGR): thumb, index, middle, ring, pinky
_FINGER_COLORS = [
    (255, 0, 0),     # Thumb: blue
    (0, 128, 255),   # Index: orange
    (0, 255, 0),     # Middle: green
    (0, 255, 255),   # Ring: yellow
    (255, 0, 255),   # Pinky: magenta
]

# Map landmark index to finger group index
_LANDMARK_TO_FINGER = {}
for _finger_idx, _start in enumerate([1, 5, 9, 13, 17]):
    for _lm in range(_start, _start + 4):
        _LANDMARK_TO_FINGER[_lm] = _finger_idx
_LANDMARK_TO_FINGER[0] = -1  # Wrist: white


def _landmark_color(index):
    """Return BGR color for a given landmark index."""
    finger = _LANDMARK_TO_FINGER.get(index, -1)
    if finger < 0:
        return (255, 255, 255)  # White for wrist
    return _FINGER_COLORS[finger]


def draw_hand_landmarks(frame, hand_landmarks):
    """Draw 21-landmark skeleton with connections on the frame.

    Uses direct OpenCV drawing calls (circles for landmarks, lines for
    connections) since mediapipe.solutions.drawing_utils is not available
    in the Task API-only package on Python 3.13.

    Args:
        frame: BGR numpy array (modified in-place).
        hand_landmarks: List of 21 landmarks from HandDetector.detect().
    """
    h, w = frame.shape[:2]

    # Convert normalized landmarks to pixel coordinates
    points = []
    for lm in hand_landmarks:
        px = int(lm.x * w)
        py = int(lm.y * h)
        points.append((px, py))

    # Draw connections first (under landmarks)
    for start_idx, end_idx in HAND_CONNECTIONS:
        if start_idx < len(points) and end_idx < len(points):
            color = _landmark_color(end_idx)
            cv2.line(frame, points[start_idx], points[end_idx], color, 2)

    # Draw landmark circles on top
    for idx, (px, py) in enumerate(points):
        color = _landmark_color(idx)
        cv2.circle(frame, (px, py), 5, color, -1)
        cv2.circle(frame, (px, py), 5, (0, 0, 0), 1)  # Black outline


def render_preview(frame, gesture_name, fps):
    """Render frame with solid bottom bar showing gesture label and FPS.

    Creates a dark gray bar below the camera feed with the gesture name
    in the bottom-left and the FPS counter in the bottom-right.

    Args:
        frame: BGR numpy array (camera feed).
        gesture_name: Current gesture label string, or None.
        fps: Current frames per second value.
    """
    h, w = frame.shape[:2]

    # Create dark gray bottom bar
    bar = np.zeros((BAR_HEIGHT, w, 3), dtype=np.uint8)
    bar[:] = (50, 50, 50)

    # Gesture label bottom-left
    label = gesture_name if gesture_name else "None"
    cv2.putText(bar, label, (10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)

    # FPS counter bottom-right
    fps_text = f"FPS: {fps:.0f}"
    text_size = cv2.getTextSize(fps_text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
    cv2.putText(bar, fps_text, (w - text_size[0] - 10, 28),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 1)

    # Stack frame + bar
    display = np.vstack([frame, bar])
    cv2.imshow("Gesture Keys", display)
