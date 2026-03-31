---
phase: 6
slug: integration-and-mutual-exclusion
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing infrastructure) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_swipe.py tests/test_integration_mutual_exclusion.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_swipe.py tests/test_integration_mutual_exclusion.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 0 | INT-01 | unit | `python -m pytest tests/test_swipe.py::TestSwipeIsSwiping -x` | ❌ W0 | ⬜ pending |
| 06-01-02 | 01 | 0 | INT-02 | unit | `python -m pytest tests/test_swipe.py::TestSwipeReset -x` | ❌ W0 | ⬜ pending |
| 06-01-03 | 01 | 0 | INT-01 | unit | `python -m pytest tests/test_swipe.py::TestSwipeMutualExclusion -x` | ❌ W0 | ⬜ pending |
| 06-01-04 | 01 | 0 | INT-01, INT-02 | integration | `python -m pytest tests/test_integration_mutual_exclusion.py -x` | ❌ W0 | ⬜ pending |
| 06-02-01 | 02 | 1 | INT-01 | unit | `python -m pytest tests/test_swipe.py::TestSwipeIsSwiping -x` | ❌ W0 | ⬜ pending |
| 06-02-02 | 02 | 1 | INT-01 | integration | `python -m pytest tests/test_integration_mutual_exclusion.py -x` | ❌ W0 | ⬜ pending |
| 06-03-01 | 03 | 1 | INT-02 | unit | `python -m pytest tests/test_swipe.py::TestSwipeReset -x` | ❌ W0 | ⬜ pending |
| 06-03-02 | 03 | 1 | INT-01, INT-02 | integration | `python -m pytest tests/test_integration_mutual_exclusion.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_swipe.py::TestSwipeIsSwiping` — test is_swiping property in IDLE, ARMED, COOLDOWN states
- [ ] `tests/test_swipe.py::TestSwipeReset` — test reset() method clears buffer and state
- [ ] `tests/test_swipe.py::TestSwipeMutualExclusion` — test static pipeline suppression when is_swiping is true
- [ ] `tests/test_integration_mutual_exclusion.py` — end-to-end tests: swipe-during-pose, pose-during-swipe, distance transitions

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real-time swipe/pose transition feels responsive | INT-01 | Subjective timing perception | 1. Run app 2. Alternate between swipes and held poses 3. Verify no perceptible lag or missed gestures |
| Distance gating suppresses both pipelines visually | INT-02 | Requires physical hand movement | 1. Run app 2. Move hand beyond distance threshold 3. Verify no gestures fire 4. Return hand and verify both resume |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
