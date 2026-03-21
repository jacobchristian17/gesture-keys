"""Shared test fixtures for gesture-keys tests."""

import pytest
from types import SimpleNamespace


def _make_landmark(x=0.0, y=0.0, z=0.0):
    """Create a mock landmark with x, y, z attributes."""
    return SimpleNamespace(x=x, y=y, z=z)


def _make_hand(positions):
    """Create a list of 21 landmarks from a dict of index -> (x, y, z).

    Default landmark position is (0.5, 0.7, 0.0) so that MCP joints
    (which serve as the base reference) are naturally below PIP joints
    in the y-axis, matching a realistic hand pose.
    """
    landmarks = [_make_landmark(0.5, 0.7, 0.0) for _ in range(21)]
    for idx, coords in positions.items():
        landmarks[idx] = _make_landmark(*coords)
    return landmarks


# MediaPipe Hand Landmark Indices:
# 0=WRIST, 1=THUMB_CMC, 2=THUMB_MCP, 3=THUMB_IP, 4=THUMB_TIP
# 5=INDEX_MCP, 6=INDEX_PIP, 7=INDEX_DIP, 8=INDEX_TIP
# 9=MIDDLE_MCP, 10=MIDDLE_PIP, 11=MIDDLE_DIP, 12=MIDDLE_TIP
# 13=RING_MCP, 14=RING_PIP, 15=RING_DIP, 16=RING_TIP
# 17=PINKY_MCP, 18=PINKY_PIP, 19=PINKY_DIP, 20=PINKY_TIP


@pytest.fixture
def mock_config():
    """Return a valid AppConfig for testing."""
    # Import here to avoid import errors if config.py doesn't exist yet
    from gesture_keys.config import load_config
    import os

    config_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "config.yaml"
    )
    return load_config(config_path)


@pytest.fixture
def mock_landmarks_open_palm():
    """All fingers extended, thumb extended -- OPEN_PALM.

    Tips are above (lower Y) their PIP joints. Thumb tip far from wrist.
    """
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST (bottom)
        3: (0.3, 0.6, 0.0),    # THUMB_IP
        4: (0.2, 0.55, 0.0),   # THUMB_TIP (further from wrist x than IP)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.4, 0.2, 0.0),    # INDEX_TIP (above PIP)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.2, 0.0),   # MIDDLE_TIP (above PIP)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.2, 0.0),   # RING_TIP (above PIP)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.2, 0.0),   # PINKY_TIP (above PIP)
    })


@pytest.fixture
def mock_landmarks_fist():
    """All fingers curled, thumb curled -- FIST.

    Tips are below (higher Y) their PIP joints. Thumb tip close to wrist x.
    """
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST
        3: (0.45, 0.6, 0.0),   # THUMB_IP
        4: (0.48, 0.65, 0.0),  # THUMB_TIP (closer to wrist x than IP)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.4, 0.7, 0.0),    # INDEX_TIP (below PIP)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.7, 0.0),   # MIDDLE_TIP (below PIP)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.7, 0.0),   # RING_TIP (below PIP)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.7, 0.0),   # PINKY_TIP (below PIP)
    })


@pytest.fixture
def mock_landmarks_thumbs_up():
    """Thumb extended, all 4 fingers curled -- THUMBS_UP."""
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST
        3: (0.3, 0.6, 0.0),    # THUMB_IP
        4: (0.2, 0.55, 0.0),   # THUMB_TIP (far from wrist = extended)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.4, 0.7, 0.0),    # INDEX_TIP (below PIP = curled)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.7, 0.0),   # MIDDLE_TIP (below PIP = curled)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.7, 0.0),   # RING_TIP (below PIP = curled)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.7, 0.0),   # PINKY_TIP (below PIP = curled)
    })


@pytest.fixture
def mock_landmarks_peace():
    """Index + middle extended, ring + pinky curled, thumb curled -- PEACE."""
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST
        3: (0.45, 0.6, 0.0),   # THUMB_IP
        4: (0.48, 0.65, 0.0),  # THUMB_TIP (curled)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.4, 0.2, 0.0),    # INDEX_TIP (extended)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.2, 0.0),   # MIDDLE_TIP (extended)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.7, 0.0),   # RING_TIP (curled)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.7, 0.0),   # PINKY_TIP (curled)
    })


@pytest.fixture
def mock_landmarks_pointing():
    """Index extended, middle + ring + pinky curled, thumb curled -- POINTING."""
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST
        3: (0.45, 0.6, 0.0),   # THUMB_IP
        4: (0.48, 0.65, 0.0),  # THUMB_TIP (curled)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.4, 0.2, 0.0),    # INDEX_TIP (extended)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.7, 0.0),   # MIDDLE_TIP (curled)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.7, 0.0),   # RING_TIP (curled)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.7, 0.0),   # PINKY_TIP (curled)
    })


@pytest.fixture
def mock_landmarks_scout():
    """Index + middle + ring extended, pinky curled -- SCOUT."""
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST
        3: (0.45, 0.6, 0.0),   # THUMB_IP
        4: (0.48, 0.65, 0.0),  # THUMB_TIP (curled)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.4, 0.2, 0.0),    # INDEX_TIP (extended)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.2, 0.0),   # MIDDLE_TIP (extended)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.2, 0.0),   # RING_TIP (extended)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.7, 0.0),   # PINKY_TIP (curled)
    })


@pytest.fixture
def mock_landmarks_pinch():
    """Thumb tip very close to index tip -- PINCH.

    Other fingers don't matter much but set them extended to ensure
    pinch priority wins over other gestures.
    """
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST
        3: (0.35, 0.5, 0.0),   # THUMB_IP
        4: (0.40, 0.35, 0.0),  # THUMB_TIP (very close to index tip)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.41, 0.35, 0.0),  # INDEX_TIP (very close to thumb tip)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.2, 0.0),   # MIDDLE_TIP (extended)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.2, 0.0),   # RING_TIP (extended)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.2, 0.0),   # PINKY_TIP (extended)
    })


@pytest.fixture
def mock_landmarks_none():
    """Ambiguous hand pose that should not match any gesture.

    Some fingers extended, some curled, in a way that doesn't match
    any specific gesture pattern.
    """
    return _make_hand({
        0: (0.5, 0.8, 0.0),    # WRIST
        3: (0.45, 0.6, 0.0),   # THUMB_IP
        4: (0.48, 0.65, 0.0),  # THUMB_TIP (curled)
        6: (0.4, 0.5, 0.0),    # INDEX_PIP
        8: (0.4, 0.2, 0.0),    # INDEX_TIP (extended)
        10: (0.5, 0.5, 0.0),   # MIDDLE_PIP
        12: (0.5, 0.7, 0.0),   # MIDDLE_TIP (curled)
        14: (0.6, 0.5, 0.0),   # RING_PIP
        16: (0.6, 0.2, 0.0),   # RING_TIP (extended)
        18: (0.7, 0.5, 0.0),   # PINKY_PIP
        20: (0.7, 0.7, 0.0),   # PINKY_TIP (curled)
    })
