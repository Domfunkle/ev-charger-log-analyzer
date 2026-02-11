# Delta AC MAX Modbus Register Reference

**Purpose:** Configuration registers for Load Management System (LMS) via Modbus RTU (RS-485)  
**Context:** LOCAL load management, NOT OCPP backend profiles (completely separate system)  
**Critical:** Misconfiguration can cause charger to enter zero-power limiting state (EV0103)

## Register Map

### 40202 (0x00C9) - Communication Timeout Enable
- **Type:** UINT16
- **Values:** 
  - `0x0000` = Timeout DISABLED (recommended for standalone operation)
  - `0x0001` = Timeout ENABLED
- **Purpose:** Enable/disable Modbus communication timeout detection
- **Related:** Works with register 40203 to define timeout behavior

### 40203 (0x00CA) - Communication Timeout
- **Type:** UINT16
- **Values:** 
  - `0x0000` = Timeout disabled
  - `0x0001-0x0258` = Timeout in seconds (1-600 seconds)
- **Purpose:** How long to wait for Modbus communication before entering fallback mode
- **Common Value:** `0x0258` (600 seconds = 10 minutes)
- **Note:** Only active if register 40202 = 0x0001

### 40204 (0x00CB) - Fallback Power
- **Type:** UINT32 (2 registers: 40204-40205)
- **Values:** 
  - `0x0000` = 0W (DANGEROUS - causes LIMIT_toNoPower)
  - `0xFFFF` = Maximum power (recommended)
  - Any value = Power limit in Watts when Modbus times out
- **Purpose:** Power limit to apply when Modbus communication fails
- **Critical:** If set to 0W, charger suspends charging per IEC 61851-1 when timeout occurs
- **Recommended:** `0xFFFF` for standalone operation, or ≥1400W (6A × 230V) if using timeout

### 41601 (0x0640) - Power Limit
- **Type:** UINT32 (2 registers: 41601-41602)
- **Values:**
  - `0x0000` = 0W (will prevent charging)
  - `0xFFFF` = Maximum power (recommended)
  - Any value = Maximum power limit in Watts
- **Purpose:** Overall maximum power limit for charger
- **Charger Behavior:** Uses MINIMUM of: DIP switches, OCPP profile, Modbus Power Limit
- **Recommended:** `0xFFFF` to let DIP switches control maximum current
- **Default Value:** UNKNOWN - may be 0 on fresh chargers or after certain operations
- **Mystery (2026-02-11):** Some chargers show 0 in Config/evcs without user ever writing to registers. Investigation ongoing to determine:
  - Factory default value (0 vs 0xFFFF)?
  - Does firmware initialization write 0?
  - Does first boot/setup wizard set this?
  - Does absence of LMS trigger default 0?
  
## Default Register Values (UNCERTAIN)

**Known Issue:** Default values for Modbus registers are **not documented** by Delta.

**Observed Behavior:**
- **Most chargers:** u32ModbusPowerLimit = 4294967295 (0xFFFFFFFF) in Config/evcs
- **Some chargers:** u32ModbusPowerLimit = 0 (cause unknown)
- **Some chargers:** No Modbus configuration present at all

**Theories:**
1. **Factory default = 0** → User must explicitly configure for LMS use
2. **Factory default = 0xFFFF** → 0 indicates someone wrote to registers
3. **Firmware-dependent** → Different firmware versions have different defaults
4. **Configuration wizard** → First-boot setup may set values based on user selections

**Investigation Status (2026-02-11):** 
- Field case KKB233100369WE has 0 values causing issues
- Field case KKB233100447WE (EVS09) also has MAX/MIN = 0, but PowerLimit/FallbackLimit = 0xFFFF (working correctly)
- **CONCLUSION:** MAX/MIN Power registers appear to be **deprecated/informational only**
- **PRIMARY controls:** u32ModbusPowerLimit and u32ModbusFallbackLimit
- Testing register writes to confirm 0 in PowerLimit is causing LIMIT_toNoPower events

## Register Priority (Updated 2026-02-11)

**Based on field observations from multiple chargers:**

