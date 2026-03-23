---
phase: 10-tuned-defaults-and-config-surface
verified: 2026-03-23T12:30:00Z
status: passed
score: 13/13 must-haves verified
re_verification:
  previous_status: passed
  previous_score: 10/10
  gaps_closed: []
  gaps_remaining: []
  regressions: []
  note: "Re-verification covers plans 10-03 and 10-04 which were added after previous verification (plans 10-01 and 10-02 only)"
---

# Phase 10: Tuned Defaults and Config Surface Verification Report

**Phase Goal:** Tune all timing/threshold defaults to proven values from Phases 8-9; expose remaining knobs in config.yaml so users can adapt without code changes.
**Verified:** 2026-03-23
**Status:** passed
**Re-verification:** Yes — plans 10-03 and 10-04 were executed after previous verification

---

## Goal Achievement

### Observable Truths

All 13 must-have truths across all four plans were verified against the actual codebase.

#### Plans 10-01 / 10-02 Truths (carried from previous verification, regression-checked)

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 1  | AppConfig defaults: activation_delay=0.15, cooldown_duration=0.3, smoothing_window=2 | VERIFIED | `config.py` lines 18-20 |
| 2  | GestureDebouncer defaults match AppConfig (0.15/0.3) | VERIFIED | `debounce.py` lines 44-45 |
| 3  | GestureSmoother default window_size is 2 | VERIFIED | `smoother.py` line 15 |
| 4  | config.yaml ships tuned values (smoothing_window:2, activation_delay:0.15, cooldown_duration:0.3) | VERIFIED | `config.yaml` lines 5-7 |
| 5  | settling_frames configurable via swipe.settling_frames with default 3 | VERIFIED | `config.yaml` line 50; `config.py` line 31; `load_config` line 160 |
| 6  | settling_frames wired to SwipeDetector in both loops with hot-reload | VERIFIED | `__main__.py` line 274; `tray.py` line 267 |
| 7  | Per-gesture cooldown override used when gesture has one | VERIFIED | `debounce.py` lines 140-142 |
| 8  | Falls back to global cooldown_duration when no override | VERIFIED | `.get(..., self._cooldown_duration)` at `debounce.py` line 141 |
| 9  | Per-gesture cooldowns hot-reloaded in both loops | VERIFIED | `__main__.py` line 271; `tray.py` line 264 |
| 10 | config.yaml ships with commented-only cooldown example, no active overrides | VERIFIED | `config.yaml` line 46 |

#### Plan 10-03 Truths (static gesture priority)

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 11 | Static gestures fire before swipe can interfere (debouncer.is_activating gates swipe arming) | VERIFIED | `debounce.py` lines 64-69: `is_activating` property; `__main__.py` line 253: `suppressed=debouncer.is_activating`; `tray.py` line 246: identical |
| 12 | Swipe cooldown does NOT suppress static gesture detection (is_swiping is ARMED-only) | VERIFIED | `swipe.py` line 135: `return self._state == _SwipeState.ARMED` — no COOLDOWN |

#### Plan 10-04 Truths (hand-entry settling guard)

| #  | Truth | Status | Evidence |
|----|-------|--------|----------|
| 13 | Moving hand into view does NOT trigger swipe before static gesture can be recognized (hand-entry settling guard active; no pipeline reset on swipe arm) | VERIFIED | `swipe.py` lines 188-193: `_hand_present` tracking with settling guard; `__main__.py` lines 220-224: no `if swiping and not was_swiping` reset (swipe ARM reset removed); `swipe.py` line 152: `suppressed` kwarg preserves `_hand_present` during is_activating gate |

