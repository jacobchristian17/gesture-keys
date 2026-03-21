---
phase: 1
slug: detection-and-preview
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 8.x |
| **Config file** | none — Wave 0 installs |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -v` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -v`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 01-01-01 | 01 | 0 | DET-01 | unit | `python -m pytest tests/test_classifier.py -x` | ❌ W0 | ⬜ pending |
| 01-01-02 | 01 | 0 | DET-02 | unit | `python -m pytest tests/test_smoother.py -x` | ❌ W0 | ⬜ pending |
| 01-01-03 | 01 | 0 | DET-03 | unit | `python -m pytest tests/test_detector.py::test_threaded_capture -x` | ❌ W0 | ⬜ pending |
| 01-01-04 | 01 | 0 | DET-04 | unit | `python -m pytest tests/test_detector.py::test_right_hand_filter -x` | ❌ W0 | ⬜ pending |
| 01-02-01 | 02 | 1 | DEV-01 | manual | Manual: run `python -m gesture_keys --preview` and verify window opens | N/A | ⬜ pending |
| 01-02-02 | 02 | 1 | DEV-02 | integration | `python -m pytest tests/test_integration.py::test_console_output -x` | ❌ W0 | ⬜ pending |
| 01-02-03 | 02 | 1 | DEV-03 | manual | Manual: verify FPS counter visible in preview window | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/__init__.py` — test package init
- [ ] `tests/test_classifier.py` — stubs for DET-01 (6 gesture classification from mock landmarks)
- [ ] `tests/test_smoother.py` — stubs for DET-02 (majority-vote smoothing logic)
- [ ] `tests/test_detector.py` — stubs for DET-03, DET-04 (threaded capture, right-hand filter)
- [ ] `tests/test_config.py` — config loading and defaults
- [ ] `tests/conftest.py` — shared fixtures (mock landmarks for each gesture, mock config)
- [ ] `pytest.ini` or `pyproject.toml` — pytest configuration
- [ ] Framework install: `pip install pytest` added to requirements.txt

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| --preview opens camera window | DEV-01 | Requires physical display and webcam hardware | Run `python -m gesture_keys --preview`, verify window with live feed appears |
| FPS counter visible | DEV-03 | Requires visual inspection of rendered overlay | Run preview, verify FPS number updates in bottom-right of bar |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