**PRIMARY Registers (Actually Control Charging):**
1. **u32ModbusPowerLimit (41601-41602)** - This is the ACTIVE power limit
2. **u32ModbusFallbackLimit (40204-40205)** - Fallback when timeout occurs

**SECONDARY/Informational Registers (Appear Unused):**
3. **u32ModbusMAXPower** - Observed at 0 on working chargers
4. **u32ModbusMINPower** - Observed at 0 on working chargers

**Evidence:**
- Charger KKB233100447WE: MAX=0, MIN=0, PowerLimit=4294967295 → **Works perfectly**
- Charger KKB233100369WE: MAX=0, MIN=0, PowerLimit=0 → **Fails with LIMIT_toNoPower**

**Analyzer Updated (v0.0.6):** Detection now focuses on PowerLimit and FallbackLimit only

## Recommended Configurations

### Standalone Operation (No Load Management)
**Recommended for most installations - let DIP switches control current:**
```
Reg 40202 = 0x0000  (Timeout DISABLED)
Reg 40203 = 0x0258  (600 seconds, but disabled anyway)
Reg 40204 = 0xFFFF  (Fallback power = MAX)
Reg 41601 = 0xFFFF  (Power limit = MAX, controlled by DIP switches)
```

**Why:** Prevents Modbus configuration from interfering with normal operation. Charger controlled entirely by physical DIP switches and OCPP backend.

### With Load Management System
**Use timeout with safe fallback:**
```
Reg 40202 = 0x0001  (Timeout ENABLED)
Reg 40203 = 0x012C  (300 seconds = 5 minutes)
Reg 40204 = 0x0640  (1600W = ~7A @ 230V, above minimum)
Reg 41601 = 0xFFFF  (Power limit = MAX, or specific value for load sharing)
```

**Why:** If LMS fails, charger falls back to safe minimum current rather than shutting down completely.

### With Active Load Balancing
**LMS actively controls power, no timeout:**
```
Reg 40202 = 0x0000  (Timeout DISABLED - LMS must communicate continuously)
Reg 40203 = 0x0000  (No timeout)
Reg 40204 = 0xFFFF  (Fallback not used)
Reg 41601 = (varies) (Set by LMS dynamically)
```

**Why:** Load management system continuously updates register 41601 with allocated power. If LMS stops communicating, last value persists (no fallback).

## Common Misconfiguration (Causes LIMIT_toNoPower)

### The Problem Configuration
```
Reg 40202 = 0x0001  (Timeout ENABLED)
Reg 40203 = 0x0258  (600 second timeout)
Reg 40204 = 0x0000  (Fallback power = 0W) ← ROOT CAUSE
```

### What Happens

1. User configures Modbus with timeout enabled + 0W fallback (often unintentionally)
2. Modbus communication fails (LMS device issue, cable disconnect, testing, etc.)
3. Charger waits for timeout period (e.g., 600 seconds = 10 minutes)
4. Timeout expires → charger enters fallback mode
5. Fallback power = 0W → charger suspends charging per IEC 61851-1 minimum current
6. Charger reports **EV0103 (LIMIT_toNoPower)** event
7. **State persists even after LMS physically disconnected** (registers still configured)
8. Charger stuck in "Preparing" state, unable to deliver power

### How It Happens

- User tests Modbus, writes 0W as "safe" fallback (thinking it prevents charging if LMS fails)
- Installer configures LMS, sets 0W fallback, then removes LMS without resetting charger
- Copy-paste configuration from documentation without understanding implications
- Factory reset may NOT clear registers (uncertain behavior)

## Diagnosis

### Symptoms
- **Log Pattern:** `Load_Mgmt_Comm.*(?:timeout|time out|fail|error)` in SystemLog
- **Event Log:** Repeated EV0103 (LIMIT_toNoPower) events
- **Charger State:** Stuck in "Preparing" or "Available" - won't start charging
- **LED:** Yellow (not red/fault)
- **Physical:** No PWM signal generated (0A limit = no pilot signal on oscilloscope)
- **Site Type:** Multi-charger sites with load balancing/sharing hardware (common)

