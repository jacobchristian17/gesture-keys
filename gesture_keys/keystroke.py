"""Key string parsing and keystroke sending via pynput.

Parses config key strings like 'ctrl+z' or 'space' into pynput key
objects, and sends keystrokes to the foreground application.
"""

from typing import Union

from pynput.keyboard import Controller, Key, KeyCode

# Map config string names to pynput Key enum members
SPECIAL_KEYS: dict[str, Key] = {
    "ctrl": Key.ctrl,
    "alt": Key.alt,
    "shift": Key.shift,
    "win": Key.cmd,
    "space": Key.space,
    "enter": Key.enter,
    "tab": Key.tab,
    "esc": Key.esc,
    "backspace": Key.backspace,
    "delete": Key.delete,
    "up": Key.up,
    "down": Key.down,
    "left": Key.left,
    "right": Key.right,
    "home": Key.home,
    "end": Key.end,
    "page_up": Key.page_up,
    "page_down": Key.page_down,
    "f1": Key.f1,
    "f2": Key.f2,
    "f3": Key.f3,
    "f4": Key.f4,
    "f5": Key.f5,
    "f6": Key.f6,
    "f7": Key.f7,
    "f8": Key.f8,
    "f9": Key.f9,
    "f10": Key.f10,
    "f11": Key.f11,
    "f12": Key.f12,
}


def parse_key_string(key_string: str) -> tuple[list[Key], Union[Key, str]]:
    """Parse a key string like 'ctrl+z' into (modifiers, key).

    Args:
        key_string: Key combination string from config (e.g. 'ctrl+z',
                    'space', 'ctrl+shift+s', 'a').

    Returns:
        Tuple of (list of modifier Key objects, final key as Key or str).

    Raises:
        ValueError: If a key name is not recognized or final key is empty.
    """
    parts = [p.strip().lower() for p in key_string.split("+")]

    # Check for empty final key (e.g. "ctrl+")
    if not parts[-1]:
        raise ValueError(
            f"Key string has empty final key: '{key_string}'"
        )

    # All but last are modifiers
    modifiers: list[Key] = []
    for part in parts[:-1]:
        if part in SPECIAL_KEYS:
            modifiers.append(SPECIAL_KEYS[part])
        else:
            raise ValueError(f"Unknown modifier: '{part}' in '{key_string}'")

    # Final part is the key to press
    final = parts[-1]
    if final in SPECIAL_KEYS:
        key: Union[Key, str] = SPECIAL_KEYS[final]
    elif len(final) == 1:
        key = final  # Single character -- pynput accepts str
    else:
        raise ValueError(f"Unknown key: '{final}' in '{key_string}'")

    return modifiers, key


class KeystrokeSender:
    """Sends keystrokes to the foreground application via pynput.

    Creates a single Controller instance and reuses it for all sends.
    Uses try/finally to ensure modifier keys are always released.
    """

    def __init__(self) -> None:
        self._controller = Controller()

    def send(
        self, modifiers: list[Key], key: Union[Key, str]
    ) -> None:
        """Press modifiers, tap key, release modifiers in reverse order.

        Args:
            modifiers: List of modifier Key objects to hold.
            key: Final key to tap (Key enum or single character str).

        Raises:
            Any exception from pynput, after releasing all modifiers.
        """
        pressed_modifiers: list[Key] = []
        try:
            for mod in modifiers:
                self._controller.press(mod)
                pressed_modifiers.append(mod)
            self._controller.press(key)
            self._controller.release(key)
        finally:
            for mod in reversed(pressed_modifiers):
                self._controller.release(mod)
