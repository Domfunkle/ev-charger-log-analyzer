# OCPP 1.6 Common Fault Patterns

**Source:** OCPP 1.6 Errata Sheet v4.0 (2019-10-23), OCPP-J 1.6 Errata v1.0 (2019-12-04), OCPP-J 1.6 Specification  
**Last Updated:** 2026-01-26  
**Purpose:** Catalog known OCPP protocol faults, misimplementations, and common issues for detection

---

## Overview

This document catalogs common OCPP 1.6 fault patterns discovered from official OCA (Open Charge Alliance) errata sheets and specifications. These patterns represent **known issues**, **clarifications**, and **common implementation bugs** that appear in real-world charger deployments.

**Why This Matters:**  
The OCPP specification has **46 documented errata** (corrections/clarifications) that reveal common pitfalls. Detecting these patterns in logs helps identify:
- Protocol violations
- Backend configuration errors
- Firmware bugs
- Data loss scenarios
- Billing discrepancies

---

## Critical Fault Patterns (Data Loss Risk)

### 1. Lost TransactionID - StartTransaction.conf Not Received

**Problem:** Charger sends StartTransaction.req but backend never responds with .conf containing transactionId

**Impact:**
- **SEVERE:** All subsequent transaction messages fail
- MeterValues.req cannot be correlated to transaction
- StopTransaction.req sent with transactionId=-1 or 0
- Billing data lost or corrupt

**Log Pattern:**
```
[2,"abc123","StartTransaction",{"connectorId":1,"idTag":"USER001",...}]
→ No [3,"abc123",...] CALLRESULT within timeout
→ Retries exhausted
→ [2,"def456","MeterValues",{"connectorId":1,"transactionId":-1,...}]  ← INVALID
```

**Root Causes:**
1. Backend timeout/overload (processing takes >60s)
2. Network packet loss during response
3. Backend crash mid-transaction
4. Firewall blocking specific message types

**Detection Strategy:**
- Count StartTransaction.req without matching .conf
- Look for MeterValues/StopTransaction with transactionId=-1, 0, or null
- Alert threshold: **>3 occurrences per day**

**Source:** OCPP 1.6 Errata v4.0, Section 3.18 - "How to deliver Transaction related messages when no transactionId is known"

**Analyzer Implementation:** `analyzers/delta_ac_max/detectors/ocpp.py::detect_lost_transaction_id()`

---

### 2. Hard Reset Data Loss

**Problem:** Hard reset immediately reboots charger WITHOUT queuing StopTransaction messages

**Impact:**
- Active transaction data lost
- Final meter readings not sent
- Billing incomplete (customer charged incorrectly)
- Transaction never closed in backend database

**Critical Difference:**

