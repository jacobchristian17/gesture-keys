---
status: resolved
trigger: "hold_key fire mode doesn't produce continuous key firing despite hold status being detected"
created: 2026-03-25T11:00:00Z
updated: 2026-03-25T12:00:00Z
---

## Current Focus

hypothesis: press_and_hold() sends a single key-down via pynput which does NOT trigger OS auto-repeat on Windows (SendInput events are not auto-repeated by Windows), AND the old tap-repeat loop was removed in Phase 16 without a replacement
test: traced full code path from config -> orchestrator -> dispatcher -> sender
expecting: confirmed by code tracing + pynput/Windows behavior
next_action: report root cause

## Symptoms

expected: Fist gesture with fire_mode: hold_key produces continuous key output (repeating characters in text editor)
actual: Hold status displayed on preview (HOLDING state), but no sustained keypress -- no characters in text editor
errors: none (no crashes, no exceptions)
reproduction: configure fist with fire_mode: hold_key, sustain fist gesture, observe text editor
started: phase 16 (action dispatch refactor). Previously used tap-repeat at 30Hz via send() calls.

## Eliminated

- hypothesis: HOLD_START signal never emitted by orchestrator
  evidence: orchestrator simulation confirms HOLD_START emitted at t=0.267s; preview displays HOLDING state
  timestamp: 2026-03-25T11:05:00Z

- hypothesis: ActionDispatcher doesn't receive HOLD_START signal
  evidence: pipeline.py line 351-353 iterates all signals, no filtering; code trace confirms dispatch
  timestamp: 2026-03-25T11:08:00Z

- hypothesis: ActionResolver returns None for fist gesture
  evidence: build_action_maps correctly maps fist -> Action(fire_mode=HOLD_KEY, key=space); tested with real config
  timestamp: 2026-03-25T11:10:00Z

- hypothesis: Action fire_mode mismatch (TAP vs HOLD_KEY)
  evidence: _extract_gesture_modes returns "hold_key" for fist; build_action_maps maps to FireMode.HOLD_KEY; resolver test confirms
  timestamp: 2026-03-25T11:12:00Z

- hypothesis: Something releases held key on same frame
  evidence: swiping check (line 356) only triggers if swiping=True, which would prevent HOLD_START from being emitted in the first place; no other release path on same frame
  timestamp: 2026-03-25T11:15:00Z

- hypothesis: Resolver hand mismatch (wrong action map active)
  evidence: both right_actions and left_actions map fist to HOLD_KEY; left_modes correctly inherits from main gesture_modes
  timestamp: 2026-03-25T11:18:00Z

## Evidence

- timestamp: 2026-03-25T11:05:00Z
  checked: orchestrator signal emission via simulation
  found: HOLD_START signal emitted correctly at t=0.267s for fist gesture with hold_key mode
  implication: orchestrator works correctly

- timestamp: 2026-03-25T11:10:00Z
  checked: full dispatch path with mock sender
  found: press_and_hold() called with correct args ([], Key.space) for fist gesture
  implication: entire code path from config to sender is correct

- timestamp: 2026-03-25T11:15:00Z
  checked: 16-RESEARCH.md line 11 and Pitfall 12
  found: "v1.x hold mode does NOT use true key holding -- it repeatedly sends press+release at 30Hz via send()" AND "press_and_hold() uses SendInput which relies on OS-level key repeat"
  implication: the old repeat mechanism was removed; the new mechanism relies on OS behavior that doesn't work for programmatic key events on Windows

- timestamp: 2026-03-25T11:20:00Z
  checked: PITFALLS.md Pitfall 12
  found: explicit warning that "OS-level key repeat only applies to physical keyboard input" and "some applications consume the first keypress and do not repeat"
  implication: the known pitfall was documented but not mitigated during implementation

- timestamp: 2026-03-25T11:22:00Z
  checked: KeystrokeSender.press_and_hold() implementation
  found: calls controller.press(key) exactly once, appends to _held_keys; no repeat loop
  implication: only one key-down event is sent; no continuous output

- timestamp: 2026-03-25T11:25:00Z
  checked: UAT results tests 2 and 3
  found: both hold_key gestures (fist/fire_mode:hold_key AND pointing/mode:hold) fail identically
  implication: systematic issue with hold_key implementation, not gesture-specific

## Resolution

root_cause: KeystrokeSender.press_and_hold() sends a single key-down event via pynput's Controller.press(). On Windows, pynput uses SendInput API for programmatic key events. Windows OS auto-repeat does NOT apply to SendInput key-down events -- auto-repeat only works for physical keyboard hardware events. Therefore, press_and_hold() produces at most one character (or possibly zero if the key-down without key-up is consumed differently by the target application), not the continuous stream expected. The old v1.x implementation used a tap-repeat loop (rapid send() calls at hold_repeat_interval=30ms) which WAS working, but Phase 16 intentionally replaced it with true key holding via press_and_hold(), which doesn't produce the desired behavior on Windows.
fix: ""
verification: ""
files_changed: []
