---
phase: 17
slug: activation-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 17 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | None (pytest defaults, collected from tests/) |
| **Quick run command** | `python -m pytest tests/test_activation.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_activation.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 17-01-01 | 01 | 1 | ACTV-01 | unit | `python -m pytest tests/test_activation.py -x -q` | ❌ W0 | ⬜ pending |
| 17-01-02 | 01 | 1 | ACTV-01 | unit | `python -m pytest tests/test_activation.py -x -q` | ❌ W0 | ⬜ pending |
| 17-02-01 | 02 | 2 | ACTV-02, ACTV-03 | unit | `python -m pytest tests/test_activation.py -x -q` | ❌ W0 | ⬜ pending |
| 17-02-02 | 02 | 2 | ACTV-03 | unit | `python -m pytest tests/test_activation.py -x -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_activation.py` — gate unit tests covering ACTV-01 (arm/tick/expiry), ACTV-02 (bypass), ACTV-03 (consume activation gesture, stuck key safety)
- [ ] Existing `ActivationGate` class has no tests — needs baseline coverage

*Existing infrastructure (pytest, conftest) covers framework needs.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Activation gesture arms system visibly in preview | ACTV-01 | UI feedback requires visual inspection | Make scout gesture, observe preview shows "ARMED" state, confirm gestures fire only while armed |
| Gate expiry stops held keys in real app | ACTV-03 | SendInput behavior on Windows | Configure hold_key gesture, activate gate, sustain gesture, wait for gate expiry, confirm key output stops |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
