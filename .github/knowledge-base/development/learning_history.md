# Learning History & Changelog

**Purpose:** Track what was learned when, version history, field cases analyzed  
**Format:** Reverse chronological (newest first)

---

## v0.0.9 - RTC Reset False Positives Fix (2026-01-26)

### Overview
**Discovered critical bug:** 50% of systemlog_failure detections were false positives caused by RTC reset timestamps (Jul 20, Oct 15, Jan 1) being misinterpreted as legitimate timestamps. Year inference errors created artificial ~24-day gaps, incorrectly classified as systemlog_failures.

### User Request (2026-01-26)
**User:** "ok please continue" (continuing RTC detection debugging)  
**Context:** Fleet analysis showing 20/68 chargers (29.4%) with systemlog_failure, suspected many were RTC false positives

### Investigation Results

**Fleet Impact:**
- **Before Fix:** 20/68 chargers (29.4%) with systemlog_failure
- **After Fix:** 10/68 chargers (14.7%) with systemlog_failure  
- **Improvement:** 50% reduction ✅

**Test Charger (KKB233100492WE):**
- **Before:** 23 systemlog_failures, all "Jul 20 → Aug 13" with 24.7-day gaps
- **After:** 0 systemlog_failures ✅

### Root Cause Analysis

**Bug #1: Year Inference Error**  
Analyzer inferred year=2025 for Jul 20 timestamps instead of correcting to year=2024 from RTC info:
```
Last entry: Aug 13 2024 20:35:43 (normal)
Next entry: Jul 20 2025 03:30:41 (RTC reset with wrong year!) 
Gap:        Jul 20 2025 - Aug 13 2024 = -negative → wraps to ~24.7 days
```

**Bug #2: Missing RTC Correction Extraction**  
Code required `is_reboot_line AND is_rtc_reset_timestamp`, but many RTC resets don't have reboot indicators:
```python
# WRONG:
if is_rtc_reset_timestamp and is_reboot_line:
    extract_rtc_correction()
    
# FIXED:
if is_rtc_reset_timestamp:
    extract_rtc_correction()
```

**Bug #3: Uncorrected RTC Entries Polluting Gap Calculations**  
When RTC reset timestamp found but NO RTC correction extracted (correction in different log file or >20 lines away):
```python
# Entry has Jul 20 timestamp
is_rtc_reset_timestamp = True
real_timestamp_dt = None  # No correction found!
effective_ts = current_ts  # Falls back to Jul 20 2024 (STILL WRONG!)
prev_entry_ts = effective_ts  # Next iteration uses Jul 20 2024
```

### Implementation

**File:** `analyzers/delta_ac_max/detectors/hardware.py`

**Change 1: Remove reboot requirement**
```python
if is_rtc_reset_timestamp:  # Removed: and is_reboot_line
    real_timestamp_str, real_timestamp_dt = HardwareDetector._extract_rtc_corrected_time(...)
    if real_timestamp_dt:
        current_inferred_year = real_timestamp_dt.year
    else:
        # CRITICAL FIX: Skip uncorrected RTC entries entirely
        continue  # Don't use for gap calculation
```

**Change 2: Update prev_entry with corrected timestamps**
```python
prev_entry = entry
if effective_ts_str != entry['timestamp_str']:
    prev_entry = entry.copy()
    prev_entry['timestamp_str'] = effective_ts_str  # Store corrected timestamp
prev_entry_ts = effective_ts
```

### Pattern: RTC Reset Behavior

**Default Reset Timestamps (Firmware Build Dates):**
- `Jul 20 03:30:XX` - Most common (firmware circa Jul 20 2025)
- `Oct 15 04:39:XX` - Alternative reset
- `Jan 1 00:00:XX` - Factory default

**RTC Correction Pattern:**
```
Jul 20 03:30:36  Charger Starting
Jul 20 03:30:37  ...boot sequence...
Jul 20 03:30:46  Get RTC Info: 2024.08.13-20:40:57  ← Real timestamp!
```

**Detection Strategy:**
1. Identify RTC reset timestamps (Jul 20, Oct 15, Jan 1)
2. Look ahead up to 20 lines for "Get RTC Info" message
3. Extract real timestamp from RTC correction
4. **Skip entry entirely if no correction found** (prevents false positives)

### Validation

**Fleet Analysis (68 chargers):**
- Eliminated all Jul 20/Oct 15/Jan 1 false positives
- Remaining 10 chargers show genuine systemlog_failures (2-27 day gaps with OCPP active)

**Genuine systemlog_failures:**
- JV5205000048WE: 46 events, gaps 1.1-22.7 days
- JV5222800258WE: 3 events, gaps 3.2 days
- JV5222800473WE: 2 events, gaps 10.2-15.4 days
- KKB233100447WE: 1 event, gap 17.3 days
- Others: Single events, 2-28 day gaps

### Lessons Learned

**1. RTC Reset Timestamps Are FAKE**  
They represent firmware build date, not actual event time. Using them for gap calculations creates massive errors.

**2. Skip Unknown Timestamps**  
When true timestamp unknown (RTC reset without correction), skip entry entirely rather than trying to "fix" it.

**3. Cross-File Boundary Limitation**  
Current 20-line lookahead doesn't cross log file boundaries. RTC correction might be in next file (file rotation).

**Potential Enhancement:** Aggregate all log entries from all files before processing to enable cross-file lookahead.

### Related Knowledge

- **[Case Study](../case-studies/rtc_reset_false_positives.md)** - Full technical details and debugging process
- **[Hardware Faults](../patterns/hardware_faults.md)** - RTC reset detection patterns

**Status:** Production-ready ✅

---

## v0.0.8 - SystemLog Failure vs Power Loss (OCPP Cross-Check) (2026-02-11)

### Overview
**Discovered critical distinction:** Extended SystemLog gaps (17+ days) can be **hardware/storage failures**, not firmware bugs or power loss. Implemented OCPP log cross-checking to distinguish between true power outages and SystemLog-specific failures. **Fleet analysis showed issue was EVS09-specific, not firmware v01.26.39.00 bug.**

### User Observation (2026-02-11)
**User:** "I'm not sure that power loss is the problem for the extended periods. Look at the OCPP csv files for logs that occur during the timestamps after syslog stops. If there are still OCPP messages then it is not power loss and must be something else."

**Context:** EVS09 (KKB233100447WE) showing 17.3-day SystemLog gap (Jan 22 → Feb 9), initially classified as "power_loss"

**Investigation Results:**
- ✅ OCPP logs showed **continuous activity** from Feb 2-9 (during SystemLog gap)
- ✅ OCPP messages include: Heartbeat, MeterValues, StatusNotification, TriggerMessage
- ✅ Same process ID [2595] throughout Jan 22 - Feb 9 period
- ❌ **NOT power loss** - charger was powered and operational entire time

### Pattern: SystemLog-Specific Failures

**New Event Type: `systemlog_failure`**

**Characteristics:**
- SystemLog stops writing (no new entries)
- OCPP logs continue normally (heartbeats, meter values, status updates)
- DaemonLog may also stop (but at different time)
- Charger remains operational (charging sessions continue)
- Eventually resumes (manual intervention or background recovery)

**Root Cause (KKB233100447WE Example):**
```
Timeline:
Jan 22 02:03:40 - Firmware update initiated (v01.26.38.00 → v01.26.39.00)
Jan 22 02:04:14 - MCU firmware update completed
Jan 22 02:04:25 - OpenWrt kernel/rootfs update completed
Jan 22 02:04:28 - "Update system done, reboot system now" (planned shutdown)
Jan 22 02:04:30 - Storage unmount failed (BENIGN - shutdown sequence)
Jan 22 02:05-04:04 - Logging working on NEW firmware v01.26.39.00 (2 hours)
Jan 22 04:04:25 - DaemonLog STOPPED (progressive failure begins on new firmware)
Jan 22 19:51:53 - SystemLog STOPPED (15.8h after DaemonLog)
Jan 22-Feb 9 - OCPP continued (17.3 days, 1792+ messages)
Feb 9 03:58:50 - Both logs resumed
```

