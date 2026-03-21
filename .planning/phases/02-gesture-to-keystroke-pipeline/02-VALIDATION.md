---
phase: 02
slug: gesture-to-keystroke-pipeline
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 02 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest >=8.0 |
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
| 02-01-01 | 01 | 1 | KEY-01 | unit | `python -m pytest tests/test_keystroke.py -x` | ❌ W0 | ⬜ pending |
| 02-01-02 | 01 | 1 | KEY-02 | unit | `python -m pytest tests/test_debounce.py -x` | ❌ W0 | ⬜ pending |
| 02-01-03 | 01 | 1 | KEY-04 | unit | `python -m pytest tests/test_debounce.py tests/test_keystroke.py -x -k log` | ❌ W0 | ⬜ pending |
| 02-02-01 | 02 | 1 | KEY-05 | unit | `python -m pytest tests/test_config.py -x -k reload` | ❌ W0 | ⬜ pending |
| 02-02-02 | 02 | 1 | KEY-03 | integration (manual) | Manual — verify in text editor | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_debounce.py` — stubs for KEY-02 (state machine logic, timing, cooldown)
- [ ] `tests/test_keystroke.py` — stubs for KEY-01, KEY-03 (key parsing, sender with mock controller)
- [ ] `tests/test_config.py` additions — stubs for KEY-05 (reload detection, new config fields)
- [ ] `pynput>=1.7.6` in requirements.txt — dependency for keystroke module

*If none: "Existing infrastructure covers all phase requirements."*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Key commands fire in foreground app | KEY-03 | Requires real OS keyboard events in a text editor | 1. Open Notepad. 2. Run gesture-keys. 3. Hold fist for 0.5s → expect Ctrl+Z. 4. Hold pointing → expect Enter. 5. Verify single keys and combos both work. |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
