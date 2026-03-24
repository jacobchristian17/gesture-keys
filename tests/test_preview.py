"""Tests for the preview overlay hand indicator."""

from unittest.mock import patch

import numpy as np

from gesture_keys.preview import BAR_HEIGHT, render_preview


class TestHandIndicator:
    """Test hand indicator rendering in the preview bar."""

    def _make_frame(self, width=640, height=480):
        """Create a dummy BGR frame."""
        return np.zeros((height, width, 3), dtype=np.uint8)

    def _get_bar_region(self, width=640):
        """Return the x-range where the hand indicator should appear (between gesture label and center)."""
        # Hand indicator positioned at roughly 1/4 of bar width
        x_start = width // 4 - 30
        x_end = width // 4 + 30
        return x_start, x_end

    @patch("gesture_keys.preview.cv2.imshow")
    def test_handedness_right_renders_R(self, mock_imshow):
        """render_preview with handedness='Right' renders 'R' text on the bar."""
        frame = self._make_frame()
        render_preview(frame, "FIST", 30.0, debounce_state="IDLE", handedness="Right")

        # Get the display frame passed to imshow
        display = mock_imshow.call_args[0][1]
        bar = display[-BAR_HEIGHT:, :, :]

        # Check the hand indicator region has non-background pixels
        x_start, x_end = self._get_bar_region()
        indicator_region = bar[:, x_start:x_end, :]
        background = np.full_like(indicator_region, 50)  # (50,50,50) is bar background
        assert not np.array_equal(indicator_region, background), \
            "Hand indicator region should contain rendered text for 'R'"

    @patch("gesture_keys.preview.cv2.imshow")
    def test_handedness_left_renders_L(self, mock_imshow):
        """render_preview with handedness='Left' renders 'L' text on the bar."""
        frame = self._make_frame()
        render_preview(frame, "FIST", 30.0, debounce_state="IDLE", handedness="Left")

        display = mock_imshow.call_args[0][1]
        bar = display[-BAR_HEIGHT:, :, :]

        x_start, x_end = self._get_bar_region()
        indicator_region = bar[:, x_start:x_end, :]
        background = np.full_like(indicator_region, 50)
        assert not np.array_equal(indicator_region, background), \
            "Hand indicator region should contain rendered text for 'L'"

    @patch("gesture_keys.preview.cv2.imshow")
    def test_handedness_none_no_indicator(self, mock_imshow):
        """render_preview with handedness=None renders no hand indicator (backward compat)."""
        frame = self._make_frame()
        render_preview(frame, "FIST", 30.0, debounce_state=None, handedness=None)

        display = mock_imshow.call_args[0][1]
        bar = display[-BAR_HEIGHT:, :, :]

        # The hand indicator region should be all background (no text rendered there)
        x_start, x_end = self._get_bar_region()
        indicator_region = bar[:, x_start:x_end, :]
        background = np.full_like(indicator_region, 50)
        assert np.array_equal(indicator_region, background), \
            "Hand indicator region should be empty when handedness is None"

    @patch("gesture_keys.preview.cv2.imshow")
    def test_no_handedness_kwarg_works(self, mock_imshow):
        """render_preview with no handedness kwarg works without error (default None)."""
        frame = self._make_frame()
        # Call without handedness keyword -- should not raise
        render_preview(frame, "FIST", 30.0, debounce_state="IDLE")

        # Verify imshow was called (render completed without error)
        assert mock_imshow.called