### Diagnostic Questions

Ask the customer:
1. "Did you configure Modbus at any stage?"
2. "Did you write to the timeout or fallback power registers?"
3. "Can you read registers 40202-40204 and 41601 via Modbus?"
4. "What are the raw hex values of those registers?"
5. "Is there a local load management system installed?"
6. "Was there previously an LMS that was removed?"

### Automated Detection (Since v0.0.5)

The analyzer now automatically detects Modbus misconfiguration by parsing Config/evcs file:

**Detection Pattern:**
```python
# Checks for:
- u32ModbusMAXPower = 0  (0W maximum - CRITICAL)
- u32ModbusMINPower = 0  (0W minimum - CRITICAL)
- u32ModbusFallbackLimit = 0 with timeout enabled
- Any power limits < 1380W (below 6A @ 230V minimum)
```

**Terminal Output:**
```
🔴 CRITICAL: Modbus Misconfiguration
  Issue: ModbusMAXPower=0W (charger cannot deliver power)
  • ModbusMAXPower: 0 W
  • ModbusMINPower: 0 W
  • FallbackLimit: 4294967295 W
  Recommended Fix:
   • Factory reset to remove LMS config, OR
   • Set ModbusMAXPower = 4294967295 (0xFFFFFFFF = MAX)
   • Set FallbackLimit ≥ 1380W (6A minimum per IEC 61851-1)
```

**CSV Export Fields:**
- `Modbus_Configured`: True/False
- `Modbus_Misconfigured`: True/False
- `Modbus_MAX_Power`: Watts (or empty if not configured)
- `Modbus_MIN_Power`: Watts (or empty if not configured)
- `Modbus_Issue`: Description of misconfiguration

**Implementation:** `detectors/lms.py` - `detect_modbus_config_issues()` (~125 lines)

**Field Case:** KKB233100369WE (2026-02-11) - Discovered partial LMS config with 0W limits causing 93 LIMIT_toNoPower events

### How to Check Registers

Use Modbus RTU tool to read registers:
```
Function Code: 0x03 (Read Holding Registers)
Register 40202: Read 1 register
Register 40203: Read 1 register
Register 40204: Read 2 registers (UINT32)
Register 41601: Read 2 registers (UINT32)
```

Expected values for standalone operation:
- 40202 should be 0x0000 (timeout disabled)
- 40204-40205 should be 0xFFFF (max fallback power)
- 41601-41602 should be 0xFFFF (max power limit)

## Resolution

### Method 1: Factory Reset (Easiest)
1. Perform factory reset on charger (consult Delta manual for procedure)
2. **Important:** Verify registers afterward - factory reset behavior uncertain
3. Read registers 40202-40204, 41601 to confirm defaults
4. Test charger standalone (no Modbus connected)

### Method 2: Modbus Write (More Reliable - Preferred)

**This is the recommended approach for verifying and fixing the issue.**

#### Step-by-Step Procedure

1. **Identify the issue** from Config/evcs file:
   - Compare against known-good charger config
   - Look for `u32ModbusPowerLimit='0'` (should be `'4294967295'`)
   - Check `u32ModbusMINPower` and `u32ModbusMAXPower` values

2. **Connect Modbus RTU tool** to charger (RS-485)

3. **Write maximum values to all power limit registers:**
   
   Each register must be set to: **0xFFFF = 65535 decimal = 1111111111111111 binary**
   
   ```
   Function Code: 0x06 (Write Single Register) or 0x10 (Write Multiple Registers)
   
   Register 40204 = 0xFFFF  (Fallback Power - high byte)
   Register 40205 = 0xFFFF  (Fallback Power - low byte)
   Register 41601 = 0xFFFF  (Power Limit - high byte)
   Register 41602 = 0xFFFF  (Power Limit - low byte)
   ```
   
   **Note:** These are UINT32 values split across 2 consecutive registers:
   - 40204-40205 = 0xFFFFFFFF = 4294967295 (maximum 32-bit unsigned value)
   - 41601-41602 = 0xFFFFFFFF = 4294967295

