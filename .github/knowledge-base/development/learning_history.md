# Learning History & Changelog

**Purpose:** Track what was learned when, version history, field cases analyzed  
**Format:** Reverse chronological (newest first)

---

## v0.0.1 - Federation University Cases & Protocol Learning (2026-01-26)

### Overview
Major knowledge expansion from Federation University multi-charger case study. Revealed complex interactions between OCPP backend, local Modbus LMS, and charger configuration.

### New Patterns Detected

#### Low-Current OCPP Profiles (<6A)
- **Pattern:** `SetChargingProfile.*limit=([\d\.]+)` where limit <6.0
- **Threshold:** >10 occurrences
- **Root Cause:** Backend (GreenFlux/CPMS) sending 0A or <6A limits
- **Impact:** Charger suspends charging per IEC 61851-1 standard
- **Resolution:** Contact backend provider to increase minimum current limits to ≥6A
- **Case Study:** KKB233100224WE - 11 profiles at 0.1A causing session suspensions
- **Implementation:** `detectors/ocpp.py` - `detect_low_current_profiles()`

#### Load Management System (LMS) Modbus Issues
- **Pattern:** `Load_Mgmt_Comm.*(?:timeout|time out|fail|error)`
- **Threshold:** >5 occurrences
- **Root Cause:** Modbus register 40204 (Fallback Power) = 0W after LMS failure
- **Impact:** Charger stuck in LIMIT_toNoPower state, unable to deliver power
- **Resolution:** Factory reset OR manually write 0xFFFF to Modbus registers
- **Case Study:** KKB233100224WE (Federation University, July-Dec 2024)
- **Key Learning:** State persists even after physical LMS disconnection
- **Implementation:** `detectors/lms.py` - `detect_load_mgmt_comm_errors()`

#### Event Code Analysis (Delta AC MAX Error Mapping)
- **Pattern:** `YYYY.MM.DD HH:MM:SS-EVXXXX` in EventLog CSV files
- **Purpose:** Cross-reference with Delta's official error code mapping
- **Examples:**
  - EV0103 (LIMIT_toNoPower) - Charger in zero-power limiting state
  - EV0082 (AC Output OCP) - Over-current protection (configuration mismatch)
  - EV0117-EV0126 (Network) - Backend/WiFi/3G connectivity errors
- **Implementation:** `detectors/events.py` - `parse_event_log()`
- **Reference:** 43 Delta AC MAX error codes (EV0081-EV0126) documented

#### RFID Module Failures (RYRR20I)
- **Pattern:** `RYRR20I.*(?:fail|time out)`
- **Threshold:** >100 occurrences = hardware fault confirmed
- **Case Study:** KKB240500004WE (Federation University, July 2024)
- **Error Count:** 51,095 RYRR20I errors over weeks
- **Resolution:** Charger replacement required (RYRR20I not serviceable)
- **Implementation:** `detectors/hardware.py` - `detect_rfid_errors()`

### Protocol Understanding

#### IEC 61851-1 Current Limiting Behavior
- **Standard:** Mode 3 AC Charging requires minimum 6.0A
- **Charger Behavior:** Suspends power delivery when limit <6A
- **OCPP State:** Charging → Preparing (when <6A applied)
- **Critical Understanding:** This is EXPECTED behavior, NOT a fault
- **Common Misdiagnosis:** "Charger keeps dropping sessions" - actually suspending per standard

#### Configuration Hierarchy (DIP / OCPP / Modbus)
- **Discovery:** Charger uses MINIMUM of three current sources
- **Sources:**
  1. Physical DIP switches (hardware limit)
  2. OCPP SetChargingProfile (backend software limit)
  3. Modbus register 41601 (local LMS limit)
- **Example:** DIP=16A, OCPP=32A, Modbus=MAX → Charger limits to 16A + EV0082 fault
- **Case Study:** Federation University (Dec 2024)
  - After fixing Modbus, EV0082 appeared
  - Backend sent 32A SetChargingProfile
  - DIP switches configured for lower current
  - Required aligning all three sources

#### Dual-Source Current Limiting (Complex Diagnosis)
- **Discovery:** OCPP backend AND Modbus LMS can BOTH limit simultaneously
- **Case:** KKB233100224WE - Both systems limiting to <6A concurrently
- **Diagnosis Challenge:** Required checking BOTH OCPP logs AND Modbus configuration
- **Resolution Order:** Fix LMS first (physical intervention) → Then fix OCPP (backend contact)

### Firmware Bugs Identified

