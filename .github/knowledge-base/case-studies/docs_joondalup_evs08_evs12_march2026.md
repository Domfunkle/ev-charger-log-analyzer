# DoCs Joondalup — EVS08 SystemLog Gap & EVS12 RCD Fault (March 2026)

**Date:** March 20, 2026 (log pull date)  
**Site:** DoCs Joondalup EV Charger Fleet (15x Delta AC MAX Smart)  
**Chargers:** KKB233100467WE (EVS08), KKB233100472WE (EVS12)  
**Firmware:** v01.26.39.00 (both units)  
**Status:** OPEN — EVS08 monitoring, EVS12 awaiting hardware service

---

## Background

DoCs Joondalup is a 15-charger Delta AC MAX Smart fleet. The site has had recurring issues:

- **EVS03** — ~20,000 backend disconnect/reconnects traced to a kinked ethernet cable (resolved by cable re-route/replacement recommendation, not recurred since EVLM disconnection)
- **EVS09** — Repeated SystemLog gaps on v01.26.37.00 and v01.26.39.00, unit physically replaced (Feb 2026). See [EVS09 SystemLog Failure](evs09_systemlog_failure.md)
- **EVS08** — MCU communication failure (Nov 27 2025, resolved by power cycle), then SystemLog gap (Feb 10–26 2026, post v01.26.39.00 upgrade)
- **EVS12** — RCD self-test failure (Mar 18 2026), permanent CP State F lockout

The OCPP backend (EVLM) was intentionally disconnected site-wide. All chargers operate in offline Plug-and-Charge mode. OCPP connection errors in logs for all units are expected and non-diagnostic.

---

## EVS08 — KKB233100467WE

### History

| Date | Event |
|---|---|
| Aug 2025 | Logs begin (v01.26.37.00) — clean, no gaps |
| Nov 27 2025 | MCU communication failure; Callum power cycles. Resolved. |
| Jan 22 2026 | Firmware updated to v01.26.39.00 (via fleet-wide update) |
| Jan 22–Feb 10 2026 | Post-update: clean logging, no MCU errors |
| Feb 10 2026 04:22:09 UTC | **SystemLog stops** (no `syslogd exiting` — unclean stop) |
| Feb 26 2026 00:48:36 UTC | Syslog resumes after reboot (RTC shows `Oct 15` falsely before MCU correction) |
| Mar 9 2026 | Callum's site visit — EVS08 found faulted, power cycled to recover |
| Mar 20 2026 | Logs pulled; post-gap analysis shows no further faults |

### SystemLog Gap Details

- **Last entry:** `Feb 10 04:22:09 OpenWrt user.info InfraMgmt[2465]: [Infra] Update Charging Volt from 239V to 243V`
- **Gap duration:** ~15.8 days (Feb 10 04:22 → Feb 26 00:48 UTC)
- **Recovery:** Reboot — `syslogd started: BusyBox v1.28.4` at Oct 15 false timestamp, corrected by MCU to Feb 26 00:48:36
- **syslogd exiting logged:** ❌ No — daemon stopped without clean shutdown (unclean crash/kill)
- **OCPP activity during gap:** OCPP log continues (expected — EVLM disconnected, so all entries are connection errors; confirms charger was powered)
- **Charging during gap:** Cannot confirm from SystemLog (logging was down), but charger recovered and resumed normal operation

### Post-Gap Findings (Feb 26 – Mar 20)

- ✅ Zero MCU communication errors
- ✅ Zero backend connection failures (EVLM offline, charger in Plug-and-Charge)
- ✅ Normal charging sessions recorded
- 3× `user.err` entries — benign model/voltage config mismatch at boot (v01.26.39.00 quirk)

### Pre-Gap Post-Update Findings (Jan 22 – Feb 10)

- ✅ Zero MCU communication errors (Nov 27 fault did not recur)
- 3× backend connection fails (Jan 23, Feb 9, Feb 10) — normal, EVLM was still being decommissioned
- 1× `user.err` — same benign boot entry

### Comparison with EVS09

| Factor | EVS09 (v01.26.39.00 gap) | EVS08 |
|---|---|---|
| Firmware | v01.26.39.00 | v01.26.39.00 |
| Gap duration | ~17.3 days | ~15.8 days |
| syslogd exiting logged | Unknown | ❌ No |
| Recovery | Unknown (manual?) | Reboot (syslogd restart visible) |
| Prior history on v01.26.37.00 | Gap on Dec 23 2025 | ✅ Clean — no gaps |

EVS09 showed a gap on **both** v01.26.37.00 and v01.26.39.00. EVS08 showed a gap **only** on v01.26.39.00, with clean logs on v01.26.37.00. This suggests the bug may be:
- More likely to trigger on v01.26.39.00, or
- Hardware-dependent (EVS09 had underlying flash degradation that made it susceptible earlier)

### Key UTC Timestamps for Delta Investigation

