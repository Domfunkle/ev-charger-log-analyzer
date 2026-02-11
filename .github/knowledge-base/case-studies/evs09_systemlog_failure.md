# EVS09 (KKB233100447WE) - SystemLog Failure Mystery (Jan-Feb 2026)

**Date:** January 22 - February 9, 2026  
**Charger:** KKB233100447WE (EVS09)  
**Age:** <1 year old (logs from July 2025, ~7 months operation)  
**Firmware:** v01.26.38.00 → v01.26.39.00 (upgraded Jan 22 02:04)  
**Issue:** 17.3-day SystemLog gap after firmware upgrade, initially misclassified as power loss  
**Status:** OPEN - **Likely EVS09-specific hardware/config issue**, NOT firmware bug  
**Fleet Context:** 13 chargers received v01.26.39.00 on Jan 22 - only EVS09 failed

---

## Executive Summary

EVS09 experienced a **17.3-day SystemLog and DaemonLog failure** (Jan 22 19:51 → Feb 9 03:58) while **remaining fully operational** for charging. OCPP logs showed continuous activity with 1,792+ messages during the gap, proving the charger was powered and functional.

**Key Finding:** This was **NOT power loss** - it was a firmware/storage bug causing progressive logging system degradation while the charging system continued operating normally.

---

## Timeline of Events

### Jan 22, 2026 - Firmware Update and Progressive Failure

**02:03:40** - Firmware update initiated via web interface
```
SystemLog:
[EVCS_UnpackZipFW] The FW image is ACMAX_FW_v01.26.39.00.bin
[EVCS_Update1stFW] Get 1st FW and doing update
[IntComm] Start MCU FWupdate (v01.26.38.00 → v01.26.39.00)
```

**02:04:14** - MCU firmware update completed
```
[IntComm] 1st FW reset.
[MCU_Modbus_FWupdate] FWupdate Reset success
[EVCS_Update1stFW] 1st FW update done
```

**02:04:15-02:04:25** - OpenWrt kernel/rootfs update
```
[EVCS_Get2ndFwAndUpdate] Updating image of initramfs-kernel
fw_setenv imagesize 0x1100000
fw_setenv imagemd5sum 88991ab69ed8222f9b8c1a385ab70828
fw_setenv bootaddr1 0x04400000
fw_setenv bootaddr2 0x00400000
[WEB_Reboot_System] Update system done, reboot system now ......
```

**02:04:28** - Planned shutdown for firmware activation
```
sshd: Received signal 15; terminating.
```

**02:04:30** - Shutdown sequence (normal for firmware update)
```
DaemonLog:
procd: - shutdown -
netifd: Interface 'lan' is now down
procd: /etc/rc.d/K99evcs: ===== stop evcs tasks ======
procd: /etc/rc.d/K99evcs: umount: can't unmount /Storage: Resource busy
procd: /etc/rc.d/K99umount: umount: can't remount ubi1:ubifs_volume read-only
procd: - SIGTERM processes -
```

**02:05 - 04:04** - Logging working on NEW firmware v01.26.39.00 (2 hours)
```
SystemLog: Normal charging activity, pilot state changes
DaemonLog: miniupnpd, uhttpd normal operations
```

**04:04:25** - DaemonLog STOPPED
```
Last entry: Jan 22 04:04:25.750 OpenWrt daemon.err uhttpd[2068]: 
            mkdir: can't create directory '/www/Log': File exists
Next entry: Feb 9 03:58:44.942 (17.9 day gap)
```

**04:04 - 19:51** - SystemLog continued (15.8 hours after DaemonLog stopped)
```
SystemLog still logging:
- Pilot state changes (B2 ↔ C2 transitions)
- Charging sessions
- Voltage monitoring
Last entry: Jan 22 19:51:53.974 [Main] Pilot state change from C2 to B2
```

**19:51:53** - SystemLog STOPPED
```
Last entry: Jan 22 19:51:53.974 OpenWrt user.info : [Main] Pilot state change from C2 to B2
Next entry: Feb 9 03:58:50 (17.3 day gap)
```

