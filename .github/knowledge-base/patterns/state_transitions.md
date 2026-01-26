# OCPP State Transitions

**Purpose:** Validate OCPP state machine transitions, detect anomalies  
**Standard:** OCPP 1.6 ChargePointStatus states  
**Scope:** Delta AC MAX OCPP 1.6 implementation

---

## OCPP State Machine

### Valid States (OCPP 1.6)

**Operative States:**
- **Available** - Connector ready, no vehicle
- **Preparing** - Vehicle connected, preparing to charge
- **Charging** - Active charging session
- **SuspendedEVSE** - Suspended by charger (load management, etc.)
- **SuspendedEV** - Suspended by vehicle
- **Finishing** - Charging complete, finalizing
- **Reserved** - Connector reserved for specific user

**Inoperative States:**
- **Unavailable** - Connector not available (maintenance)
- **Faulted** - Error condition, inoperative

**See:** [OCPP Protocol](ocpp_protocol.md) for detailed state descriptions

---

## Expected State Transitions

### Normal Charging Session

```
Available → Preparing → Charging → Finishing → Available
```

**Triggers:**
1. Vehicle plugs in → **Available → Preparing**
2. Authorization granted → **Preparing → Charging**
3. Charging completes → **Charging → Finishing**
4. Transaction ends → **Finishing → Available**

### Load Management Suspension

```
Charging → SuspendedEVSE → Charging
```

**Triggers:**
1. SetChargingProfile <6A → **Charging → SuspendedEVSE**
2. SetChargingProfile ≥6A → **SuspendedEVSE → Charging**

**See:** [Current Limiting](current_limiting.md) for IEC 61851-1 behavior

### Vehicle Suspension

```
Charging → SuspendedEV → Charging
```

**Triggers:**
1. Vehicle stops requesting power → **Charging → SuspendedEV**
2. Vehicle resumes requesting power → **SuspendedEV → Charging**

### Fault Transitions

```
[Any State] → Faulted → Available
```

**Triggers:**
1. Hardware fault detected → **→ Faulted**
2. Fault cleared → **Faulted → Available**

**See:** [Error Codes](../reference/error_codes.md) for fault types

---

## Suspicious Transitions

### Invalid Sequences

**Charging without Preparing:**
```
Available → Charging  ← SUSPICIOUS (should go through Preparing)
```

**Direct to Faulted:**
```
Available → Faulted  ← May indicate startup fault
```

**Skipping Finishing:**
```
Charging → Available  ← SUSPICIOUS (should go through Finishing)
```

**Rapid State Changes:**
```
Charging → Preparing → Charging → Preparing (multiple times in seconds)
```
- May indicate:
  - Current limiting cycling (<6A limits applied/removed rapidly)
  - Vehicle communication issues
  - Backend SetChargingProfile thrashing

---

## State Transition Validation

### Detection Implementation

**Module:** `analyzers/delta_ac_max/detectors/state_machine.py`  
**Purpose:** Parse OCPP logs, validate state transitions, flag anomalies

**What It Detects:**
1. **State transition sequences** - Normal vs suspicious patterns
2. **Rapid state changes** - Multiple transitions in short time
3. **Invalid transitions** - States that violate OCPP spec
4. **State duration** - How long charger spends in each state

### Thresholds

**Rapid State Changes:**
- **>5 Charging ↔ Preparing cycles:** Flag for investigation
- **>10 SuspendedEVSE ↔ Charging cycles:** Current limiting issues

**Invalid Transitions:**
- **Any occurrence:** Flag as protocol violation
- **>5 occurrences:** Firmware bug or backend misconfiguration

---

## Common Patterns

### Current Limiting Cycles

**Pattern:**
```
Charging → Preparing → Charging → Preparing → Charging
```

**Cause:**
- Backend sending <6A SetChargingProfile → Suspends charging → State: Preparing
- Backend restores ≥6A → Resumes charging → State: Charging
- Cycle repeats as backend adjusts current limits

**Resolution:**
- Contact backend provider
- Request stable current limits ≥6A
- See [Current Limiting](current_limiting.md)

### App Unlock Before Plug-In

**Pattern:**
```
Available → Available (RemoteStartTransaction Rejected)
```

**Cause:**
- User presses "Unlock" in app before plugging in vehicle
- Charger state still "Available" (no vehicle detected)
- RemoteStartTransaction rejected (vehicle must be connected)

**Resolution:**
- User education: "Plug in first, then start charging"
- See [OCPP Protocol](ocpp_protocol.md) - RemoteStartTransaction

### Fault Recovery

**Pattern:**
```
Charging → Faulted → Available → Preparing → Charging
```

**Cause:**
- Hardware fault during charging (e.g., EV0082 overcurrent)
- Fault cleared (e.g., user unplugs/replugs)
- Charger recovers and resumes

**Action:**
- Identify fault type from EventLog (EVXXXX codes)
- See [Error Codes](../reference/error_codes.md)

---

## Future Enhancements

**TODO: Deep OCPP State Machine Analysis**

When OCPP 1.6 specification is fully studied:
- [ ] Define ALL valid state transitions per spec
- [ ] Identify ALL invalid transitions
- [ ] Measure state duration statistics (how long in each state)
- [ ] Detect state machine deadlocks (stuck states)
- [ ] Correlate state changes with OCPP messages (which message triggered which transition)

**See:** [OCPP Protocol](ocpp_protocol.md) - TODO section

---

**Related Knowledge:**
- [OCPP Protocol](ocpp_protocol.md) - State definitions, message types
- [Current Limiting](current_limiting.md) - Charging ↔ Preparing cycles
- [Error Codes](../reference/error_codes.md) - Fault states
- [Hardware Faults](hardware_faults.md) - Hardware-induced state changes

---

**Last Updated:** 2026-01-26  
**Source:** OCPP 1.6 spec, field observations  
**Status:** Basic validation implemented, deep analysis pending
