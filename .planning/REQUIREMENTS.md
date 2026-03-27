# Requirements: Gesture Keys

**Defined:** 2026-03-27
**Core Value:** Hand gestures reliably trigger the correct keyboard commands in real applications without false fires.

## v3.1 Requirements

Requirements for moving_fire dispatch throttling. Each maps to roadmap phases.

### Dispatch Throttling

- [ ] **THRT-01**: User can configure a global dispatch interval for moving_fire actions (time-based cooldown between dispatches)
- [ ] **THRT-02**: User can configure a per-action dispatch interval override on individual moving trigger actions
- [ ] **THRT-03**: Moving_fire dispatches are skipped when the interval since last dispatch for that action has not elapsed

## Future Requirements

None identified.

## Out of Scope

| Feature | Reason |
|---------|--------|
| Direction-specific throttle rates | Per-action override covers this via individual action entries |
| Adaptive throttling based on velocity | Adds complexity; fixed interval is predictable and sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| THRT-01 | Phase 25 | Pending |
| THRT-02 | Phase 25 | Pending |
| THRT-03 | Phase 25 | Pending |

**Coverage:**
- v3.1 requirements: 3 total
- Mapped to phases: 3
- Unmapped: 0

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 after roadmap creation*
