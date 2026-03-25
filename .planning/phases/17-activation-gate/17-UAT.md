---
status: complete
phase: 17-activation-gate
source: [17-01-SUMMARY.md, 17-02-SUMMARY.md]
started: 2026-03-26T00:00:00Z
updated: 2026-03-26T00:00:00Z
---

## Current Test

[testing complete]

## Tests

### 1. Bypass mode (default config)
expected: Run gesture-keys with default config (`activation_gate.enabled: false`). All mapped gestures fire their keys exactly as before — zero behavioral change.
result: pass

### 2. Gate blocks gestures when disarmed
expected: Set `activation_gate.enabled: true` in config.yaml. Make a non-activation gesture (e.g., fist for space). The key should NOT fire — the gate is disarmed and blocks all non-activation gestures.
result: pass

### 3. Activation gesture arms gate, subsequent gestures fire
expected: With `enabled: true`, make a scout or peace gesture. Then within 3 seconds, make a fist. Scout/peace should arm the gate (no visible key output). Fist should then fire space. After 3 seconds of inactivity, fist should stop working again (gate expired).
result: pass

### 4. Activation gesture consumed (no mapped key fires)
expected: With `enabled: true`, perform the scout gesture. The gate should arm, but scout's own mapped key (`win+ctrl+right`) should NOT fire. The activation gesture is consumed by the gate.
result: pass

### 5. Re-arming extends the activation window
expected: Arm with scout. Wait ~2 seconds. Arm again with peace. The 3-second window should restart from the second arm. A fist gesture made 2+ seconds after the peace (but 4+ seconds after the scout) should still fire.
result: pass

### 6. Hot-reload disable restores bypass
expected: With `enabled: true` and gate operational, edit config.yaml to set `enabled: false`. Wait ~2 seconds for hot-reload. Make a fist — it should fire immediately without needing to arm the gate first. Bypass mode restored live.
result: pass

## Summary

total: 6
passed: 6
issues: 0
pending: 0
skipped: 0

## Gaps

[none]
