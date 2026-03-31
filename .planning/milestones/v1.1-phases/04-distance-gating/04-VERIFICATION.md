---
phase: 04-distance-gating
verified: 2026-03-21T14:00:00Z
status: passed
score: 13/13 must-haves verified
re_verification: false
---

# Phase 4: Distance Gating Verification Report

**Phase Goal:** Distance gating — filter out detections when hand is too far from camera
**Verified:** 2026-03-21
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

All 13 must-have truths from plans 01 and 02 are verified against the actual codebase.

#### Plan 01 Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | DistanceFilter passes landmarks when palm span >= threshold | VERIFIED | `distance.py:59` — `in_range = palm_span >= self._min_hand_size`; `return in_range` |
| 2  | DistanceFilter rejects landmarks when palm span < threshold | VERIFIED | Same expression returns False when span < threshold; test_distance.py:18 passes |
| 3  | DistanceFilter always passes when disabled | VERIFIED | `distance.py:55-56` — `if not self._enabled: return True` |
| 4  | Transition logging fires once per range change, not every frame | VERIFIED | `distance.py:62-75` — logs only on `in_range != _was_in_range`; 3 transition tests pass |
| 5  | Config loads distance section with enabled and min_hand_size fields | VERIFIED | `config.py:109,117-118` — `distance = raw.get("distance", {})`; returns `distance_enabled` and `min_hand_size` |
| 6  | Config without distance section defaults to gating disabled | VERIFIED | `config.py:117` — `bool(distance.get("enabled", False))` defaults to False when section missing |
| 7  | enabled: false preserves min_hand_size value in config | VERIFIED | `config.py:118` — `float(distance.get("min_hand_size", 0.15))` parsed regardless of enabled flag; TestDistanceConfig confirms |

#### Plan 02 Truths

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 8  | Gestures are suppressed when hand is too far (palm span < threshold) | VERIFIED | `__main__.py:173-179`, `tray.py:176-182` — `if not in_range: ... landmarks = None` |
| 9  | Gestures fire normally when hand is close enough or distance gating disabled | VERIFIED | Gating only when `not in_range`; disabled path in `DistanceFilter.check()` returns True unconditionally |
| 10 | Smoother and debouncer reset when hand transitions out of range | VERIFIED | `__main__.py:175-177`, `tray.py:178-180` — `if hand_was_in_range: smoother.reset(); debouncer.reset()` |
| 11 | Distance gating settings hot-reload when config.yaml changes | VERIFIED | `__main__.py:215-216`, `tray.py:210-211` — `distance_filter.enabled = new_config.distance_enabled; distance_filter.min_hand_size = new_config.min_hand_size` |
| 12 | Both preview mode and tray mode have identical distance gating behavior | VERIFIED | Both loops use identical `hand_was_in_range` pattern with `distance_filter.check()`; only `__main__.py` adds distance to reload log |
| 13 | Existing v1.0 configs with no distance section work exactly as before | VERIFIED | `AppConfig.distance_enabled` defaults to False; `config.py:109` uses `raw.get("distance", {})` — missing section is safe |

**Score:** 13/13 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `gesture_keys/distance.py` | DistanceFilter class with check() and palm span computation | VERIFIED | 83 lines; DistanceFilter, check(), _compute_palm_span(), properties |
| `gesture_keys/config.py` | AppConfig with distance_enabled and min_hand_size fields | VERIFIED | `distance_enabled: bool = False`, `min_hand_size: float = 0.15` at lines 22-23 |
| `tests/test_distance.py` | Unit tests for DistanceFilter behavior | VERIFIED | 111 lines, 14 tests across 4 test classes |
| `tests/test_config.py` | Unit tests for distance config parsing | VERIFIED | TestDistanceConfig class at line 193, 4 tests |
| `gesture_keys/__main__.py` | Preview loop with distance gating | VERIFIED | Contains `distance_filter`, import, instantiation, gating loop, hot-reload |
| `gesture_keys/tray.py` | Tray loop with distance gating | VERIFIED | Contains `distance_filter`, import, instantiation, identical gating loop, hot-reload |
| `tests/conftest.py` | Landmark fixtures for distance testing | VERIFIED | `mock_landmarks_close_hand` (span=0.25) and `mock_landmarks_far_hand` (span=0.08) at lines 183-205 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `gesture_keys/distance.py` | `gesture_keys/config.py` | DistanceFilter constructor takes min_hand_size and enabled from AppConfig | WIRED | Pattern `min_hand_size` found in both `__main__.py` and `tray.py` instantiation; AppConfig fields exist |
| `tests/test_distance.py` | `gesture_keys/distance.py` | imports DistanceFilter | WIRED | `from gesture_keys.distance import DistanceFilter` at line 8 |
| `gesture_keys/__main__.py` | `gesture_keys/distance.py` | import and instantiate DistanceFilter | WIRED | `from gesture_keys.distance import DistanceFilter` at line 18; instantiated at line 141 |
| `gesture_keys/tray.py` | `gesture_keys/distance.py` | import and instantiate DistanceFilter | WIRED | `from gesture_keys.distance import DistanceFilter` at line 16; instantiated at line 148 |
| `gesture_keys/__main__.py` | `gesture_keys/config.py` | reads distance_enabled and min_hand_size from AppConfig | WIRED | `config.distance_enabled` at line 143; hot-reload at line 215 |
| `gesture_keys/tray.py` | `gesture_keys/config.py` | reads distance_enabled and min_hand_size from AppConfig | WIRED | `config.distance_enabled` at line 150; hot-reload at line 210 |