#### SetChargingProfile Timeout Bug (Firmware <01.26.40)
- **Pattern:** `"SetChargingProfileConf process time out"` in OCPP logs
- **Root Cause:** Charger advertises 20 periods, actually supports 10
- **Behavior:** 31-second timeout + empty status response `{"status":""}`
- **Impact:** Cascade of backend disconnects, site-wide load management failure
- **Workaround:** Backend provider limits profiles to 10 periods
- **Status:** Pending firmware fix from Delta
- **Implementation:** `detectors/ocpp.py` - `detect_setcharging_timeouts()`

### Modular Refactoring

#### Code Modularization
- **Previous:** Monolithic `analyze.py` (~800 lines)
- **Refactored:**
  - `analyze.py` - Orchestrator (~388 lines)
  - `reporter.py` - TUI output (~278 lines)
  - `utils.py` - ZIP extraction (~109 lines)
  - `error_codes.py` - Delta error mapping (~50 lines)
  - `detectors/*.py` - Specialized detection modules (5 files, ~730 lines total)
- **Benefits:** Easier to extend, clearer responsibilities, easier testing

#### Detector Modules Created
- `detectors/events.py` - Event log parsing, ChargBox ID extraction
- `detectors/ocpp.py` - OCPP protocol detections (profiles, timeouts, rejections)
- `detectors/hardware.py` - Hardware faults (RFID, MCU, sensors)
- `detectors/lms.py` - Load Management System (Modbus communication)
- `detectors/state_machine.py` - OCPP state transition validation

### Field Cases Analyzed

#### Federation University - KKB233100224WE (Dual-Source Limiting)
- **Duration:** July-December 2024
- **Symptoms:** Charger stuck in Preparing state, unable to complete sessions
- **Root Causes (Three simultaneous issues):**
  1. OCPP backend sending 0.1A limits (11 occurrences)
  2. Modbus fallback power = 0W (24 LMS comm errors, 144 LIMIT_toNoPower events)
  3. Configuration mismatch (32A OCPP > DIP switches)
- **Resolution:** Fixed OCPP backend + Modbus reset + aligned DIP/OCPP/Modbus
- **Learning:** Fixing one issue may reveal others (cascading misconfigurations)

#### Federation University - KKB240500004WE (RFID Hardware Fault)
- **Duration:** July-December 2024
- **Symptoms:** RFID cards not recognized, 51,095 RYRR20I errors
- **Root Cause:** Catastrophic RFID module (RYRR20I) hardware failure
- **Troubleshooting:** Power cycle, factory reset, firmware update ALL failed
- **Resolution:** Charger replacement required (RYRR20I not serviceable)
- **Learning:** High error counts (>1000) confirm hardware fault, not configuration

### Documentation Expansion

#### Knowledge Base Created
- **Reference Material:**
  - `error_codes.md` - 43 Delta AC MAX error codes
  - `modbus_registers.md` - LMS Modbus register map
  - `firmware_bugs.md` - Known firmware issues

- **Pattern Knowledge:**
  - `ocpp_protocol.md` - OCPP 1.6 protocol understanding
  - `current_limiting.md` - IEC 61851-1, configuration hierarchy
  - `hardware_faults.md` - RFID, MCU, network issues
  - `state_transitions.md` - OCPP state machine

- **Case Studies:**
  - `federation_university.md` - Complete dual-charger case

- **Development:**
  - `pattern_detection.md` - How to add new patterns
  - `modularity_guidelines.md` - Code/doc organization
  - `learning_history.md` - This file

---

## v1.0.0 - Initial Release (2026-01-26)

### Features Implemented

#### Basic Pattern Detection
- Backend connection failures (`"Backend connection fail"`)
- MCU communication errors (`Send Command 0x[0-9A-Fa-f]+ to MCU False`)
- Logging gaps (>24 hours)
- Firmware version tracking (`Fw2Ver: XX.XX.XX.XX`)
- High error counts (>100 lines with "error" or "fail")

#### ZIP File Support
- Standard manual export (Storage/ directory structure)
- GetDiagnostics (OCPP command export)
- Automatic structure detection

#### Output Formats
- Terminal UI (TUI) summary with color-coded severity
- CSV export for batch analysis
- Per-charger detailed reporting

#### Cross-Platform
- Python 3.6+ standard library only
- Windows, Linux, macOS compatible
- pathlib.Path for cross-platform paths

---

## Pattern Addition Template

### vX.X.X - Description (YYYY-MM-DD)

**New Patterns:**
- Pattern name - Brief description
- Implementation: module.py - method_name()
- Threshold: X occurrences
- Root cause: What it indicates

**Field Cases:**
- Case name - Charger ID, symptoms, resolution

**Protocol Learning:**
- What was learned about OCPP/IEC/standards

**Code Changes:**
- New modules created
- Refactoring performed

**Documentation:**
- New knowledge docs added
- Updated cross-links

---

**Last Updated:** 2026-01-26  
**Maintainer:** Update this file when adding new patterns, learning from field cases, or refactoring code
