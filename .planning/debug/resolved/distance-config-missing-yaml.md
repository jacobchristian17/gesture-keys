---
status: resolved
trigger: "Distance gating is not configured in the YAML config file (config.yaml). The user cannot configure distance thresholds for gating."
created: 2026-03-22T00:30:00Z
updated: 2026-03-22T12:00:00Z
---

## Current Focus

hypothesis: config.yaml has no `distance:` section, so DistanceFilter defaults kick in with `enabled=False`
test: confirmed by reading config.yaml and config.py
expecting: n/a - root cause confirmed
next_action: return diagnosis

## Symptoms

expected: Distance gating thresholds should be configurable via config.yaml so the user can adjust when hands are considered "in range" vs "out of range"
actual: config.yaml has no `distance:` section at all; distance gating defaults to disabled with hardcoded min_hand_size=0.15
errors: none
reproduction: Open config.yaml and search for "distance" - nothing present
started: Always missing - never added to config.yaml

## Eliminated

(none needed - root cause found on first hypothesis)

## Evidence

- timestamp: 2026-03-22T00:31:00Z
  checked: config.yaml contents
  found: No `distance:` section exists in config.yaml. The file has `camera:`, `detection:`, `gestures:`, and `swipe:` sections only.
  implication: Users cannot configure distance gating at all via the config file.

- timestamp: 2026-03-22T00:31:30Z
  checked: config.py load_config() function, lines 115-116 and 132-133
  found: Code reads `distance = raw.get("distance", {})` then extracts `distance.get("enabled", False)` and `distance.get("min_hand_size", 0.15)`. When no `distance:` section exists, `distance` is `{}`, so `enabled` defaults to `False` and `min_hand_size` defaults to `0.15`.
  implication: The code already supports a `distance:` config section with `enabled` and `min_hand_size` keys. The section is simply missing from config.yaml.

- timestamp: 2026-03-22T00:32:00Z
  checked: distance.py DistanceFilter class
  found: DistanceFilter accepts `min_hand_size` (float, default 0.15) and `enabled` (bool, default True). Only uses `min_hand_size` as a lower threshold - hand must have palm_span >= min_hand_size to be "in range".
  implication: The feature is fully implemented in code. Only the YAML config entry is missing.

## Resolution

root_cause: config.yaml is missing the `distance:` section entirely. The config.py loader already supports `distance.enabled` and `distance.min_hand_size` keys (lines 115-116, 132-133), and both __main__.py and tray.py already wire these values into the DistanceFilter. The only gap is that config.yaml was never updated to include the `distance:` section, so users have no way to enable or tune distance gating without editing source code.
fix:
verification:
files_changed: []
