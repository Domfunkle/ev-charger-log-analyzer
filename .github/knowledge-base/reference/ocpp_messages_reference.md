# OCPP 1.6 Message Reference

**Source:** mobilityhouse/ocpp v16 implementation (authoritative Python library)  
**Purpose:** Complete catalog of OCPP 1.6 messages, enumerations, and data structures  
**Last Updated:** 2026-01-26

---

## Overview

This document provides a **comprehensive reference** to all OCPP 1.6 messages, error codes, measurands, configuration keys, and data structures. Use this for:
- Understanding OCPP message catalog
- Validating log data against spec
- Implementing new OCPP detectors
- Cross-referencing with [OCPP Protocol Patterns](../patterns/ocpp_protocol.md)

**For practical patterns and detection strategies**, see [OCPP Protocol Patterns](../patterns/ocpp_protocol.md).

---

## All OCPP 1.6 Actions (43 Total)

**From Charger → Backend (14 messages):**
1. `Authorize` - RFID authorization check
2. `BootNotification` - Charger startup/registration
3. `DiagnosticsStatusNotification` - Diagnostics upload status
4. `FirmwareStatusNotification` - Firmware update status
5. `Heartbeat` - Keep-alive message
6. `LogStatusNotification` - Log upload status (OCPP 1.6 Security Extension)
7. `MeterValues` - Energy meter readings
8. `SecurityEventNotification` - Security events (OCPP 1.6 Security Extension)
9. `SignCertificate` - Certificate signing request (ISO 15118 PnC)
10. `SignedFirmwareStatusNotification` - Signed firmware update status
11. `StartTransaction` - Transaction started
12. `StatusNotification` - Connector status change
13. `StopTransaction` - Transaction stopped
14. `DataTransfer` - Vendor-specific data (bidirectional)

**From Backend → Charger (29 messages):**
1. `CancelReservation` - Cancel existing reservation
2. `CertificateSigned` - Signed certificate response (ISO 15118)
3. `ChangeAvailability` - Change connector availability
4. `ChangeConfiguration` - Modify configuration keys
5. `ClearCache` - Clear authorization cache
6. `ClearChargingProfile` - Remove charging profiles
7. `DeleteCertificate` - Remove installed certificate (Security Extension)
8. `ExtendedTriggerMessage` - Trigger message with extended options
9. `GetCompositeSchedule` - Get effective charging schedule
10. `GetConfiguration` - Query configuration keys
11. `GetDiagnostics` - Request diagnostics upload
12. `GetInstalledCertificateIds` - List installed certificates
13. `GetLocalListVersion` - Get local auth list version
14. `GetLog` - Request log upload (Security Extension)
15. `InstallCertificate` - Install certificate (Security Extension)
16. `RemoteStartTransaction` - Start charging remotely
17. `RemoteStopTransaction` - Stop charging remotely
18. `ReserveNow` - Reserve connector
19. `Reset` - Reboot charger (Soft/Hard)
20. `SendLocalList` - Update local authorization list
21. `SetChargingProfile` - Apply charging schedule (load management)
22. `SignedUpdateFirmware` - Signed firmware update (Security Extension)
23. `TriggerMessage` - Trigger specific message (e.g., StatusNotification)
24. `UnlockConnector` - Remotely unlock cable
25. `UpdateFirmware` - Firmware update (legacy, unsigned)
26. `DataTransfer` - Vendor-specific data (bidirectional)

---

## ChargePointErrorCode Values (16 Total)

Reported in `StatusNotification`:
- `NoError` - No error condition
- `ConnectorLockFailure` - Cable lock mechanism failed
- `EVCommunicationError` - Communication error with vehicle
- `GroundFailure` - Ground fault detected
- `HighTemperature` - Overheating condition
- `InternalError` - Internal charger error
- `LocalListConflict` - Authorization list conflict
- `OtherError` - Other unspecified error
- `OverCurrentFailure` - Overcurrent protection triggered
- `OverVoltage` - Overvoltage detected
- `PowerMeterFailure` - Energy meter malfunction
- `PowerSwitchFailure` - Contactor/relay failure
- `ReaderFailure` - RFID reader fault
- `ResetFailure` - Charger reset failed
- `UnderVoltage` - Undervoltage detected
- `WeakSignal` - Weak network signal (cellular/WiFi)

---