All 6 key links verified.

---

### Requirements Coverage

| Requirement | Source Plans | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DIST-01 | 04-01, 04-02 | User can configure a minimum hand size threshold in config.yaml to ignore hands too far from the camera | SATISFIED | AppConfig.min_hand_size field; load_config() parses optional `distance:` section; config.yaml integration confirmed |
| DIST-02 | 04-01, 04-02 | Gestures are only detected when the hand's palm span (wrist-to-MCP distance) exceeds the configured threshold | SATISFIED | DistanceFilter.check() computes WRIST-to-MIDDLE_MCP Euclidean distance; both detection loops gate on result |

**DIST-03** (Phase 7, preview overlay) — correctly not claimed by this phase. REQUIREMENTS.md traceability table maps it to Phase 7. No orphaned requirements.

**Requirements coverage: 2/2 phase requirements satisfied.**

---

### Test Suite Results

| Test File | Tests | Result |
|-----------|-------|--------|
| tests/test_distance.py | 14 | All 14 pass |
| tests/test_config.py::TestDistanceConfig | 4 | All 4 pass |
| Full suite | 119 | 116 pass, 3 fail |

The 3 failures are pre-existing (documented in both 04-01-SUMMARY.md and 04-02-SUMMARY.md as unrelated to Phase 04):
- `TestLoadConfigDefault::test_smoothing_window_default` — config.yaml has `smoothing_window: 1`, test expects `3`
- `TestLoadConfigDefault::test_key_mappings` — stale assertion against old gesture set
- `TestAppConfigTimingFields::test_default_config_has_timing_fields` — config.yaml timing values differ from test expectations

These failures pre-date Phase 04 and are not caused by any Phase 04 change.

---

### Anti-Patterns Found

None. No TODO/FIXME/placeholder comments, empty implementations, or console-log-only stubs found in the phase 04 files.

---

### Human Verification Required

None. All phase 04 behaviors are testable programmatically. The distance calibration workflow (DIST-03 — preview overlay showing palm span value) is deferred to Phase 7 and out of scope here.

---

### Commit Verification

All three commits documented in the summaries verified present in git history:
- `ef6cb5b` — test(04-01): add failing tests for DistanceFilter and distance config
- `e2d8c6a` — feat(04-01): implement DistanceFilter class and config integration
- `2ffd54c` — feat(04-02): integrate DistanceFilter into both detection loops

---

## Summary

Phase 04 goal is fully achieved. The distance gating feature is implemented end-to-end:

1. **Core logic** — `DistanceFilter` in `gesture_keys/distance.py` computes WRIST-to-MIDDLE_MCP palm span and filters when below threshold, with transition-only logging and settable properties for hot-reload.

2. **Config integration** — `AppConfig` carries `distance_enabled` and `min_hand_size` fields; `load_config()` handles missing `distance:` section with v1.0-compatible defaults (disabled by default).

3. **Pipeline integration** — Both `__main__.py` and `tray.py` have identical distance gating between `detector.detect()` and `classifier.classify()`. Smoother and debouncer reset only on the in-range-to-out-of-range transition (not every filtered frame). Hot-reload updates both settings in both loops.

4. **Test coverage** — 18 new tests (14 distance, 4 config) all passing. TDD cycle documented with RED and GREEN commits.

Requirements DIST-01 and DIST-02 are satisfied. DIST-03 is correctly deferred to Phase 7.

---

_Verified: 2026-03-21_
_Verifier: Claude (gsd-verifier)_