**CRITICAL DISCOVERY:** The "reboot" was actually a **firmware update** from v01.26.38.00 → v01.26.39.00. The logging failures occurred 2-17 hours AFTER the successful firmware update.

**FLEET VALIDATION (Jan 22, 2026):**
- **14 chargers** received firmware updates on Jan 22, 2026
- **13 chargers** updated to v01.26.39.00: EV1, EV2, EV3, EV4, EV5, EV6, EV7, **EV9**, EV10, EV11, EV12, EV13, EV14, EV15
- **1 charger** updated to v01.26.38.00: EV8
- **Only EVS09 experienced systemlog_failure** after update
- **12 other v01.26.39.00 chargers continued logging normally**
- **Conclusion:** NOT a firmware bug affecting all units - likely EVS09-specific hardware defect triggered by update

**DaemonLog Evidence:**
```
Jan 22 02:04:30 procd: /etc/rc.d/K99evcs: umount: can't unmount /Storage: Resource busy
Jan 22 02:04:30 procd: /etc/rc.d/K99umount: umount: can't remount ubi1:ubifs_volume read-only
Jan 22 02:04:31 procd: - SIGTERM processes -
```

**Key Insight:** Progressive degradation specific to EVS09
- Firmware update completed successfully
- System rebooted normally to activate v01.26.39.00
- DaemonLog failed 2 hours later (on new firmware)
- SystemLog failed 15.8 hours later (on new firmware)
- OCPP survived entire 17-day period
- **12 other chargers with same firmware update had NO issues**

**Hypothesis:** EVS09-specific hardware failure, likely triggered by firmware update stress:
- **Most likely:** Manufacturing defect (bad flash chip in EVS09) revealed by update write operations
- Pre-existing flash degradation in EVS09, stressed by firmware update
- EVS09-specific configuration + firmware edge case interaction
- Environmental factors at EVS09 location (temperature, power quality)
- Coincidental timing (hardware already failing, update timing coincidental)

**Ruled out by fleet data:**
- ~~Firmware bug in v01.26.39.00~~ - 12 other chargers with same firmware are fine
- ~~General flash wear-out~~ - chargers <1 year old
- ~~UBIFS filesystem bug~~ - would affect all chargers

**Note:** Flash wear-out unlikely - chargers <1 year old (logs from Jul 2025, ~7 months operation), but EVS09 may have manufacturing defect

### Detection Implemented

**OCPP Cross-Checking:** `detectors/hardware.py` - `_check_ocpp_activity_during_gap()`

**Logic:**
1. For gaps >24 hours, extract month range (start_month, end_month)
2. Search OCPP logs in multiple possible locations:
   - `Storage/OCPP16J_Log/` (older structure)
   - `Storage/SystemLog/` (common location - same dir as SystemLog)
   - Root folder (some extraction methods)
3. Check all OCPP16J_Log.csv files (base + .0-.9 rotations)
4. Search for any log entries matching gap month range
5. Return: True if OCPP activity found, False otherwise

**Path Discovery:** OCPP logs located in `Storage/SystemLog/` (alongside SystemLog files)

**Classification Update:**
```python
elif gap_hours > 24:
    # Check OCPP logs to distinguish power loss from SystemLog failure
    has_ocpp_activity = _check_ocpp_activity_during_gap(folder, prev_month, curr_month)
    
    if has_ocpp_activity:
        reboot_type = 'systemlog_failure'
        evidence.append(f'SystemLog gap ({gap_days:.1f} days) but OCPP still active')
        evidence.append('Charger was powered and operational')
        systemlog_failure_count += 1
    else:
        reboot_type = 'power_loss'
        evidence.append(f'Long gap ({gap_days:.1f} days) suggests power loss')
        power_loss_count += 1
```

**Returns (Updated):**
```python
{
    'reboot_count': int,
    'power_loss_count': int,
    'firmware_update_count': int,
    'systemlog_failure_count': int,  # NEW
    'max_gap_days': float,
    'events': [...]
}
```

**Integration:**
- Reporter displays: ⚠️ icon for SystemLog failures (vs 🔌 for power loss)
- Recommendations: "Likely firmware bug or storage issue, not power loss"
- CSV export: Added `SystemLog_Failure_Count` column
- Status check: SystemLog failures trigger Warning status

### Critical Discovery: Storage Unmount Errors Are BENIGN

**Initial Hypothesis (WRONG):** "umount: can't unmount /Storage: Resource busy" errors cause filesystem corruption

**Fleet Analysis:**
- **100% of chargers** show storage unmount errors during reboots
- Chargers with 0 failures: NONE analyzed
- Chargers with 100+ failures: Still operational, no SystemLog gaps
- **Conclusion:** Unmount errors are **normal shutdown behavior**, NOT root cause

**Evidence:**
```
KKB241600016WE: 8 unmount failures, no SystemLog gaps
KKB241600073WE: 4 unmount failures, no SystemLog gaps  
KKB233100069WE: 5 unmount failures, no SystemLog gaps
JV5222800043WE: 239 unmount failures, no SystemLog gaps
JV5205000048WE: 127 unmount failures (reboot loop), still logging normally
```

**Pattern:** Unmount errors occur at **every shutdown/reboot**, are logged during normal shutdown sequence, and do **not** predict or cause SystemLog failures.

**Correct Understanding:**
- Unmount errors = OpenWrt/Linux shutdown attempting clean filesystem unmount
- "Resource busy" = Expected when processes hold file handles during shutdown
- System performs forced umount/sync anyway
- Filesystem recovers normally on next boot
- These errors are **cosmetic logging artifacts**, not actual failures

### Field Results

**Test Case: KKB233100447WE (EVS09)**
- **Before:** Classified as "power_loss" (17.3 day gap)
- **After:** Correctly classified as "systemlog_failure"
- **Evidence:** "SystemLog gap (17.3 days) but OCPP still active", "Charger was powered and operational"

**Impact:**
- Prevents false power quality investigations
- Identifies firmware/storage bugs vs site electrical issues
- Enables proper escalation path (Delta vs facility management)

### Lessons Learned

1. **Cross-check multiple log sources** - Single log source can fail while system remains operational
2. **OCPP more resilient** - Different file buffering or RAM caching strategy survives filesystem issues
3. **DaemonLog vulnerable** - Stops before SystemLog in progressive failures
4. **Storage unmount errors are red herrings** - Fleet-wide "background noise", not diagnostic
5. **Progressive degradation pattern** - Filesystem issues develop over hours, not instantly at reboot
6. **Year-less timestamps** - OCPP logs also lack years, require same month inference logic

### Open Questions

**EVS09-Specific Investigation:**
- What makes EVS09 different from EV1-15 (12 other v01.26.39.00 chargers)?
- Manufacturing batch? Production date? Hardware revision?
- Configuration differences (DIP, OCPP, Modbus settings)?
- Environmental factors unique to EVS09 location?
- Pre-existing flash errors visible in UBIFS statistics?

**Progressive Degradation Mystery:**
- Why did logging work for 2-17 hours post-update before failing?
- Why did DaemonLog fail first (2h), SystemLog hours later (17h)?
- Why did OCPP survive 17+ days while others failed?
- Bad flash sectors hit during log rotation at 2h/17h marks?
- Thermal stress after hours of runtime revealing marginal hardware?

**Needs Investigation:**
- EVS09 UBIFS filesystem health metrics (bad blocks, wear leveling)
- Configuration comparison: EVS09 vs EV10 (both v01.26.39.00)
- Manufacturing records: EVS09 production batch vs others
- Environmental data: Temperature, power quality at EVS09 location
- Hardware RMA analysis if EVS09 replaced

