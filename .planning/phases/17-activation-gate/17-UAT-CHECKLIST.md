# Phase 17 — Activation Gate: Manual UAT Checklist

## Test 1: Bypass mode (default)
- Run gesture-keys normally with activation_gate.enabled: false (default)
- All gestures should fire as before — no behavior change

## Test 2: Gate blocks when disarmed
- Set activation_gate.enabled: true in config.yaml
- Make a non-activation gesture (e.g. fist) — should NOT fire

## Test 3: Activation gesture arms the gate
- Make scout or peace gesture — gate arms for 3 seconds
- Within 3 seconds, make fist — should fire
- Wait 3+ seconds, make fist again — should NOT fire

## Test 4: Activation gesture consumed
- Scout gesture arms gate but its mapped key (win+ctrl+right) should NOT fire

## Test 5: Re-arming extends window
- Arm with scout → wait 2 seconds → arm again with peace → 3-second window restarts

## Test 6: Hot-reload
- Set enabled: false in config.yaml while running → bypass restores immediately
