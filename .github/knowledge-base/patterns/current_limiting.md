# Current Limiting Patterns

**Purpose:** Understand charger behavior when current/power limiting is applied  
**Critical Context:** Current limiting can come from THREE sources - understanding which is key to diagnosis  
**Standard:** IEC 61851-1 Mode 3 AC Charging (6A minimum)

---

## IEC 61851-1 Standard Behavior (<6A Minimum)

### The Standard

**IEC 61851-1 Mode 3 AC Charging Requirements:**
- Minimum current for AC charging: **6.0 Amperes**
- Vehicle onboard charger **MUST stop charging** when current limit <6A
- Charger **MUST suspend power delivery** when commanded <6A

**Why 6A Minimum:**
- Safety: Below 6A, contactors and protection devices may not operate correctly
- Vehicle compatibility: Onboard chargers designed for minimum 6A pilot signal
- Standard compliance: Industry-wide agreement on minimum safe operating current

### Charger Behavior When Limit <6A

**What Happens:**
1. Charger receives current limit <6A (from OCPP, LMS, or configuration)
2. **Suspends power delivery** per IEC 61851-1 standard
3. PWM pilot signal stops (0A = no pilot signal on oscilloscope)
4. Contactors remain open (no power to vehicle)
5. State changes based on context:
   - Charging → **Preparing** (vehicle connected, awaiting sufficient current)
   - Charging → **SuspendedEVSE** (suspended by charger/EVSE)
   - Vehicle disconnects → **Available**
6. Transaction may remain active (not stopped, just suspended)
7. When limit ≥6A restored → Resumes charging automatically

**OCPP State Transitions (Expected):**
```
Charging → Preparing (when <6A limit applied during active session)
Charging → SuspendedEVSE (when <6A limit suspends charging)
SuspendedEVSE → Preparing (when <6A limit prevents resume)
Preparing → Charging (when ≥6A limit restored)
```

### Common Misdiagnosis

**User/Technician Reports:**
- "Charger keeps dropping sessions" → **Reality:** Charger suspending per standard, not dropping
- "Charger rebooting randomly" → **Reality:** Responding to current limits, not rebooting
- "Faulty charger hardware" → **Reality:** Backend/LMS sending 0A limits
- "Charger won't charge my car" → **Reality:** External system limiting current to 0A

**Critical Understanding:**  
**THIS IS STANDARDS-COMPLIANT BEHAVIOR, NOT A CHARGER FAULT.**

---

## Configuration Hierarchy (Three Sources of Current Limiting)

The charger uses the **MINIMUM** of three current sources:

### 1. Physical DIP Switches (Hardware Limit)

**Purpose:** Maximum rated current for charger installation  
**Set by:** Electrician during installation  
**Examples:** 16A, 24A, 32A  
**Location:** Physical switches inside charger enclosure  
**Override:** Cannot be overridden by software (hardware safety limit)

### 2. OCPP SetChargingProfile (Backend Limit)

**Purpose:** Dynamic load management from backend server  
**Set by:** OCPP backend (e.g., GreenFlux, CPMS, Chargefox)  
**Examples:** 6A-32A (or 0A-0.1A if misconfigured)  
**Location:** Software command via OCPP protocol  
**Override:** Can change dynamically based on site load, time-of-use, grid capacity

**See:** [OCPP Protocol Knowledge](ocpp_protocol.md) for SetChargingProfile details

### 3. Modbus Power Limit (Local LMS Limit)

**Purpose:** Local load management system (multi-charger sites)  
**Set by:** External Modbus master device (LMS controller)  
**Examples:** 0W-7400W (0A-32A @ 230V)  
**Location:** Modbus holding register 41601 (Power Limit)  
**Override:** Can change dynamically OR get stuck if LMS fails

**See:** [Modbus Registers Reference](../reference/modbus_registers.md) for register details

### How Charger Determines Current Limit

**The Algorithm:**
```python
effective_current = MIN(dip_switches, ocpp_profile, modbus_limit)
```

**Example Scenario 1: DIP Limit Exceeded**
- DIP switches: **16A max** (hardware)
- OCPP backend: 32A SetChargingProfile (software)
- Modbus 41601: 0xFFFF (no limit)
- **Result:** Charger limits to 16A, reports **EV0082 fault** (OCPP > DIP)

