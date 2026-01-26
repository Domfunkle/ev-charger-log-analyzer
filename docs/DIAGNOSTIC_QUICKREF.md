# Delta AC MAX Charger - Diagnostic Quick Reference

**For Field Engineers & Support Staff**

Quick diagnosis guide mapping symptoms to likely causes and what to check in logs.

---

## 🚨 Common Issues Quick Lookup

### Charger Starts Charging Then Immediately Stops

**Symptom:** Charging session begins, then charger returns to "Preparing" state within seconds/minutes.

**Likely Causes:**
1. **Low-current OCPP profile** (<6A) from backend
2. **Modbus LMS misconfiguration** (0W fallback power)
3. **Dual-source current limiting** (OCPP + Modbus both active)

**What to Check in Logs:**
- OCPP log: `SetChargingProfile` with `limit=0.100000` or other <6A values
- SystemLog: `LIMIT_toNoPower` events (EV0103)
- SystemLog: `Load_Mgmt_Comm` timeout errors

**Root Cause:**
Per IEC 61851-1, Mode 3 AC charging requires vehicle to **stop charging** when current limit <6A. This is CORRECT charger behavior - the issue is with the limiting source.

**Fix:**
- If OCPP profiles: Contact backend provider (check why 0A profiles being sent)
- If Modbus: Check registers 40204, 40205 (should be 0xFFFF, not 0x0000)
- If both: Determine which limiting source is intended, disable/fix the other

**Reference:** [Federation University Case Study](../.github/knowledge-base/case-studies/federation_university.md)

---

### RFID Cards Not Working

**Symptom:** Charger not responding to RFID card swipes, intermittent authorization failures.

**Likely Cause:** Faulty RFID reader module (hardware fault)

**What to Check in Logs:**
- SystemLog: `RYRR20I` errors (RFID reader module)
  - `RYRR20I Register write request fail`
  - `RYRR20I Set StandBy Mode fail`
  - `RYRR20I Reset fail`
  - `RYRR20I_Check_Request] Time Out`

**Diagnostic Threshold:**
- **<10 errors:** Normal, intermittent communication glitch
- **10-100 errors:** Monitor, may worsen over time
- **>100 errors:** Hardware fault confirmed - requires charger replacement

**Fix:** Delta AC MAX does not have user-replaceable RFID module - whole charger must be replaced if under warranty.

---

### "Unlock Port Request Rejected" (ChargeFox App)

**Symptom:** User presses "Unlock Connector" in app, gets rejection error.

**OCPP Translation:** `RemoteStartTransaction` response: `Rejected`

**Likely Cause:** Vehicle not connected when remote start requested.

**What to Check in Logs:**
- OCPP log: Look for `RemoteStartTransaction` followed by `Rejected`
- OCPP log: Check connector state BEFORE rejection
  - `"status":"Available"` = No vehicle connected → **Expected Rejection**
  - `"status":"Preparing"` = Vehicle connected → Investigate further

**Expected Behavior:**
OCPP standard allows RemoteStartTransaction in Available state, but ChargeFox recommends users **plug in first** before unlocking via app.

**Fix:**
- Educate users: Plug in FIRST, then unlock via app
- Most "Rejected" errors are user workflow issues, not charger faults