```
Last SystemLog entry before gap:
  Feb 10 2026 04:22:09 UTC
  [Infra] Update Charging Volt from 239V to 243V

syslogd exiting: NOT LOGGED (unclean stop)

syslog resumption (false RTC, then MCU-corrected):
  Oct 15 04:39:09 UTC (false) → corrected to Feb 26 00:48:36 UTC
```

---

## EVS12 — KKB233100472WE

### Summary

EVS12 suffered a **hardware RCD self-test failure** on March 18 2026 at 04:46:55 UTC, immediately entering CP State F (permanent fault lockout). The charger was fully operational up to this point with a successful charging session ending 47 minutes earlier.

### EventLog Record

```
2026.03.18 04:46:55 — EV0086 (RCD self-test failure)
```

### SystemLog Sequence

```
Mar 18 03:28:10  Start Charging — NonAuthorizedTag (Plug-and-Charge)
Mar 18 03:59:47  Stop Charging — 31 min 37 sec, 3,639 Wh (EV unplugged)

Mar 18 04:46:47  [Auth4ChgMgmt] Start charging OK (Plug-and-Charge policy)
Mar 18 04:46:48  [Main] Start Charging: 2026.03.18-04:46:48-NonAuthorizedTag
Mar 18 04:46:48  [IntComm] Send Remote Start Charging to MCU
Mar 18 04:46:55  user.alert: [IntComm] RCD self-test        ← RCD test fires
Mar 18 04:46:55  [Main] Pilot state change from B1 to B1
Mar 18 04:46:55  user.alert: [CGI] RCD self-test
Mar 18 04:46:55  [Main] Pilot state change from B1 to F    ← FAULT STATE
```

No further Pilot state changes logged for the remaining 150+ hours until log pull on Mar 20.

### Root Cause

**Event code EV0086 = RCD self-test failure.** The Delta AC MAX performs periodic RCD self-tests per IEC 62955. On failure, the charger transitions to CP State F and locks out charging. This is a safety-critical function — it cannot be bypassed via software/configuration.

The RCD assembly either:
1. Failed to trip correctly under the test current, or
2. Has a fault in the test circuit itself (relay, test signal path)

### Firmware and History

- Firmware: v01.26.39.00 (upgraded Jan 22 2026)
- No prior RCD events in SystemLog history (Aug 2025 – Mar 2026)
- No MCU communication errors throughout history
- Total energy delivered: ~352 kWh (Jan 22 – Mar 18, offline Plug-and-Charge)
- 2× reboots on Feb 26 (~36 min apart) — possibly watchdog or attempted OTA; no further context logged

### Recovery

**EVS12 will NOT self-recover.** CP State F is permanent until hardware is inspected/replaced:
- A factory reset may allow the charger to attempt operation, but if the RCD hardware is faulty the test will fail again
- Physical inspection or replacement of the RCD module is required
- This is a warranty/service call item

---

## Site-Level Observations

### Why Is This Site Having More Issues Than Others?

Based on full log history:

1. **EVS03** — Kinked ethernet cable → ~20,000 backend disconnects. Physical cause, not charger hardware.
2. **EVS09** — SystemLog gap (twice) → replaced. Likely hardware flash degradation or firmware interaction.
3. **EVS08** — MCU fault (Nov 2025) + SystemLog gap (Feb 2026). Same firmware bug pattern as EVS09.
4. **EVS12** — RCD self-test failure (Mar 2026). Independent hardware fault.

The site does not appear to have a single systemic cause — rather, a combination of:
- Physical infrastructure issues (cabling, EVS03)
- A firmware-level logging bug affecting at least two units (EVS08, EVS09)
- A hardware failure on EVS12 (unrelated to the logging issue)

### Recommendations

**EVS08:**
- Continue monitoring — no immediate action required
- If SystemLog gap recurs, consider replacing the unit
- Raise the syslog gap pattern with Delta as a firmware defect (two independent units, same pattern, same firmware)

**EVS12:**
- Raise a service call for hardware inspection/RCD replacement
- Do not attempt to return to service without physical inspection

**Delta Escalation:**
- Two units (KKB233100447WE and KKB233100467WE) have exhibited identical ~16-day silent SystemLog gaps on v01.26.39.00
- Key diagnostic: `syslogd exiting` is NOT logged before the gap — unclean daemon stop
- OCPP log continues during gap (confirms charger powered and partially operational)
- EVS09 also showed a gap on prior firmware v01.26.37.00 — may not be version-specific

---

## Related Knowledge

- [EVS09 SystemLog Failure](evs09_systemlog_failure.md) — First instance of syslog gap pattern
- [EVS09 Replacement Misconfiguration](evs09_replacement_misconfiguration.md) — Post-replacement issues
- [Hardware Faults](../patterns/hardware_faults.md) — RCD, MCU, logging failures
- [Error Codes](../reference/error_codes.md) — EV0086 (RCD self-test failure)
- [Learning History v0.0.17](../development/learning_history.md#v0017)

---

**Last Updated:** 2026-03-20  
**Lines:** ~190
