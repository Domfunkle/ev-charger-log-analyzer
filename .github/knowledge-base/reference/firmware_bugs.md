# Delta AC MAX Known Firmware Bugs

**Purpose:** Document confirmed firmware bugs, workarounds, and escalation status  
**Audience:** Field engineers, support staff, firmware team

---

## CRITICAL: SetChargingProfile Timeout Bug (Firmware <01.26.40)

### Overview
**Pattern:** `"SetChargingProfileConf process time out"` in OCPP16J_Log.csv  
**Severity:** CRITICAL - Affects entire multi-charger sites  
**Firmware Affected:** <01.26.40 (unconfirmed upper bound)  
**First Discovered:** October 2024 (load management deployments)

### Symptoms
- Frequent backend disconnects correlating with smart charging profile updates
- Chargers appear to reboot/reconnect when receiving OCPP SetChargingProfile commands
- Pattern repeats hundreds or thousands of times per charger
- Affects load management deployments using CPMS/GreenFlux backend systems
- Residents experience intermittent charging failures
- CPMS loses capacity allocation visibility across site
- Load management coordination fails

### Root Cause

**The Bug:**
1. Charger advertises support for **20 periods** in `ChargingScheduleMaxPeriods` via GetConfiguration
2. Actual firmware implementation can only handle **10 periods max**
3. When backend sends 20-period profiles (believing charger supports it), charger times out processing
4. Returns **empty status response** instead of "Accepted" or "Rejected"
5. Connection drops (unclear if charger or backend initiated)
6. Results in cascade of disconnects affecting entire site load management

**GetConfiguration Response (INCORRECT):**
```json
{
  "key": "ChargingScheduleMaxPeriods",
  "readonly": true,
  "value": "20"  ← INCORRECT, should be "10"
}
```

**Actual Behavior When Receiving 20 Periods:**
```
Oct 21 19:06:06.698: [OCPP16J] Received SetChargingProfile with 20 periods
Oct 21 19:06:37.706: [OCPP16J] SetChargingProfileConf process time out (31 seconds)
Oct 21 19:06:37.706: Sends response: [3,"UniqueID",{"status":""}]
<connection drops, charger reconnects>
```

**Expected Behavior:**
- Charger should respond within 2-5 seconds
- Response should be: `{"status":"Accepted"}` or `{"status":"Rejected"}`
- Should NOT disconnect after receiving profile

### Impact

**Site-Wide:**
- Load management coordination fails
- CPMS cannot balance loads across chargers
- Potential for electrical panel overcurrent if all chargers charge simultaneously

**Per Charger:**
- Hundreds to thousands of SetChargingProfile timeouts per day
- Continuous backend disconnects/reconnects
- Intermittent charging availability

**Customer-Facing:**
- EV owner starts charging → backend sends profile → charger times out → disconnect
- Charging session interrupted
- App shows charger offline/unavailable
- Resident complaints, support calls

### Detection

**Log Analysis:**
1. Count `SetChargingProfileConf process time out` in OCPP16J_Log.csv
2. If **>100 occurrences**: Critical firmware bug highly likely
3. Correlate with backend disconnect spikes (EV0117/EV0118/EV0119 events)
4. Check OCPP logs for 20-period SetChargingProfile commands

**Example:**
- Charger with 1,200 SetChargingProfile timeouts over 3 months
- Corresponds to 1,200+ backend disconnects
- Backend logs show sending 20-period profiles
- Charger GetConfiguration shows ChargingScheduleMaxPeriods=20

### Workaround (Temporary)

**Backend Configuration Change:**
1. Contact backend provider (e.g., GreenFlux, Charge Point Operator)
2. Request limiting `ChargingScheduleMaxPeriods` to **10 periods** in their profile generation logic
3. Backend should:
   - Split longer schedules into multiple 10-period profiles
   - OR limit profiles to 10 periods maximum
   - Send SetChargingProfile with ≤10 periods