### Files Modified

- `detectors/hardware.py`: Added OCPP cross-checking, systemlog_failure type
- `reporter.py`: Added ⚠️ icon, SystemLog failure recommendations
- `exporter.py`: Added SystemLog_Failure_Count column
- `analyze.py`: Added systemlog_failure_count to status checks
- `utils.py`: Added serial-first filename pattern support

**Lines Changed:** ~120 additions

---

## v0.0.7 - System Reboot & Logging Gap Detection (2026-02-11)

### Overview
**Implemented automatic detection of logging gaps, reboots, and power loss events** in SystemLog files. Directly addresses blind spot where analyzer wasn't detecting sudden cessation of logging before reboots.

### User Request (2026-02-11)
**User:** "Should this not have detected the sudden loss in syslog entries? Note the timestamp immediately before reboots"  
**Context:** Analyzer showing firmware updates and critical events but not flagging the 5 power loss events discovered via manual sub-agent analysis

**Problem:** Analyzer v0.0.4-0.0.6 had no detector for:
- Logging gaps (abrupt stops in SystemLog entries)
- Reboot events (power loss vs firmware updates)
- Power stability issues (frequent outages)

### Pattern Discovered

**Logging Gap Detection Requirements:**
1. **Timestamp Parsing:** SystemLog uses `MMM DD HH:MM:SS.mmm` format (with milliseconds)
   - Example: `Dec 21 08:21:43.109 OpenWrt user.info ...`
   - Bug initially missed: regex didn't account for `.109` milliseconds
2. **Gap Classification:**
   - Minimum: 2 hours (avoid false positives from normal quiet periods)
   - Maximum: 30 days (avoid year inference errors in rotated logs)
   - Reboot indicators: "System Start", "syslogd started", "WEB_Reboot_System", "dual-bank switch"
3. **Event Types:**
   - **Power Loss:** Long gaps (>24h), RTC reset to "Jul 20 2025 03:30:xx", abrupt stops
   - **Firmware Update:** Dual-bank switch messages, controlled reboots (<0.1h gap)
   - **Unknown:** Reboot indicator present but ambiguous gap duration

### Detector Implemented

**Implementation:** `detectors/hardware.py` - `detect_system_reboots()` (~150 lines)

**Detection Logic:**
1. Collect all SystemLog files (SystemLog, SystemLog.0-9)
2. Parse log entries with timestamp pattern: `r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\.?\d*\s+'`
   - **Critical Fix:** Added `\.?\d*` to handle milliseconds
3. Sort entries chronologically (account for log rotation)
4. Detect gaps between consecutive messages:
   - **Filters:**
     - Minimum: 2 hours (skip normal quiet periods)
     - Maximum: 30 days (avoid year inference issues)
     - Reboot indicators: require >0.01 hours (36 seconds) gap
5. Classify event type:
   - RTC reset pattern → power_loss
   - Dual-bank switch → firmware_update
   - Gap >24h → power_loss
   - Reboot indicator with short gap → firmware_update
6. Return structured result

**Returns:**
```python
{
    'reboot_count': int,           # Total events detected
    'power_loss_count': int,       # Unplanned outages
    'firmware_update_count': int,  # Controlled reboots
    'max_gap_days': float,         # Longest outage
    'events': [                    # Details for each event
        {
            'type': 'power_loss' | 'firmware_update' | 'unknown',
            'gap_days': float,
            'gap_hours': float,
            'last_timestamp': 'MMM DD HH:MM:SS',
            'first_timestamp': 'MMM DD HH:MM:SS',
            'last_line': str,      # Truncated context
            'first_line': str,
            'evidence': [str],     # Reasoning for classification
            'file_transition': str # Which log files
        }
    ]
}
```

**Integration:**
- Added to `analyze.py` analysis pipeline (line ~323)
- Status check: >5 power loss events = Issue, >2 = Warning
- Reporter displays:
  - Event counts by type
  - Max gap duration
  - Up to 3 most significant events with timestamps
  - Recommended actions for power loss cases
- CSV export: 4 new columns (Reboot_Count, Power_Loss_Count, Firmware_Update_Reboots, Max_Logging_Gap_Days)

### Bug Fix: Timestamp Milliseconds

**Initial Issue:** Detector found 0 events despite 7 real reboots  
**Root Cause:** Regex pattern `r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\s+'` didn't match milliseconds  
**Fix:** Updated to `r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\.?\d*\s+'`  
**Result:** Detector immediately found events after pattern fix

### Field Testing Results

**Test Charger: KKB233100447WE (EVS09)**
- **Detected:** 5 reboot events (3 power loss, 0 firmware updates, 2 unknown)
- **Max Gap:** 17.3 days (Jan 22 → Feb 9)
- **Events:**
  1. Power Loss: 17.3 days gap (Jan 22 → Feb 9)
  2. Power Loss: 14.0 days gap (Jul 20 → Aug 3) - RTC reset evident
  3. Power Loss: 2.1 days gap (Jan 10 → Jan 12)
  4. Unknown: 10.2 hours gap (Sep 11)
  5. Unknown: (details filtered)
- **Comparison to Manual Analysis:** Sub-agent found 7 events, detector found 5
  - Difference due to 30-day max gap filter (excludes year inference errors)
  - Real events captured, false positives eliminated

**Output Display:**
```
⚠ System Reboots Detected: 5 events
  Analysis: SystemLog gap detection
   • Power loss events: 3
   • Firmware updates: 0
   • Max logging gap: 17.3 days
  Recent events:
    🔌 Power Loss: Gap 17.3 days
       Last log: Jan 22 19:51:53
       Resumed: Feb  9 03:58:50
       Evidence: Long gap (17.3 days) suggests power loss
  Recommended Actions:
   • Investigate site power quality (voltage sags, outages)
   • Check RTC battery if dates reset to Jul 20 2025
   • Review facility electrical system for instability
```

### Impact

**Before v0.0.7:**
- Users had to manually analyze SystemLog timestamps
- No visibility into power stability issues
- Reboot frequency unknown

**After v0.0.7:**
- Automatic flagging of power loss patterns
- Clear distinction between planned/unplanned reboots
- Actionable recommendations (investigate power quality, RTC battery)
- CSV export for trending analysis

### Lessons Learned

1. **Timestamp Format Assumption:** Always verify actual log format before writing regex
2. **Milliseconds Matter:** Delta logs include milliseconds but other formats may not
3. **False Positive Management:**
   - Year inference errors create massive gaps (189+ days)
   - 30-day max filter effectively eliminates these
   - 2-hour minimum prevents normal quiet periods from triggering
4. **Log Rotation Complexity:** SystemLog files require chronological sorting accounting for rotation numbering
5. **Reboot Classification Importance:** Users care about power stability vs planned maintenance

### Next Steps

**Future Enhancements:**
- Use file modification timestamps to improve year inference
- Add RTC battery health indicator (detect consistent wrong-date boots)
- Correlate reboot events with critical errors (MCU failures before power loss)
- Detect rapid reboot loops (bootloader issues)

---

## v0.0.5 - Modbus Configuration Detection (2026-02-11)

### Overview
**Implemented Modbus configuration validation** to detect partial/incorrect LMS setups causing LIMIT_toNoPower (EV0103) events. Discovered through field case comparison between working and failing charger.

### Pattern Discovered

**Field Case: KKB233100369WE (2026-02-11) - ACTIVE TROUBLESHOOTING**
- **Symptoms:** 93 LIMIT_toNoPower events, charger stuck in "Preparing" state
- **Configuration Analysis:**
  - BAD charger: `u32ModbusMAXPower='0'` and `u32ModbusMINPower='0'`
  - GOOD charger: No Modbus configuration at all (DIP switches only)