**Example Scenario 2: OCPP Low Current**
- DIP switches: 32A max (hardware)
- OCPP backend: **0.1A** SetChargingProfile (software)
- Modbus 41601: 0xFFFF (no limit)
- **Result:** Charger suspends charging (<6A), state = **Preparing**

**Example Scenario 3: Modbus 0W Fallback**
- DIP switches: 32A max (hardware)
- OCPP backend: 16A SetChargingProfile (software)
- Modbus 41601: **0x0000 (0W)** - misconfigured fallback
- **Result:** Charger suspends charging, reports **EV0103 (LIMIT_toNoPower)**

**Example Scenario 4: Dual-Source Issue (Complex)**
- DIP switches: 32A max
- OCPP backend: **0.1A** (backend misconfiguration)
- Modbus 41601: **0x0000** (LMS misconfiguration)
- **Result:** Both systems limiting to 0A, diagnosis requires checking both sources

---

## Low-Current OCPP Profiles (<6A)

### Pattern Detection

**Log Pattern:**
```
SetChargingProfile.*limit=([\d\.]+)
```
where `limit < 6.0`

**Thresholds:**
- **>10 occurrences:** Flag for backend investigation

**Example Log Lines:**
```
Jul 18 20:00:07.328 OpenWrt local7.info OpenWrt[2596]: [Info][OCPP16J]CommandParsing:...limit=0.100000...
Aug 05 14:23:19.445 OpenWrt local7.info OpenWrt[2612]: [Info][OCPP16J]SetChargingProfile limit=3.500000
```

### Root Cause

**Backend Load Management:**
- OCPP backend (GreenFlux, CPMS) sending current limits below 6A
- Often **0.1A** or **0A** due to load management algorithm
- Usually **unintentional** configuration or software bug
- May be site-wide issue affecting multiple chargers

**Common Scenarios:**
1. Backend load management algorithm sends 0A to "pause" charging
2. Grid capacity monitoring sends low limits during peak demand
3. Backend software bug sends malformed current values
4. Time-of-use scheduling sends 0A during off-peak hours

### Impact

**Charger Behavior:**
- Charger **suspends charging** per IEC 61851-1 standard
- State changes: Charging → **Preparing** OR **SuspendedEVSE**
- Transaction may remain active but no power delivered
- User sees "Preparing" indefinitely in app/display

**User Experience:**
- Plug in vehicle → Session starts → Charging for 5 minutes → Suddenly "Preparing"
- Cannot complete charging session
- App shows "Preparing" or "Suspended" - confusing status
- Support calls: "Charger stopped charging for no reason"

### Resolution

1. **Identify Pattern:** Count SetChargingProfile messages with limit <6.0A in OCPP logs
2. **Confirm Root Cause:** Backend sending low-current profiles, not LMS or hardware issue
3. **Contact Backend Provider:** 
   - Report: "Backend sending SetChargingProfile with limit <6A (e.g., 0.1A)"
   - Request: "Increase minimum current limits to ≥6A for IEC 61851-1 compliance"
   - Provide: Log excerpts showing low-current profiles
4. **Backend Adjustment:** Provider adjusts load management algorithm to never send <6A
5. **Verify Resolution:** Monitor logs for reduction in <6A profiles

**Related:**
- [OCPP Protocol](ocpp_protocol.md) - SetChargingProfile details
- [Error Codes](../reference/error_codes.md) - EV0103 (LIMIT_toNoPower)
- [Firmware Bugs](../reference/firmware_bugs.md) - SetChargingProfile timeout bug (separate issue)

---

## Load Management System (LMS) Modbus Issues

### Pattern Detection

**Log Pattern:**
```
Load_Mgmt_Comm.*(?:timeout|time out|fail|error)
```

**Thresholds:**
- **>5 occurrences:** Flag for LMS investigation

**Example Log Line:**
```
Jul 21 10:11:31.491 OpenWrt user.info : [Load_Mgmt_Comm] Communication Timeout ENABLE change to Disabled
```

**Associated Event:** **EV0103 (LIMIT_toNoPower)** - charger enters zero-power limiting state

### Root Causes

1. **LMS Hardware Failure:** Local Modbus master device stopped responding (most common at multi-charger sites)
2. **Modbus Register Misconfiguration:** Fallback power set to 0W in register 40204 (CRITICAL - see below)
3. **Cable/Wiring Issue:** Modbus RS-485 cable disconnected or damaged

### Common Scenario

