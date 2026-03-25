---
phase: 16
slug: action-dispatch-and-fire-modes
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-25
---

# Phase 16 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_action.py tests/test_config.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q --ignore=tests/test_pipeline.py --ignore=tests/test_preview.py --ignore=tests/test_tray.py --ignore=tests/test_detector.py` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_action.py tests/test_config.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q --ignore=tests/test_pipeline.py --ignore=tests/test_preview.py --ignore=tests/test_tray.py --ignore=tests/test_detector.py`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 16-01-01 | 01 | 0 | ACTN-01 | unit | `python -m pytest tests/test_action.py::TestActionResolver -x` | ❌ W0 | ⬜ pending |
| 16-01-02 | 01 | 0 | ACTN-02 | unit | `python -m pytest tests/test_action.py::TestTapFireMode -x` | ❌ W0 | ⬜ pending |
| 16-01-03 | 01 | 0 | ACTN-03 | unit | `python -m pytest tests/test_action.py::TestHoldKeyFireMode -x` | ❌ W0 | ⬜ pending |
| 16-01-04 | 01 | 0 | ACTN-04 | unit | `python -m pytest tests/test_action.py::TestStuckKeyPrevention -x` | ❌ W0 | ⬜ pending |
| 16-01-05 | 01 | 0 | ACTN-05 | unit | `python -m pytest tests/test_config.py::TestFireModeConfig -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_action.py` — stubs for ACTN-01, ACTN-02, ACTN-03, ACTN-04 (new file)
- [ ] `gesture_keys/action.py` — ActionResolver + ActionDispatcher + FireMode + Action (new file)
- [ ] Config schema tests for `fire_mode` field in `tests/test_config.py` (extend existing, ACTN-05)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Hold key releases on app toggle off | ACTN-04 | Requires system tray interaction | 1. Map fist→hold_key→shift 2. Make fist gesture 3. Toggle app off via tray 4. Verify shift released |
| Hold key releases on distance exit | ACTN-04 | Requires physical hand movement | 1. Map fist→hold_key→shift 2. Make fist gesture 3. Move hand out of range 4. Verify shift released |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