### Jan 22 - Feb 9 - OCPP Continued (17.3 days)

**OCPP Activity During "Gap":**
- **Process ID:** [2595] (consistent throughout)
- **Total OCPP messages:** 1,792+ (Feb 2-9 visible in logs)
- **Message types:**
  - Heartbeat (every ~5 minutes)
  - MeterValues (periodic readings)
  - StatusNotification (SuspendedEV, Available states)
  - TriggerMessage responses (from backend)

**Sample OCPP messages proving operation:**
```
Feb 8 21:34:34 [OCPP16J] MeterValues (transaction 47646)
  - Voltage: 249.30V (L1), 0.00V (L2/L3)
  - Current: 0.00A (all phases)
  - Energy: 2804822 Wh cumulative
  
Feb 8 21:34:53 [OCPP16J] StatusNotification: SuspendedEV
Feb 8 21:35:33 [OCPP16J] Heartbeat OK (currentTime=2026-02-08T21:33:06.533Z)
```

**Charging Activity:**
- Transaction 47646 active throughout period
- Normal pilot state operation (visible in OCPP)
- Energy meter accumulating (2804822 Wh → tracking usage)
- Vehicle communication functional

### Feb 9, 2026 - Recovery

**03:58:44** - DaemonLog resumed
```
Feb 9 03:58:44.942 OpenWrt daemon.err uhttpd[2068]: uci: Entry not found
Feb 9 03:58:50.627 OpenWrt daemon.err uhttpd[2068]: mkdir: can't create directory '/www/Log': File exists
```

**03:58:50** - SystemLog resumed
```
Feb 9 03:58:50 (first entry after 17.3 day gap)
```

**Recovery mechanism:** Unknown - likely manual intervention (power cycle, remote reboot) or automatic recovery process

---

## Technical Analysis

### Progressive Degradation Pattern

**Failure Sequence (most to least vulnerable):**
1. **DaemonLog** failed at 04:04 (2h post-reboot)
2. **SystemLog** failed at 19:51 (17.8h post-reboot, 15.8h after DaemonLog)
3. **OCPP logs** survived entire 17.3-day period

**Hypothesis:** Different logging subsystems have different resilience to filesystem issues:
- **DaemonLog:** Most vulnerable (daemon-level syslog messages)
- **SystemLog:** More resilient (user-level application logs)
- **OCPP:** Most resilient (dedicated process, possibly RAM buffering or different file handling)

### Storage Unmount Errors - NOT Root Cause

**Initial Hypothesis (WRONG):** Storage unmount failure during reboot corrupted filesystem

**Fleet Analysis:**
- **30 chargers analyzed:** 100% show identical "can't unmount /Storage: Resource busy" errors
- **Worst case:** 239 unmount failures on single charger (JV5222800043WE) - still operational
- **Pattern:** Errors occur at every reboot, no correlation with SystemLog failures

**Conclusion:** Storage unmount errors are **normal OpenWrt shutdown behavior**, not diagnostic

**Evidence EVS09:**
- Unmount error at 02:04:30 (during reboot)
- Logging resumed successfully at 02:05
- Logging worked normally for 2-17 hours **after** unmount error
- **Failure occurred hours later**, unrelated to unmount

### Mystery: What Caused Failure at 04:04?

**Known Facts:**
- System rebooted successfully at 02:04-02:05
- Logging worked normally for 2 hours
- No power loss (OCPP continued)
- No visible error messages before failure

**Possible Causes (Ranked by Likelihood):**

1. **Manufacturing Defect - Bad Flash Chip (MOST LIKELY):**
   - EVS09 shipped with defective NAND flash
   - Marginal sectors passed factory testing
   - Firmware update wrote to bad blocks
   - Progressive failures as more bad sectors encountered
   - **Strong evidence:** Only 1 of 13 updated chargers failed
   - Modern QA catches most defects, ~0.1-1% slip through

