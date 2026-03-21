---
phase: 3
slug: system-tray-and-background-operation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 3 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | pyproject.toml |
| **Quick run command** | `python -m pytest tests/test_tray.py -v` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_tray.py -v`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 03-01-01 | 01 | 1 | TRAY-01 | unit | `python -m pytest tests/test_tray.py -k tray_icon` | ❌ W0 | ⬜ pending |
| 03-01-02 | 01 | 1 | TRAY-02 | unit | `python -m pytest tests/test_tray.py -k toggle` | ❌ W0 | ⬜ pending |
| 03-01-03 | 01 | 1 | TRAY-03 | manual | N/A | N/A | ⬜ pending |
| 03-01-04 | 01 | 1 | TRAY-04 | unit | `python -m pytest tests/test_tray.py -k quit` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_tray.py` — stubs for TRAY-01, TRAY-02, TRAY-04
- [ ] Existing `tests/conftest.py` — shared fixtures (if needed)

*pystray and Pillow must be installed as dependencies.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Edit Config opens default editor | TRAY-03 | Requires OS-level editor launch | Click "Edit Config" in tray menu, verify config.yaml opens in default editor |
| Camera LED turns off on inactive | TRAY-02 | Requires physical camera observation | Toggle to inactive, observe camera LED is off |
| Console window hidden | TRAY-01 | Requires visual OS-level check | Launch without flags, verify no console or preview window visible |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
