---
phase: 21
slug: orchestrator-refactor
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-26
---

# Phase 21 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml (existing) |
| **Quick run command** | `python -m pytest tests/test_orchestrator.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_orchestrator.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 21-01-01 | 01 | 1 | ORCH-01 | unit | `python -m pytest tests/test_orchestrator.py -k "moving_fire" -x` | Will be created | pending |
| 21-01-02 | 01 | 1 | ORCH-02 | unit | `python -m pytest tests/test_orchestrator.py -k "sequence_fire" -x` | Will be created | pending |
| 21-01-03 | 01 | 1 | ORCH-03 | unit | `python -m pytest tests/test_orchestrator.py -k "type_def" -x` | Existing, needs update | pending |
| 21-01-04 | 01 | 1 | ORCH-04 | unit | `python -m pytest tests/test_orchestrator.py -k "sequence_window" -x` | Will be created | pending |

*Status: pending / green / red / flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements. New test functions will be added to the existing test_orchestrator.py file.

---

## Manual-Only Verifications

All phase behaviors have automated verification.

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