4. **Optional: Disable timeout** (if enabled):
   ```
   Register 40202 = 0x0000  (Timeout disabled)
   ```

5. **Power cycle charger** (turn off, wait 10 seconds, turn on)

6. **Test charging:**
   - Plug in vehicle
   - Start session (RFID or app)
   - Verify charger enters "Charging" state and delivers power
   
7. **Verify fix** by re-analyzing logs:
   ```bash
   delta-ac-max-analyzer -z charger_after_fix.zip
   ```
   - Should show: `Modbus_Misconfigured: False`
   - LIMIT_toNoPower events should stop occurring

#### Field Troubleshooting Notes (2026-02-11)

**Diagnostic Question to Customer:**
> "I have checked logs from many other chargers and noted from the Config > evcs file that the u32ModbusPowerLimit was set to 4294967295 (maximum value). Your logs show this value as 0. Can you please write to the following registers all binary 1s (0xFFFF = 65535)?"

**Why This Approach:**
- Tests if Modbus misconfiguration is the root cause before deeper investigation
- Verifies customer's Modbus tool is working correctly
- Non-destructive (easily reversible)
- Faster than factory reset
- Confirms registers can be written (rules out hardware issues)

### Method 3: Physical LMS Disconnection + Reset
1. Physically disconnect Modbus RS-485 cable from charger
2. Factory reset charger
3. Verify registers (see Method 2)
4. Test standalone before reconnecting LMS

### Post-Resolution Notes

**Warning:** Fixing Modbus registers may reveal OTHER configuration mismatches!

Example: [Federation University case](../case-studies/federation_university.md) (Dec 2024)
- After writing 0xFFFF to all registers → charger started charging
- **But** EV0082 (overcurrent protection) fault immediately appeared
- **Secondary issue:** 32A OCPP profile exceeded charger DIP switch configuration
- **Lesson:** Modbus 0W fallback was masking EV0082 configuration mismatch

## Configuration Hierarchy

The charger uses the **MINIMUM** of three current sources:

1. **Physical DIP Switches** (hardware limit - e.g., 16A, 24A, 32A)
2. **OCPP SetChargingProfile** (backend command - software limit)
3. **Modbus Power Limit** (register 41601 - local limit)

**Example Scenario:**
- DIP switches: 16A max (hardware)
- OCPP backend: 32A SetChargingProfile (software)
- Modbus 41601: 0xFFFF (no limit)
- **Result:** Charger limits to 16A, but reports EV0082 fault (OCPP > DIP)

**See Also:** [Current Limiting Patterns](../patterns/current_limiting.md)

## Factory Reset Behavior (Uncertain)

**Known:**
- Factory reset clears OCPP configuration
- Factory reset clears network settings

**Uncertain:**
- Whether Modbus registers reset to defaults
- Daniel Nathanson (2024-12-10): "I don't know if it clears the modbus registers to defaults. I haven't tested it."

**Safer Approach:**
- Manually write 0xFFFF to registers via Modbus **OR**
- Factory reset + manually verify registers afterward

## Real-World Cases

### Federation University (July 2024)
- **Charger:** KKB233100224WE
- **Symptoms:** 24 Load_Mgmt_Comm errors, 144 LIMIT_toNoPower events
- **Root Cause:** Modbus registers 40204-40205 = 0x0000 (0W fallback)
- **Context:** LMS was removed/disconnected but registers persisted
- **Resolution:** Factory reset → registers cleared → charging restored
- **Secondary Issue:** EV0082 appeared after fix (32A OCPP > DIP configuration)

**See:** [Full case study](../case-studies/federation_university.md)

## Related Knowledge

- [Error Codes](error_codes.md) - EV0103 (LIMIT_toNoPower), EV0082 (overcurrent)
- [Current Limiting Patterns](../patterns/current_limiting.md) - Configuration hierarchy, IEC 61851-1
- [Federation University Case Study](../case-studies/federation_university.md) - Real-world Modbus misconfiguration

---

**Last Updated:** 2026-01-26  
**Source:** Field cases, Delta documentation, Federation University diagnosis
