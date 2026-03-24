---
phase: 14
slug: shared-types-and-pipeline-unification
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-24
---

# Phase 14 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (stdlib) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/ -x -q` |
| **Full suite command** | `python -m pytest tests/ -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/ -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 14-01-01 | 01 | 1 | PIPE-01 | unit | `python -m pytest tests/test_pipeline.py::TestFrameResult -x` | ❌ W0 | ⬜ pending |
| 14-01-02 | 01 | 1 | PIPE-02 | unit | `python -m pytest tests/test_pipeline.py::TestPipelineProcessFrame -x` | ❌ W0 | ⬜ pending |
| 14-01-03 | 01 | 1 | PIPE-02 | unit | `python -m pytest tests/test_pipeline.py::TestPipelineReload -x` | ❌ W0 | ⬜ pending |
| 14-01-04 | 01 | 1 | PIPE-02 | unit | `python -m pytest tests/test_pipeline.py::TestPipelineReset -x` | ❌ W0 | ⬜ pending |
| 14-02-01 | 02 | 2 | PIPE-03 | regression | `python -m pytest tests/test_integration.py -x` | ✅ | ⬜ pending |
| 14-02-02 | 02 | 2 | PIPE-04 | regression | `python -m pytest tests/test_tray.py -x` | ✅ | ⬜ pending |
| 14-02-03 | 02 | 2 | PIPE-03 | manual-only | Line count check: preview wrapper < 80 lines | N/A | ⬜ pending |
| 14-02-04 | 02 | 2 | PIPE-04 | manual-only | Line count check: tray wrapper < 50 lines | N/A | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_pipeline.py` — stubs for PIPE-01, PIPE-02 (FrameResult, Pipeline.process_frame, reload, reset)
- [ ] Framework install: None needed — pytest already configured

*Existing infrastructure covers regression requirements (PIPE-03, PIPE-04).*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Preview wrapper under 80 lines | PIPE-03 | Line count metric, not behavioral | `wc -l gesture_keys/__main__.py` after refactor |
| Tray wrapper under 50 lines | PIPE-04 | Line count metric, not behavioral | `wc -l gesture_keys/tray.py` after refactor |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