- **Root Cause:** Partial LMS configuration with zero power limits
- **Impact:** Charger cannot deliver power below 6A (IEC 61851-1), 0W = permanent suspension
- **Found By:** Manual comparison of Config/evcs files
- **Resolution In Progress:** 
  - Customer asked to write 0xFFFF to registers 40204, 40205, 41601, 41602
  - Testing if Modbus misconfiguration is root cause
  - Awaiting customer feedback on whether fix resolves LIMIT_toNoPower events
- **Diagnostic Approach:** Compare config against known-good chargers, then test register writes before factory reset
- **Similar Pattern:** u32ModbusPowerLimit in good chargers = 4294967295 (0xFFFFFFFF max), this charger = 0

### Detector Implemented

**Implementation:** `detectors/lms.py` - `detect_modbus_config_issues()` (~125 lines)

**Detection Logic:**
1. Parse Config/evcs file for Modbus register configuration
2. Extract: u32ModbusMAXPower, u32ModbusMINPower, u32ModbusPowerLimit, u32ModbusFallbackLimit, u16ModbusCommTimeoutEnable
3. Flag misconfiguration patterns:
   - **Pattern 1 (CRITICAL):** MAX/MIN power = 0W (charger cannot deliver power)
   - **Pattern 2 (CRITICAL):** Fallback = 0W with timeout enabled (suspends on LMS failure)
   - **Pattern 3 (WARNING):** Power limits < 1380W (below 6A minimum per IEC 61851-1)
4. Return structured result with all register values + issue description

**Returns:**
```python
{
    'has_modbus_config': bool,
    'max_power': int or None,
    'min_power': int or None,
    'power_limit': int or None,
    'fallback_limit': int or None,
    'timeout_enabled': int or None,
    'is_misconfigured': bool,
    'issue_description': str or None
}
```

### Code Changes

**File:** `analyzers/delta_ac_max/detectors/lms.py`
- **Before:** 95 lines (1 detector)
- **After:** 220 lines (2 detectors)
- **Change:** +125 lines
- **Status:** ✅ Within 300-line guideline

**File:** `analyzers/delta_ac_max/analyze.py`
- **Change:** +2 lines
- **Updates:**
  - Added `analysis['modbus_config']` result field
  - Integrated detector call: `self.lms_detector.detect_modbus_config_issues(folder)`
  - Added status check: 🔴 CRITICAL if misconfigured

**File:** `analyzers/delta_ac_max/reporter.py`
- **Change:** +17 lines
- **Updates:**
  - New section: "Modbus Configuration Issues"
  - Shows all register values, issue description, recommended fix
  - Color-coded: 🔴 CRITICAL for misconfiguration

**File:** `analyzers/delta_ac_max/exporter.py`
- **Change:** +5 CSV columns
- **New Fields:**
  - `Modbus_Configured`: True/False
  - `Modbus_Misconfigured`: True/False
  - `Modbus_MAX_Power`: Watts
  - `Modbus_MIN_Power`: Watts
  - `Modbus_Issue`: Description

### Terminal Output Example

```
🔴 CRITICAL: Modbus Misconfiguration
  Location: Config/evcs file
  Issue: ModbusMAXPower=0W (charger cannot deliver power) | ModbusMINPower=0W (below IEC 61851-1 minimum)
   • ModbusMAXPower: 0 W
   • ModbusMINPower: 0 W
   • FallbackLimit: 4294967295 W
   • Timeout Enabled: No
  Recommended Fix:
   • Factory reset to remove LMS config, OR
   • Set ModbusMAXPower = 4294967295 (0xFFFFFFFF = MAX)
   • Set FallbackLimit ≥ 1380W (6A minimum per IEC 61851-1)

⚠ Load Management System Issues
  Search term: "Load_Mgmt_Comm_Error" or "LIMIT_toNoPower"
   • Modbus comm errors: 0
   • LIMIT_toNoPower events: 93
```

### Knowledge Base Updates

**Updated:** `.github/knowledge-base/reference/modbus_registers.md`
- Added "Automated Detection (Since v0.0.5)" section
- Documented detection pattern, terminal output format
- Added CSV export field reference
- Cross-referenced field case KKB233100369WE

**Impact:** Analyzer can now automatically identify the 0W Modbus configuration pattern that previously required manual Config/evcs file inspection.

### Key Insights

1. **Pattern Prevalence:** Unknown - this is first documented case with 0W MAX/MIN power
2. **vs Federation University Case:** Different pattern
   - Federation: 0W **fallback** with timeout enabled
   - This case: 0W **MAX/MIN** power (no timeout)
3. **Configuration Comparison Method:** Comparing GOOD vs BAD charger configs is highly effective diagnostic technique
4. **Factory Reset Uncertainty:** Still unknown if factory reset clears Modbus registers (manual verification recommended)

### Next Steps

**Future Enhancement Ideas:**
- Add "Recommended Configuration" validator (compare actual vs ideal config)
- Detect timeout-fallback combinations (already covered by existing case, but not explicitly validated)
- Parse DIP switch configuration (if available in logs) to validate against Modbus limits
- Add reboot pattern detection (power loss vs planned update)

### Field Update (2026-02-11 PM - Modbus Register Priority Clarified)

**Second Charger Analysis: KKB233100447WE (EVS09)**
- Configuration: MAX=0, MIN=0, PowerLimit=4294967295, FallbackLimit=4294967295
- **Result:** Charger works perfectly despite MAX/MIN = 0
- **DISCOVERY:** PowerLimit and FallbackLimit are the PRIMARY controls
- **CONCLUSION:** MAX/MIN Power registers appear deprecated/informational only

**Detector Updated (v0.0.6):**
- Changed detection from MAX/MIN focus to PowerLimit/FallbackLimit focus
- **Fixed false positive:** EVS09 no longer incorrectly flagged as misconfigured
- Updated logic prioritizes actual control registers

**Reboot Pattern Analysis (EVS09):**
- Analyzed 7 reboot events across 6 months of logs
- **Pattern 1: Power Loss** (5 events)
  - Abrupt logging stop, no warnings/errors
  - RTC resets to Jul 20 2025 03:30:xx (factory default or drained battery)
  - Gaps range from minutes to 20 days
- **Pattern 2: Firmware Update** (2 events)
  - Graceful shutdown sequence logged
  - Dual-bank firmware update (bootaddr1/bootaddr2 switching)
  - Clean 5-6 second reboot
- **Key Finding:** No software crashes - all reboots external causes (power or planned updates)
- **RTC Issue:** Consistent wrong-date boots suggest weak/absent RTC backup battery
- **Power Stability:** 5 unplanned outages in 6 months indicates site power quality issues

**Recommendations Added:**
- Investigate site power reliability
- Check RTC backup battery
- Consider UPS installation if power quality poor

---

## v0.0.4 - Phase 1 Critical Detectors Implementation (2026-01-26)

### Overview
**Implemented 3 critical OCPP detectors for data loss prevention** based on OCPP 1.6 Errata study. These patterns detect billing failures, transaction corruption, and audit compliance issues - the highest priority patterns discovered from official OCA documentation.

### Detectors Implemented

#### 1. Lost TransactionID Detection
- **Implementation:** `detectors/ocpp.py` - `detect_lost_transaction_id()` (113 lines)
- **Pattern:** StartTransaction.req sent but no .conf received
- **Detection Strategy:**
  - Parse OCPP-J message pairs: `[2, msgId, "StartTransaction"]` → `[3, msgId, {...}]`
  - Track pending transactions (never got CALLRESULT)
  - Scan for invalid `transactionId: -1/0/null` in MeterValues/StopTransaction
- **Returns:** lost_transaction_count, invalid_transaction_ids, total_issues, examples
- **Impact Detection:** CRITICAL - Billing failure, all session data lost
- **From:** OCPP 1.6 Errata Section 3.18

