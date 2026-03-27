---
phase: 19
slug: motiondetector
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 19 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (pyproject.toml) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_motion.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_motion.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 19-01-01 | 01 | 1 | MOTN-01 | unit | `python -m pytest tests/test_motion.py::TestMotionDetection -x` | ❌ W0 | ⬜ pending |
| 19-01-02 | 01 | 1 | MOTN-02 | unit | `python -m pytest tests/test_motion.py::TestDirectionClassification -x` | ❌ W0 | ⬜ pending |
| 19-01-03 | 01 | 1 | MOTN-03 | unit | `python -m pytest tests/test_motion.py::TestHysteresis -x` | ❌ W0 | ⬜ pending |
| 19-01-04 | 01 | 1 | MOTN-04 | unit | `python -m pytest tests/test_motion.py::TestSettlingFrames -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_motion.py` — stubs for MOTN-01, MOTN-02, MOTN-03, MOTN-04
- [ ] Test helpers: `_make_wrist_landmarks()` and position sequence generators (borrow from test_swipe.py)

*Existing infrastructure covers framework needs — pytest already configured and used extensively.*

---

## Manual-Only Verifications

*All phase behaviors have automated verification.*

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
