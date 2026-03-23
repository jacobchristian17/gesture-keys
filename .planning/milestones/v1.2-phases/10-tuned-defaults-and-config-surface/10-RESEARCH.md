# Phase 10: Tuned Defaults and Config Surface - Research

**Researched:** 2026-03-23
**Domain:** Python config/YAML parsing, debounce tuning, gesture timing
**Confidence:** HIGH

## Summary

Phase 10 is a config-layer and defaults-tuning phase with no new algorithms or external libraries. All three requirements (TUNE-01, TUNE-02, TUNE-03) involve modifying existing Python dataclasses, YAML parsing, and the debounce state machine to accept new parameters.

The codebase has a clear pattern for adding config fields: add to `AppConfig` dataclass, parse in `load_config()`, wire into component constructors in both `__main__.py` and `tray.py`, and add hot-reload support. This pattern has been repeated for distance gating (Phase 4) and swipe detection (Phase 5-6) and is well-established.

**Critical finding:** The current `config.yaml` has `smoothing_window: 30` which appears to be a user-modified value (code default is 3). The tuned target is ~2. The code defaults in `AppConfig` (activation_delay=0.4, cooldown_duration=0.8) are stale -- they predate the tuning insights from Phases 8-9. Both the code defaults AND the `config.yaml` shipped defaults need updating.

**Primary recommendation:** Three plans: (1) update code defaults in AppConfig/Debouncer/Smoother + config.yaml, (2) add settling_frames to config surface, (3) add per-gesture cooldown overrides. Each is independent and testable.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TUNE-01 | Code defaults updated to match proven real-usage values (activation_delay ~0.15s, cooldown ~0.3s, smoothing_window ~2) | Defaults live in `AppConfig` dataclass, `GestureDebouncer.__init__`, and `GestureSmoother.__init__`. Config.yaml also needs updating. Tests in `test_config.py` and `test_debounce.py` hardcode old defaults and must be updated. |
| TUNE-02 | Settling frames are configurable in config.yaml swipe section | `SwipeDetector` already accepts `settling_frames` param (default 3). Missing: `AppConfig.settling_frames` field, `load_config()` parsing from `swipe.settling_frames`, hot-reload wiring in both loops. |
| TUNE-03 | Per-gesture cooldown overrides are configurable in config.yaml | `GestureDebouncer` uses single `_cooldown_duration`. Needs: per-gesture cooldown dict, lookup on FIRED->COOLDOWN transition using the gesture that just fired. Config format: `gestures.pinch.cooldown: 0.6` alongside existing `key`/`threshold`. |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| PyYAML | existing | Config parsing | Already in use, no changes needed |
| dataclasses | stdlib | AppConfig structure | Already in use |
| pytest | existing | Testing | Already configured in pyproject.toml |

No new libraries required. This phase is purely internal refactoring of existing code.

## Architecture Patterns

### Current Config Flow (established pattern)
```
config.yaml -> load_config() -> AppConfig dataclass -> component constructors
                                                    -> hot-reload property setters
```

### Pattern 1: Adding a Config Field
**What:** The established 4-step pattern for adding any new config parameter
**When to use:** TUNE-02 (settling_frames), TUNE-03 (per-gesture cooldowns)
**Steps:**
1. Add field to `AppConfig` dataclass with sensible default
2. Parse from YAML in `load_config()` with fallback to default
3. Pass to component constructor in both `__main__.py` AND `tray.py`
4. Add hot-reload update in both loops' `watcher.check()` blocks

### Pattern 2: Per-Gesture Config Nesting
**What:** Gesture-specific overrides nested under each gesture entry
**When to use:** TUNE-03 (per-gesture cooldowns)
**Example:**
```yaml
gestures:
  pinch:
    key: win+down
    threshold: 0.06
    cooldown: 0.6    # <-- override, falls back to detection.cooldown_duration
  fist:
    key: esc
    threshold: 0.7
    # no cooldown override -> uses global default
```

This pattern is already established -- `threshold` is already a per-gesture field parsed from the same nested dict. Adding `cooldown` follows the exact same pattern.

### Pattern 3: Debouncer Per-Gesture Cooldown Lookup
**What:** Debouncer receives a cooldown lookup dict instead of (or in addition to) a single float
**When to use:** TUNE-03
**Example:**
```python
class GestureDebouncer:
    def __init__(self, activation_delay=0.15, cooldown_duration=0.3,
                 gesture_cooldowns: dict[str, float] | None = None):
        self._cooldown_duration = cooldown_duration
        self._gesture_cooldowns = gesture_cooldowns or {}

    def _get_cooldown(self, gesture: Gesture) -> float:
        return self._gesture_cooldowns.get(gesture.value, self._cooldown_duration)
```

The lookup happens in `_handle_fired()` when setting `self._cooldown_start` -- the cooldown duration used should be based on the gesture that just fired.

