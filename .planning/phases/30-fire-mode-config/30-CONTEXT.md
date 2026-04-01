# Phase 30: Fire Mode & Config - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Add FireMode.SCROLL enum value, extend ActionEntry/Action for scroll config, update parse_actions() for optional key field, update derive_from_actions() to respect explicit fire_mode: scroll override, and add scroll param override maps to DerivedConfig.

</domain>

<decisions>
## Implementation Decisions

### FireMode & Action Data Model
- Make key_string, modifiers, key empty defaults for scroll Actions — key_string="", modifiers=[], key="" preserves frozen dataclass
- scroll_speed, min_ticks, max_ticks live on ActionEntry — parsed from YAML alongside trigger/key
- derive_from_actions: explicit `fire_mode: scroll` in config overrides state-inferred mode (only for moving triggers)

### Config Validation
- fire_mode: scroll → key not required (ignored if present); all other fire modes → key required
- fire_mode field only required for scroll — tap/hold_key continue to be inferred from trigger state
- Default scroll_speed: 3.0 (matches ScrollSender constructor default from Phase 29)

### Scroll Config Params in DerivedConfig
- New override maps on DerivedConfig: scroll_speed_overrides, scroll_min_ticks_overrides, scroll_max_ticks_overrides keyed by (gesture_value, direction_value)
- Acceleration curve params NOT configurable in v1.0.1 — hardcoded exponent 1.5 in ScrollSender

### Claude's Discretion
- Internal implementation details, test organization, error message wording

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `FireMode` enum in `action.py` — add SCROLL value
- `Action` frozen dataclass in `action.py` — needs empty defaults for scroll
- `ActionEntry` in `config.py` — add fire_mode, scroll_speed, scroll_min_ticks, scroll_max_ticks fields
- `parse_actions()` in `config.py` — modify key field requirement logic
- `derive_from_actions()` in `config.py` — add fire_mode override and scroll param collection
- `DerivedConfig` in `config.py` — add scroll override maps

### Established Patterns
- ActionEntry uses Optional[float] for per-action overrides (min_velocity, dispatch_interval)
- derive_from_actions collects overrides into typed dicts keyed by (gesture_value, direction_value)
- parse_key_string() called in derive_from_actions — skip for scroll actions

### Integration Points
- ActionDispatcher will read scroll_speed from resolver (Phase 31)
- ScrollSender constructor takes scroll_speed, max_ticks, ema_alpha (Phase 29)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — follows established config patterns.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