**Multi-Charger Site with Load Balancing:**
- Site has 4-8 chargers sharing electrical panel capacity
- External LMS controller (Modbus master) coordinates load sharing
- LMS sends current limits via Modbus to each charger
- If LMS fails or cable disconnects → chargers enter timeout/fallback mode

### Modbus Register Configuration (The Problem)

**Critical Registers:**
- **40202 (0x00C9)** - Communication Timeout Enable (0=Disabled, 1=Enabled)
- **40203 (0x00CA)** - Communication Timeout (seconds, e.g., 600s = 10 minutes)
- **40204 (0x00CB)** - Fallback Power (Watts) ← **ROOT CAUSE IF 0x0000**
- **41601 (0x0640)** - Power Limit (Watts)

**Common Misconfiguration:**
```
Reg 40202 = 0x0001  (Timeout ENABLED)
Reg 40203 = 0x0258  (600 second timeout)
Reg 40204 = 0x0000  (Fallback power = 0W) ← CAUSES LIMIT_toNoPower
```

**What Happens:**
1. User configures Modbus with timeout enabled + **0W fallback** (thinking it's "safe")
2. Modbus communication fails (LMS device issue, cable disconnect, testing)
3. Charger waits for timeout period (e.g., 600 seconds = 10 minutes)
4. Timeout expires → charger enters **fallback mode**
5. Fallback power = **0W** → charger suspends charging per IEC 61851-1
6. Charger reports **EV0103 (LIMIT_toNoPower)** event
7. **State persists even after LMS physically disconnected** (registers still configured)
8. Charger stuck in "Preparing" state indefinitely

**See:** [Modbus Registers Reference](../reference/modbus_registers.md) for full register details

### Diagnosis

**Symptoms:**
- Load_Mgmt_Comm timeout messages in SystemLog
- EV0103 (LIMIT_toNoPower) events in EventLog (may be dozens to hundreds)
- Charger state stuck in "Preparing" or "Available"
- No PWM signal generated (0A limit = no pilot signal on oscilloscope)
- Site has or HAD load management hardware installed

**Key Questions to Ask Customer:**
1. "Did you configure Modbus at any stage?"
2. "Did you write to the timeout or fallback power registers?"
3. "Can you read registers 40202-40204 and 41601 via Modbus?"
4. "What are the raw hex values of those registers?"
5. "Is there a local load management system installed?"
6. "Was there previously an LMS that was removed/disconnected?"

### Resolution

**Method 1: Factory Reset (Easiest)**
1. Perform factory reset on charger
2. **Important:** Verify registers afterward (factory reset behavior uncertain - see [Firmware Bugs](../reference/firmware_bugs.md))
3. Read registers 40202-40204, 41601 to confirm defaults
4. Test charger standalone (no Modbus connected)

**Method 2: Modbus Write (More Reliable)**
```
Write 40202 = 0x0000  (Timeout DISABLED)
Write 40204 = 0xFFFF  (Fallback power = MAX)
Write 41601 = 0xFFFF  (Power limit = MAX)
```

**Method 3: Physical LMS Disconnection + Reset**
1. Physically disconnect Modbus RS-485 cable
2. Factory reset charger
3. Verify registers via Modbus read
4. Test standalone before reconnecting LMS

**Post-Resolution Warning:**
Fixing Modbus registers may reveal OTHER configuration mismatches! (See Federation University case below)

### Related Errors

**EV0103 - LIMIT_toNoPower:**
- Event code indicating charger in zero-power limiting state
- May be due to LMS Modbus 0W fallback OR OCPP <6A profile
- **NOT an error** - informational event indicating external limiting is active
- See [Error Codes Reference](../reference/error_codes.md)

**EV0082 - AC Output OCP (Over-Current Protection):**
- May appear AFTER fixing Modbus issue
- Indicates SECONDARY configuration mismatch (OCPP profile > DIP switches)
- Example: 32A OCPP profile but 16A DIP switches
- See [Error Codes Reference](../reference/error_codes.md)

---

## Dual-Source Current Limiting (Complex Diagnosis)

### The Nightmare Scenario

**What Is It:**
- Charger experiencing <6A limiting from **BOTH** OCPP backend AND Modbus LMS simultaneously
- Makes diagnosis extremely complex
- Fixing one source may not resolve issue if other source still limiting

**Example: Federation University Case (July 2024)**
- Charger: KKB233100224WE
- **Source 1:** 11 low-current OCPP profiles (0.1A) from GreenFlux backend
- **Source 2:** 24 LMS Modbus comm errors + 144 LIMIT_toNoPower events
- **Result:** Charger stuck in Preparing state, unable to deliver power
- **Diagnosis:** Required checking BOTH OCPP logs AND Modbus configuration
- **Resolution:** Fix LMS Modbus first (physical intervention) → revealed EV0082 (OCPP > DIP issue)

### How to Diagnose

**Step 1: Check OCPP Logs**
```
grep "SetChargingProfile.*limit=" OCPP16J_Log.csv
```
- Look for limit values <6.0
- If found → OCPP backend contributing to issue

**Step 2: Check SystemLog for LMS**
```
grep -i "Load_Mgmt_Comm.*timeout\|fail\|error" SystemLog
```
- Look for Modbus communication errors
- If found → LMS contributing to issue

**Step 3: Check EventLog for EV0103**
```
grep "EV0103\|LIMIT_toNoPower" EventLog
```
- Count occurrences
- If >10 → Strong indication of LMS Modbus 0W fallback issue

**Step 4: Determine Priority**
- If **both** found → Resolve LMS first (requires physical intervention: factory reset or Modbus write)
- Then address OCPP backend (contact provider, no physical access needed)

### Resolution Order

1. **Fix LMS Issue First:**
   - Factory reset or Modbus register write (requires site visit)
   - Test charger standalone
   - Verify charging works without LMS

2. **Then Fix OCPP Backend:**
   - Contact backend provider
   - Request minimum current limits ≥6A
   - May reveal secondary issues (e.g., EV0082)

3. **Monitor Both Sources:**
   - Continue monitoring logs for low-current profiles
   - Verify Modbus registers remain correct
   - Ensure no recurrence of dual-source limiting

---

## Summary: Root Cause Identification Flowchart

```
Charger stuck in "Preparing" / No charging?
│
├─ Check OCPP logs for SetChargingProfile limit <6A
│  └─ Yes → OCPP Backend Issue
│     └─ Contact backend provider
│
├─ Check SystemLog for Load_Mgmt_Comm errors
│  └─ Yes → LMS Modbus Issue
│     ├─ Check Modbus registers 40202-40204
│     └─ Factory reset or Modbus write
│
├─ Check EventLog for EV0103 (LIMIT_toNoPower)
│  └─ Yes → LMS Modbus Fallback Issue (reg 40204 = 0x0000)
│     └─ Factory reset or write 0xFFFF to reg 40204
│
├─ Check for BOTH OCPP and LMS errors
│  └─ Yes → Dual-Source Issue (complex)
│     ├─ Fix LMS first (physical intervention)
│     └─ Then fix OCPP (backend contact)
│
└─ Check DIP switches vs OCPP profile
   └─ OCPP > DIP → EV0082 fault
      └─ Align all three: DIP, OCPP, Modbus
```

---

## Known Cases

### Federation University (July 2024) - KKB233100224WE

**Symptoms:**
- Charger stuck in "Preparing" state
- Cannot deliver power to vehicles

**Diagnosis:**
- **OCPP:** 11 low-current SetChargingProfile messages (0.1A)
- **LMS:** 24 Load_Mgmt_Comm errors + 144 LIMIT_toNoPower events
- **Dual-source issue:** Both OCPP backend AND Modbus LMS limiting to <6A

**Resolution:**
1. Factory reset → cleared Modbus registers
2. Charging resumed → BUT EV0082 fault appeared
3. **Secondary issue:** 32A OCPP profile exceeded charger DIP switch configuration
4. Final fix: Aligned DIP switches, OCPP profile, Modbus registers

**Lesson Learned:**
Fixing one configuration issue may reveal OTHER mismatches. Always verify all three sources: DIP, OCPP, Modbus.

**See:** [Full Case Study](../case-studies/federation_university.md)

---

**Related Knowledge:**
- [OCPP Protocol](ocpp_protocol.md) - SetChargingProfile details
- [Modbus Registers](../reference/modbus_registers.md) - LMS configuration
- [Error Codes](../reference/error_codes.md) - EV0082, EV0103
- [Federation University Case](../case-studies/federation_university.md) - Real-world dual-source issue

---

**Last Updated:** 2026-01-26  
**Source:** IEC 61851-1 standard, field cases, Federation University diagnosis