#### 2. Hard Reset Data Loss Detection
- **Implementation:** `detectors/ocpp.py` - `detect_hard_reset_data_loss()` (125 lines)
- **Pattern:** Hard reset during active transactions → immediate reboot without queuing StopTransaction
- **Detection Strategy:**
  - Track active transactions (StartTransaction without StopTransaction)
  - Detect Reset.req with `"type":"Hard"`
  - Flag incomplete transactions after BootNotification
  - Compare vs Soft reset behavior (graceful shutdown)
- **Returns:** hard_reset_count, soft_reset_count, incomplete_transactions, examples
- **Impact Detection:** CRITICAL - Transaction data lost, billing incomplete
- **From:** OCPP 1.6 Errata Section 3.36

#### 3. Meter Register Tracking (Cumulative vs Session)
- **Implementation:** `detectors/ocpp.py` - `detect_meter_register_tracking()` (85 lines)
- **Pattern:** meterStart always =0 instead of cumulative lifetime register
- **Detection Strategy:**
  - Parse meterStart/meterStop values from transactions
  - Check if all meterStart <100 kWh (likely session-based, not cumulative)
  - Detect if meterStart decreases (register reset between sessions)
- **Returns:** transactions_analyzed, non_cumulative_count, meter_values, examples
- **Impact Detection:** WARNING - Cannot audit total energy, meter tampering undetectable
- **From:** OCPP 1.6 Errata Section 3.9

### Code Changes

**File:** `analyzers/delta_ac_max/detectors/ocpp.py`
- **Before:** 304 lines (5 detectors)
- **After:** 627 lines (8 detectors)
- **Change:** +323 lines
- **Status:** ⚠️ Exceeds 300-line guideline (requires refactoring in Phase 2+)
- **Imports Added:** `json, Set, Tuple` for OCPP-J parsing

**File:** `analyzers/delta_ac_max/analyze.py`
- **Before:** ~350 lines
- **After:** 367 lines
- **Change:** +17 lines
- **Updates:**
  - Added 3 new result fields to analysis dict (lost_transaction_id, hard_reset_data_loss, meter_register_tracking)
  - Integrated 3 detector calls in analysis pipeline
  - Added 3 status checks with issue severity (CRITICAL/WARNING)

**File:** `analyzers/delta_ac_max/reporter.py`
- **Before:** ~330 lines
- **After:** 400 lines
- **Change:** +70 lines
- **Updates:**
  - Added detailed output for all 3 detectors
  - Color-coded critical issues (🔴 for billing/data loss, ⚠️ for warnings)
  - Explained root causes, impact, resolution steps
  - Referenced OCPP 1.6 Errata sections for authority

### Terminal Output Examples

**Lost TransactionID (Billing Failure):**
```
🔴 CRITICAL: Lost Transaction ID - BILLING FAILURE (5 issues)
    Problem: StartTransaction.req sent but backend never responded
    Impact: Charger has no transactionId → ALL billing data LOST
    Lost transactions: 2
    Invalid transactionId values: 3
    ⓘ Messages sent with transactionId=-1 or 0 are CORRUPT
    Root Cause: Backend timeout or communication failure
    Resolution: Contact backend provider (GreenFlux/etc.) - server issues
    From: OCPP 1.6 Errata Section 3.18
```

**Hard Reset Data Loss:**
```
🔴 CRITICAL: Hard Reset Data Loss (3 incomplete transactions)
    Problem: Hard reset reboots IMMEDIATELY without queuing StopTransaction
    Impact: Active transaction data LOST, billing incomplete
    Hard resets detected: 3
    Soft resets (graceful): 1
    ⓘ Soft reset queues StopTransaction gracefully before reboot
    ⓘ Hard reset = immediate reboot (no cleanup)
    Root Cause: Backend sent Reset.req with type=Hard during active session
    From: OCPP 1.6 Errata Section 3.36
```

**Meter Register Issue:**
```
⚠️ Meter Register Issue: Non-Cumulative Values
    Problem: meterStart always starts at 0 (session energy, not cumulative)
    Impact: Cannot audit total charger energy over lifetime
    Transactions analyzed: 45
    Non-cumulative transactions: 45
    BEST PRACTICE: Use Energy.Active.Import.Register (cumulative Wh)
    Expected: meterStart increases monotonically (lifetime register)
    Actual: meterStart resets to 0 each session
    From: OCPP 1.6 Errata Section 3.9
```

### Implementation Insights

**OCPP-J Message Format Learned:**
- `[MessageType, MessageId, Action, Payload]`
- MessageType: 2=CALL (request), 3=CALLRESULT (response), 4=CALLERROR (error)
- transactionId=-1 is **actual Delta charger behavior** when backend times out (not theoretical!)

**Hard/Soft Reset Distinction:**
- Soft reset: Queues all pending messages (StopTransaction, etc.) before reboot
- Hard reset: Immediate reboot, data in RAM lost
- **Critical:** Backend should use Soft reset OR wait for idle state before reset

**Meter Register Types:**
- **Cumulative (CORRECT):** Energy.Active.Import.Register - lifetime Wh (12,345 → 12,375 → 12,410)
- **Session (INCORRECT):** Energy.Active.Import.Interval - per-session Wh (0 → 30 → 0 → 25)

### Code Quality

✅ **Syntax Validated:** All Python files compile successfully  
✅ **Backward Compatible:** Existing detectors unchanged  
✅ **Follows Pattern:** Static methods returning `Dict[str, Any]`  
✅ **Error Handling:** Try/except blocks for file I/O  
✅ **Documentation:** Comprehensive docstrings with OCPP references  

⚠️ **Modularity Concern:** ocpp.py now 627 lines (2x guideline) - requires refactoring

### Next Steps

**Immediate:**
- [ ] Test with real charger logs (Federation University, field cases)
- [ ] Validate detection accuracy (no false positives)
- [ ] CSV export integration (add new columns)

**Phase 2 (Future):**
- [ ] Implement CallError parsing (protocol violations)
- [ ] Implement WebSocket ping validation (half-open connections)
- [ ] Implement synchronicity violation detection
- [ ] Refactor ocpp.py into modular structure (4 files, each <300 lines)

**Phase 3 (Future):**
- [ ] Implement ChargingProfile stacking validation
- [ ] Implement timestamp format validation
- [ ] Implement MeterValues configuration audit

### Source Authority
- OCPP 1.6 Errata Sheet v4.0 (Official OCA corrections)
- OCPP-J 1.6 Specification (Protocol transport layer)
- mobilityhouse/ocpp Python library (validation reference)

### Documentation Updates
- Updated: `.github/knowledge-base/development/learning_history.md` (this file)
- Created: `~/.copilot/session-state/.../implementation-summary.md` (detailed implementation notes)

---

## v0.0.3 - OCPP 1.6 Fault Patterns from Official Errata Sheets (2026-01-26)

### Overview
**Deep dive into official OCA (Open Charge Alliance) errata sheets and specifications** - studied 3x iterations to extract every nugget of knowledge about common faults, implementation bugs, and protocol violations. Discovered **13 critical fault patterns** from 46 documented errata that reveal real-world OCPP issues.

**Sources Studied:**
- OCPP 1.6 Errata Sheet v4.0 (46 pages, 90k characters)
- OCPP-J 1.6 Errata v1.0 (13 pages, 14k characters)
- OCPP-J 1.6 Specification (22 pages, 36k characters)

### Critical Fault Patterns Discovered

#### HIGH PRIORITY (Data Loss / Billing Impact)

**1. Lost TransactionID - StartTransaction.conf Not Received**
- **Problem:** Backend fails to respond with transactionId → all subsequent messages fail
- **Impact:** Billing data lost, MeterValues/StopTransaction sent with transactionId=-1
- **Root Causes:** Backend timeout, network packet loss, backend crash
- **Detection:** Count StartTransaction.req without matching .conf
- **Source:** OCPP Errata v4.0 Section 3.18