| Reset Type | Transaction Handling | Message Queuing | Data Preserved |
|------------|---------------------|----------------|----------------|
| **Soft Reset** | Gracefully stop transactions | SHALL queue StopTransaction.req | ✅ YES |
| **Hard Reset** | Immediate restart | MAY queue (often doesn't) | ❌ OFTEN LOST |

**Log Pattern:**
```
[2,"xyz789","Reset",{"type":"Hard"}]
→ BootNotification.req (charger reboots immediately)
→ NO StopTransaction.req for previous transaction
```

**Detection Strategy:**
- After BootNotification following Reset: Check for StopTransaction messages
- If Reset type=Hard AND no StopTransaction within 60s: Flag as "Transaction data lost"
- Count incomplete transactions (StartTransaction without StopTransaction)

**Source:** OCPP 1.6 Errata v4.0, Section 3.36 - "Improved description of Soft/Hard Reset"

---

### 3. Meter Register Not Cumulative (Starting at 0)

**Problem:** Charger resets meterStart to 0 for each transaction instead of using lifetime cumulative register

**Impact:**
- Cannot track total energy delivered by charger over lifetime
- Difficult to detect meter tampering
- Billing audits fail
- Charger replacement requires manual meter reading transfer

**Expected Behavior:**
- Transaction 1: meterStart=12,345 kWh, meterStop=12,375 kWh (30 kWh delivered)
- Transaction 2: meterStart=12,375 kWh, meterStop=12,410 kWh (35 kWh delivered)

**Incorrect Behavior:**
- Transaction 1: meterStart=0 kWh, meterStop=30 kWh
- Transaction 2: meterStart=0 kWh, meterStop=35 kWh ← Lost cumulative tracking

**Detection Strategy:**
- Track meterStart values across transactions
- If meterStart always <100 kWh: Flag as "Meter not using cumulative register"
- Expected: meterStart increases monotonically over time

**Source:** OCPP 1.6 Errata v4.0, Section 3.9 - "Missing advice to send meter register value"

---

## Medium Priority Patterns (Performance/Reliability)

### 4. WebSocket Half-Open Connections

**Problem:** Network connection appears active but is actually dead (NAT timeout, firewall dropped)

**Impact:**
- Messages sent into void (no error, no delivery)
- Charger thinks backend received message
- Backend never sees message
- Silent failures (hardest to debug)

**Prevention:** WebSocket Ping/Pong frames

**Critical Configuration Rule:**
```
WebSocketPingInterval < (TransactionMessageAttempts × TransactionMessageRetryInterval)
```

**Example:**
- WebSocketPingInterval=60s (send ping every 60 seconds)
- TransactionMessageAttempts=5
- TransactionMessageRetryInterval=30s
- Retry window=150s (5×30)
- **GOOD:** 60s < 150s → Dead connection detected before retries exhausted

**Bad Configuration:**
- WebSocketPingInterval=300s (5 minutes)
- Retry window=150s
- **BAD:** 300s > 150s → Retries exhausted before ping detects dead connection

**Detection Strategy:**
- Parse GetConfiguration response for `WebSocketPingInterval`
- Calculate retry window: attempts × interval
- If pingInterval > retryWindow: Flag as "Half-open connections possible"

**Source:** OCPP-J 1.6 Errata v1.0, Section 3.9 - "How to handle half open connections"

---

### 5. OCPP-J CallError Codes (Protocol Violations)

**Message Type 4** = CALLERROR (error response)

**Error Code Taxonomy:**

| Code | Meaning | Common Cause | Severity |
|------|---------|--------------|----------|
| **NotImplemented** | Action unknown | Feature not supported | Low |
| **NotSupported** | Action recognized but unsupported | Feature profile mismatch | Low |
| **InternalError** | Processing failed | Firmware crash, exception | **HIGH** |
| **ProtocolError** | Incomplete payload | Missing required fields | Medium |
| **SecurityError** | Security issue | Auth failure, certificate invalid | **HIGH** |
| **FormationViolation** | Syntax error | Malformed JSON | Medium |
| **PropertyConstraintViolation** | Invalid field value | Out of range, wrong type | Medium |
| **OccurenceConstraintViolation** | Wrong field count | Missing/extra fields | Medium |
| **TypeConstraintViolation** | Wrong data type | String instead of integer | Medium |

**Log Pattern:**
```
[4,"162376037","PropertyConstraintViolation","Current limit exceeds ChargingScheduleMaxPeriods","{}"]
     ↑           ↑                            ↑                                                    ↑
  MessageType  MessageId                   ErrorCode                           ErrorDescription   ErrorDetails
     (4)
```

**Detection Strategy:**
- Parse OCPP16J logs for `[4,`
- Extract errorCode (3rd field)
- Count by errorCode type
- **Threshold:** >10 of same errorCode = systemic issue

**Source:** OCPP-J 1.6 Specification, Section 4.2.3 - "CallError"

---

### 6. Synchronicity Violations (Message Out of Order)

**OCPP Rule:** Charger SHOULD NOT send next CALL until previous CALL is responded to or times out

**Violation Example:**
```
10:00:00 [2,"123","StartTransaction",{...}]      ← CALL 1 sent
10:00:01 [2,"124","StatusNotification",{...}]    ← CALL 2 sent (VIOLATION!)
10:00:05 [3,"123",{"status":"Accepted"}]         ← CALL 1 response
```

**Correct Behavior:**
```
10:00:00 [2,"123","StartTransaction",{...}]      ← CALL 1 sent
10:00:05 [3,"123",{"status":"Accepted"}]         ← CALL 1 response
10:00:05 [2,"124","StatusNotification",{...}]    ← CALL 2 sent (after response)
```

**Impact:**
- Backend may reject second message
- Race conditions in state machine
- Messages processed out of order
- Transaction state corruption

**Detection Strategy:**
- Track pending CALL messages (messageId not yet responded)
- If new CALL sent while pending CALL exists: Flag violation
- Exception: CALL from backend while charger waiting (crossing allowed)

**Source:** OCPP-J 1.6 Specification, Section 4.1.1 - "Synchronicity"

---

## Configuration/Best Practice Patterns

### 7. ChargingProfile Stacking Without Duration

**Problem:** High stackLevel profile without duration blocks all lower profiles **forever**

**Example:**
```
Backend sends:
  SetChargingProfile: stackLevel=2, limit=32A, duration=null

Profile stack:
  Level 2: 32A (active, no expiry) ← BLOCKS LEVEL 1 FOREVER
  Level 1: 16A (never executes)
```

**Impact:**
- Load management profiles never execute
- Charger stuck at single limit indefinitely
- Manual ClearChargingProfile required to fix

**Detection Strategy:**
- Parse SetChargingProfile messages
- If stackLevel >1 AND duration=null: Flag "Profile blocks lower levels"
- Recommend: All high-level profiles should have duration

**Source:** OCPP 1.6 Errata v4.0, Section 3.7 - "Add description of stacking without duration"

---

### 8. TxDefaultProfile Removed During Active Transaction

**Problem:** Backend clears TxDefaultProfile while transaction running

**Behavior:**
- Transaction SHALL continue WITHOUT any ChargingProfile
- No current limiting applied
- Vehicle charges at full power (may exceed site limits)

**Log Pattern:**
```
StartTransaction (transaction 12345 begins)
ClearChargingProfile: chargingProfilePurpose=TxDefaultProfile
→ Transaction 12345 now unmanaged (no power limits)
```

**Detection Strategy:**
- Track active transactions (StartTransaction without StopTransaction)
- If ClearChargingProfile removes TxDefaultProfile during active transaction:
  Flag as "Unmanaged charging session - no power limits"

**Source:** OCPP 1.6 Errata v4.0, Section 3.8 - "Effect of updating or deleting TxDefaultProfile"

---

### 9. Charging Before BootNotification Accepted

**Problem:** Charger allows StartTransaction before BootNotification.conf status=Accepted

**Risk:**
- Charger may not have valid date/time (no RTC hardware)
- Transaction timestamps incorrect (e.g., 1970-01-01 00:00:00)
- Backend may reject transactions later
- Billing data invalid

**Recommended:** Deny all charging until first `status=Accepted` response

**Detection Strategy:**
- After BootNotification.req: Track if StartTransaction sent before BootNotification.conf
- Check transaction timestamps for validity (not in past or future)
- Flag timestamps =1970-01-01 as "Clock not synchronized"

**Source:** OCPP 1.6 Errata v4.0, Section 3.11 - "Boot Notification: Note on behaviour while not accepted"

---

### 10. Missing MeterValues Configuration

**Problem:** MeterValueSampleInterval=0 or MeterValuesSampledData empty

**Impact:**
- No real-time meter data sent to backend
- User cannot see charging progress in app
- Cannot detect charging faults remotely

**Critical Configuration Keys:**
- `MeterValueSampleInterval` - Seconds between samples (0=disabled)
- `MeterValuesSampledData` - Comma-separated measurands (e.g., "Energy.Active.Import.Register,Current.Import")
- `ClockAlignedDataInterval` - Billing interval (900=15min)
- `MeterValuesAlignedData` - Fiscal meter measurands

**Detection Strategy:**
- Query GetConfiguration for these keys
- If MeterValueSampleInterval=0: Flag "No meter samples sent"
- If MeterValuesSampledData empty: Flag "Only default measurands sent"

**Source:** OCPP 1.6 Errata v4.0, Section 3.13 - "Missing description of configuration keys for MeterValues"

---

## JSON Implementation Bugs (Interoperability)

### 11. "Celsius" Typo (Celcius vs Celsius)

**Problem:** Original JSON schema misspelled "Celsius" as "Celcius"

**Location:** MeterValues.json, StopTransaction.json - SampledValue unit field

**Fix:** Backends MUST accept **both** spellings

**Detection Strategy:**
- Check unit field in MeterValues/StopTransaction
- If "Celcius" found: Flag as "Using legacy misspelling"
- Recommend firmware update to use correct "Celsius"

**Source:** OCPP-J 1.6 Errata v1.0, Section 2.1 - "MeterValues.json and StopTransaction.json incorrect spelling of Celsius"

---

### 12. StopTransaction "reason" Incorrectly Required

**Problem:** Original JSON schema marked "reason" as required, but spec says optional

**Spec:** reason is optional, default="Local"

**Impact:** Some chargers omit reason field (spec-compliant), some backends reject (schema-compliant)

**Detection Strategy:**
- Check StopTransaction messages for missing "reason" field
- If missing AND backend rejects: Flag "Backend incorrectly requires reason field"

**Source:** OCPP-J 1.6 Errata v1.0, Section 2.5 - "StopTransaction.json reason incorrectly required"

---

### 13. Timestamp Format Validation

**Requirement:** ISO 8601 with timezone

**Valid Examples:**
- `2024-07-15T14:23:45.123Z` (UTC)
- `2024-07-15T14:23:45+10:00` (UTC+10)
- `2024-07-15T14:23:45-05:00` (UTC-5)

**Invalid Examples:**
- `2024-07-15T14:23:45` ← Missing timezone
- `2024/07/15 14:23:45` ← Wrong format
- `2024-07-15 14:23:45Z` ← Missing 'T' separator

**Detection Strategy:**
- Regex validate all timestamp fields: `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$`
- Flag timestamps without timezone
- Flag timestamps >1 week in past or future
- Correlate with Heartbeat.conf currentTime (backend clock)

**Source:** OCPP 1.6 Errata v4.0, Section 3.10 - "Time notations"

---

## Detection Priority Matrix

**HIGH PRIORITY** (Data Loss / Billing Impact):
1. ✅ Lost TransactionID (StartTransaction.conf not received)
2. ✅ Hard reset data loss
3. ✅ Meter register not cumulative

**MEDIUM PRIORITY** (Performance / Reliability):
4. ⚠️ WebSocket half-open connections
5. ⚠️ CallError protocol violations
6. ⚠️ Synchronicity violations

**LOW PRIORITY** (Configuration / Best Practice):
7. ⚡ ChargingProfile stacking without duration
8. ⚡ TxDefaultProfile removed during transaction
9. ⚡ Charging before BootNotification accepted
10. ⚡ Missing MeterValues configuration
11. ⚡ Timestamp format validation
12. ⚡ JSON implementation bugs

---

## Implementation Roadmap

**Phase 1: Critical Detection** (Immediate)
- [ ] Lost TransactionID detection
- [ ] Hard/Soft reset differentiation
- [ ] Meter register value tracking

**Phase 2: Protocol Validation** (Next)
- [ ] CallError parsing and counting
- [ ] WebSocket ping interval validation
- [ ] Synchronicity violation detection

**Phase 3: Configuration Audit** (Later)
- [ ] MeterValues config validation
- [ ] ChargingProfile stacking analysis
- [ ] Timestamp format validation

---

**Related Knowledge:**
- [OCPP Protocol](../patterns/ocpp_protocol.md) - Complete OCPP 1.6 reference
- [Current Limiting](../patterns/current_limiting.md) - SetChargingProfile behavior
- [Firmware Bugs](firmware_bugs.md) - Delta-specific issues
- [Learning History](../development/learning_history.md) - v0.0.2 OCPP study

---

**Last Updated:** 2026-01-26  
**Source:** OCPP 1.6 Errata v4.0, OCPP-J 1.6 Errata v1.0, OCPP-J 1.6 Spec  
**Lines:** ~490
