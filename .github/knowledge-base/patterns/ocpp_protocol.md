# OCPP 1.6 Protocol Knowledge

**Source:** OCPP 1.6 Specification, mobilityhouse/ocpp Python implementation  
**Purpose:** Understand expected OCPP behavior to detect protocol violations and anomalies  
**Scope:** Delta AC MAX charger OCPP 1.6 JSON implementation

---

## Charger States (ChargePointStatus)

### Valid States per OCPP 1.6

**Operative States:**
- **Available** - Connector ready for use, no vehicle connected
- **Preparing** - Vehicle connected, preparing to charge (authentication, authorization pending)
- **Charging** - Active charging session in progress (power delivery)
- **SuspendedEVSE** - Charging suspended by charger/EVSE (e.g., load management)
- **SuspendedEV** - Charging suspended by vehicle (vehicle stopped requesting power)
- **Finishing** - Charging complete, finalizing transaction (meter final read, receipt)
- **Reserved** - Connector reserved for specific user via reservation system

**Inoperative States:**
- **Unavailable** - Connector not available for use (maintenance, disabled, etc.)
- **Faulted** - Error condition, connector inoperative (hardware fault, safety trip)

### State Transition Patterns

**Normal Charging Session:**
```
Available → Preparing → Charging → Finishing → Available
```

**Suspended by Load Management:**
```
Charging → SuspendedEVSE → Charging (when power restored)
```

**Vehicle Suspension:**
```
Charging → SuspendedEV → Charging (when vehicle resumes)
```

**Fault During Charging:**
```
Charging → Faulted → Available (after recovery)
```

**See Also:** [State Transitions Detection](state_transitions.md) for validation logic

---

## RemoteStartTransaction Protocol

### Purpose
Backend-initiated charging start (used by mobile apps for "unlock port" / "start charging")

### Expected Flow (Normal)

```
1. User plugs in vehicle
   → Charger state: Available → Preparing
   → StatusNotification sent to backend

2. User presses "Start" button in mobile app
   → Backend sends RemoteStartTransaction
   → Charger validates request

3. Charger response: {"status": "Accepted"}
   → Charger state: Preparing → Charging
   → StartTransaction sent to backend

4. Charging begins
```

### Rejection Reasons

**Common Reasons for Rejected Response:**
1. **Connector state = Available** (vehicle not connected) ← MOST COMMON
2. **Connector state = Faulted** (charger in error state)
3. **Connector state = Unavailable** (charger offline/disabled)
4. **Invalid authorization ID** (user not authorized)
5. **Connector already in use** (another session active)
6. **Malformed request** (missing required fields, invalid data)

### User-Facing Behavior

**When Rejection Occurs:**
- Mobile app displays: "Unlock port request Rejected" (Chargefox app wording)
- User cannot start charging via app
- Must resolve issue (usually plug in vehicle) and retry

**Recommended User Workflow:**
1. **Plug in cable FIRST** (charger state → Preparing)
2. **Then** start session via app or RFID
3. Charger accepts RemoteStartTransaction → Charging begins

### Detection Pattern

**Log Pattern:**
```
[OCPP16J] RemoteStartTransaction.conf: [3,"UID",{"status":"Rejected"}]
```

**Thresholds:**
- **>5 occurrences:** Flag for user education (likely plugging in too late)
- **>50 occurrences:** Investigate for firmware/backend issue

### Known Issues

**Firmware-Related:**
- Firmware 1.26.37 appears more susceptible to rejections
- Firmware 1.26.38 and 1.25.13 less affected (unconfirmed)
- May correlate with faulty RFID readers (separate hardware issue)

**See Also:**
- Detection implementation: `analyzers/delta_ac_max/detectors/ocpp.py`
- Related: RFID faults in [hardware_faults.md](hardware_faults.md)

---

## SetChargingProfile Protocol

### Purpose
Smart charging / load management - backend commands charger to limit current/power

### ChargingScheduleMaxPeriods

**What It Means:**
- Configuration key in GetConfiguration response
- Defines maximum number of schedule periods charger can handle
- Backend should NOT send profiles exceeding this limit