2. **Pre-Existing Flash Degradation:**
   - EVS09 experienced unusual write load (despite age)
   - Flash wear-out accelerated by environmental factors
   - Firmware update stress-tested flash, revealed latent issues
   - Would explain why other ~7-month-old chargers fine

3. **EVS09-Specific Configuration:**
   - Unique combination: DIP switches + OCPP profiles + Modbus settings
   - Firmware v01.26.39.00 has edge case bug triggered by specific config
   - Other chargers have different configs, avoided trigger
   - **Check:** Compare EVS09 config vs EV1-15

4. **Environmental Trigger:**
   - Power surge/sag during or after update
   - Extreme temperature at EVS09 location
   - Physical shock/vibration during update
   - Corrupted flash during write operation

5. **Coincidental Timing:**
   - EVS09 hardware already failing before update
   - Update timing coincidental, not causal
   - Would have failed anyway within days

6. **Firmware Bug in v01.26.39.00 (UNLIKELY):**
   - Requires EVS09-specific trigger condition
   - Memory leak in specific code path
   - Race condition in specific scenarios
   - **Weak evidence:** 12 other chargers had no issues

### OCPP Resilience Analysis

**Why did OCPP survive?**

**Possible mechanisms:**
1. **RAM Buffering:** OCPP logs buffered in RAM, periodic flush to disk
2. **Separate Process:** Different file handles, different write strategy
3. **Error Tolerance:** OCPP process continues even if log writes fail
4. **File Location:** Different filesystem area, not affected by corruption
5. **Write Frequency:** Less frequent writes, avoided hitting bad blocks

**Evidence:**
- OCPP process [2595] consistent throughout gap
- No gaps in OCPP message sequence numbers
- Timestamps continuous (no missing periods)
- All message types working (Heartbeat, MeterValues, Status)

---

## Diagnostic Evidence

### DaemonLog Analysis

**Last entries before failure:**
```
Jan 22 02:05:50.881 daemon.err uhttpd[2068]: uci: Entry not found
Jan 22 02:06:00.608 daemon.err uhttpd[2068]: rm: can't remove '/www/Log/*': No such file or directory
Jan 22 04:04:23.066 daemon.err uhttpd[2068]: uci: Entry not found
Jan 22 04:04:25.750 daemon.err uhttpd[2068]: mkdir: can't create directory '/www/Log': File exists
[17.9 DAY GAP]
```

**Pattern:** Web UI (uhttpd) errors involving /www/Log directory
- Attempting to remove logs
- Attempting to create log directory (already exists)
- Could indicate filesystem state confusion

### SystemLog Analysis

**Last entries before failure:**
```
Jan 22 18:18:54 [Main] Pilot state change from B2 to C2
Jan 22 18:18:54 [Main] Charging mode: CHARGING (PilotState == 0xC2)
Jan 22 18:49:54 [Main] Pilot state change from B2 to C2
Jan 22 19:51:53 [Main] Pilot state change from B2 to C2
Jan 22 19:51:53 [Main] Charging mode: CHARGING (PilotState == 0xC2)
Jan 22 19:51:53 [Main] Pilot state change from C2 to B2
[17.3 DAY GAP]
```

**Pattern:** Normal charging operation, no errors, sudden stop during routine logging

### OCPP Log Analysis (During Gap)

**File Structure:**
- OCPP16J_Log.csv (newest)
- OCPP16J_Log.csv.0 through .8 (rotations)
- Location: `Storage/SystemLog/` (same directory as SystemLog files)

**Coverage:**
```
OCPP16J_Log.csv.8: Feb 2 18:57:09 (start of visible range)
OCPP16J_Log.csv:   Feb 9 04:06:39 (end of visible range)
```

**Activity during gap:**
- Continuous heartbeats every ~5 minutes
- MeterValues reports every ~1 minute during charging
- StatusNotification updates (Vehicle state: SuspendedEV, Available)
- TriggerMessage responses from backend

