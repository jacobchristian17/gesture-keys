# Phase 20: Config Loader for Actions - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

New `actions:` config section parsing and orchestrator input derivation, replacing separate `gestures:` and `swipe:` sections. Users define all gesture-to-key mappings with trigger strings in a single `actions:` section. System derives gesture_modes, cooldown maps, and gate bypass sets from action definitions. Old config format still supported as fallback when `actions:` is absent. Pipeline integration (wiring into orchestrator/dispatcher) is Phase 21-23. Legacy code deletion is Phase 24.

</domain>

<decisions>
## Implementation Decisions

### Action entry YAML structure
- Named entries under `actions:` — YAML key is the action name (e.g., `volume_up:`)
- User-chosen names are required — every action must have a unique name as its YAML key
- Each action entry contains: `trigger` (trigger string), `key` (keystroke), and optional `threshold`, `cooldown`, `bypass_gate`
- One action per trigger — duplicate trigger strings across actions raise a clear validation error
- Global defaults (cooldown, activation_delay) come from existing `detection:` section — per-action fields override

### Left-hand action handling
- Per-action `hand:` field with values `left`, `right`, or `both` (default: `both` when omitted)
- `hand: both` means the same action fires for either hand
- Different per-hand behavior requires two separate action entries with `hand: left` and `hand: right`
- Old `left_gestures:` and `left_swipe:` section parsing removed in this phase (not deferred to Phase 24)

### Old section coexistence
- If both `actions:` and `gestures:`/`swipe:` exist in config.yaml, raise a clear error — no mixed formats
- If `actions:` is absent, fall back to reading `gestures:`/`swipe:` as before (backward compat for old configs)
- When using old path, behavior identical to current `load_config()`
- Convert the repo's `config.yaml` to new `actions:` format in this phase (dogfood immediately)

### Claude's Discretion
- Sequence trigger format in actions: section (trigger parser from Phase 18 already handles `>` syntax)
- Fire mode inference from trigger state vs explicit field (`:static` -> tap, `:holding` -> hold_key, `:moving` -> tap)
- Trigger uniqueness scoping per hand (whether same trigger allowed for hand:left and hand:right separately)
- Mirror/fallback behavior for hand:both (simple same-action-for-both is the baseline)
- Derivation output structure — how gesture_modes, cooldown maps, gate bypass sets are exposed from parsed actions
- Old path fallback: whether gestures: is still required when no actions: present (current behavior is fine)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `trigger.py:parse_trigger()`: Parses trigger strings into Trigger/SequenceTrigger — config loader calls this for each action's trigger field
- `trigger.py:Trigger`, `SequenceTrigger`, `TriggerState`, `Direction`: Data model for parsed triggers
- `config.py:_extract_gesture_cooldowns()`: Pattern for extracting per-gesture cooldowns — similar logic for per-action cooldowns
- `config.py:_extract_gesture_modes()`: Pattern for deriving fire modes — can be replaced by trigger state inference
- `config.py:_extract_bypass_gestures()`: Pattern for collecting bypass_gate flags
- `config.py:build_action_maps()`: Builds gesture_name -> Action map with pre-parsed key strings — new loader builds similar maps keyed by trigger
- `action.py:Action` dataclass: Existing action model with key_string, fire_mode, gesture_name, modifiers, key
- `keystroke.py:parse_key_string()`: Pre-parses key strings into pynput objects — reused directly

### Established Patterns
- Config pattern: top-level YAML section -> AppConfig dataclass fields -> load_config() parser with defaults
- Helper functions for extraction: `_extract_gesture_cooldowns()`, `_extract_gesture_modes()`, `_extract_bypass_gestures()`
- Pre-parse at startup: action maps built once, not per-frame
- Hot-reload: ConfigWatcher triggers full reload — new actions: path must work with this
- Hand resolution: `resolve_hand_gestures()` returns gesture dict for active hand — new approach uses hand: field per action

### Integration Points
- `config.py:load_config()`: Main entry point — adds actions: parsing path alongside existing gestures: path
- `config.py:AppConfig`: Needs new fields for parsed action data (or new dataclass)
- `pipeline.py`: Creates ActionResolver from config — will need to accept new action map format (Phase 23)
- `action.py:ActionResolver`: Currently takes right_actions/left_actions dicts — new format builds these from hand: field

</code_context>

<specifics>
## Specific Ideas

- Trigger strings from Phase 18 are the compact syntax for the trigger field: `"fist:static"`, `"fist:holding"`, `"open_palm:moving:left"`, `"fist > open_palm"`
- Config.yaml conversion should preserve all current gesture mappings and behavior using the new actions: format
- Error messages for invalid configs should be clear and actionable (which field, what's wrong, what's expected)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 20-config-loader-for-actions*
*Context gathered: 2026-03-26*