**Delta AC MAX Bug:**
```json
GetConfiguration response:
{
  "key": "ChargingScheduleMaxPeriods",
  "readonly": true,
  "value": "20"  ← ADVERTISED (incorrect)
}

Actual capability: 10 periods maximum ← REALITY
```

**See:** [Firmware Bugs](../reference/firmware_bugs.md) for SetChargingProfile timeout bug details

### Expected Flow (Normal)

```
1. Backend sends SetChargingProfile with N periods
   → N ≤ ChargingScheduleMaxPeriods (e.g., ≤10 for Delta AC MAX)

2. Charger validates request:
   - Period count within limits?
   - Schedule times valid?
   - Current limits reasonable?

3. Charger response: {"status": "Accepted"}
   → Profile applied immediately
   → Current limiting begins

4. Charging continues at limited power
```

### Valid Status Responses

- **Accepted** - Profile accepted and applied successfully
- **Rejected** - Profile rejected (malformed, exceeds limits, invalid schedule)
- **NotSupported** - Smart charging feature not supported by charger

### Delta Firmware Bug Behavior

```
1. Backend sends SetChargingProfile with 20 periods
   → Exceeds actual 10-period limit (though advertised as 20)

2. Charger attempts to process for 31 seconds
   → Processing timeout

3. Charger response: {"status": ""}  ← EMPTY (protocol violation)
   → Connection drops
   → Charger reconnects

4. Pattern repeats hundreds/thousands of times
   → Site-wide load management fails
```

**See:** [SetChargingProfile Timeout Bug](../reference/firmware_bugs.md)

---

## OCPP Message Types

### Connection Management

**BootNotification**
- Sent when charger boots/powers on
- Registers charger with backend
- Receives configuration (heartbeat interval, etc.)

**Heartbeat**
- Periodic keep-alive message
- Default interval: 300 seconds (5 minutes)
- Backend responds with current time

### Status Reporting

**StatusNotification**
- Reports connector state changes
- Includes: state, errorCode, timestamp, vendorErrorCode
- Examples: Available → Preparing, Charging → Faulted

### Transaction Management

**StartTransaction**
- Reports transaction start
- Includes: connectorId, idTag, timestamp, meterStart
- Backend responds with transactionId

**StopTransaction**
- Reports transaction end
- Includes: transactionId, timestamp, meterStop, reason
- May include final meter values

**MeterValues**
- Energy meter readings during charging
- Periodic or triggered by events
- Includes: kWh delivered, power, voltage, current, etc.

### Authorization

**Authorize**
- RFID card authorization check
- Backend validates idTag
- Response: Accepted or Blocked

### Remote Commands (Backend → Charger)

**RemoteStartTransaction**
- Backend initiates charging (app unlock)
- See "RemoteStartTransaction Protocol" section above

**RemoteStopTransaction**
- Backend stops charging (app stop)
- Includes transactionId to stop

**SetChargingProfile**
- Load management / smart charging
- See "SetChargingProfile Protocol" section above

**GetConfiguration**
- Query charger configuration keys
- Example: ChargingScheduleMaxPeriods, HeartbeatInterval

**UnlockConnector**
- Remotely unlock cable
- Used after session ends if cable stuck

---

## OCPP Timeouts & Error Patterns

### IsTxCmdOK Timeout

**Pattern:** `"[IsTxCmdOK] Time out"` in OCPP logs

**Meaning:**
- Communication delay between charger and backend
- Transaction command did not complete within expected time
- May indicate network latency or backend overload

**Thresholds:**
- **>20 occurrences:** Flag for investigation
- **>100 occurrences:** Network or backend performance issue

**Typical Causes:**
- Network latency / packet loss
- Backend server overload
- 3G/4G connection quality (if using cellular)
- Firewall/proxy interference

**Note:** Excludes SetChargingProfile timeouts (separate firmware bug)

### NG Flags (Message Processing Errors)

**Pattern:** `\bNG\b|result:\s*NG|\[NG\]` in SystemLog

**Meaning:**
- "Not Good" - Message processing failure
- Invalid data received or sent
- Communication protocol error