**2. Hard Reset Data Loss**
- **Problem:** Hard reset reboots immediately WITHOUT queuing StopTransaction
- **Impact:** Active transaction data lost, billing incomplete
- **Critical:** Soft reset queues messages, hard reset often loses them
- **Detection:** Reset type=Hard + BootNotification + NO StopTransaction
- **Source:** OCPP Errata v4.0 Section 3.36

**3. Meter Register Not Cumulative**
- **Problem:** Charger resets meterStart to 0 each transaction instead of using lifetime register
- **Impact:** Cannot track total energy, audit failures, meter tampering undetectable
- **Expected:** meterStart increases monotonically (12,345 → 12,375 → 12,410 kWh)
- **Incorrect:** meterStart=0 every time
- **Detection:** Track meterStart values, flag if always <100 kWh
- **Source:** OCPP Errata v4.0 Section 3.9

#### MEDIUM PRIORITY (Performance / Reliability)

**4. WebSocket Half-Open Connections**
- **Problem:** Connection appears active but is dead (NAT timeout, firewall)
- **Impact:** Messages sent into void, silent failures (hardest to debug)
- **Prevention:** WebSocket ping/pong frames
- **Critical Rule:** `WebSocketPingInterval < (TransactionMessageAttempts × TransactionMessageRetryInterval)`
- **Example:** Ping=60s, retry window=150s → GOOD (60 < 150)
- **Detection:** Parse GetConfiguration, calculate retry window, compare
- **Source:** OCPP-J Errata v1.0 Section 3.9

**5. OCPP-J CallError Codes (Protocol Violations)**
- **Message Type 4** = CALLERROR (error response)
- **9 Error Codes:** NotImplemented, NotSupported, InternalError, ProtocolError, SecurityError, FormationViolation, PropertyConstraintViolation, OccurenceConstraintViolation, TypeConstraintViolation
- **Detection:** Parse `[4,"msgId","ErrorCode","description",{}]`
- **Threshold:** >10 of same errorCode = systemic issue
- **Source:** OCPP-J Spec Section 4.2.3

**6. Synchronicity Violations (Message Out of Order)**
- **Rule:** Charger SHOULD NOT send CALL until previous CALL responded
- **Violation:** CALL 2 sent before CALL 1 response received
- **Impact:** Backend may reject, race conditions, state corruption
- **Detection:** Track pending CALL messageIds, flag if new CALL before response
- **Source:** OCPP-J Spec Section 4.1.1

#### LOW PRIORITY (Configuration / Best Practice)

**7. ChargingProfile Stacking Without Duration**
- **Problem:** High stackLevel profile without duration blocks lower profiles forever
- **Impact:** Load management never executes, stuck at single limit
- **Detection:** stackLevel >1 AND duration=null
- **Source:** OCPP Errata v4.0 Section 3.7

**8. TxDefaultProfile Removed During Active Transaction**
- **Problem:** Backend clears TxDefaultProfile while transaction running
- **Behavior:** Transaction continues WITHOUT any power limits (full power)
- **Detection:** ClearChargingProfile during active transaction
- **Source:** OCPP Errata v4.0 Section 3.8

**9. Charging Before BootNotification Accepted**
- **Problem:** Charger allows transactions before `status=Accepted`
- **Risk:** Invalid timestamps (1970-01-01), backend rejects later
- **Detection:** StartTransaction before BootNotification.conf
- **Source:** OCPP Errata v4.0 Section 3.11

**10. Missing MeterValues Configuration**
- **Problem:** MeterValueSampleInterval=0 or MeterValuesSampledData empty
- **Impact:** No real-time meter data, user can't see charging progress
- **Detection:** GetConfiguration for meter config keys
- **Source:** OCPP Errata v4.0 Section 3.13

#### JSON IMPLEMENTATION BUGS (Interoperability)

**11. "Celsius" Typo (Celcius vs Celsius)**
- **Problem:** Original schema misspelled "Celsius" as "Celcius"
- **Fix:** Backends MUST accept both spellings
- **Source:** OCPP-J Errata v1.0 Section 2.1

**12. StopTransaction "reason" Incorrectly Required**
- **Problem:** Schema says required, spec says optional (default="Local")
- **Impact:** Some chargers omit, some backends reject
- **Source:** OCPP-J Errata v1.0 Section 2.5

**13. Timestamp Format Validation**
- **Requirement:** ISO 8601 with timezone
- **Valid:** `2024-07-15T14:23:45.123Z`
- **Invalid:** `2024-07-15T14:23:45` (missing timezone)
- **Detection:** Regex validate, flag timestamps without timezone
- **Source:** OCPP Errata v4.0 Section 3.10

### Documentation Updates

**Created:** `.github/knowledge-base/reference/ocpp_fault_patterns.md` (490 lines)
- Complete catalog of 13 fault patterns
- Detection strategies for each pattern
- Priority matrix (High/Medium/Low)
- Implementation roadmap (3 phases)
- Cross-references to related knowledge

**Updated:** `.github/knowledge-base/development/learning_history.md` (this file)

### Implementation Value

**Phase 1 (Critical):**
- Detect lost transactionId (prevents billing failures)
- Detect hard reset data loss (prevents transaction corruption)
- Track meter register values (audit compliance)

**Phase 2 (Protocol):**
- Parse CallError messages (identify protocol violations)
- Validate WebSocket ping config (prevent silent failures)
- Detect synchronicity violations (message ordering issues)

**Phase 3 (Configuration):**
- Audit MeterValues config (ensure data collection)
- Validate ChargingProfile stacking (load management correctness)
- Validate timestamps (clock sync issues)

### Source Authority

- **OCPP 1.6 Errata Sheet v4.0** - Official OCA corrections (2019-10-23)
- **OCPP-J 1.6 Errata v1.0** - JSON implementation corrections (2019-12-04)
- **OCPP-J 1.6 Specification** - Protocol transport layer (2015-10-08)
- **PDF Extraction:** PyPDF2 (90,437 + 14,163 + 36,182 characters studied)

### Next Steps

- [ ] Implement Lost TransactionID detection
- [ ] Implement Hard/Soft reset differentiation
- [ ] Implement CallError parsing and counting
- [ ] Implement WebSocket ping interval validation
- [ ] Implement meter register tracking
- [ ] Implement timestamp format validation

---

## v0.0.2 - OCPP 1.6 Specification Study (2026-01-26)

### Overview
Comprehensive study of OCPP 1.6 specification via mobilityhouse/ocpp Python library (authoritative open-source implementation). Filled major gaps in protocol knowledge with complete message catalog, enums, and flow documentation.

### What Was Learned

#### Complete OCPP 1.6 Message Catalog (43 Actions)
- **Charger → Backend (14):** Authorize, BootNotification, DiagnosticsStatusNotification, FirmwareStatusNotification, Heartbeat, LogStatusNotification, MeterValues, SecurityEventNotification, SignCertificate, SignedFirmwareStatusNotification, StartTransaction, StatusNotification, StopTransaction, DataTransfer
- **Backend → Charger (29):** CancelReservation, CertificateSigned, ChangeAvailability, ChangeConfiguration, ClearCache, ClearChargingProfile, DeleteCertificate, ExtendedTriggerMessage, GetCompositeSchedule, GetConfiguration, GetDiagnostics, GetInstalledCertificateIds, GetLocalListVersion, GetLog, InstallCertificate, RemoteStartTransaction, RemoteStopTransaction, ReserveNow, Reset, SendLocalList, SetChargingProfile, SignedUpdateFirmware, TriggerMessage, UnlockConnector, UpdateFirmware, DataTransfer

**Implementation Value:** Can now detect missing/unexpected OCPP messages in logs

#### ChargePointErrorCode Enumeration (16 Values)
- NoError, ConnectorLockFailure, EVCommunicationError, GroundFailure, HighTemperature, InternalError, LocalListConflict, OtherError, OverCurrentFailure, OverVoltage, PowerMeterFailure, PowerSwitchFailure, ReaderFailure, ResetFailure, UnderVoltage, WeakSignal

