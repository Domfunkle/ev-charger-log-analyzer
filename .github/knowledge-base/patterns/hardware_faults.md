# Hardware Faults

**Purpose:** Detect and diagnose hardware-related faults in Delta AC MAX chargers  
**Scope:** RFID modules, MCU communication, sensors, and physical component failures

---

## RFID Module Fault (RYRR20I)

### Overview

**Module:** RYRR20I is the RFID reader card/module used for NFC/RFID card authentication  
**Severity:** CRITICAL - Complete loss of RFID functionality  
**Resolution:** **CHARGER REPLACEMENT REQUIRED** (not a serviceable part)

### Pattern Detection

**Log Pattern:**
```
RYRR20I.*(?:fail|time out|error)
```

**Common Error Messages:**
```
[RFID] RYRR20I Register write request 2 fail
[RFID] RYRR20I Set StandBy Mode fail
[RFID] RYRR20I Reset fail
[RYRR20I_Check_Request] Time Out
```

**Thresholds:**
- **>100 occurrences:** CRITICAL hardware fault confirmed
- **Typical faulty module:** 10,000-50,000+ errors over days/weeks
- **Extreme case:** 51,095 errors (Federation University case)

### Symptoms

**User-Facing:**
- RFID cards not recognized by charger (tap has no effect)
- Users unable to start charging via RFID tap
- Multiple RFID cards tested with no response (not a card issue)
- LED may flash red briefly on tap, then no action

**System Behavior:**
- Continuous RYRR20I error messages in SystemLog
- Errors persist through power cycles
- Errors persist through factory reset
- Errors persist through firmware updates

**Impact:**
- Complete loss of RFID functionality
- Users cannot authenticate locally
- Must use alternative start methods:
  - Mobile app (RemoteStartTransaction via OCPP)
  - Backend remote start
  - Pre-authorized sessions (if configured)

### Troubleshooting (Won't Fix Hardware Fault)

**Attempts that WON'T resolve RYRR20I fault:**
- ✗ **Power cycling** - No effect on hardware failure
- ✗ **Factory reset** - Clears software config, not hardware fault
- ✗ **Firmware update** - Software cannot fix hardware failure
- ✗ **Check wiring** - RYRR20I is internal module, not wiring issue
- ✗ **Try different RFID cards** - Module fault, not card issue
- ✗ **Disable/enable RFID in settings** - Module hardware failed

### Diagnosis

**Log Analysis:**
1. Extract SystemLog and all rotated logs (SystemLog.1, SystemLog.2, etc.)
2. Count RYRR20I error occurrences:
   ```bash
   grep -i "RYRR20I.*fail\|RYRR20I.*time out" SystemLog* | wc -l
   ```
3. If count **>100**: Hardware fault confirmed
4. If count **>1000**: Severe fault, charger unusable for RFID

**Field Testing:**
1. Power cycle charger
2. Test with known-good RFID card
3. Check SystemLog for RYRR20I errors after tap attempt
4. If errors persist → Hardware RMA required

### Resolution

**CRITICAL: CHARGER REPLACEMENT REQUIRED**

- RFID module (RYRR20I) is **NOT a serviceable spare part**
- Cannot be replaced independently by field technicians
- Entire charger unit must be replaced under warranty
- Escalate to Delta for RMA process

**Temporary Workaround:**
- Disable RFID requirement in backend configuration
- Enable app-only authentication (RemoteStartTransaction)
- May require backend support to adjust authorization settings

### Escalation

**Priority:** CRITICAL - Hardware RMA required  
**Action:** Open Delta support ticket with:
- Charger serial number
- Firmware version
- Log excerpts showing RYRR20I errors
- Error count (e.g., "51,095 RYRR20I errors")
- Impact statement (e.g., "RFID non-functional, users cannot authenticate")

**Expected Resolution Time:** Depends on warranty status and Delta RMA process

### Known Instances

**Federation University (July 2024):**
- **Charger:** KKB240500004WE
- **Error Count:** 51,095 RYRR20I errors
- **Outcome:** Charger replaced under warranty
- **Timeframe:** Issues persisted for weeks before replacement

**See:** [Federation University Case Study](../case-studies/federation_university.md)

---

## MCU Communication Errors

### Overview

