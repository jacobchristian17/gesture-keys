---
phase: 5
slug: swipe-detection
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 (Python 3.13) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_swipe.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_swipe.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| TBD | 01 | 1 | SWIPE-01 | unit | `python -m pytest tests/test_swipe.py::TestSwipeDirectionClassification -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SWIPE-02 | unit | `python -m pytest tests/test_config.py::TestSwipeConfig -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SWIPE-03 | unit | `python -m pytest tests/test_swipe.py::TestSwipeCooldown -x` | ❌ W0 | ⬜ pending |
| TBD | 01 | 1 | SWIPE-04 | unit | `python -m pytest tests/test_swipe.py::TestSwipePoseIndependence -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_swipe.py` — stubs for SWIPE-01, SWIPE-03, SWIPE-04
- [ ] `tests/test_config.py::TestSwipeConfig` — stubs for SWIPE-02 (add to existing file)
- [ ] Conftest fixture: `mock_swipe_landmarks_sequence` helper for generating position sequences with known velocities

*Existing infrastructure covers framework and config — only test files needed.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Swipe feels responsive in real-time use | SWIPE-01 | Latency perception is subjective | Run with --preview, perform 10 swipes in each direction, verify <200ms perceived delay |
| Casual repositioning doesn't trigger swipes | SWIPE-04 | Depends on natural hand movement patterns | Run with --preview, slowly move hand around frame without swiping intent, verify no false fires over 30 seconds |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
