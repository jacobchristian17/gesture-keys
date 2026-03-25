---
phase: 15
slug: gesture-orchestrator
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 15 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (configured in pyproject.toml) |
| **Config file** | `pyproject.toml` [tool.pytest.ini_options] |
| **Quick run command** | `pytest tests/test_orchestrator.py -x` |
| **Full suite command** | `pytest tests/ -x` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest tests/test_orchestrator.py -x`
- **After every plan wave:** Run `pytest tests/ -x`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 15-01-01 | 01 | 0 | ORCH-01 | unit | `pytest tests/test_orchestrator.py -x -k "TestOrchestratorStateTransitions"` | ❌ W0 | ⬜ pending |
| 15-01-02 | 01 | 0 | ORCH-02 | unit | `pytest tests/test_orchestrator.py -x -k "test_base_gesture"` | ❌ W0 | ⬜ pending |
| 15-01-03 | 01 | 0 | ORCH-03 | unit | `pytest tests/test_orchestrator.py -x -k "TestHoldMode"` | ❌ W0 | ⬜ pending |
| 15-01-04 | 01 | 0 | ORCH-04 | unit | `pytest tests/test_orchestrator.py -x -k "TestSwipeWindow"` | ❌ W0 | ⬜ pending |
| 15-01-05 | 01 | 0 | ORCH-05 | unit | `pytest tests/test_orchestrator.py -x -k "TestDirectTransitions or TestEdgeCases"` | ❌ W0 | ⬜ pending |
| 15-02-01 | 02 | 1 | ORCH-01 | unit | `pytest tests/test_orchestrator.py -x` | ❌ W0 | ⬜ pending |
| 15-02-02 | 02 | 1 | ORCH-02 | unit | `pytest tests/test_orchestrator.py -x -k "test_base_gesture"` | ❌ W0 | ⬜ pending |
| 15-02-03 | 02 | 1 | ORCH-03 | unit | `pytest tests/test_orchestrator.py -x -k "TestHoldMode"` | ❌ W0 | ⬜ pending |
| 15-02-04 | 02 | 1 | ORCH-04 | unit | `pytest tests/test_orchestrator.py -x -k "TestSwipeWindow"` | ❌ W0 | ⬜ pending |
| 15-02-05 | 02 | 1 | ORCH-05 | unit | `pytest tests/test_orchestrator.py -x -k "TestEdgeCases"` | ❌ W0 | ⬜ pending |
| 15-03-01 | 03 | 2 | ORCH-01 | integration | `pytest tests/test_pipeline.py -x` | Yes (needs update) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_orchestrator.py` — stubs for ORCH-01 through ORCH-05 (ported from test_debounce.py + new hierarchical tests)
- [ ] No framework install needed — pytest already configured
- [ ] No shared fixtures needed beyond existing conftest.py

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual gesture confirmation in live camera feed | ORCH-01 | Requires webcam + hand gestures | Run app, perform each gesture, verify keystroke fires |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
