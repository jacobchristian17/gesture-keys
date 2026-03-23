---
phase: 8
slug: direct-gesture-transitions
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-22
---

# Phase 8 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 |
| **Config file** | pyproject.toml (`[tool.pytest.ini_options]`) |
| **Quick run command** | `python -m pytest tests/test_debounce.py -x` |
| **Full suite command** | `python -m pytest tests/ -x` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_debounce.py -x`
- **After every plan wave:** Run `python -m pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 08-01-01 | 01 | 0 | TRANS-01 | unit | `python -m pytest tests/test_debounce.py::TestDirectTransitions -x` | ❌ W0 | ⬜ pending |
| 08-01-02 | 01 | 0 | TRANS-02 | unit | `python -m pytest tests/test_debounce.py::TestDirectTransitions -x` | ❌ W0 | ⬜ pending |
| 08-01-03 | 01 | 1 | TRANS-01 | unit | `python -m pytest tests/test_debounce.py::TestDirectTransitions -x` | ❌ W0 | ⬜ pending |
| 08-01-04 | 01 | 1 | TRANS-02 | unit | `python -m pytest tests/test_debounce.py::TestDirectTransitions -x` | ❌ W0 | ⬜ pending |
| 08-02-01 | 02 | 1 | TRANS-03 | unit | `python -m pytest tests/test_preview_state.py -x` | ❌ W0 | ⬜ pending |
| 08-02-02 | 02 | 1 | TRANS-03 | unit | `python -m pytest tests/test_preview_state.py -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_debounce.py::TestDirectTransitions` — stubs for TRANS-01, TRANS-02 direct transition scenarios
- [ ] `tests/test_preview_state.py` — stubs for TRANS-03 debounce state display verification
- [ ] Verify `render_preview` accepts optional `debounce_state` kwarg without breaking existing tests

*Existing infrastructure covers basic debounce state machine. New tests needed for the COOLDOWN->ACTIVATING path and same-gesture-blocking during cooldown.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual debounce state indicator colors/position | TRANS-03 | OpenCV rendering requires visual inspection | Run preview mode, observe state text changes color/label as gestures activate/cooldown |
| End-to-end gesture-to-gesture switching feels fluid | TRANS-01 | Subjective user experience | Switch between FIST->PEACE->POINTING rapidly, verify each fires without returning to None |
| Transitional pose pass-through doesn't spuriously fire | TRANS-01 | Real camera noise varies | Switch between gestures while watching preview, verify no extra fires during transition |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