### Anti-Patterns to Avoid
- **Modifying only one loop:** Both `__main__.py` and `tray.py` have duplicated detection loops. Every config change MUST be applied to both. STATE.md explicitly warns about this.
- **Breaking backward compatibility:** A config.yaml without new fields must still work. All new fields need defaults in both `AppConfig` and `load_config()`.
- **Hardcoded test values matching old defaults:** Tests that assert `activation_delay == 0.4` or `cooldown_duration == 0.8` will break when defaults change. Update them.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| YAML parsing | Custom parser | PyYAML `safe_load` + `.get()` with defaults | Already used throughout |
| Config validation | Schema validator | Simple `.get(key, default)` pattern | Consistent with existing code |

**Key insight:** This phase adds no new infrastructure. Every pattern already exists in the codebase.

## Common Pitfalls

### Pitfall 1: Test Assertions Hardcoded to Old Defaults
**What goes wrong:** Tests in `test_config.py` assert `activation_delay == 0.4` and `cooldown_duration == 0.8`. Changing defaults breaks them.
**Why it happens:** Tests were written against original defaults.
**How to avoid:** Update ALL test assertions that reference old default values. Search for `0.4` and `0.8` in test files.
**Warning signs:** Test failures in `test_config.py::TestAppConfigTimingFields`

### Pitfall 2: Config.yaml User Values vs Code Defaults Confusion
**What goes wrong:** The user's `config.yaml` has `activation_delay: 0.2`, `cooldown_duration: 0.3`. Code defaults are `0.4`/`0.8`. The "tuned" targets are `0.15`/`0.3`. Three different value sets.
**Why it happens:** Code defaults are fallbacks for missing config keys; config.yaml is user-facing; tuned values are the new recommendation.
**How to avoid:** Update BOTH code defaults AND config.yaml. Code defaults = tuned values. Config.yaml = tuned values. Clear in commit messages which is which.

### Pitfall 3: Duplicate Loop Code Drift
**What goes wrong:** Change applied to `__main__.py` hot-reload but not `tray.py`, or vice versa.
**Why it happens:** Two copies of the detection loop exist (STATE.md concern).
**How to avoid:** Make changes to both files in the same plan/task. Verify both files in each commit.

### Pitfall 4: Per-Gesture Cooldown Not Wired Through Hot-Reload
**What goes wrong:** Per-gesture cooldowns work on startup but don't update when config is reloaded.
**Why it happens:** Hot-reload block doesn't extract gesture-specific cooldowns.
**How to avoid:** Extract per-gesture cooldowns in the hot-reload section, update debouncer's cooldown dict.

### Pitfall 5: Smoothing Window 30 in Config
**What goes wrong:** User's config.yaml has `smoothing_window: 30` which is almost certainly a typo/experiment. If we only update code defaults to 2, the user's config still overrides to 30.
**Why it happens:** Config file values override code defaults by design.
**How to avoid:** Update config.yaml to the tuned value (2). Document that this is intentional.

## Code Examples

### Updating AppConfig Defaults (TUNE-01)
```python
# config.py - AppConfig dataclass
@dataclass
class AppConfig:
    camera_index: int = 0
    smoothing_window: int = 2          # was 3
    activation_delay: float = 0.15     # was 0.4
    cooldown_duration: float = 0.3     # was 0.8
    # ... rest unchanged
```

### Adding settling_frames to Config (TUNE-02)
```python
# config.py - AppConfig dataclass
@dataclass
class AppConfig:
    # ... existing fields ...
    swipe_settling_frames: int = 3     # NEW

# config.py - load_config()
def load_config(path: str = "config.yaml") -> AppConfig:
    # ... existing parsing ...
    swipe = raw.get("swipe", {})
    return AppConfig(
        # ... existing fields ...
        swipe_settling_frames=int(swipe.get("settling_frames", 3)),
    )
```

### Per-Gesture Cooldown Extraction (TUNE-03)
```python
# In load_config() or a helper
def _extract_gesture_cooldowns(gestures: dict) -> dict[str, float]:
    """Extract per-gesture cooldown overrides from gesture config."""
    cooldowns = {}
    for name, settings in gestures.items():
        if isinstance(settings, dict) and "cooldown" in settings:
            cooldowns[name] = float(settings["cooldown"])
    return cooldowns
```

### Debouncer Per-Gesture Cooldown (TUNE-03)
```python
# debounce.py - modified _handle_fired
def _handle_fired(self, gesture, timestamp):
    self._state = DebounceState.COOLDOWN
    self._cooldown_start = timestamp
    # Use per-gesture cooldown if available, else global default
    fired_gesture = self._activating_gesture
    self._cooldown_duration_active = self._gesture_cooldowns.get(
        fired_gesture.value, self._cooldown_duration
    )
    self._cooldown_gesture = fired_gesture
    self._activating_gesture = None
    return None
```

Note: `_handle_cooldown` must use `self._cooldown_duration_active` instead of `self._cooldown_duration` for the elapsed check.

### Config.yaml Swipe Settling Frames (TUNE-02)
```yaml
swipe:
  cooldown: 0.5
  settling_frames: 3    # NEW: frames to wait after swipe before static gestures
  min_velocity: 0.15
  # ... rest unchanged
```