## Measurands (Meter Value Types - 22 Total)

Used in `MeterValues` and `StopTransaction`:
- `Current.Export` - Current flowing to grid
- `Current.Import` - Current drawn from grid
- `Current.Offered` - Max current available to vehicle
- `Energy.Active.Export.Register` - Total energy exported
- `Energy.Active.Import.Register` - Total energy imported (default)
- `Energy.Reactive.Export.Register` - Reactive energy exported
- `Energy.Reactive.Import.Register` - Reactive energy imported
- `Energy.Active.Export.Interval` - Energy exported this interval
- `Energy.Active.Import.Interval` - Energy imported this interval
- `Energy.Reactive.Export.Interval` - Reactive energy exported this interval
- `Energy.Reactive.Import.Interval` - Reactive energy imported this interval
- `Frequency` - AC frequency
- `Power.Active.Export` - Active power to grid
- `Power.Active.Import` - Active power from grid
- `Power.Factor` - Power factor
- `Power.Offered` - Max power available to vehicle
- `Power.Reactive.Export` - Reactive power to grid
- `Power.Reactive.Import` - Reactive power from grid
- `RPM` - Motor RPM (rare)
- `SoC` - Vehicle State of Charge percentage
- `Temperature` - Temperature measurement
- `Voltage` - Voltage measurement

---

## Stop Transaction Reasons (11 Total)

Values for `StopTransaction.reason`:
- `DeAuthorized` - Authorization revoked during session
- `EmergencyStop` - Emergency stop button pressed
- `EVDisconnected` - Vehicle unplugged
- `HardReset` - Charger hard reset
- `Local` - Stopped locally (button, RFID)
- `Other` - Other reason
- `PowerLoss` - Power outage
- `Reboot` - Charger rebooted
- `Remote` - Backend RemoteStopTransaction
- `SoftReset` - Charger soft reset
- `UnlockCommand` - UnlockConnector command

---

## Configuration Keys (Core Profile - 33 Keys)

**Connection & Communication:**
- `ConnectionTimeOut` - WebSocket connection timeout (seconds)
- `HeartbeatInterval` - Time between Heartbeat messages (seconds)
- `WebSocketPingInterval` - WebSocket ping interval (seconds)

**Authorization:**
- `AllowOfflineTxForUnknownId` - Allow unknown RFID when offline
- `AuthorizationCacheEnabled` - Enable auth cache
- `AuthorizeRemoteTxRequests` - Require auth for remote starts
- `LocalAuthorizeOffline` - Use local list when offline
- `LocalPreAuthorize` - Pre-authorize before StartTransaction

**Transaction Behavior:**
- `StopTransactionOnEVSideDisconnect` - Stop when cable unplugged
- `StopTransactionOnInvalidId` - Stop if invalid RFID
- `UnlockConnectorOnEVSideDisconnect` - Unlock when unplugged
- `MaxEnergyOnInvalidId` - Max kWh for invalid RFID sessions

**Meter Values:**
- `ClockAlignedDataInterval` - Interval for aligned meter samples
- `MeterValueSampleInterval` - Interval for sampled meter values
- `MeterValuesAlignedData` - Measurands for aligned samples
- `MeterValuesSampledData` - Measurands for sampled values
- `StopTxnAlignedData` - Aligned data in StopTransaction
- `StopTxnSampledData` - Sampled data in StopTransaction

**Smart Charging (if supported):**
- `ChargeProfileMaxStackLevel` - Max stack level for profiles
- `ChargingScheduleAllowedChargingRateUnit` - Allowed units (W or A)
- `ChargingScheduleMaxPeriods` - Max schedule periods **← DELTA BUG: Says 20, actually 10**
- `MaxChargingProfilesInstalled` - Max total profiles
- `ConnectorSwitch3to1PhaseSupported` - Can switch phases

**System:**
- `NumberOfConnectors` - Number of connectors
- `SupportedFeatureProfiles` - Enabled OCPP profiles
- `ResetRetries` - Max reset retry attempts

---

## ChargingProfile Structure

**Purpose Types (3):**
- `ChargePointMaxProfile` - Site-wide limit (connector 0 only)
- `TxDefaultProfile` - Default limit for new sessions
- `TxProfile` - Session-specific limit (requires active transaction)