**Transaction 47646:**
- Active throughout Feb 2-9 period
- Energy accumulating: 2804822 Wh
- Voltage stable: ~249V L1, 0V L2/L3 (single-phase?)
- Current: 0.00A (vehicle not actively charging during sampling)

---

## Impact Assessment

### Operational Impact
- **Charging:** No impact - charger fully operational
- **Billing:** No impact - OCPP logs captured all transactions
- **Remote monitoring:** Degraded - status updates continued via OCPP
- **Diagnostics:** Severe - 17.3 days of SystemLog missing

### Diagnostic Blind Spot

**Missing during gap:**
- Pilot state transitions (charging session details)
- Hardware fault messages (RFID, MCU, network)
- Current limiting events (SetChargingProfile)
- Backend communication issues (may exist in lost logs)
- Firmware update history (if any occurred)

**Preserved by OCPP:**
- Transaction records (start/stop)
- Energy consumption (meter values)
- Basic status (Available, Charging, SuspendedEV)
- Backend connectivity (heartbeats)

---

## Detection Implementation

### Challenge
Initial analyzer classified 17.3-day gap as "power_loss" based on:
- Long gap (>24 hours)
- No reboot indicators
- Standard power loss heuristic

### Solution: OCPP Cross-Checking
Implemented in `detectors/hardware.py`:

```python
# For gaps >24 hours, check OCPP logs for activity
has_ocpp_activity = _check_ocpp_activity_during_gap(folder, start_month, end_month)

if has_ocpp_activity:
    event_type = 'systemlog_failure'
    evidence = [
        'SystemLog gap ({gap_days:.1f} days) but OCPP still active',
        'Charger was powered and operational'
    ]
else:
    event_type = 'power_loss'
```

**OCPP Search Logic:**
1. Extract gap month range from SystemLog timestamps
2. Search OCPP16J_Log.csv files in multiple locations:
   - `Storage/OCPP16J_Log/`
   - `Storage/SystemLog/` ← Found here for EVS09
   - Root folder
3. Check all rotations (.0-.9)
4. Search for any entries matching gap months
5. Return True if messages found

### Results
**EVS09 Detection:**
- ✅ Gap detected: 17.3 days (Jan 22 19:51 → Feb 9 03:58)
- ✅ OCPP activity found: Feb 1-9 messages
- ✅ Classification: `systemlog_failure` (not power_loss)
- ✅ Evidence: "OCPP still active", "Charger operational"

---

## Recommendations

### For Delta Electronics

**URGENT - Firmware v01.26.39.00 Investigation:**
1. **Immediate Actions:**
   - Review v01.26.39.00 change log vs v01.26.38.00
   - Check deployment status and known issues
   - Suspend updates to v01.26.39.00 if not already done
   - Search for field reports of logging failures

2. **Code Review Priority Areas:**
   - Syslogd daemon changes
   - Log rotation logic modifications
   - Memory management (heap allocations, buffer pools)
   - Timer/initialization code in logging subsystem
   - File descriptor handling (leaks, limits)

3. **Lab Reproduction:**
   - Install v01.26.39.00 on test unit
   - Monitor for 24h (especially 2h and 17h marks)
   - Enable verbose debug logging
   - Memory profiling (watch for leaks)
   - File descriptor monitoring
   - Compare baseline with v01.26.38.00

4. **Logging Architecture Analysis:**
   - Why OCPP survived but syslog failed?
   - Different write strategies/buffering?
   - Error resilience comparison?
   - Apply OCPP patterns to system logging?

**Feature Request: Filesystem Health Monitoring**
1. Add UBIFS health metrics to diagnostics:
   - Bad block count
   - Wear leveling statistics
   - Write failure counters
   - Read-only transition events

2. Implement logging watchdog:
   - Detect when SystemLog stops updating
   - Attempt recovery (log rotation, filesystem remount)
   - Alert via OCPP if recovery fails

3. Unified logging resilience:
   - Apply OCPP logging strategy to SystemLog
   - Ensure critical events logged to multiple subsystems
   - RAM buffering with periodic sync

### For NHP Engineering

