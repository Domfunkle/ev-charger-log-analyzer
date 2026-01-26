# Federation University Case Study (July-December 2024)

**Site:** Federation University, Australia  
**Duration:** July 2024 - December 2024  
**Chargers Affected:** 2 units (KKB233100224WE, KKB240500004WE)  
**Issues:** Dual-source current limiting, RFID module failure, configuration mismatches  
**Outcome:** One charger replaced (RFID fault), one charger fixed (configuration corrected)

---

## Overview

Federation University experienced multiple complex issues affecting two Delta AC MAX chargers:

1. **KKB233100224WE** - Dual-source current limiting (OCPP + LMS Modbus)
2. **KKB240500004WE** - Catastrophic RFID module failure

Both chargers exhibited symptoms that were initially misdiagnosed as charger faults, but revealed complex configuration issues and one genuine hardware failure.

---

## Charger 1: KKB233100224WE (Dual-Source Current Limiting)

### Timeline

**July 2024:** Initial reports of charging failures  
**July-November 2024:** Intermittent issues, user complaints  
**December 2024:** Deep log analysis reveals root causes  
**December 2024:** Configuration corrected, charger operational

### Symptoms

**User-Facing:**
- Charger starts charging, then stops after minutes/hours
- State stuck in "Preparing" indefinitely
- Unable to complete full charging sessions
- Intermittent operation (sometimes works, sometimes doesn't)

**System Behavior:**
- OCPP state: Charging → Preparing (repeated cycles)
- No power delivery despite vehicle connected
- Yellow LED (not red/fault)
- No PWM pilot signal generated

### Diagnosis

**Initial Hypothesis:** Charger hardware fault

**Log Analysis Revealed THREE Simultaneous Issues:**

#### Issue 1: Low-Current OCPP Profiles (<6A)

**Pattern:**
```
Jul 18 20:00:07.328: SetChargingProfile...limit=0.100000
Aug 05 14:23:19.445: SetChargingProfile...limit=0.100000
[11 total occurrences of limit <6A]
```

**What It Meant:**
- GreenFlux/CPMS backend sending 0.1A current limits
- Charger suspending charging per IEC 61851-1 (6A minimum)
- State: Charging → Preparing (correctly implementing standard)

**Root Cause:** Backend load management misconfiguration

#### Issue 2: LMS Modbus Communication Failures

**Pattern:**
```
Jul 21 10:11:31.491: [Load_Mgmt_Comm] Communication Timeout ENABLE change to Disabled
[24 total Load_Mgmt_Comm errors]
```

**Associated Events:**
```
EventLog: 144 EV0103 (LIMIT_toNoPower) events
```

**What It Meant:**
- Local Load Management System (Modbus master) stopped responding
- Charger entered timeout fallback mode
- Modbus register 40204 (Fallback Power) = **0x0000** (0W)
- Charger limiting to 0A, unable to deliver power

**Root Cause:** Modbus misconfiguration persisting after LMS removal

#### Issue 3: Configuration Mismatch (Discovered Post-Fix)

**After fixing Modbus registers:**
```
EventLog: EV0082 (AC Output OCP - Over-Current Protection) appeared
```

**What It Meant:**
- DIP switches configured for lower current (e.g., 16A)
- OCPP backend sending 32A SetChargingProfile
- Charger using MINIMUM (16A from DIP switches)
- But detecting configuration mismatch → EV0082 fault

**Root Cause:** Misalignment of DIP switches, OCPP profile, and Modbus settings

### The Complexity: Dual-Source + Hidden Third Issue

**Why Diagnosis Was Difficult:**

```
Issue 1 (OCPP):     0.1A limit → Suspends charging
Issue 2 (Modbus):   0W fallback → Suspends charging
Issue 3 (Hidden):   EV0082 masked by Issues 1 & 2

Result: Charger stuck in Preparing state
Diagnosis: Required checking BOTH OCPP logs AND Modbus configuration
```

**Fixing Issue 2 revealed Issue 3:**
- When Modbus registers corrected (0W → MAX)
- Charger attempted to start charging
- EV0082 fault immediately appeared (OCPP 32A > DIP 16A)
- Required THIRD fix: Align DIP switches, OCPP, Modbus

### Resolution

**Step 1: Fix OCPP Backend**
- Contacted GreenFlux/CPMS provider
- Requested minimum current limits set to ≥6A
- Backend adjusted load management algorithm
- Low-current profiles stopped

**Step 2: Fix Modbus Registers**
- Read registers via Modbus RTU:
  - 40202 (Timeout Enable) = 0x0001 (enabled)
  - 40204-40205 (Fallback Power) = **0x0000** (0W) ← ROOT CAUSE
- Factory reset charger (cleared registers)
- Verified registers after reset:
  - 40202 = 0x0000 (disabled)
  - 40204 = 0xFFFF (max)
  - 41601 = 0xFFFF (max)

**Step 3: Fix Configuration Mismatch**
- Checked DIP switch configuration (physical inspection)
- Verified current rating (16A vs 32A)
- Aligned all three sources:
  - DIP switches: Set to maximum rated current
  - OCPP backend: Adjusted profiles to ≤ DIP rating
  - Modbus 41601: Set to 0xFFFF (max)
- EV0082 fault cleared

**Step 4: Test and Verify**
- Charger started charging successfully
- No Preparing → Charging cycles
- No EV0103 events
- No EV0082 faults
- Full charging sessions completed

### Lessons Learned

**Diagnosis:**
1. **Check ALL THREE current sources:** DIP switches, OCPP, Modbus
2. **Dual-source issues are COMPLEX:** OCPP and Modbus can both limit simultaneously
3. **Fixing one issue may reveal another:** Modbus fix exposed EV0082 mismatch
4. **Log analysis is CRITICAL:** Without OCPP and Modbus logs, impossible to diagnose

**Modbus Configuration:**
5. **Modbus registers PERSIST:** Even after LMS disconnection, registers remain configured
6. **0W fallback is DANGEROUS:** Should be ≥1400W or 0xFFFF
7. **Factory reset may not clear Modbus:** Manually verify registers afterward

**Standards Compliance:**
8. **Charger behavior was CORRECT:** Suspending at <6A per IEC 61851-1 is standards-compliant
9. **Not a charger fault:** All issues were configuration/backend problems

**Configuration Hierarchy:**
10. **Charger uses MINIMUM:** Of DIP, OCPP, Modbus - all three must align

### Technical Details

**Modbus Register Values (Before Fix):**
```
Reg 40202 = 0x0001  (Timeout ENABLED)
Reg 40203 = 0x0258  (600 second timeout)
Reg 40204 = 0x0000  (Fallback power = 0W) ← CRITICAL
Reg 41601 = 0x????  (Unknown power limit)
```

**Modbus Register Values (After Fix):**
```
Reg 40202 = 0x0000  (Timeout DISABLED)
Reg 40203 = 0x0258  (600 seconds, but disabled)
Reg 40204 = 0xFFFF  (Fallback power = MAX)
Reg 41601 = 0xFFFF  (Power limit = MAX)
```

**OCPP Profile Examples (Before Fix):**
```
SetChargingProfile limit=0.100000  (0.1A - below minimum)
SetChargingProfile limit=3.500000  (3.5A - below minimum)
```

**OCPP Profile Examples (After Fix):**
```
SetChargingProfile limit=16.000000  (16A - above minimum)
SetChargingProfile limit=24.000000  (24A - above minimum)
```

### Impact Statistics

**Before Fix:**
- 11 low-current OCPP profiles (<6A)
- 24 Load_Mgmt_Comm errors
- 144 EV0103 (LIMIT_toNoPower) events
- Charger non-functional for weeks
- Multiple user complaints

**After Fix:**
- Zero low-current profiles
- Zero Load_Mgmt_Comm errors
- Zero EV0103 events
- Zero EV0082 faults
- Charger fully operational

---

## Charger 2: KKB240500004WE (RFID Module Failure)

### Timeline

**July 2024:** Initial reports of RFID not working  
**July-December 2024:** RFID failures escalate  
**December 2024:** Log analysis confirms hardware fault  
**December 2024:** Charger replaced under warranty

### Symptoms

**User-Facing:**
- RFID cards not recognized (tap has no effect)
- Users unable to start charging via RFID
- Multiple cards tested - all failed
- Must use mobile app to start charging

**System Behavior:**
- Continuous RYRR20I error messages in SystemLog
- Errors persist through power cycles
- Errors persist through factory reset
- Errors persist through firmware update

### Diagnosis

**Log Analysis:**
```
[RFID] RYRR20I Register write request 2 fail
[RFID] RYRR20I Set StandBy Mode fail
[RFID] RYRR20I Reset fail
[RYRR20I_Check_Request] Time Out
[...repeated 51,095 times...]
```

**Error Count:**
- **51,095 RYRR20I errors** over weeks/months
- Average: Hundreds to thousands per day
- Pattern: Continuous, no improvement

**Conclusion:** **Catastrophic RFID module (RYRR20I) hardware failure**

### Troubleshooting Attempts (All Failed)

1. ✗ Power cycle charger - No effect
2. ✗ Factory reset - No effect
3. ✗ Firmware update - No effect
4. ✗ Test with multiple RFID cards - All failed
5. ✗ Check wiring/connections - Hardware fault, not connection issue

### Resolution

**CHARGER REPLACEMENT REQUIRED**

- RFID module (RYRR20I) is NOT a serviceable spare part
- Cannot be replaced independently
- Entire charger unit replaced under warranty
- Escalated to Delta for RMA process

**Temporary Workaround:**
- Disabled RFID requirement in backend
- Users instructed to use mobile app (RemoteStartTransaction)
- Backend configuration adjusted to allow app-only authorization

### Lessons Learned

1. **RYRR20I failures are NON-SERVICEABLE:** Only resolution is charger replacement
2. **High error counts confirm hardware fault:** >1000 errors = replacement required
3. **Firmware/reset cannot fix hardware:** Don't waste time on software troubleshooting
4. **Temporary workaround possible:** App-only authentication until replacement arrives

---

## Summary: Dual-Site, Dual-Issue Case

**Key Takeaways:**

1. **Complex Diagnosis Required:**
   - KKB233100224WE: Three simultaneous configuration issues
   - KKB240500004WE: Genuine hardware failure
   - Different root causes, similar symptoms (charging failures)

2. **Log Analysis Critical:**
   - OCPP logs revealed backend low-current profiles
   - SystemLog revealed Modbus communication failures
   - EventLog revealed LIMIT_toNoPower and RFID errors
   - Without logs, diagnosis impossible

3. **Not Always Charger Fault:**
   - KKB233100224WE: 100% configuration issues (OCPP + Modbus + DIP mismatch)
   - KKB240500004WE: 100% hardware failure (RYRR20I module)
   - But symptoms appeared similar to users

4. **Configuration Hierarchy Matters:**
   - ALL THREE must align: DIP switches, OCPP, Modbus
   - Charger uses MINIMUM of three sources
   - Misalignment causes faults (EV0082) or suspension (Preparing state)

5. **Standards Compliance Is Not a Fault:**
   - Charger suspending at <6A is CORRECT behavior per IEC 61851-1
   - Technician must understand standards to avoid misdiagnosis

---

**Related Knowledge:**
- [Current Limiting Patterns](../patterns/current_limiting.md) - Dual-source issues
- [Modbus Registers](../reference/modbus_registers.md) - 0W fallback problem
- [Hardware Faults](../patterns/hardware_faults.md) - RFID module failures
- [Error Codes](../reference/error_codes.md) - EV0103, EV0082
- [OCPP Protocol](../patterns/ocpp_protocol.md) - Low-current profiles

---

**Last Updated:** 2026-01-26  
**Source:** Field logs, email chain, Modbus register reads, Daniel Nathanson diagnosis  
**Status:** Resolved (KKB233100224WE operational, KKB240500004WE replaced)