**MCU:** Microcontroller Unit - low-level hardware controller for charger  
**MPU:** Main Processing Unit - runs OpenWrt, handles OCPP, network, etc.  
**Communication:** MCU and MPU communicate via internal UART (serial)

### Pattern Detection

**Log Pattern:**
```
Send Command 0x[0-9A-Fa-f]+ to MCU False
```

**Example:**
```
Nov 27 03:30:27.595 OpenWrt user.info : [IntComm] Send Command 0x 102 to MCU False, Resend Command 0 time
```

**What It Means:**
- MPU attempting to send command to MCU
- MCU not responding or rejecting command
- Command format: Hexadecimal (e.g., 0x102, 0x201)
- Retry count shown (e.g., "Resend Command 0 time" = first attempt)

### Normal vs. Problematic MCU Errors

**Normal (Benign):**
- **During startup:** 1-3 retries that eventually succeed
- **During reboot:** MCU initializing, may miss initial commands
- **Isolated instances:** Single error, followed by success
- **Low retry count:** 0-1 retries before success

**Problematic (Concerning):**
- **Continuous failures:** All 3 retries exhausted, command never succeeds
- **During operation:** Errors appearing during active charging (not reboot)
- **High frequency:** Multiple errors per minute
- **Command-specific:** Same command (e.g., 0x102) failing repeatedly

**Critical (Hardware Fault):**
- MCU errors followed by hard reset or system crash
- Complete loss of communication (MCU unresponsive)
- Associated with EV0110 error code (Internal Comm Fail)
- Charger enters Faulted state

### Common Scenarios

**Scenario 1: Startup (Normal)**
```
[Reboot sequence starts]
Send Command 0x102 to MCU False, Resend Command 0 time
Send Command 0x102 to MCU True, Resend Command 1 time  ← Success on retry
[Charger continues normal operation]
```

**Scenario 2: Transient Issue (Monitor)**
```
Send Command 0x201 to MCU False, Resend Command 0 time
Send Command 0x201 to MCU True, Resend Command 1 time  ← Success on retry
[No further errors for hours/days]
```

**Scenario 3: Persistent Fault (Critical)**
```
Send Command 0x102 to MCU False, Resend Command 0 time
Send Command 0x102 to MCU False, Resend Command 1 time
Send Command 0x102 to MCU False, Resend Command 2 time
Send Command 0x102 to MCU False, Resend Command 3 time  ← All retries failed
[System may crash or enter fault state]
```

### Thresholds

- **>5 failures (all retries exhausted):** Flag for investigation
- **>20 failures:** Likely hardware communication issue
- **>100 failures:** Critical MCU fault, charger replacement may be needed

**Note:** Count FAILURES (retries exhausted), not individual retry attempts

### Diagnosis

**Log Analysis:**
1. Search for MCU communication failures
2. Check retry counts (0, 1, 2, 3)
3. Determine if failures eventually succeed
4. Look for patterns (specific commands, time of day, reboot correlation)

**Field Testing:**
1. Power cycle charger
2. Monitor SystemLog for MCU errors during boot
3. If errors clear after boot → Normal
4. If errors persist during operation → Investigate further

### Resolution

**If Normal Startup Errors:**
- No action required
- Monitor for frequency increase

**If Persistent Errors:**
1. Power cycle charger (full power off, wait 30 seconds, power on)
2. Check internal connections (requires technician)
3. Firmware update (may resolve timing issues)
4. If persists → Escalate for hardware RMA

**Associated Error Codes:**
- **EV0110** - Internal Comm Fail (MPU/MCU) - See [Error Codes](../reference/error_codes.md)

---

## Backend Network Disconnects

### Pattern Detection

**Log Pattern:**
```
Backend connection fail
```

**Example:**
```
Jan 22 03:54:01.046 OpenWrt user.info InfraMgmt[2454]: [Infra] Backend connection fail
```

**Associated Event Codes:**
- **EV0117** - Disconnect from Backend (Ethernet)
- **EV0118** - Disconnect from Backend (WiFi)
- **EV0119** - Disconnect from Backend (3G)
- **EV0123** - Disconnect from AP (WiFi)
- **EV0124** - Disconnect from APN (3G)