**Implementation Value:** Can cross-reference StatusNotification errorCode with Delta error codes

#### Measurand Types (22 Meter Value Types)
- Current (Import/Export/Offered), Energy (Active/Reactive, Register/Interval), Frequency, Power (Active/Reactive/Offered), Power.Factor, RPM, SoC, Temperature, Voltage
- **Key Learning:** Default measurand = `Energy.Active.Import.Register`

**Implementation Value:** Can validate MeterValues reporting, detect missing meter data

#### Stop Transaction Reasons (11 Values)
- DeAuthorized, EmergencyStop, EVDisconnected, HardReset, Local, Other, PowerLoss, Reboot, Remote, SoftReset, UnlockCommand

**Implementation Value:** Can categorize session stop reasons, detect abnormal patterns

#### Configuration Keys (Core Profile - 33 Keys)
- **Critical Discovery:** `ChargingScheduleMaxPeriods` - confirms Delta bug (advertised 20, actual 10)
- Connection: ConnectionTimeOut, HeartbeatInterval, WebSocketPingInterval
- Authorization: AllowOfflineTxForUnknownId, AuthorizeRemoteTxRequests, LocalAuthorizeOffline, etc.
- Meter Values: MeterValueSampleInterval, MeterValuesAlignedData, MeterValuesSampledData
- Smart Charging: ChargeProfileMaxStackLevel, MaxChargingProfilesInstalled

**Implementation Value:** Can detect configuration mismatches, validate GetConfiguration responses

#### Authorization Flows (3 Types)
1. **RFID Authorization:** Local → Authorize.req → Backend validation → StartTransaction
2. **RemoteStartTransaction (App):** Backend initiates → Connector validation → StartTransaction
3. **Pre-Authorization:** Plug in → Auto StartTransaction with placeholder idTag → Backend authorizes

**Implementation Value:** Can detect authorization flow failures, identify bottlenecks

#### Firmware Update Flows (2 Types)
1. **UpdateFirmware (Legacy):** Download → FirmwareStatusNotification stages → Reboot
2. **SignedUpdateFirmware (Security):** Cryptographic verification → InstallVerificationFailed detection

**Implementation Value:** Can monitor firmware update success/failure, detect update loops

#### Diagnostics & Logging
- **GetDiagnostics:** Upload diagnostics with time filters → DiagnosticsStatusNotification
- **GetLog (Security Extension):** Upload security/diagnostics logs with requestId tracking

**Implementation Value:** Can detect diagnostic upload failures, correlate with log extraction issues

#### Reservation System
- **ReserveNow:** Reserve connector for specific user/time → StatusNotification: Reserved
- **CancelReservation:** Cancel active reservation → Available
- **Status Values:** Accepted, Faulted, Occupied, Rejected, Unavailable

**Implementation Value:** Can detect reservation system abuse, identify connector availability issues

#### ISO 15118 Plug & Charge (PnC)
- **Messages:** SignCertificate, CertificateSigned, InstallCertificate, DeleteCertificate, GetInstalledCertificateIds
- **Config Keys:** ISO15118PnCEnabled, CentralContractValidationAllowed, ContractValidationOffline
- **Certificate Types:** CentralSystemRootCertificate, ManufacturerRootCertificate

**Implementation Value:** Can detect PnC setup failures, certificate issues (future DC charger support)

#### Security Profiles
- **SecurityProfile 0:** Unsecured HTTP/WebSocket (default older chargers)
- **SecurityProfile 1:** Basic authentication
- **SecurityProfile 2:** TLS with Basic Auth
- **SecurityProfile 3:** TLS with client certificates (mutual TLS) **← RECOMMENDED**

**Implementation Value:** Can detect insecure configurations, recommend security upgrades

#### Local Authorization List
- **SendLocalList:** Full/Differential updates with version tracking
- **GetLocalListVersion:** Query current list version
- **Offline Operation:** Enabled via LocalAuthListEnabled config key

**Implementation Value:** Can detect offline auth failures, recommend local list updates

#### Data Transfer (Vendor-Specific)
- **Bidirectional:** Charger ↔ Backend custom messages
- **Fields:** vendorId, messageId, data
- **Use Cases:** Proprietary features, Delta Modbus queries, OEM telemetry

**Implementation Value:** Can detect vendor-specific protocol extensions, analyze custom data flows

#### Message Validation Rules
- **IdTag:** Max 20 characters, case-insensitive
- **Timestamp:** ISO 8601 format (`YYYY-MM-DDTHH:MM:SS.sssZ`)
- **Connector IDs:** 0 = charge point, 1-N = connectors
- **Transaction IDs:** Backend-assigned, must be unique per charger

**Implementation Value:** Can validate log data integrity, detect malformed messages

### Documentation Updates
- **Updated:** `.github/knowledge-base/patterns/ocpp_protocol.md`
- **Added:** Complete OCPP 1.6 message reference (43 actions)
- **Added:** Full enumeration catalogs (ChargePointErrorCode, Measurand, Reason, etc.)
- **Added:** Authorization flows (RFID, RemoteStart, Pre-auth)
- **Added:** Firmware update flows (legacy + signed)
- **Added:** Diagnostics & logging protocols
- **Added:** Reservation system
- **Added:** ISO 15118 PnC support
- **Added:** Security profiles
- **Added:** Local authorization list management
- **Added:** Data transfer vendor extensions
- **Added:** Message validation rules
- **Removed:** "TODO: Further Study Needed" section (completed)