**Reference:** [OCPP Protocol](../.github/knowledge-base/patterns/ocpp_protocol.md#remotestartaction-rejected)

---

### Backend Disconnects / Communication Failures

**Symptom:** Charger shows offline in backend portal, intermittent connectivity.

**Likely Causes:**
1. **Network connectivity** (Wi-Fi/4G signal, firewall blocking)
2. **SetChargingProfile timeout bug** (firmware <1.26.38)
3. **Certificate expiration** (OCPP over TLS/WSS)

**What to Check in Logs:**
- SystemLog: `Backend connection fail` count
  - <10: Normal intermittent issues
  - 10-50: Investigate network quality
  - >50: Systematic problem (firmware bug, network infrastructure)

- OCPP log: `SetChargingProfileConf process time out`
  - Indicates firmware bug (advertises 20 periods, handles only 10)
  - **Fix:** Upgrade to firmware ≥1.26.38

**Network Diagnostics:**
- Check Wi-Fi signal strength (if applicable)
- Ping backend server from site network
- Check firewall rules (allow WebSocket traffic to OCPP server)

---

### EV0082 - Overcurrent Protection Triggered

**Symptom:** Charger faults immediately when attempting to charge, red LED.

**Likely Cause:** Configuration mismatch - OCPP profile current exceeds DIP switch setting.

**Configuration Hierarchy:**
Charger uses **MINIMUM** of:
1. DIP switch hardware limit (e.g., 16A)
2. OCPP SetChargingProfile limit (e.g., 32A)
3. Modbus Power Limit register 41601 (e.g., 0xFFFF = unlimited)

**Example Fault Scenario:**
- DIP switches: 16A maximum
- OCPP profile: 32A limit
- Charger attempts 32A → Exceeds hardware limit → EV0082 fault

**What to Check in Logs:**
- OCPP log: `SetChargingProfile` with `limit=32.000000` (or other high value)
- EventLog: `EV0082` - Overcurrent protection

**Fix:**
- Adjust OCPP profile to match or be below DIP switch setting
- OR adjust DIP switches to support higher current (if wiring permits)
- Ensure Modbus registers 41601, 41602 = 0xFFFF (unlimited)

**Reference:** [Error Codes](../.github/knowledge-base/reference/error_codes.md#ev0082---overcurrent-protection)

---

### Modbus/LMS Issues (Multi-Charger Sites)

**Symptom:** Charger limiting itself even when disconnected from Load Management System.

**Likely Cause:** Modbus fallback power register set to 0W.

**What to Check in Logs:**
- SystemLog: `Load_Mgmt_Comm` errors (indicates Modbus was in use)
- EventLog: `LIMIT_toNoPower` (EV0103) persisting after LMS disconnected

**Modbus Register Check:**
Use Modbus scanner to read registers (Modbus TCP, port 502):
- 40202 (Comm. Timeout EN): Should be 0x0000 (disabled for standalone)
- 40203 (Comm. Timeout): Can be 0x0258 (600s) if timeout enabled
- 40204, 40205 (Fallback Power): **Should be 0xFFFF** (unlimited)
- 41601, 41602 (Power Limit): **Should be 0xFFFF** (unlimited)

**Diagnostic Questions to Ask Customer:**
1. "Did you previously use Modbus to control this charger?"
2. "Was the charger part of a load management system?"
3. "Did you write to any Modbus registers during testing?"

**Fix:**
- Write 0xFFFF to registers 40204, 40205, 41601, 41602
- If uncertain, perform factory reset (may not clear Modbus registers - test and verify)

**Reference:** [Modbus Registers](../.github/knowledge-base/reference/modbus_registers.md)

---

## 📊 Log File Locations

**Extracted ZIP structure:**
```
[YYYY.MM.DD-HH.MM]SERIALNUMBER/
├── Storage/
│   ├── SystemLog/
│   │   ├── SystemLog         (main syslog, most recent)
│   │   ├── SystemLog.0       (rotated logs, older)
│   │   ├── OCPP16J_Log.csv   (OCPP protocol messages)
│   │   └── OCPP16J_Log.csv.0 (rotated OCPP logs)
│   ├── EventLog/
│   │   └── Events.csv        (error event codes, timestamps)
│   └── Config/
│       └── evcs              (configuration, ChargBox ID)
```

---

## 🔍 Quick Log Searches

**Using grep or text search tools:**

### Find Low-Current Profiles
```bash
grep -i "SetChargingProfile.*limit=" OCPP16J_Log.csv | grep -E "limit=[0-5]\."
```

### Find RFID Errors
```bash
grep "RYRR20I" SystemLog
```

### Find Load Management Errors
```bash
grep "Load_Mgmt_Comm" SystemLog
```

### Find OCPP Rejections
```bash
grep "Rejected" OCPP16J_Log.csv
```

### Find State Transitions
```bash
grep "StatusNotification" OCPP16J_Log.csv
```

### Find Backend Disconnects
```bash
grep "Backend connection fail" SystemLog | wc -l
```

---

## 🛠️ Firmware Versions

### Known Issues by Firmware

**1.26.37:**
- SetChargingProfile timeout bug (advertises 20 periods, handles only 10)
- Some units experiencing RemoteStartTransaction intermittent rejections
- **Recommendation:** Upgrade to ≥1.26.38

**1.26.38:**
- SetChargingProfile timeout bug **fixed**
- Improved OCPP stability
- **Recommendation:** Current stable version

**1.25.13:**
- Older but stable
- Missing some newer features
- **Recommendation:** Upgrade if experiencing issues

---

## 📞 Escalation Checklist

Before escalating to engineering:

- [ ] Checked firmware version (SystemLog: `Fw2Ver:`)
- [ ] Counted backend disconnects (<10 normal, >50 investigate)
- [ ] Searched for error codes in EventLog
- [ ] Checked OCPP log for Rejected/Timeout patterns
- [ ] Verified DIP switch settings vs OCPP profiles
- [ ] Asked customer about Modbus/LMS usage
- [ ] Collected full log ZIP (not screenshots)

**Include in escalation:**
1. Full log ZIP file
2. Firmware version
3. Timeline of issue (when started, how often occurs)
4. What user was doing when issue occurred
5. Any recent changes (firmware update, config changes, network changes)

---

## 📚 Full Documentation

For detailed technical knowledge:
- [Main Project README](../README.md) - Usage, installation
- [Delta AC MAX Usage Guide](delta_ac_max_usage.md) - CLI options
- [Knowledge Base](../.github/knowledge-base/) - Complete technical knowledge
  - [Error Codes](../.github/knowledge-base/reference/error_codes.md) - All 43 Delta error codes
  - [OCPP Protocol](../.github/knowledge-base/patterns/ocpp_protocol.md) - OCPP 1.6 details
  - [Current Limiting](../.github/knowledge-base/patterns/current_limiting.md) - IEC 61851-1 standard
  - [Hardware Faults](../.github/knowledge-base/patterns/hardware_faults.md) - RFID, MCU, network
  - [Modbus Registers](../.github/knowledge-base/reference/modbus_registers.md) - LMS configuration

---

**Last Updated:** 2026-01-26  
**Maintainer:** Daniel Nathanson (dnathanson@nhp.com.au)  
**Analyzer Version:** 0.0.1 (Development)
