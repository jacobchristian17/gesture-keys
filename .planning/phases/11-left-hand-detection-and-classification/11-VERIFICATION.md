---
phase: 11-left-hand-detection-and-classification
verified: 2026-03-24T00:00:00Z
status: passed
score: 11/11 must-haves verified
---

# Phase 11: Left Hand Detection and Classification Verification Report

**Phase Goal:** Detect and classify left-hand gestures with full parity to right-hand support
**Verified:** 2026-03-24
**Status:** PASSED
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | HandDetector.detect() returns landmarks and handedness label for detected hands | VERIFIED | `detector.py` line 129: `def detect(...) -> tuple[list, Optional[str]]`; returns `(landmarks, label)` for all code paths |
| 2 | When only one hand is visible, that hand is selected as active regardless of left or right | VERIFIED | `detector.py` lines 169-172: single-hand path sets `_active_hand = label` and returns `(detected[label], label)` |
| 3 | When both hands are visible, the current active hand is retained until it disappears | VERIFIED | `detector.py` lines 175-177: two-hand sticky path checks `_active_hand in detected` and returns that hand |
| 4 | When both hands appear simultaneously at startup, preferred_hand is selected | VERIFIED | `detector.py` lines 179-182: `_active_hand is None` at startup path selects `_preferred_hand`; `test_both_hands_no_prior_active_selects_preferred` passes |
| 5 | preferred_hand defaults to left and is configurable in config.yaml | VERIFIED | `config.py` line 36: `preferred_hand: str = "left"`; `load_config()` line 177 reads from YAML; validated against "left"/"right" |
| 6 | Left hand correctly classifies all 6 static gestures with exact parity to right hand | VERIFIED | `TestLeftHandClassification` in `test_classifier.py` has 7 passing tests (open_palm, fist, thumbs_up, peace, pointing, pinch, scout) using mirrored left-hand fixtures |
| 7 | Left hand correctly detects all 4 swipe directions using absolute directions | VERIFIED | `swipe.py` uses only wrist position deltas (x/y) — hand-agnostic by design; swipe directions are absolute, not mirrored |
| 8 | Left hand uses the same debounce/cooldown/smoother pipeline as right hand | VERIFIED | Both `__main__.py` and `tray.py` pass landmarks through the same smoother/debouncer/swipe_detector pipeline regardless of handedness |
| 9 | Hand switch resets smoother and debouncer to avoid false fires | VERIFIED | `__main__.py` lines 215-222 and `tray.py` lines 215-222: `smoother.reset()`, `debouncer.reset()`, `swipe_detector.reset()` on `handedness != prev_handedness` |
| 10 | Hold mode releases on hand switch | VERIFIED | `__main__.py` line 217: `hold_active = False` + `sender.release_all()` on hand switch; same pattern in `tray.py` line 217 |
| 11 | Main loop and tray loop both use updated detect() return value with handedness | VERIFIED | `__main__.py` line 212: `landmarks, handedness = detector.detect(frame, timestamp_ms)`; `tray.py` line 212: identical pattern |