**Thresholds:**
- **>10 occurrences:** Flag for investigation

**Typical Causes:**
- Malformed messages from backend
- Data validation failures
- Protocol version mismatches
- Corrupted data transmission

---

## Current Limiting via OCPP

### Low-Current Profiles (<6A)

When backend sends `SetChargingProfile` with current limit **<6.0A**:

**Charger Behavior:**
1. Receives profile with limit <6A (e.g., 0.1A, 3.5A)
2. **Suspends charging per IEC 61851-1** (6A minimum for AC Mode 3)
3. State changes: Charging → SuspendedEVSE OR Charging → Preparing
4. No PWM signal generated (0A = no pilot signal)
5. Reports `EV0103 (LIMIT_toNoPower)` in some cases

**This is EXPECTED BEHAVIOR, NOT A FAULT.**

**Root Cause:**
- Backend load management sending <6A limits (often 0.1A)
- Backend misconfiguration or unintentional load balancing algorithm

**Resolution:**
- Contact backend provider (e.g., GreenFlux, CPMS)
- Request minimum current limits set to ≥6A
- Adjust load management algorithm

**See Also:**
- [Current Limiting Patterns](current_limiting.md) - IEC 61851-1 behavior
- [Error Codes](../reference/error_codes.md) - EV0103 (LIMIT_toNoPower)

---

## Backend Disconnect Patterns

### Event Codes

**Network Connectivity Errors:**
- **EV0117** - Disconnect from Backend (Ethernet)
- **EV0118** - Disconnect from Backend (WiFi)
- **EV0119** - Disconnect from Backend (3G)
- **EV0123** - Disconnect from AP (WiFi)
- **EV0124** - Disconnect from APN (3G)

**See:** [Error Codes Reference](../reference/error_codes.md)

### Detection Thresholds

**Log Pattern:** `"Backend connection fail"` in SystemLog

**Thresholds:**
- **Normal:** <5 per day, quick reconnection (<10 seconds)
- **Concerning:** 10-50 per day - suggests network issues
- **Critical:** >100 per day or >1000 total - cable/switch/infrastructure problem

**Pattern:** Often comes in clusters (multiple disconnects within minutes)

### Common Causes

1. **Network cable** - Damaged Ethernet cable, loose connection
2. **Network switch** - Port flapping, power issues, switch failure
3. **Backend server** - OCPP server downtime, maintenance, overload
4. **Firewall/NAT** - Connection timeout, port blocking
5. **Cellular signal** - Weak 3G/4G, tower handoff (if using cellular)

**Correlation:** May correlate with SetChargingProfile timeout bug (firmware issue)

---

## TODO: Further Study Needed

When OCPP 1.6 PDF specification is accessible, study:

- [ ] Complete message flow diagrams
- [ ] State transition rules (when is each state allowed?)
- [ ] Timeout requirements (how long should responses take?)
- [ ] Error handling requirements (retry logic, etc.)
- [ ] Heartbeat and connection management details
- [ ] Transaction lifecycle (proper start/stop sequences)
- [ ] Authorization flows (RFID, app, pre-auth, etc.)
- [ ] Meter value reporting requirements
- [ ] Firmware update flows (GetDiagnostics, UpdateFirmware)

**Resources:**
- `docs/v16/ocpp-1.6.pdf` - Main specification
- `docs/v16/ocpp-j-1.6-specification.pdf` - JSON implementation
- `docs/v16/ocpp-1.6-errata-sheet.pdf` - Known issues/corrections

---

**Related Knowledge:**
- [Current Limiting](current_limiting.md) - SetChargingProfile <6A behavior
- [State Transitions](state_transitions.md) - OCPP state machine validation
- [Firmware Bugs](../reference/firmware_bugs.md) - SetChargingProfile timeout bug
- [Error Codes](../reference/error_codes.md) - OCPP-related error codes
- [Hardware Faults](hardware_faults.md) - Network disconnect correlation

---

**Last Updated:** 2026-01-26  
**Source:** OCPP 1.6 spec, field cases, Delta AC MAX logs
