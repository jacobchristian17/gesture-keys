# Requirements: Gesture Keys

**Defined:** 2026-03-24
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v2.0 Requirements

Requirements for structured gesture architecture rewrite. Each maps to roadmap phases.

### Pipeline Foundation

- [x] **PIPE-01**: Shared data types (FrameResult, GestureState, TemporalState enums) used by all pipeline components
- [x] **PIPE-02**: Unified pipeline class that both preview and tray modes call, eliminating duplicated loop logic
- [x] **PIPE-03**: Preview mode wrapper using unified pipeline (~50 lines)
- [x] **PIPE-04**: Tray mode wrapper using unified pipeline (~30 lines)

### Activation

- [ ] **ACTV-01**: Activation gate arms/disarms gesture detection via configurable activation gestures (scout/peace default)
- [ ] **ACTV-02**: Bypass mode disables activation gating (all gestures pass through directly)
- [ ] **ACTV-03**: Activation gate integrates with gesture orchestrator (consumed gesture doesn't fire actions)

### Gesture Orchestration

- [x] **ORCH-01**: Unified gesture orchestrator replacing debouncer + main-loop coordination as single state machine
- [x] **ORCH-02**: Static gesture as base layer in gesture hierarchy
- [x] **ORCH-03**: Hold temporal state — sustained static gesture detected over consecutive frames
- [x] **ORCH-04**: Swiping temporal state — directional movement modifier on current static gesture
- [x] **ORCH-05**: Gesture type prioritization and state transitions managed by orchestrator

### Action Dispatch

- [ ] **ACTN-01**: Action resolver maps static gesture x temporal state to configured keyboard command
- [ ] **ACTN-02**: Tap fire mode — press and release key once on action trigger
- [ ] **ACTN-03**: Hold_key fire mode — key held down while gesture sustained, released on gesture change
- [ ] **ACTN-04**: Centralized key lifecycle management preventing stuck keys across all exit paths (gate expiry, hand switch, distance out-of-range, app toggle)
- [ ] **ACTN-05**: Config schema supporting structured gesture-to-action mappings with fire mode per action

## Future Requirements

### Enhancements

- **ENH-01**: Activation bypass per-gesture (some gestures always pass through)
- **ENH-02**: Hold-to-hold chaining (transition from one held gesture to another without release)
- **ENH-03**: Per-action fire mode override in config
- **ENH-04**: Repeat fire mode (repeated press at interval while gesture held)
- **ENH-05**: Visual feedback for activation state and temporal modifiers in preview

## Out of Scope

| Feature | Reason |
|---------|--------|
| Simultaneous two-hand gestures | State space explosion (42+ cells), complexity deferred |
| Sequence gestures (gesture A then B) | Adds latency to all gestures per QMK community consensus |
| Double-tap temporal modifier | Adds latency to single taps, unreliable with hand gestures |
| Custom gesture training | MediaPipe landmarks sufficient for current gesture set |
| GUI configuration | YAML config editing is sufficient for this milestone |
| Config auto-migration from v1.x | Clean rewrite — manual config update acceptable |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| PIPE-01 | Phase 14 | Complete |
| PIPE-02 | Phase 14 | Complete |
| PIPE-03 | Phase 14 | Complete |
| PIPE-04 | Phase 14 | Complete |
| ACTV-01 | Phase 17 | Pending |
| ACTV-02 | Phase 17 | Pending |
| ACTV-03 | Phase 17 | Pending |
| ORCH-01 | Phase 15 | Complete |
| ORCH-02 | Phase 15 | Complete |
| ORCH-03 | Phase 15 | Complete |
| ORCH-04 | Phase 15 | Complete |
| ORCH-05 | Phase 15 | Complete |
| ACTN-01 | Phase 16 | Pending |
| ACTN-02 | Phase 16 | Pending |
| ACTN-03 | Phase 16 | Pending |
| ACTN-04 | Phase 16 | Pending |
| ACTN-05 | Phase 16 | Pending |

**Coverage:**
- v2.0 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after roadmap creation*
