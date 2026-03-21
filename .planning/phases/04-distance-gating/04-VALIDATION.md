---
phase: 4
slug: distance-gating
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-21
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (existing) |
| **Config file** | pyproject.toml `[tool.pytest.ini_options]` |
| **Quick run command** | `python -m pytest tests/test_distance.py tests/test_config.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_distance.py tests/test_config.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 4-01-01 | 01 | 0 | DIST-01 | unit | `python -m pytest tests/test_config.py -x -q -k distance` | ❌ W0 | ⬜ pending |
| 4-01-02 | 01 | 0 | DIST-01 | unit | `python -m pytest tests/test_config.py -x -q -k distance_missing` | ❌ W0 | ⬜ pending |
| 4-01-03 | 01 | 0 | DIST-02 | unit | `python -m pytest tests/test_distance.py -x -q -k passes` | ❌ W0 | ⬜ pending |
| 4-01-04 | 01 | 0 | DIST-02 | unit | `python -m pytest tests/test_distance.py -x -q -k rejects` | ❌ W0 | ⬜ pending |
| 4-01-05 | 01 | 0 | DIST-02 | unit | `python -m pytest tests/test_distance.py -x -q -k disabled` | ❌ W0 | ⬜ pending |
| 4-01-06 | 01 | 0 | DIST-02 | unit | `python -m pytest tests/test_distance.py -x -q -k transition` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_distance.py` — stubs for DIST-02 (DistanceFilter pass/fail/disabled/transition)
- [ ] Update `tests/test_config.py` — stubs for DIST-01 (distance config section parsing, defaults, missing section)
- [ ] Update `tests/conftest.py` — add landmark fixtures with known palm span values for distance testing

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visual feedback in tray when hand goes out of range | DIST-02 | Requires live webcam + physical hand movement | 1. Enable distance gating 2. Move hand away from camera 3. Verify gesture stops firing 4. Move hand back, verify gesture resumes |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
