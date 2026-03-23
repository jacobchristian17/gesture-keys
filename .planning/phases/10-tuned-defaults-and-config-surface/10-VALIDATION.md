---
phase: 10
slug: tuned-defaults-and-config-surface
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-23
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (configured in pyproject.toml) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | TUNE-01 | unit | `python -m pytest tests/test_config.py -x -q` | Exists (update assertions) | ⬜ pending |
| 10-01-02 | 01 | 1 | TUNE-01 | unit | `python -m pytest tests/test_debounce.py -x -q` | Exists (update assertions) | ⬜ pending |
| 10-01-03 | 01 | 1 | TUNE-02 | unit | `python -m pytest tests/test_config.py -x -q` | New test needed | ⬜ pending |
| 10-02-01 | 02 | 1 | TUNE-02 | unit | `python -m pytest tests/test_swipe.py -x -q` | Exists (needs config test) | ⬜ pending |
| 10-02-02 | 02 | 1 | TUNE-03 | unit | `python -m pytest tests/test_config.py -x -q` | New test needed | ⬜ pending |
| 10-02-03 | 02 | 1 | TUNE-03 | unit | `python -m pytest tests/test_debounce.py -x -q` | New test needed | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_config.py` — update default assertions for TUNE-01, add settling_frames parsing tests for TUNE-02, add per-gesture cooldown parsing tests for TUNE-03
- [ ] `tests/test_debounce.py` — update default assertions for TUNE-01, add per-gesture cooldown behavior tests for TUNE-03

*Existing infrastructure covers framework requirements.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Fresh install feels responsive | TUNE-01 | Subjective responsiveness | Launch with default config, perform 10 gesture sequences, verify no false fires and responsive feel |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