**Kind Types (3):**
- `Absolute` - Fixed schedule with absolute times
- `Recurring` - Repeats periodically (daily/weekly)
- `Relative` - Starts relative to trigger event (e.g., session start)

**Charging Rate Units (2):**
- `W` - Watts (power limit)
- `A` - Amperes (current limit) **← IEC 61851-1: Min 6A for AC Mode 3**

**Recurrency (2):**
- `Daily` - Restarts each day at midnight
- `Weekly` - Restarts each Monday

---

## Authorization Flows

### RFID Authorization (Local)

```
1. User taps RFID card on reader
   → Charger reads idTag

2. Charger checks local authorization list
   → If enabled and idTag in list: Proceed to step 4
   → If disabled or not in list: Proceed to step 3

3. Charger sends Authorize.req to backend
   → Backend responds with Authorize.conf:
     - status: Accepted → Proceed to step 4
     - status: Blocked/Invalid/Expired → Reject, display error

4. Charger starts transaction
   → Sends StartTransaction.req with idTag
   → State: Available → Preparing → Charging
```

### RemoteStartTransaction (App-Initiated)

**See [OCPP Protocol Patterns](../patterns/ocpp_protocol.md#remotest arttransaction-protocol) for full details.**

### Pre-Authorization

**Configuration:** `LocalPreAuthorize = true`

```
1. User plugs in cable (no RFID tap yet)
   → Charger immediately sends StartTransaction.req
   → idTag: "00000000" or similar placeholder

2. Backend authorizes/denies in response
   → Accepted: Charging begins immediately
   → Rejected: Charger waits for RFID tap
```

---

## Firmware Update Flows

### Legacy UpdateFirmware (Unsigned)

```
1. Backend sends UpdateFirmware.req:
   - location: FTP/HTTP URL of firmware file
   - retrieveDate: When to download
   - retries: Download retry count (optional)
   - retryInterval: Seconds between retries (optional)

2. Charger responds UpdateFirmware.conf (empty)

3. Charger sends FirmwareStatusNotification at each stage:
   - "Downloading" → downloading firmware
   - "Downloaded" → download complete
   - "Installing" → applying firmware
   - "Installed" → firmware updated successfully
   - "InstallationFailed" → update failed

4. After "Installed", charger reboots automatically
   → Sends BootNotification with new firmware version
```

### SignedUpdateFirmware (Security Extension)

**Additional Steps:**
- Firmware must be cryptographically signed
- Charger verifies signature before installing
- Status values include:
  - `SignatureVerified` - Signature valid
  - `InvalidSignature` - Signature check failed
  - `InstallVerificationFailed` - Firmware verification failed

---

## Diagnostics & Logging

### GetDiagnostics Flow

```
1. Backend sends GetDiagnostics.req:
   - location: FTP/HTTP URL to upload diagnostics
   - startTime: Optional filter (logs after this time)
   - stopTime: Optional filter (logs before this time)
   - retries: Upload retry count
   - retryInterval: Seconds between retries

2. Charger responds GetDiagnostics.conf:
   - fileName: Name of diagnostics file to upload

3. Charger sends DiagnosticsStatusNotification:
   - "Uploading" → upload in progress
   - "Uploaded" → upload complete
   - "UploadFailed" → upload failed
```

### GetLog (Security Extension)

```
1. Backend sends GetLog.req:
   - logType: "DiagnosticsLog" or "SecurityLog"
   - requestId: Unique ID for this request
   - log: LogParameters (remote location, time filters)

2. Charger responds GetLog.conf:
   - status: "Accepted", "Rejected", "AcceptedCanceled"
   - filename: Log file name (if accepted)

3. Charger sends LogStatusNotification with requestId
```

---

## Reservation System

### ReserveNow Flow

```
1. Backend sends ReserveNow.req:
   - connectorId: Connector to reserve (or 0 for any)
   - expiryDate: Reservation expires at this time
   - idTag: User authorized to use reservation
   - reservationId: Unique reservation ID
   - parentIdTag: Optional parent authorization

2. Charger validates:
   - Connector available?
   - Reservation system enabled?
   - Not already reserved?

3. Charger responds ReserveNow.conf:
   - "Accepted" → Reservation active
   - "Faulted" → Connector faulted
   - "Occupied" → Connector in use
   - "Rejected" → Feature not supported
   - "Unavailable" → Connector unavailable

4. If accepted:
   → StatusNotification: Available → Reserved
   → Only specified idTag can start charging
   → After expiryDate: Reserved → Available
```

### CancelReservation

```
Backend sends CancelReservation.req with reservationId
→ Charger cancels reservation
→ StatusNotification: Reserved → Available
```

---

## Advanced Features

### ISO 15118 Plug & Charge (PnC)

**Configuration Keys:**
- `ISO15118PnCEnabled` - Enable ISO 15118 support
- `CentralContractValidationAllowed` - Backend validates contracts
- `ContractValidationOffline` - Offline contract validation

**Messages:**
- `SignCertificate` - Request certificate signing (Charger → Backend)
- `CertificateSigned` - Signed certificate response (Backend → Charger)
- `InstallCertificate` - Install root/manufacturer certificates
- `DeleteCertificate` - Remove certificates
- `GetInstalledCertificateIds` - List installed certificates

**Certificate Types:**
- `CentralSystemRootCertificate` - Backend trust root
- `ManufacturerRootCertificate` - OEM trust root

### Security Profile Configuration

**Configuration Key:** `SecurityProfile`  
**Values:**
- `0` - Unsecured HTTP/WebSocket (default for older chargers)
- `1` - Basic authentication (HTTP Basic Auth)
- `2` - TLS with Basic Auth
- `3` - TLS with client certificates (mutual TLS) **← RECOMMENDED**

### Local Authorization List

**Purpose:** Offline RFID authorization when backend unreachable

**Flow:**
```
1. Backend sends SendLocalList.req:
   - listVersion: Version number (incremental)
   - updateType: "Full" or "Differential"
   - localAuthorizationList: Array of AuthorizationData
     - idTag: RFID card ID
     - idTagInfo: Status (Accepted/Blocked), expiryDate

2. Charger updates list and responds:
   - "Accepted" → List updated successfully
   - "Failed" → Update failed
   - "NotSupported" → Feature not supported
   - "VersionMismatch" → Version number error

3. Charger uses list when:
   - LocalAuthListEnabled = true
   - Backend unreachable
   - AllowOfflineTxForUnknownId = false
```

**Query Version:**
```
Backend sends GetLocalListVersion.req
→ Charger responds with current listVersion number
```

---

## Data Transfer (Vendor-Specific)

**Bidirectional:** Can be sent by Charger OR Backend

```
DataTransfer.req:
  - vendorId: Manufacturer identifier (e.g., "Delta")
  - messageId: Optional message type
  - data: Optional vendor-specific data (string)

DataTransfer.conf:
  - status: "Accepted", "Rejected", "UnknownMessageId", "UnknownVendorId"
  - data: Optional response data
```

**Use Cases:**
- Proprietary features not in OCPP spec
- Manufacturer diagnostics
- Custom load management
- Extended configuration

**Example (Delta-specific):**
- Modbus register queries
- Custom error codes
- OEM telemetry

---

## Message Validation Rules

### IdTag Format
- Type: String (case-insensitive)
- Max length: 20 characters
- Examples: "04E3F89A2C3C80", "USER123", "FLEET_VEHICLE_42"

### Timestamp Format
- ISO 8601: `YYYY-MM-DDTHH:MM:SS.sssZ`
- Example: `2024-07-15T14:23:45.123Z`
- Must include timezone (Z for UTC or ±HH:MM offset)

### Connector IDs
- `0` - Charge Point itself (whole unit)
- `1, 2, ...` - Individual connectors
- Max connectors: Reported in `NumberOfConnectors` config key

### Transaction IDs
- Assigned by backend in `StartTransaction.conf`
- Used in: `StopTransaction`, `MeterValues`, `RemoteStopTransaction`
- Must be unique per charger

---

**Related Knowledge:**
- [OCPP Protocol Patterns](../patterns/ocpp_protocol.md) - Practical detection patterns
- [OCPP Fault Patterns](ocpp_fault_patterns.md) - Common faults and issues
- [Current Limiting](../patterns/current_limiting.md) - SetChargingProfile <6A behavior
- [Firmware Bugs](firmware_bugs.md) - Delta-specific issues
- [Error Codes](error_codes.md) - Delta AC MAX error codes

---

**Last Updated:** 2026-01-26  
**Source:** mobilityhouse/ocpp v16 library, OCPP 1.6 specification  
**Lines:** ~460