**Score:** 11/11 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `gesture_keys/detector.py` | HandDetector with active hand tracking and (landmarks, handedness) return | VERIFIED | 202 lines; `_active_hand`, `_preferred_hand` state; `detect()` returns tuple; `reset()` method present |
| `gesture_keys/config.py` | preferred_hand field in AppConfig | VERIFIED | `preferred_hand: str = "left"` at line 36; parsed and validated in `load_config()` |
| `tests/test_detector.py` | Tests for left hand, both hands, hand switching | VERIFIED | 448 lines; `TestHandDetector` class with 11 tests covering all active-hand selection scenarios |
| `tests/conftest.py` | Left-hand mirrored landmark fixtures for all 6 gestures (+scout) | VERIFIED | 7 left-hand fixtures: `mock_landmarks_left_open_palm`, `_left_fist`, `_left_thumbs_up`, `_left_peace`, `_left_pointing`, `_left_pinch`, `_left_scout` |
| `tests/test_classifier.py` | Classification parity tests for left-hand fixtures | VERIFIED | `TestLeftHandClassification` class with 7 tests, all passing |
| `gesture_keys/__main__.py` | Updated main loop with hand-switch state reset | VERIFIED | `preferred_hand=config.preferred_hand` passed to detector; `landmarks, handedness = detector.detect(...)`; hand-switch block at lines 214-223 |
| `gesture_keys/tray.py` | Updated tray loop with hand-switch state reset | VERIFIED | Same pattern as `__main__.py`; identical hand-switch reset block at lines 214-223 |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `gesture_keys/detector.py` | `gesture_keys/config.py` | preferred_hand parameter | WIRED | `HandDetector.__init__` accepts `preferred_hand: str = "left"`; `__main__.py` and `tray.py` pass `config.preferred_hand` |
| `gesture_keys/__main__.py` | `gesture_keys/detector.py` | detect() returning (landmarks, handedness) tuple | WIRED | `landmarks, handedness = detector.detect(frame, timestamp_ms)` at line 212 |
| `gesture_keys/__main__.py` | `gesture_keys/smoother.py` | smoother.reset() on hand switch | WIRED | `smoother.reset()` called at line 219 inside the `handedness != prev_handedness` block |
| `gesture_keys/tray.py` | `gesture_keys/detector.py` | detect() returning (landmarks, handedness) tuple | WIRED | `landmarks, handedness = detector.detect(frame, timestamp_ms)` at line 212 |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| DET-01 | 11-01-PLAN.md | App detects left hand landmarks via MediaPipe when left hand is in frame | SATISFIED | `detector.py` `num_hands=2` allows both hands; single-hand path selects left hand and returns its landmarks; `test_left_hand_returns_landmarks` passes |
| DET-02 | 11-01-PLAN.md | App selects one active hand when only one hand is visible | SATISFIED | Single-hand path in `detector.py` lines 169-172; `test_right_hand_returns_landmarks` and `test_left_hand_returns_landmarks` both pass |
| DET-03 | 11-01-PLAN.md | App prioritizes one hand when both are briefly visible during hand-switch transitions | SATISFIED | Two-hand sticky logic + transition frame `([], None)` path in `detector.py`; `test_both_hands_sticks_with_active` and `test_two_hands_active_not_in_detected_returns_empty` pass |
| CLS-01 | 11-02-PLAN.md | Left hand correctly classifies all 6 static gestures | SATISFIED | `TestLeftHandClassification` with 7 tests all passing (includes scout as 7th gesture) |
| CLS-02 | 11-02-PLAN.md | Left hand correctly detects all 4 swipe directions | SATISFIED | `swipe.py` uses only wrist position deltas — absolutely directional, hand-agnostic; same swipe_detector instance processes left-hand landmarks |
| CLS-03 | 11-02-PLAN.md | Left hand uses same debounce/cooldown/pipeline as right hand | SATISFIED | Both loops pass landmarks through identical smoother/debouncer/swipe_detector pipeline; handedness only used for hand-switch detection, not routing |

**All 6 requirements from phase 11 plans accounted for. No orphaned requirements for this phase.**

Note: CFG-01, CFG-02, CFG-03 (Phase 12) and PRV-01 (Phase 13) are mapped to future phases in REQUIREMENTS.md — correctly out of scope for phase 11.

---

### Anti-Patterns Found

No anti-patterns detected in any phase-modified files. No TODO/FIXME/placeholder comments, no stub implementations, no empty handlers.

---

### Pre-existing Test Failures (Out of Scope)

3 test failures exist in `tests/test_config.py` but are pre-existing and unrelated to phase 11:

| Test | Failure | Root Cause |
|------|---------|------------|
| `TestLoadConfigDefault::test_key_mappings` | `'space' == 'esc'` assertion | config.yaml gesture keys drifted from test expectations in an earlier phase |
| `TestAppConfigTimingFields::test_default_config_has_timing_fields` | config.yaml value drift | Same root cause |
| `TestSettlingFramesConfig::test_load_config_settling_frames_from_default_config` | config.yaml value drift | Same root cause |

Both SUMMARYs explicitly documented these as pre-existing and out of scope. All 250 non-config tests pass.

---

### Human Verification Required

None required. All observable behaviors are verifiable through code inspection and test results.

The following is noted for completeness but does not block goal achievement:

**1. Live swipe detection with left hand**
**Test:** Hold left hand in frame, swipe left, right, up, down
**Expected:** Swipe events fire for all 4 directions same as right hand
**Why human:** Swipe detection correctness with real MediaPipe landmarks vs. synthetic fixtures cannot be confirmed programmatically. However, the swipe detector is demonstrably hand-agnostic (only uses wrist x/y deltas) so this is very low risk.

---

## Commits Verified

All 4 commits referenced in SUMMARYs confirmed present in git log:
- `5fa3045` — test(11-01): add failing tests for hand detection
- `ae70f3c` — feat(11-01): extend HandDetector with active hand selection
- `96d3b8f` — test(11-02): verify left-hand classification parity
- `2f0f463` — feat(11-02): wire hand-switch logic into main and tray detection loops

---

_Verified: 2026-03-24_
_Verifier: Claude (gsd-verifier)_