**Score:** 13/13 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `gesture_keys/config.py` | AppConfig with tuned defaults, swipe_settling_frames, gesture_cooldowns | VERIFIED | `swipe_settling_frames: int = 3` line 31; `gesture_cooldowns: dict[str, float]` line 32; activation_delay=0.15, cooldown_duration=0.3 lines 19-20 |
| `gesture_keys/debounce.py` | Debouncer with tuned defaults, per-gesture cooldown, is_activating property | VERIFIED | activation_delay=0.15 line 44; cooldown_duration=0.3 line 45; `gesture_cooldowns` line 50; `is_activating` property lines 63-69 |
| `gesture_keys/smoother.py` | Smoother with tuned default window_size=2 | VERIFIED | `window_size: int = 2` line 15 |
| `gesture_keys/swipe.py` | SwipeDetector with is_swiping=ARMED-only, _hand_present tracking, suppressed kwarg | VERIFIED | `is_swiping` line 135 returns only for ARMED; `_hand_present: bool = False` line 77; `suppressed: bool = False` kwarg line 152; hand-entry block lines 188-193 |
| `gesture_keys/__main__.py` | Detection loop: static-first, suppressed flag, swipe-arm reset removed | VERIFIED | Static block before swipe lines 217-248; `suppressed=debouncer.is_activating` line 253; no `if swiping and not was_swiping` reset block |
| `gesture_keys/tray.py` | Same detection loop changes as __main__.py | VERIFIED | Identical structure lines 217-255; `suppressed=debouncer.is_activating` line 246; no swipe-arm reset block |
| `config.yaml` | Tuned values, settling_frames, commented cooldown example | VERIFIED | detection block lines 4-7; swipe.settling_frames line 50; comment-only cooldown line 46 |

---

### Key Link Verification

#### Plans 10-01 / 10-02 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `config.py` | `__main__.py` | `config.swipe_settling_frames` to SwipeDetector constructor | VERIFIED | `__main__.py` line 171 |
| `config.py` | `tray.py` | `config.swipe_settling_frames` to SwipeDetector constructor | VERIFIED | `tray.py` line 175 |
| `config.py` | `debounce.py` | `gesture_cooldowns` dict passed to GestureDebouncer constructor | VERIFIED | `__main__.py` line 147; `tray.py` line 163 |
| `debounce.py` | `debounce.py` | `_handle_fired` uses per-gesture cooldown for active gesture | VERIFIED | `debounce.py` lines 140-142 |
| `__main__.py` | `debounce.py` | hot-reload updates `debouncer._gesture_cooldowns` | VERIFIED | `__main__.py` line 271 |
| `tray.py` | `debounce.py` | hot-reload updates `debouncer._gesture_cooldowns` | VERIFIED | `tray.py` line 264 |

#### Plan 10-03 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `debounce.py` | `__main__.py` | `debouncer.is_activating` property check gates swipe | VERIFIED | `__main__.py` line 253: `suppressed=debouncer.is_activating` |
| `swipe.py` | `__main__.py` | `is_swiping` now ARMED-only (not COOLDOWN) | VERIFIED | `swipe.py` line 135; used at `__main__.py` line 219 |

#### Plan 10-04 Key Links

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `swipe.py` | `__main__.py` | `SwipeDetector.update()` accepts `suppressed` kwarg; callers pass `suppressed=debouncer.is_activating` instead of faking None | VERIFIED | `swipe.py` line 152; `__main__.py` line 253 |
| `__main__.py` | `tray.py` | Identical loop changes: no swipe-arm reset, suppressed flag wired | VERIFIED | Both files have identical structure; grep for `if swiping and not was_swiping` returns nothing |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| TUNE-01 | 10-01, 10-03 | Code defaults updated to match proven real-usage values (activation_delay ~0.15s, cooldown ~0.3s, smoothing_window ~2) | SATISFIED | AppConfig: 0.15/0.3/2; GestureDebouncer: 0.15/0.3; GestureSmoother: 2; config.yaml: 0.15/0.3/2. Plan 10-03 extended this with static-gesture priority behaviour that completes the real-usage tuning goal. |
| TUNE-02 | 10-01 | Settling frames are configurable in config.yaml swipe section | SATISFIED | `config.yaml` `swipe.settling_frames: 3`; `AppConfig.swipe_settling_frames: int = 3`; parsed in `load_config`; wired to SwipeDetector in both loops with hot-reload |
| TUNE-03 | 10-02 | Per-gesture cooldown overrides configurable in config.yaml | SATISFIED | `_extract_gesture_cooldowns` in config.py; `AppConfig.gesture_cooldowns`; per-fire `_cooldown_duration_active` in debouncer; wired constructor and hot-reload in both loops; commented example in config.yaml |

All 3 phase-10 requirements (TUNE-01, TUNE-02, TUNE-03) satisfied. REQUIREMENTS.md Traceability table maps exactly these three IDs to Phase 10 — no orphaned requirements.

Plans 10-03 and 10-04 carry `requirements: [TUNE-01]` and `requirements: []` respectively. They are gap-closure plans (defect fixes that were required to make TUNE-01 work in practice), not new requirements. This is consistent with REQUIREMENTS.md.

---

### Anti-Patterns Found

None. No TODOs, FIXMEs, placeholders, empty returns, or stub implementations found in any modified file.