4. Monitor OCPP logs for reduction in timeout errors
5. Verify backend disconnects decrease

**Verification:**
- SetChargingProfile timeout count should drop to near-zero
- Backend disconnect events should significantly decrease
- Charging sessions should complete without interruption

**Limitations:**
- Workaround requires backend provider cooperation
- May reduce smart charging flexibility (fewer periods)
- Does not fix underlying firmware bug

### Permanent Fix

**Firmware Update Required:**
- Report to Delta as firmware defect
- Request one of:
  1. **Option A:** Correct `ChargingScheduleMaxPeriods` GetConfiguration response to "10" (honest reporting)
  2. **Option B:** Implement actual support for 20 periods (match advertised capability)
- Upgrade all chargers to fixed firmware version (when available)

**Escalation:**
- **Priority:** HIGH - Customer-facing impact, site-wide failures
- **Delta Ticket:** (if available, add ticket number here)
- **Status:** (Update as firmware fix progresses)

### Related Patterns

- **SetChargingProfile Protocol:** See [ocpp_protocol.md](../patterns/ocpp_protocol.md)
- **Backend Disconnects:** See [hardware_faults.md](../patterns/hardware_faults.md)

---

## Factory Reset Register Behavior (Uncertain)

### Issue
**Status:** UNCONFIRMED  
**Impact:** May leave Modbus registers in misconfigured state after factory reset

### Description

It is **uncertain** whether factory reset clears Modbus holding registers to default values.

**What We Know:**
- Factory reset clears OCPP configuration (confirmed)
- Factory reset clears network settings (confirmed)

**What We Don't Know:**
- Whether Modbus registers (40202-40204, 41601, etc.) reset to defaults
- Daniel Nathanson (2024-12-10): "I don't know if it clears the modbus registers to defaults. I haven't tested it."

### Impact

**If Registers Persist After Factory Reset:**
- Charger may remain in misconfigured state even after reset
- Example: Modbus fallback power = 0W persists → charger still stuck in LIMIT_toNoPower
- Technician performs factory reset, assumes issue fixed, but Modbus config remains

### Recommended Practice

**Safer Approach (Until Tested):**
1. **Option A:** Manually write 0xFFFF to critical registers via Modbus RTU **before** factory reset
2. **Option B:** Perform factory reset **then** verify registers afterward via Modbus read
3. **Option C:** Both - reset, then verify, then write if needed

**Critical Registers to Verify:**
- 40202 (Timeout Enable) - should be 0x0000
- 40204-40205 (Fallback Power) - should be 0xFFFF
- 41601-41602 (Power Limit) - should be 0xFFFF

**See:** [Modbus Registers Reference](modbus_registers.md)

### Testing Needed

**To Confirm Behavior:**
1. Set Modbus register to known non-default value (e.g., 40204 = 0x1234)
2. Perform factory reset via charger menu/button
3. Read register 40204 after reset
4. Compare to expected default value

**Result Documentation:**
- If register = default: Factory reset DOES clear Modbus registers ✓
- If register = 0x1234: Factory reset does NOT clear Modbus registers ✗

---

## Future Issues (Template)

### Issue Name
**Pattern:** Log pattern or behavior  
**Severity:** CRITICAL / HIGH / MEDIUM / LOW  
**Firmware Affected:** Version range  
**First Discovered:** Date  

**Symptoms:**
- List observable symptoms

**Root Cause:**
- Technical explanation

**Detection:**
- How to identify in logs

**Workaround:**
- Temporary mitigation steps

**Permanent Fix:**
- Required firmware update or configuration

**Escalation:**
- Priority and status

---

**Related Knowledge:**
- [OCPP Protocol Patterns](../patterns/ocpp_protocol.md)
- [Modbus Registers](modbus_registers.md)
- [Error Codes](error_codes.md)
- [Case Studies](../case-studies/) - Real-world bug impacts

---

**Last Updated:** 2026-01-26  
**Maintainer:** Add new firmware bugs as they are discovered and confirmed
