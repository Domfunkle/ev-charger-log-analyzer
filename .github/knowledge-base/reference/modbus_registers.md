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

### Method 2: Modbus Write (More Reliable)
1. Connect Modbus RTU tool to charger
2. Write recommended values:
   ```
   Write 40202 = 0x0000
   Write 40203 = 0x0258 (optional, timeout disabled anyway)
   Write 40204 = 0xFFFF (high byte)
   Write 40205 = 0xFFFF (low byte)
   Write 41601 = 0xFFFF (high byte)
   Write 41602 = 0xFFFF (low byte)
   ```
3. Power cycle charger
4. Verify charger starts charging

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