---

### Test Results

| Suite | Result | Notes |
|-------|--------|-------|
| `tests/test_debounce.py` | PASSED (all 81 in combined run) | Includes is_activating property tests |
| `tests/test_swipe.py` | PASSED | Includes 5 new hand-entry settling tests; is_swiping COOLDOWN regression test passes |
| `tests/test_integration_mutual_exclusion.py` | PASSED | Updated for ARMED-only semantics and initial hand-entry settling |
| All 157 non-config tests | PASSED | `python -m pytest --ignore=tests/test_config.py` → 157 passed |
| `tests/test_config.py::test_key_mappings` | FAILED (pre-existing) | `config.yaml` has local user modification: `fist.key` changed from `esc` to `space`. This is a personal user config edit predating Phase 10 and unrelated to any Phase 10 goal. Acknowledged in 10-04 SUMMARY. Not a Phase 10 regression. |

---

### Human Verification Required

None required for automated verification. The following are informational notes for manual QA:

**Note on config.yaml / test_config.py mismatch:**
`config.yaml` line 19 has `key: space` for the `fist` gesture; `test_config.py::test_key_mappings` expects `esc`. This mismatch predates Phase 10 (first noted in 10-04 SUMMARY) and is a user edit to their personal config, not a Phase 10 artifact.

**Note on `min_hand_size` AppConfig default vs config.yaml:**
`AppConfig.min_hand_size` defaults to `0.15` (config.py line 23), but `config.yaml` ships `min_hand_size: 0.12`. Pre-existing behaviour from Phase 4; `load_config` parses the YAML value correctly. Not introduced by Phase 10.

---

### Commits Verified

All implementation commits verified present in git history:

| Plan | Commit | Description |
|------|--------|-------------|
| 10-01 | `a9ddb91` | feat(10-01): update code defaults to tuned values (TUNE-01) |
| 10-01 | `4107381` | feat(10-01): add settling_frames config surface (TUNE-02) |
| 10-02 | `b419c70` | feat(10-02): add per-gesture cooldown config parsing and debouncer lookup (TUNE-03 part 1) |
| 10-02 | `4a0bc56` | feat(10-02): wire per-gesture cooldowns to both loops and config.yaml (TUNE-03 part 2) |
| 10-03 | `198a252` | test(10-03): failing tests for is_activating and is_swiping scope |
| 10-03 | `048b30d` | feat(10-03): add is_activating property and fix is_swiping to ARMED-only |
| 10-03 | `7624fed` | feat(10-03): static-first priority gate in both detection loops |
| 10-04 | `e046862` | test(10-04): failing tests for hand-entry settling guard and suppressed parameter |
| 10-04 | `ec5f514` | feat(10-04): add hand-entry settling guard and suppressed parameter to SwipeDetector |
| 10-04 | `41a1ddb` | fix(10-04): remove destructive pipeline reset on swipe arm, wire suppressed flag |

---

## Summary

Phase 10 goal is fully achieved across all four plans. All three requirements are implemented with real, wired, substantive code:

- **TUNE-01:** AppConfig, GestureDebouncer, and GestureSmoother carry the proven 0.15/0.3/2 defaults. config.yaml ships with the same values. Plans 10-03 and 10-04 completed the practical side of TUNE-01 by ensuring static gestures have priority over swipe detection (is_activating gate) and that approach motion no longer triggers spurious swipes (hand-entry settling guard, removal of swipe-arm pipeline reset).

- **TUNE-02:** `swipe_settling_frames` is a first-class AppConfig field, parsed from `swipe.settling_frames` in config.yaml (default 3), and wired to SwipeDetector in both `__main__.py` and `tray.py` at constructor time and on hot-reload.

- **TUNE-03:** Per-gesture cooldowns extracted by `_extract_gesture_cooldowns`, stored as `AppConfig.gesture_cooldowns`, passed to `GestureDebouncer`, applied per-fire via `_cooldown_duration_active`. Both detection loops wire the dict at construction and refresh it on hot-reload. config.yaml ships with a commented-only example.

Plans 10-03 and 10-04 are gap-closure plans with no new ROADMAP requirements: they fix the static-vs-swipe priority interaction that prevented TUNE-01 from delivering its real-usage goal in practice. 157 of 158 tests pass; the single failure (`test_key_mappings`) is a pre-existing user edit to config.yaml unrelated to Phase 10.

---

_Verified: 2026-03-23_
_Verifier: Claude (gsd-verifier)_