### Config.yaml Per-Gesture Cooldown (TUNE-03)
```yaml
gestures:
  pinch:
    key: win+down
    threshold: 0.06
    cooldown: 0.6    # longer cooldown for pinch (prone to false repeat)
  fist:
    key: esc
    threshold: 0.7
    # uses global cooldown (0.3s)
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| activation_delay=0.4 | Target: 0.15 | Phase 8-9 research | Faster response, safe with direct transitions |
| cooldown_duration=0.8 | Target: 0.3 | Phase 8-9 research | Faster re-fire, proven with direct transitions |
| smoothing_window=3 | Target: 2 | Phase 9 research | Lower latency: perceived = (window/fps) + activation |
| settling_frames=10 | settling_frames=3 | Phase 9 impl | Already changed in code, not yet configurable |
| Single global cooldown | Per-gesture overrides | Phase 10 (new) | Pinch/confusable gestures can have longer cooldowns |

**Key timing insight from Phase 9 research:**
`perceived_latency = (smoothing_window / fps) + activation_delay`
At 30 FPS with window=2, activation=0.15: `(2/30) + 0.15 = 0.217s` -- well under 300ms target.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (configured in pyproject.toml) |
| Config file | pyproject.toml `[tool.pytest.ini_options]` |
| Quick run command | `python -m pytest tests/ -x -q` |
| Full suite command | `python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TUNE-01 | Code defaults match tuned values | unit | `python -m pytest tests/test_config.py -x -q` | Exists but assertions need updating |
| TUNE-01 | Debouncer defaults match tuned values | unit | `python -m pytest tests/test_debounce.py -x -q` | Exists but uses old defaults |
| TUNE-02 | settling_frames parsed from config.yaml | unit | `python -m pytest tests/test_config.py -x -q` | New test needed |
| TUNE-02 | settling_frames wired to SwipeDetector | unit | `python -m pytest tests/test_swipe.py -x -q` | Exists, needs config test |
| TUNE-03 | Per-gesture cooldown parsed from config | unit | `python -m pytest tests/test_config.py -x -q` | New test needed |
| TUNE-03 | Debouncer uses per-gesture cooldown | unit | `python -m pytest tests/test_debounce.py -x -q` | New test needed |

### Sampling Rate
- **Per task commit:** `python -m pytest tests/ -x -q`
- **Per wave merge:** `python -m pytest tests/ -v`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_config.py` -- needs new tests for settling_frames parsing, per-gesture cooldown parsing, updated default assertions
- [ ] `tests/test_debounce.py` -- needs tests for per-gesture cooldown behavior, updated default assertions

## Files That Must Change

| File | Changes | Why |
|------|---------|-----|
| `gesture_keys/config.py` | Update AppConfig defaults, add `swipe_settling_frames` field, add `gesture_cooldowns` field, parse both in `load_config()` | TUNE-01, TUNE-02, TUNE-03 |
| `gesture_keys/debounce.py` | Update `__init__` defaults, add `gesture_cooldowns` param, per-gesture lookup in `_handle_fired`/`_handle_cooldown` | TUNE-01, TUNE-03 |
| `gesture_keys/smoother.py` | Update `__init__` default `window_size` from 3 to 2 | TUNE-01 |
| `gesture_keys/__main__.py` | Pass new config fields to constructors, add hot-reload for settling_frames and gesture_cooldowns | TUNE-02, TUNE-03 |
| `gesture_keys/tray.py` | Same as __main__.py (duplicate loop) | TUNE-02, TUNE-03 |
| `config.yaml` | Update detection defaults, add settling_frames example, add per-gesture cooldown examples | TUNE-01, TUNE-02, TUNE-03 |
| `tests/test_config.py` | Update default assertions, add new field tests | All |
| `tests/test_debounce.py` | Update default assertions, add per-gesture cooldown tests | TUNE-01, TUNE-03 |

## Open Questions

1. **Config.yaml smoothing_window: 30**
   - What we know: Code default is 3, config.yaml has 30, tuned target is 2
   - What's unclear: Whether 30 was intentional user tuning or a typo
   - Recommendation: Update to 2 in config.yaml (matches tuned target). The user can always change it back.

2. **Per-gesture cooldown config key name**
   - What we know: Need per-gesture cooldown override in gesture config section
   - What's unclear: Whether to use `cooldown` or `cooldown_duration` as the key name
   - Recommendation: Use `cooldown` (shorter, matches swipe section's `cooldown` key name for consistency)

## Sources

### Primary (HIGH confidence)
- Direct codebase analysis of all relevant source files
- STATE.md accumulated decisions from Phases 8-9
- REQUIREMENTS.md TUNE-01/02/03 specifications

### Secondary (MEDIUM confidence)
- Phase 9 research insight on perceived_latency formula (from STATE.md decisions)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - no new libraries, pure internal changes
- Architecture: HIGH - all patterns already exist in codebase, following established conventions
- Pitfalls: HIGH - identified from direct code analysis and STATE.md warnings

**Research date:** 2026-03-23
**Valid until:** 2026-04-23 (stable -- internal project, no external dependencies changing)
