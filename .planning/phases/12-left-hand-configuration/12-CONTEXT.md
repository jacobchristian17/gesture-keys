# Phase 12: Left Hand Configuration - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Users can control left hand key mappings through config.yaml with sensible defaults. Left hand mirrors right-hand mappings when no overrides are defined. Optional separate left-hand gesture-to-key mappings can be added. Config hot-reload applies to left-hand mappings. This phase covers CFG-01, CFG-02, CFG-03.

</domain>

<decisions>
## Implementation Decisions

### Default Mirroring
- Left hand mirrors right-hand mappings by default — no config changes needed for basic use
- Mirroring includes ALL per-gesture settings: key, threshold, cooldown, and mode (hold/tap)
- Per-gesture fallback: if user overrides only some left-hand gestures, un-overridden gestures fall back to the corresponding right-hand mapping
- No all-or-nothing requirement — user defines only what's different

### Hot-Reload Behavior
- Immediate apply on config reload — same behavior as existing hot-reload for right-hand mappings
- New/changed/removed left-hand overrides take effect on next gesture fire, not buffered until hand switch

### Claude's Discretion
- YAML structure for left-hand overrides (e.g., `left_gestures:` top-level section vs nested approach) — pick whichever keeps config clean and consistent
- Whether to support left-hand swipe overrides (`left_swipe:` section) — decide based on config cleanliness. Swipe directions are absolute (not mirrored), so overrides may not add much value. Either include for consistency or omit for simplicity.
- Internal implementation of mapping resolution (merge dicts at load time vs runtime lookup chain)

</decisions>

<specifics>
## Specific Ideas

- User's primary hand is left — left hand is the default preferred hand
- Config should feel natural for the common case: just use `gestures:` and both hands do the same thing. Left-hand overrides are the uncommon case.

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AppConfig` (config.py) — dataclass with `gestures`, `swipe_mappings`, `gesture_cooldowns`, `gesture_modes` fields. Needs new fields for left-hand overrides.
- `_parse_key_mappings()` — exists in both `__main__.py` and `tray.py`. Parses gesture dict into pynput objects. Can be reused for left-hand mappings.
- `_parse_swipe_key_mappings()` — same pattern for swipe directions.
- `ConfigWatcher` — mtime-based hot-reload already works. Left-hand mapping reload plugs into existing reload blocks.

### Established Patterns
- Config loading: YAML -> `load_config()` -> `AppConfig` dataclass -> consumed by main loop
- Key mapping resolution: `config.gestures` parsed once into `key_mappings` dict, looked up by gesture name at fire time
- Hot-reload: watcher detects change -> full `load_config()` -> re-parse all mappings -> update component settings
- Both `__main__.py` and `tray.py` have duplicated loop code with identical mapping logic

### Integration Points
- `load_config()` needs to parse new left-hand config sections from YAML
- `AppConfig` needs new fields for left-hand gesture/swipe overrides
- Main loops in `__main__.py` and `tray.py` need to resolve mappings based on active hand (from `HandDetector`)
- Hot-reload blocks in both files need to re-parse left-hand mappings

</code_context>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 12-left-hand-configuration*
*Context gathered: 2026-03-24*
