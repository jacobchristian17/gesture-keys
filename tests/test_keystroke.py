"""Tests for key string parsing and keystroke sending."""

from unittest.mock import MagicMock, call

import pytest
from pynput.keyboard import Key

from gesture_keys.keystroke import SPECIAL_KEYS, KeystrokeSender, parse_key_string


class TestParseKeyString:
    """Test key string parsing into pynput objects."""

    def test_single_special_key_space(self):
        modifiers, key = parse_key_string("space")
        assert modifiers == []
        assert key == Key.space

    def test_single_special_key_enter(self):
        modifiers, key = parse_key_string("enter")
        assert modifiers == []
        assert key == Key.enter

    def test_single_character_key(self):
        modifiers, key = parse_key_string("a")
        assert modifiers == []
        assert key == "a"

    def test_combo_ctrl_z(self):
        modifiers, key = parse_key_string("ctrl+z")
        assert modifiers == [Key.ctrl]
        assert key == "z"

    def test_combo_ctrl_shift_s(self):
        modifiers, key = parse_key_string("ctrl+shift+s")
        assert modifiers == [Key.ctrl, Key.shift]
        assert key == "s"

    def test_case_insensitive(self):
        modifiers, key = parse_key_string("CTRL+Z")
        assert modifiers == [Key.ctrl]
        assert key == "z"

    def test_unknown_key_raises_valueerror(self):
        with pytest.raises(ValueError, match="Unknown key"):
            parse_key_string("unknown_key")

    def test_empty_final_key_raises_valueerror(self):
        with pytest.raises(ValueError, match="empty"):
            parse_key_string("ctrl+")

    def test_special_keys_dict_has_common_keys(self):
        for name in ["ctrl", "alt", "shift", "space", "enter", "tab", "esc",
                      "backspace", "delete", "up", "down", "left", "right"]:
            assert name in SPECIAL_KEYS

    def test_f_keys_present(self):
        for i in range(1, 13):
            assert f"f{i}" in SPECIAL_KEYS


class TestKeystrokeSender:
    """Test keystroke sending with mock controller."""

    def test_send_single_key(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.send([], "a")

        mock_ctrl.press.assert_called_once_with("a")
        mock_ctrl.release.assert_called_once_with("a")

    def test_send_with_modifiers_correct_order(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.send([Key.ctrl, Key.shift], "s")

        # Modifiers pressed in order, then key pressed and released,
        # then modifiers released in reverse
        expected_presses = [call(Key.ctrl), call(Key.shift), call("s")]
        expected_releases = [call("s"), call(Key.shift), call(Key.ctrl)]
        assert mock_ctrl.press.call_args_list == expected_presses
        assert mock_ctrl.release.call_args_list == expected_releases

    def test_send_releases_modifiers_on_error(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        # Make key press raise an exception
        def side_effect(k):
            if k == "z":
                raise RuntimeError("key press failed")

        mock_ctrl.press.side_effect = side_effect

        with pytest.raises(RuntimeError, match="key press failed"):
            sender.send([Key.ctrl], "z")

        # Ctrl should still be released despite the error
        mock_ctrl.release.assert_any_call(Key.ctrl)

    def test_send_special_key(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.send([], Key.space)

        mock_ctrl.press.assert_called_once_with(Key.space)
        mock_ctrl.release.assert_called_once_with(Key.space)


class TestKeystrokeSenderHold:
    """Test hold-mode keystroke methods."""

    def test_press_and_hold_single_key(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([], Key.space)

        mock_ctrl.press.assert_called_once_with(Key.space)
        mock_ctrl.release.assert_not_called()

    def test_press_and_hold_with_modifiers(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.ctrl, Key.shift], "a")

        expected_presses = [call(Key.ctrl), call(Key.shift), call("a")]
        assert mock_ctrl.press.call_args_list == expected_presses
        mock_ctrl.release.assert_not_called()

    def test_press_and_hold_tracks_held_keys(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.ctrl], "z")

        assert len(sender._held_keys) == 2
        assert sender._held_keys == [Key.ctrl, "z"]

    def test_release_held_releases_in_reverse(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.ctrl, Key.shift], "s")
        mock_ctrl.reset_mock()

        sender.release_held()

        expected_releases = [call("s"), call(Key.shift), call(Key.ctrl)]
        assert mock_ctrl.release.call_args_list == expected_releases
        assert sender._held_keys == []

    def test_release_held_noop_when_empty(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.release_held()  # should not raise

        mock_ctrl.release.assert_not_called()

    def test_release_all_releases_everything(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.press_and_hold([Key.alt], Key.tab)
        mock_ctrl.reset_mock()

        sender.release_all()

        expected_releases = [call(Key.tab), call(Key.alt)]
        assert mock_ctrl.release.call_args_list == expected_releases
        assert sender._held_keys == []

    def test_release_all_idempotent(self):
        sender = KeystrokeSender()
        mock_ctrl = MagicMock()
        sender._controller = mock_ctrl

        sender.release_all()
        sender.release_all()

        mock_ctrl.release.assert_not_called()
