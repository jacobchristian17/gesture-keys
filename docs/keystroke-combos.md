# Keystroke Combination Reference

## Key Combination Format

Keys are specified as strings in `config.yaml` using `+` as separator:
- `key` — single key
- `modifier+key` — one modifier + key
- `modifier+modifier+key` — multiple modifiers + key

All parts are **case-insensitive** (normalized to lowercase). The **last** part is always the final key; everything before it is treated as a modifier.

## Modifiers

| Name    | Maps to       |
|---------|---------------|
| `ctrl`  | `Key.ctrl`    |
| `alt`   | `Key.alt`     |
| `shift` | `Key.shift`   |
| `win`   | `Key.cmd`     |

## Special Keys

| Name        | Key              |
|-------------|------------------|
| `space`     | Space bar        |
| `enter`     | Enter/Return     |
| `tab`       | Tab              |
| `esc`       | Escape           |
| `backspace` | Backspace        |
| `delete`    | Delete           |
| `home`      | Home             |
| `end`       | End              |
| `page_up`   | Page Up          |
| `page_down` | Page Down        |
| `up`        | Up arrow         |
| `down`      | Down arrow       |
| `left`      | Left arrow       |
| `right`     | Right arrow      |
| `f1`–`f12`  | Function keys    |

## Single Character Keys

Any single character works as a final key: `a`–`z`, digits, punctuation. pynput accepts them directly.

## Valid Examples

- `space`, `enter`, `tab`, `esc`, `backspace`, `delete`
- `a`, `z`, `1` (single characters)
- `f1` through `f12`
- `ctrl+z`, `ctrl+s`, `ctrl+c`, `ctrl+v`
- `alt+tab`, `shift+f1`
- `ctrl+shift+s`, `ctrl+alt+delete`
- `win+d`, `win+e`, `win+l`

## Invalid Examples (raise ValueError)

- `ctrl+` — empty final key
- `unknown_key` — not in SPECIAL_KEYS and not a single char

## Execution Order

1. Press all modifiers left-to-right
2. Press + release the final key
3. Release all modifiers in reverse order
4. try/finally guarantees modifier release on failure

## Config Format

```yaml
gestures:
  gesture_name:
    key: "ctrl+z"       # key combo string
    threshold: 0.7       # optional confidence threshold
```

## Source

Defined in `gesture_keys/keystroke.py`: `SPECIAL_KEYS` dict, `parse_key_string()`, `KeystrokeSender.send()`.