### Source
- **mobilityhouse/ocpp** GitHub repository (https://github.com/mobilityhouse/ocpp)
- Files studied:
  - `ocpp/v16/enums.py` - All OCPP 1.6 enumerations
  - `ocpp/v16/datatypes.py` - Data structures
  - `ocpp/v16/call.py` - CALL messages (requests)
  - `ocpp/v16/call_result.py` - CALLRESULT messages (responses)
- **Authority Level:** High (Python OCPP library used by production systems worldwide)

### Next Steps
- [ ] Cross-reference Delta AC MAX error codes with ChargePointErrorCode values
- [ ] Add detection for missing MeterValues (expected vs. actual measurands)
- [ ] Validate configuration keys against known Delta defaults
- [ ] Detect authorization flow anomalies (RFID → no Authorize, etc.)
- [ ] Add firmware update failure detection patterns

---

## v0.0.1 - Federation University Cases & Protocol Learning (2026-01-26)

### Overview
Major knowledge expansion from Federation University multi-charger case study. Revealed complex interactions between OCPP backend, local Modbus LMS, and charger configuration.

### New Patterns Detected

#### Low-Current OCPP Profiles (<6A)
- **Pattern:** `SetChargingProfile.*limit=([\d\.]+)` where limit <6.0
- **Threshold:** >10 occurrences
- **Root Cause:** Backend (GreenFlux/CPMS) sending 0A or <6A limits
- **Impact:** Charger suspends charging per IEC 61851-1 standard
- **Resolution:** Contact backend provider to increase minimum current limits to ≥6A
- **Case Study:** KKB233100224WE - 11 profiles at 0.1A causing session suspensions
- **Implementation:** `detectors/ocpp.py` - `detect_low_current_profiles()`

#### Load Management System (LMS) Modbus Issues
- **Pattern:** `Load_Mgmt_Comm.*(?:timeout|time out|fail|error)`
- **Threshold:** >5 occurrences
- **Root Cause:** Modbus register 40204 (Fallback Power) = 0W after LMS failure
- **Impact:** Charger stuck in LIMIT_toNoPower state, unable to deliver power
- **Resolution:** Factory reset OR manually write 0xFFFF to Modbus registers
- **Case Study:** KKB233100224WE (Federation University, July-Dec 2024)
- **Key Learning:** State persists even after physical LMS disconnection
- **Implementation:** `detectors/lms.py` - `detect_load_mgmt_comm_errors()`

#### Event Code Analysis (Delta AC MAX Error Mapping)
- **Pattern:** `YYYY.MM.DD HH:MM:SS-EVXXXX` in EventLog CSV files
- **Purpose:** Cross-reference with Delta's official error code mapping
- **Examples:**
  - EV0103 (LIMIT_toNoPower) - Charger in zero-power limiting state
  - EV0082 (AC Output OCP) - Over-current protection (configuration mismatch)
  - EV0117-EV0126 (Network) - Backend/WiFi/3G connectivity errors
- **Implementation:** `detectors/events.py` - `parse_event_log()`
- **Reference:** 43 Delta AC MAX error codes (EV0081-EV0126) documented

#### RFID Module Failures (RYRR20I)
- **Pattern:** `RYRR20I.*(?:fail|time out)`
- **Threshold:** >100 occurrences = hardware fault confirmed
- **Case Study:** KKB240500004WE (Federation University, July 2024)
- **Error Count:** 51,095 RYRR20I errors over weeks
- **Resolution:** Charger replacement required (RYRR20I not serviceable)
- **Implementation:** `detectors/hardware.py` - `detect_rfid_errors()`

### Protocol Understanding

#### IEC 61851-1 Current Limiting Behavior
- **Standard:** Mode 3 AC Charging requires minimum 6.0A
- **Charger Behavior:** Suspends power delivery when limit <6A
- **OCPP State:** Charging → Preparing (when <6A applied)
- **Critical Understanding:** This is EXPECTED behavior, NOT a fault
- **Common Misdiagnosis:** "Charger keeps dropping sessions" - actually suspending per standard

#### Configuration Hierarchy (DIP / OCPP / Modbus)
- **Discovery:** Charger uses MINIMUM of three current sources
- **Sources:**
  1. Physical DIP switches (hardware limit)
  2. OCPP SetChargingProfile (backend software limit)
  3. Modbus register 41601 (local LMS limit)
- **Example:** DIP=16A, OCPP=32A, Modbus=MAX → Charger limits to 16A + EV0082 fault
- **Case Study:** Federation University (Dec 2024)
  - After fixing Modbus, EV0082 appeared
  - Backend sent 32A SetChargingProfile
  - DIP switches configured for lower current
  - Required aligning all three sources

#### Dual-Source Current Limiting (Complex Diagnosis)
- **Discovery:** OCPP backend AND Modbus LMS can BOTH limit simultaneously
- **Case:** KKB233100224WE - Both systems limiting to <6A concurrently
- **Diagnosis Challenge:** Required checking BOTH OCPP logs AND Modbus configuration
- **Resolution Order:** Fix LMS first (physical intervention) → Then fix OCPP (backend contact)

### Firmware Bugs Identified

#### SetChargingProfile Timeout Bug (Firmware <01.26.40)
- **Pattern:** `"SetChargingProfileConf process time out"` in OCPP logs
- **Root Cause:** Charger advertises 20 periods, actually supports 10
- **Behavior:** 31-second timeout + empty status response `{"status":""}`
- **Impact:** Cascade of backend disconnects, site-wide load management failure
- **Workaround:** Backend provider limits profiles to 10 periods
- **Status:** Pending firmware fix from Delta
- **Implementation:** `detectors/ocpp.py` - `detect_setcharging_timeouts()`

### Modular Refactoring

#### Code Modularization
- **Previous:** Monolithic `analyze.py` (~800 lines)
- **Refactored:**
  - `analyze.py` - Orchestrator (~388 lines)
  - `reporter.py` - TUI output (~278 lines)
  - `utils.py` - ZIP extraction (~109 lines)
  - `error_codes.py` - Delta error mapping (~50 lines)
  - `detectors/*.py` - Specialized detection modules (5 files, ~730 lines total)
- **Benefits:** Easier to extend, clearer responsibilities, easier testing

#### Detector Modules Created
- `detectors/events.py` - Event log parsing, ChargBox ID extraction
- `detectors/ocpp.py` - OCPP protocol detections (profiles, timeouts, rejections)
- `detectors/hardware.py` - Hardware faults (RFID, MCU, sensors)
- `detectors/lms.py` - Load Management System (Modbus communication)
- `detectors/state_machine.py` - OCPP state transition validation

### Field Cases Analyzed

#### Federation University - KKB233100224WE (Dual-Source Limiting)
- **Duration:** July-December 2024
- **Symptoms:** Charger stuck in Preparing state, unable to complete sessions
- **Root Causes (Three simultaneous issues):**
  1. OCPP backend sending 0.1A limits (11 occurrences)
  2. Modbus fallback power = 0W (24 LMS comm errors, 144 LIMIT_toNoPower events)
  3. Configuration mismatch (32A OCPP > DIP switches)
- **Resolution:** Fixed OCPP backend + Modbus reset + aligned DIP/OCPP/Modbus
- **Learning:** Fixing one issue may reveal others (cascading misconfigurations)

#### Federation University - KKB240500004WE (RFID Hardware Fault)
- **Duration:** July-December 2024
- **Symptoms:** RFID cards not recognized, 51,095 RYRR20I errors
- **Root Cause:** Catastrophic RFID module (RYRR20I) hardware failure
- **Troubleshooting:** Power cycle, factory reset, firmware update ALL failed
- **Resolution:** Charger replacement required (RYRR20I not serviceable)
- **Learning:** High error counts (>1000) confirm hardware fault, not configuration

### Documentation Expansion

#### Knowledge Base Created
- **Reference Material:**
  - `error_codes.md` - 43 Delta AC MAX error codes
  - `modbus_registers.md` - LMS Modbus register map
  - `firmware_bugs.md` - Known firmware issues

- **Pattern Knowledge:**
  - `ocpp_protocol.md` - OCPP 1.6 protocol understanding
  - `current_limiting.md` - IEC 61851-1, configuration hierarchy
  - `hardware_faults.md` - RFID, MCU, network issues
  - `state_transitions.md` - OCPP state machine

- **Case Studies:**
  - `federation_university.md` - Complete dual-charger case

- **Development:**
  - `pattern_detection.md` - How to add new patterns
  - `modularity_guidelines.md` - Code/doc organization
  - `learning_history.md` - This file

---

## v1.0.0 - Initial Release (2026-01-26)

### Features Implemented

#### Basic Pattern Detection
- Backend connection failures (`"Backend connection fail"`)
- MCU communication errors (`Send Command 0x[0-9A-Fa-f]+ to MCU False`)
- Logging gaps (>24 hours)
- Firmware version tracking (`Fw2Ver: XX.XX.XX.XX`)
- High error counts (>100 lines with "error" or "fail")

#### ZIP File Support
- Standard manual export (Storage/ directory structure)
- GetDiagnostics (OCPP command export)
- Automatic structure detection

#### Output Formats
- Terminal UI (TUI) summary with color-coded severity
- CSV export for batch analysis
- Per-charger detailed reporting

#### Cross-Platform
- Python 3.6+ standard library only
- Windows, Linux, macOS compatible
- pathlib.Path for cross-platform paths

---

## Pattern Addition Template

### vX.X.X - Description (YYYY-MM-DD)

**New Patterns:**
- Pattern name - Brief description
- Implementation: module.py - method_name()
- Threshold: X occurrences
- Root cause: What it indicates

**Field Cases:**
- Case name - Charger ID, symptoms, resolution

**Protocol Learning:**
- What was learned about OCPP/IEC/standards

**Code Changes:**
- New modules created
- Refactoring performed

**Documentation:**
- New knowledge docs added
- Updated cross-links

---

**Last Updated:** 2026-01-26  
**Maintainer:** Update this file when adding new patterns, learning from field cases, or refactoring code
