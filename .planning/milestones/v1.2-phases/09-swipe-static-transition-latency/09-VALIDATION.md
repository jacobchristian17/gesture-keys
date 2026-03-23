---
phase: 9
slug: swipe-static-transition-latency
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 9 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | pytest default discovery |
| **Quick run command** | `python -m pytest tests/test_swipe.py tests/test_debounce.py tests/test_integration_mutual_exclusion.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_swipe.py tests/test_debounce.py tests/test_integration_mutual_exclusion.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 09-01-01 | 01 | 1 | LAT-02 | integration | `python -m pytest tests/test_integration_mutual_exclusion.py -x -q -k "exit_reset"` | No - W0 | pending |
| 09-01-02 | 01 | 1 | LAT-02 | unit | `python -m pytest tests/test_swipe.py -x -q -k "hot_reload_reset"` | No - W0 | pending |
| 09-02-01 | 02 | 2 | LAT-03 | unit | `python -m pytest tests/test_swipe.py -x -q -k "default_settling"` | No - W0 | pending |
| 09-02-02 | 02 | 2 | LAT-01 | integration | `python -m pytest tests/test_integration_mutual_exclusion.py -x -q -k "transition_latency"` | No - W0 | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_integration_mutual_exclusion.py::TestSwipeExitReset` — stubs for LAT-02 exit reset verification
- [ ] `tests/test_integration_mutual_exclusion.py::TestTransitionLatency` — stubs for LAT-01 end-to-end timing
- [ ] `tests/test_swipe.py::test_default_settling_frames_is_3` — stub for LAT-03 default check
- [ ] Hot-reload smoother reset test — stub for LAT-02 hot-reload sub-fix

*Existing infrastructure covers baseline swipe/debounce behavior; gaps are for NEW behaviors added in this phase.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Perceived latency feels responsive | LAT-01 | Subjective UX assessment | Run with `--preview`, perform swipe, immediately hold static gesture, observe fire timing feels ~300ms or better |
| No false fires from residual motion | LAT-03 | Depends on real camera input | Run with `--preview`, perform fast swipes, verify no unintended static fires during settling |

---

## Validation Sign-Off

- [ ] All tasks have automated verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