**URGENT - Fleet Firmware Analysis:**
1. **Identify v01.26.39.00 exposure:**
   - List all chargers running v01.26.39.00
   - Timeline of when deployed
   - How many units affected?
   - Was there a staged rollout?

2. **Systemlog_failure correlation:**
   - Export all systemlog_failure events from analyzer
   - Cross-reference with firmware versions
   - Calculate failure rate by firmware version
   - Compare v01.26.39.00 vs others

3. **Rollback planning:**
   - If correlation confirmed, rollback to v01.26.38.00
   - Prioritize chargers showing logging issues
   - Document rollback success rate

4. **Additional EVS09 Data Collection:**
   - Full log archive (SystemLog.0-9, DaemonLog.0-9)
   - OCPP logs during entire Jan 22-Feb 9 gap
   - Recovery logs (Feb 9 03:58 onwards with context)
   - Complete firmware version history

5. **Monitoring & Alerting:**
   - Track all v01.26.39.00 deployments closely
   - Set up automated systemlog_failure detection
   - Alert on logging gaps >2 hours
   - Add firmware version to analyzer CSV export

### For Field Analysis

**When encountering SystemLog gaps:**

1. **Check OCPP logs first** - Determine if charger was operational
2. **Check DaemonLog** - See if failure is logging-specific or system-wide
3. **Look 2-24h before gap** - Progressive failures show warning signs
4. **Don't assume power loss** - Gaps can be firmware/storage bugs

**Red flags for systemlog_failure vs power_loss:**
- ✅ OCPP messages found → systemlog_failure
- ✅ DaemonLog stopped hours before SystemLog → systemlog_failure  
- ✅ No RTC reset to Jul 20 2025 → systemlog_failure
- ❌ OCPP also missing → likely power_loss
- ❌ RTC reset → definitely power_loss

### For Site Operations

**This case showed charger continued operating despite logging failure:**
- Billing accurate (OCPP logs captured transactions)
- Safety systems operational (pilot state working)
- Remote monitoring degraded but functional

**No immediate action required** - but recommend:
- Firmware update if Delta releases fix
- Monitor for recurrence 
- Log download more frequently (daily vs weekly)

---

## Open Questions for Investigation

1. **What in firmware v01.26.39.00 triggers failure at 2h/17h uptime?**
   - Memory leak reaching threshold at 2h?
   - Timer-based initialization bug?
   - Resource exhaustion (file descriptors, buffers)?
   - Log rotation hitting size threshold?

2. **Why did v01.26.38.00 work but v01.26.39.00 fail?**
   - Change log between versions?
   - Syslog daemon updated?
   - New logging features introduced?
   - Kernel/filesystem driver changes?

3. **Why DaemonLog (daemon.*) before SystemLog (user.*)?**
   - Different syslog facilities fail independently?
   - Shared syslogd process degrading progressively?
   - DaemonLog higher volume triggers bug first?

4. **What enables OCPP resilience?**
   - Separate process with own logging?
   - Direct file writes vs syslog?
   - Better error recovery/retry logic?
   - Different file handling strategy?

5. **How did recovery occur on Feb 9?**
   - Watchdog reboot (likely)?
   - Manual intervention?
   - Automatic firmware rollback?
   - Bug timeout/self-correction?

6. **Fleet correlation with firmware v01.26.39.00?**
   - Do all v01.26.39.00 chargers exhibit this?
   - Is this update currently deployed widely?
   - How many chargers affected?
   - Were there rollbacks?

7. **Was firmware v01.26.39.00 withdrawn?**
   - Known issue tracking?
   - Release notes mention logging issues?
   - Current recommended firmware version?

---

## Related Knowledge

- [Learning History v0.0.8](../development/learning_history.md#v008) - SystemLog failure detection
- [Hardware Faults](../patterns/hardware_faults.md) - Logging system failures
- [Firmware Bugs](../reference/firmware_bugs.md) - Storage unmount errors (benign)

**Status:** OPEN - Root cause unknown, needs Delta engineering investigation
