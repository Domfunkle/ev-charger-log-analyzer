# KKB241600082WE - ChangeConfiguration Burst Pattern

**Case Date:** 2026-02-26 analysis session  
**Charger:** KKB241600082WE (EY-111B-216)  
**Firmware:** 01.26.29.00  
**Scope:** Correlation between `AC output OCP` and OCPP config storms

---

## Summary

Field logs showed repeated `AC output OCP` alarms alongside heavy backend/OCPP activity.  
Analysis confirmed a repeatable pattern:

1. Backend reconnect (`fail` → `success`)
2. Rapid `ChangeConfiguration` command burst
3. Dense `[OCPP16J][ConfigTable] Write Success` sequence
4. OCP events and `Faulted/EV0082` notifications in the same time window (for key incidents)

The burst pattern itself is broad (many reconnects), but **bursts near OCP** are a strong triage signal.

---

## Key Evidence (Feb 23 Cluster)

### SystemLog (UTC)

- `21:27:42.367` backend connection fail
- `21:27:43.646` backend connection success
- `21:27:43.646` onward repeated `ConfigTable Write Success`
- `21:27:50.578` `AC output OCP`
- `21:28:01.863` `AC output OCP`
- `21:28:12.655` `AC output OCP`

### OCPP16J_Log

Window shows:
- `RemoteStartTransaction` accepted
- `StartTransaction` accepted
- `SetChargingProfile` (`limit=6.000000`)
- `ClearChargingProfile`
- burst of `ChangeConfiguration` keys
- `StatusNotification` with `Faulted` / `EV0082`

---

## Burst Characteristics in This Bundle

- Total `ChangeConfiguration` commands: **6492**
- Unique keys: **29**
- Bursts detected (gap-based clustering): **235**
- Largest burst: **29** changes
- Bursts near backend reconnects: **224**
- Bursts near OCP windows: **1**

Interpretation:
- Frequent reconnect replay behavior exists across the log set.
- OCP-correlated burst windows are fewer and higher value for fault diagnosis.

---

## Operational Guidance

Use burst detection as **context/correlation**, not sole root cause.

Prioritize investigation when all are true:
- burst size is high (e.g., 20+ key changes), and
- burst overlaps reconnect window, and
- OCP/EV0082 appears in same ±45s incident window.

Cross-check with:
- DIP current limits (`SB1` / `MAXCurrent(0.1A)`)
- active smart-charging limits (`SetChargingProfile`)
- LMS/Modbus limits and fallback behavior

---

## Additional Field Learnings (2026-02-27)

### 1) ChangeConfiguration Storms: likely upstream replay policy

Field interpretation:
- EY/CSMS appears to replay broad key sets, including keys not necessarily relevant to AC MAX
- Charger may tolerate this traffic, but burst volume creates operational noise and may contribute to instability

Action for EY/CSMS:
- Confirm Delta AC MAX onboarding/profile support
- Use only required key allowlist
- Avoid reconnect-time full replay storms

### 2) OCP not always explained by EVLM profile timing

Observed behavior:
- OCP can appear before first EVLM profile is sent/applied
- Test charging around 12A still reported OCP in field feedback

Interpretation:
- Possible limit-path or sensing-path integrity issue
- Not sufficient to assume true vehicle overcurrent from OCP label alone

### 3) Modbus handling rule from field

If registers were altered:
- Restore known-good values once
- Do **not** write zero to "unused" registers as a reset shortcut
- After restore, avoid continuous write loops

### 4) Service-tech simplified plan (used in comms)

1. Stop EY config storms and validate key set relevance
2. Check Modbus write ownership (single owner, no zeroing)
3. Check site network stability (cables/ports/upstream drops)
4. Upgrade charger firmware (factory reset + recommission)
5. Upgrade EVLM firmware (no factory reset)

---

## Related Docs

- [OCPP Protocol](../patterns/ocpp_protocol.md)
- [Current Limiting](../patterns/current_limiting.md)
- [Hardware Faults](../patterns/hardware_faults.md)
- [Pattern Detection Guide](../development/pattern_detection.md)