**See:** [Error Codes Reference](../reference/error_codes.md) and [OCPP Protocol](ocpp_protocol.md)

### Thresholds

**Normal:**
- **<5 per day:** Typical network variability
- **Quick reconnection:** <10 seconds between disconnect and reconnect
- **Isolated events:** Not clustered

**Concerning:**
- **10-50 per day:** Suggests network instability
- **Slow reconnection:** >30 seconds to reconnect
- **Random times:** No clear pattern

**Critical:**
- **>100 per day:** Cable, switch, or infrastructure problem
- **>1000 total (over weeks):** Chronic network issue
- **Clustered:** Multiple disconnects within minutes (pattern)

### Common Causes

**Physical Layer:**
1. **Ethernet cable damaged** - Cuts, kinks, wear at connectors
2. **Loose RJ45 connection** - Cable not fully seated
3. **Network switch port issue** - Port flapping, power issue
4. **Switch failure** - Switch rebooting, firmware bug

**Network Layer:**
5. **Firewall/NAT timeout** - Connection state timeout
6. **Port blocking** - Firewall dropping OCPP WebSocket
7. **Proxy interference** - Corporate proxy breaking WebSocket

**Backend Server:**
8. **OCPP server downtime** - Maintenance, crashes
9. **Server overload** - Too many chargers, insufficient capacity
10. **DNS issues** - Backend hostname not resolving

**Cellular (3G/4G):**
11. **Weak signal** - Poor coverage, tower handoff
12. **APN misconfiguration** - Incorrect carrier settings
13. **SIM card issue** - Expired, deactivated, damaged

**Correlation:**
- May correlate with SetChargingProfile timeout bug (firmware issue causing disconnects)
- See [Firmware Bugs](../reference/firmware_bugs.md)

### Diagnosis

**Step 1: Check Pattern**
- Count disconnects over 24 hours
- Look for time-of-day patterns (e.g., every hour = heartbeat issue)
- Check reconnection times (seconds vs minutes)

**Step 2: Check Physical Connections**
- Verify Ethernet cable fully seated
- Test with known-good cable
- Check switch port lights (link/activity LEDs)
- Verify switch port configuration (speed, duplex)

**Step 3: Check Network Path**
- Ping backend server from charger (if possible)
- Check firewall logs for dropped connections
- Verify OCPP WebSocket port open (typically 80/443/9000)
- Test backend from different network (isolate charger vs backend issue)

**Step 4: Check Backend Server**
- Contact backend provider (e.g., GreenFlux, Chargefox)
- Ask about server status, maintenance windows
- Check backend monitoring for server health

### Resolution

**Physical Layer Fixes:**
1. Replace Ethernet cable
2. Reseat cable connections
3. Change switch port
4. Replace network switch

**Network Layer Fixes:**
5. Adjust firewall timeout settings
6. Whitelist OCPP traffic
7. Remove proxy for OCPP WebSocket

**Backend Server Fixes:**
8. Escalate to backend provider
9. Request server capacity upgrade
10. Verify DNS resolution

**Cellular Fixes:**
11. Relocate antenna for better signal
12. Verify APN settings with carrier
13. Replace SIM card

---

## Logging Gaps

### Pattern Detection

**Method:** Compare timestamps between log entries, identify gaps **>24 hours**

**Example:**
```
Last log: Dec 23 07:12:05
Next log: Jan 10 01:13:37
Gap: 18 days
```

### Thresholds

**Normal:**
- **<1 hour gaps:** Brief reboots, normal operation
- **<6 hour gaps:** Extended reboots, firmware updates

**Concerning:**
- **>24 hour gaps:** System crashes, power loss
- **>7 day gaps:** Extended power outage, logging system failure

**Critical:**
- **>30 day gaps:** Major issue, requires investigation

### Common Causes

1. **Power loss** - Site power outage, circuit breaker trip
2. **System crash** - Firmware bug, kernel panic, watchdog timeout
3. **Logging system failure** - Disk full, filesystem corruption
4. **Intentional shutdown** - Maintenance, relocation
5. **Charger replacement** - Unit swapped, logs from old charger

### Diagnosis

**Log Analysis:**
1. Identify gap start (last log before gap)
2. Identify gap end (first log after gap)
3. Check first log after gap for reboot indicators:
   - "syslogd started: BusyBox"
   - "Init message queue"
   - "Fw2Ver:" (firmware version)
