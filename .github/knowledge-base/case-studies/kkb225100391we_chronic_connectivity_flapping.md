# KKB225100391WE - Chronic Connectivity Flapping Baseline

**Case Date:** 2026-03-06 analysis session  
**Charger:** KKB225100391WE  
**Firmware Seen:** 01.25.13.00 -> 01.26.38.00 (latest available: 01.26.39.00)  
**Scope:** Long-horizon backend disconnect/reconnect persistence and remediation path

---

## Summary

This charger shows repeated backend connect/disconnect behavior that appears chronic, not new.
Event history indicates recurring connectivity fault/recovery patterns from late 2023 onward,
and similar behavior is still visible after upgrade to `01.26.38.00`.

Primary interpretation:
- The issue is unlikely to be explained by firmware age alone.
- Most likely branches are:
  1) physical Ethernet/path instability, or
  2) deeper charger comms stack/firmware instability.

---

## Key Evidence

### EventLog History

- `011002/111002` fault/recovery pairs appear repeatedly from late 2023 through 2026.
- Pattern remains active in latest retained monthly logs.

Interpretation:
- Strong evidence of a long-standing condition likely present since early lifecycle.

### Post-Upgrade Behavior

- Flapping persisted after the unit moved to `01.26.38.00`.
- This weakens the hypothesis that the issue is only from older firmware.

---

## Operational Test Plan

Run this sequence in order:

1. Upgrade to latest firmware (`01.26.39.00`)
2. Factory reset
3. Clear browser cache
4. Recommission charger
5. Run transport A/B test to GreenFlux:
   - baseline on Ethernet
   - repeat on Wi-Fi or cellular

Expected discriminator:
- Improves only on Wi-Fi/cellular -> likely physical Ethernet/path issue.
- Persists across Ethernet and Wi-Fi/cellular -> likely charger comms stack/firmware issue.

---

## Escalation Rule

If repeated disconnects persist after latest firmware + full recommission + transport A/B testing,
treat as charger-side fault and progress replacement.

---

## Related Docs

- [OCPP Protocol](../patterns/ocpp_protocol.md)
- [Hardware Faults](../patterns/hardware_faults.md)
- [Firmware Bugs](../reference/firmware_bugs.md)
- [Learning History](../development/learning_history.md)