4. Look for crash/panic messages before gap

**Field Investigation:**
1. Ask customer: "Was there a power outage during this period?"
2. Check electrical panel: "Were circuit breakers tripped?"
3. Verify charger serial number: "Was charger replaced?"

### Resolution

**If Power Loss:**
- Verify site electrical system stable
- Consider UPS for charger network equipment

**If System Crashes:**
- Check firmware version (may need update)
- Escalate to Delta with crash logs

**If Logging System Failure:**
- Firmware update (may fix filesystem issues)
- Factory reset (clears logs, resets logging system)

---

## Firmware Version Tracking

### Pattern Detection

**Log Pattern:**
```
Fw2Ver: XX.XX.XX.XX
```

**Example:**
```
Jan 22 01:54:55.130 OpenWrt user.info InfraMgmt[2481]: [Infra] Fw2Ver: 01.26.39.00
```

### Purpose

- **Track firmware versions** - Know what version charger is running
- **Verify firmware updates** - Confirm update completed successfully
- **Correlate bugs with versions** - Identify firmware-specific issues

**Example Firmware Versions:**
- 01.25.13 - Older stable version
- 01.26.37 - Known issues with RemoteStartTransaction rejections
- 01.26.38 - Improved RemoteStartTransaction handling
- 01.26.39 - Current version (as of Jan 2026)

### Detection

**Analyzer automatically extracts firmware version from logs:**
- Searches for "Fw2Ver:" pattern
- Reports in CSV output and summary
- Helps identify firmware-related issues

### Known Firmware Issues

- **SetChargingProfile timeout** (<01.26.40?) - See [Firmware Bugs](../reference/firmware_bugs.md)
- **RemoteStartTransaction rejections** (01.26.37) - See [OCPP Protocol](ocpp_protocol.md)

---

## Reboot Detection

### Pattern Detection

**Primary Pattern:**
```
syslogd started: BusyBox v1.28.4
```

**Secondary Indicators:**
- Process IDs reset to low values (e.g., [2447], [2454])
- "Init message queue" logs
- "dnsmasq: DNS rebinding protection is active"

### Normal Reboot Sequence

```
Jul 20 03:30:36.749 OpenWrt syslog.info syslogd started: BusyBox v1.28.4
Jul 20 03:30:37.394 OpenWrt user.notice dnsmasq: DNS rebinding protection is active
Jul 20 03:30:37.965 OpenWrt user.info InfraMgmt[2447]: [Infra] Init message queue:0
Jul 20 03:30:38.123 OpenWrt user.info : [LED] Set LED mode
Jul 20 03:30:38.456 OpenWrt user.info : [IntComm] Send Command 0x102 to MCU
```

**Expected Sequence:**
1. BusyBox syslogd starts
2. dnsmasq starts (DNS/DHCP services)
3. InfraMgmt process initializes
4. LED controller initializes
5. MCU commands sent
6. Network configuration applied

### Causes of Reboots

**Intentional:**
- Firmware update
- Factory reset
- Backend-initiated reboot (via OCPP Reset command)
- Power cycle by user/technician

**Unintentional:**
- Watchdog timeout (software hang detected)
- Kernel panic (critical software error)
- Power loss/brown-out
- Hardware fault triggering reset

### Diagnosis

**Frequency:**
- **<1 per month:** Normal (updates, maintenance)
- **1-5 per week:** Investigate for software issues
- **>1 per day:** Critical - firmware bug or hardware fault

**Pattern:**
- **After firmware update:** Expected
- **Random times:** Watchdog timeout, software hang
- **During charging:** May indicate load-related issue
- **Same time daily:** Scheduled reboot (unusual for charger)

---

**Related Knowledge:**
- [Error Codes](../reference/error_codes.md) - Hardware fault error codes
- [OCPP Protocol](ocpp_protocol.md) - Network disconnect correlation
- [Firmware Bugs](../reference/firmware_bugs.md) - Known firmware issues
- [Federation University Case](../case-studies/federation_university.md) - RFID fault example

---

**Last Updated:** 2026-01-26  
**Source:** Field cases, Delta documentation, SystemLog analysis
