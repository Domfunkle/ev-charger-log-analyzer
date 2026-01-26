# Delta AC MAX Error Code Reference

**Source:** Delta ACMAX-TG-002-EN Error Mapping Document  
**Purpose:** Cross-reference event codes from EventLog CSV files with official error descriptions and troubleshooting

## Critical Hardware Errors

### EV0081 - AC Input OVP (Over-Voltage Protection)
- **Code:** 10001 | **MCU Alarm:** 201 | **LED:** Red, 1 Flash
- **Cause:** AC input voltage over protection value (>265V)
- **Root Cause:** Input voltage too high
- **Fix:** Check input voltage, reduce to correct voltage range

### EV0083 - AC Input UVP (Under-Voltage Protection)
- **Code:** 10004 | **MCU Alarm:** 202 | **LED:** Red, 1 Flash
- **Cause:** AC input voltage under protection value (<180V)
- **Root Cause:** Input voltage too low
- **Fix:** Check input voltage, increase to correct voltage range

### EV0082 - AC Output OCP (Over-Current Protection)
- **Code:** 10015 | **MCU Alarm:** 801(low)/802(High) | **LED:** Red, 4 Flashes
- **Cause:** AC output current over protection value
- **Root Causes:**
  1. **Configuration Mismatch:** Backend sending higher current profile than charger configured for
  2. **DIP Switch Setting:** Physical DIP switches set to lower current than OCPP profile
  3. **Modbus Limit:** Modbus Power Limit register (41601) set lower than OCPP profile
  4. **Vehicle Drawing Excessive Current:** Uncontrolled load (e.g., resistance heater)
- **Charger Behavior:** Uses **MINIMUM** of: DIP switches, OCPP profile, Modbus settings
- **Example Scenario:** 
  - DIP switches: 16A max
  - OCPP backend sends: 32A SetChargingProfile
  - Charger tries to close contactors for 32A
  - Safety check fails → EV0082 fault
  - Contactors don't close, no PWM signal generated
- **Symptoms:**
  - Charger state changes to "Faulted"
  - vendorErrorCode: "EV0082" in StatusNotification
  - LED: Red, 4 flashes
  - No PWM signal on oscilloscope (straight DC voltage, no square wave)
  - Charger may cycle in/out of fault state
- **Diagnosis:**
  1. Check DIP switch configuration (physical setting on charger)
  2. Check OCPP SetChargingProfile messages (what current is backend commanding?)
  3. Check Modbus register 41601 (Power Limit) - should be 0xFFFF for max
  4. Verify vehicle is not uncontrolled load (e.g., resistance heater test equipment)
- **Fix:**
  1. Align all three settings (DIP, OCPP, Modbus) to same maximum current
  2. Set DIP switches to maximum rated current
  3. Set Modbus register 41601 to 0xFFFF (maximum)
  4. Configure OCPP backend to send profiles ≤ DIP switch rating
  5. Unplug gun, replug, verify fault clears
- **Critical Understanding:** This is a **safety feature**, not a malfunction. Charger preventing overcurrent condition.
- **Related:** See [current_limiting.md](../patterns/current_limiting.md) for configuration hierarchy
- **Known Case:** [Federation University](../case-studies/federation_university.md) (Dec 2024) - After fixing 0W Modbus fallback, EV0082 appeared due to 32A OCPP profile vs lower charger configuration

### EV0099 - AC Output SCP (Short-Circuit Protection)
- **Code:** 10015 | **MCU Alarm:** 803(SCP) | **LED:** Red, 4 Flashes → Solid Red
- **Cause:** AC output current over protection (short circuit)
- **Root Cause:** Same as OCP but more severe
- **Fix:** Same as EV0082

## Thermal Protection Errors

### EV0084 - Ambient OTP (Over-Temperature Protection)
- **Code:** 10050 | **MCU Alarm:** 401 | **LED:** Red, 5 Flashes
- **Cause:** Ambient temperature too high
- **Root Cause:** Environmental temperature exceeds limits
- **Fix:** Power off for 10 minutes, check ventilation, contact support if persists

### EV0090 - Terminal OTP
- **Code:** 10040 | **MCU Alarm:** 402 | **LED:** Red, 5 Flashes
- **Cause:** Terminal temperature too high
- **Root Cause:** Connection point overheating
- **Fix:** Same as Ambient OTP

## Safety & Ground Errors

### EV0085 - RCD Fault (AC)
- **Code:** 10138 | **MCU Alarm:** 601(AC) | **LED:** Red, 2 Flashes → Solid Red
- **Cause:** Residual Current Detection activated
- **Root Cause:** Ground fault or RCD module fault
- **Fix:** Unplug gun, retry charging, check RCD module if persists

### EV0098 - RCD DC Fault
- **Code:** 10138 | **MCU Alarm:** 602(DC) | **LED:** Red, 2 Flashes → Solid Red
- **Cause:** DC residual current detected
- **Root Cause:** DC ground fault
- **Fix:** Same as AC RCD fault

### EV0086 - RCD Self-Test Fail
- **Code:** 10100 | **MCU Alarm:** 511 | **LED:** Solid Red
- **Cause:** RCD module self-test failed
- **Root Cause:** Faulty RCD module
- **Fix:** Power cycle, replace RCD module if persists

### EV0088 - GMI (Ground Monitor - Infrastructure)
- **Code:** 10139 | **MCU Alarm:** 203 | **LED:** Red, 3 Flashes
- **Cause:** Ground monitoring activated
- **Root Cause:** Ground connection issue
- **Fix:** Check ground connection, verify PE line, contact support if persists

### EV0089 - Input Miswiring
- **Code:** 10140 | **MCU Alarm:** 204 | **LED:** Red, 6 Flashes → Solid Red
- **Cause:** Incorrect input wiring detected
- **Root Cause:** L1/L2/N wired incorrectly
- **Fix:** Requires technician - verify L1/L2/N connections

## Relay Errors

### EV0087 - Relay Welding
- **Code:** 10115 | **MCU Alarm:** 512(weld) | **LED:** Solid Red → Red, N Flashes
- **Cause:** Relay welding detected
- **Root Cause:** Relay contacts stuck/welded
- **Fix:** Power cycle, replace relay if error persists

### EV0097 - Relay Driving Fault
- **Code:** 10115 | **MCU Alarm:** 513(Driver) | **LED:** Solid Red
- **Cause:** Relay driving circuit fault
- **Root Cause:** Relay driver hardware failure
- **Fix:** Power cycle, replace relay if persists

## Pilot Signal Errors

### EV0091 - PWMP Error (Pilot Positive/Diode/Error)
- **Code:** 10141 | **MCU Alarm:** 701(P)/702(D)/703(E) | **LED:** Red, 7 Flashes
- **Cause:** Pilot signal not in normal range
- **Root Cause:** Communication signal integrity issue
- **Fix:** Use oscilloscope to measure pilot signal level

### EV0100 - PWMN Error (Pilot Negative)
- **Code:** 10141 | **MCU Alarm:** 704(N) | **LED:** Red, 7 Flashes → Solid Red
- **Cause:** Pilot signal negative not in normal range
- **Root Cause:** Same as PWMP
- **Fix:** Same as PWMP

## Gun Connector Errors

### EV0092 - GUN PP Error
- **Code:** 10149 | **MCU Alarm:** 811 | **LED:** Red, 7 Flashes
- **Cause:** Gun type error
- **Root Cause:** Incorrect or incompatible gun connector
- **Fix:** Check gun connector type

### EV0093 - GUN Motor Lock Fail
- **Code:** 10143 | **MCU Alarm:** 521 | **LED:** Red, 7 Flashes
- **Cause:** Gun lock function failure
- **Root Cause:** Mechanical lock malfunction
- **Fix:** Requires technician - power cycle, check lock status

### EV0101 - GUN Motor Unlock Fail
- **Code:** 10149 | **MCU Alarm:** 811 | **LED:** Red, 7 Flashes → Solid Red
- **Cause:** Gun unlock function failure
- **Root Cause:** Mechanical unlock malfunction
- **Fix:** Same as lock fail

## Sensor Errors

### EV0094 - NTC Error
- **MCU Alarm:** 501/502 | **LED:** Solid Red
- **Cause:** Ambient/Terminal NTC open or short
- **Root Cause:** Temperature sensor failure
- **Fix:** Replace NTC sensor

### EV0095 - MCU Self Test Fail
- **MCU Alarm:** 531 | **LED:** Solid Red
- **Cause:** MCU self-test failed (UL model)
- **Root Cause:** MCU hardware fault
- **Fix:** Replace MCU/board

### EV0096 - METER IC Fail
- **MCU Alarm:** 24 | **LED:** Solid Red
- **Cause:** Internal meter abnormal
- **Root Cause:** Metering IC failure
- **Fix:** Replace meter module

## Communication Errors

### EV0110 - Internal Comm Fail (MPU/MCU)
- **MCU Alarm:** 21 | **LED:** Solid Red
- **Cause:** Internal UART communication failure
- **Root Cause:** MPU-MCU communication broken
- **Fix:** Power cycle, check internal connections
- **Related:** See [hardware_faults.md](../patterns/hardware_faults.md)

### EV0102 - BT Abnormal
- **MCU Alarm:** 521 | **LED:** Solid Red
- **Cause:** Bluetooth module abnormal
- **Root Cause:** BT module failure
- **Fix:** Disable BT or replace module

### EV0111 - RFID Card Abnormal
- **Cause:** RFID reader malfunction
- **Fix:** Check RFID module
- **Related:** See [hardware_faults.md](../patterns/hardware_faults.md) for RYRR20I pattern

## Network Connectivity Errors (Common)

### EV0117 - Disconnect from Backend (Ethernet)
- **Code:** 11002
- **Cause:** Lost connection to OCPP backend via Ethernet
- **Root Cause:** Network cable, switch, or backend server issue
- **Fix:** Check Ethernet cable, verify switch port, check backend server status

### EV0118 - Disconnect from Backend (WiFi)
- **Code:** 11003
- **Cause:** Lost connection to OCPP backend via WiFi
- **Root Cause:** WiFi signal, AP, or backend server issue
- **Fix:** Check WiFi signal strength, AP connectivity, backend server status

### EV0119 - Disconnect from Backend (3G)
- **Code:** 11004
- **Cause:** Lost connection to OCPP backend via cellular
- **Root Cause:** Cellular signal or backend server issue
- **Fix:** Check 3G signal, verify APN settings, check backend

### EV0120 - Internet Not OK (Ethernet)
- **Code:** 11005
- **Cause:** No internet connectivity via Ethernet
- **Root Cause:** Upstream network issue
- **Fix:** Check router/gateway, verify internet connection

### EV0121 - Internet Not OK (WiFi)
- **Code:** 11006
- **Cause:** No internet connectivity via WiFi
- **Root Cause:** WiFi AP has no internet
- **Fix:** Check AP internet connectivity

### EV0122 - Internet Not OK (3G)
- **Code:** 11007
- **Cause:** No internet connectivity via cellular
- **Root Cause:** Cellular carrier issue
- **Fix:** Check APN settings, verify carrier service

### EV0123 - Disconnect from AP (WiFi)
- **Code:** 11008
- **Cause:** Lost connection to WiFi access point
- **Root Cause:** WiFi signal weak, AP down, credentials changed
- **Fix:** Check WiFi signal, verify AP status, check credentials

### EV0124 - Disconnect from APN (3G)
- **Code:** 11009
- **Cause:** Lost connection to cellular APN
- **Root Cause:** APN settings incorrect or carrier issue
- **Fix:** Verify APN settings, check SIM card, contact carrier

### EV0125 - 3G Signal Weak
- **Code:** 11015
- **Cause:** Cellular signal strength low
- **Root Cause:** Poor cellular coverage
- **Fix:** Relocate antenna, use external antenna, check carrier coverage

### EV0126 - WiFi Signal Weak
- **Code:** 11016
- **Cause:** WiFi signal strength low
- **Root Cause:** Distance from AP, interference, obstacles
- **Fix:** Move closer to AP, reduce interference, use better antenna

## Module Status Errors

### EV0112 - WiFi Module Not OK
- **Code:** 10128
- **Cause:** WiFi module initialization failed
- **Fix:** Power cycle, check module

### EV0113 - 3G Module Not OK
- **Code:** 10129
- **Cause:** Cellular module initialization failed
- **Fix:** Check SIM card, power cycle, verify module

## System Errors

### EV0114 - Memory Error
- **Code:** 10144
- **Cause:** Memory read/write error
- **Fix:** Power cycle, replace board if persists

### EV0115 - Init Failed
- **Code:** 10145
- **Cause:** System initialization failure
- **Fix:** Power cycle, check firmware

### EV0116 - Rating Current Set Error
- **Code:** 10146
- **Cause:** Current rating configuration invalid
- **Fix:** Check DIP switch settings

## Operational Events

### EV0103 - LIMIT_toNoPower
- **MCU Alarm:** 101 | **LED:** Yellow
- **Cause:** Charger in current-limited state (0A or no power)
- **Root Causes:**
  1. **Local LMS (Modbus):** Load management system commanding 0A limit
  2. **OCPP Backend:** SetChargingProfile with <6A limit
  3. **Network Issue:** LMS communication failure causing stuck state
- **Symptoms:** Charger state stuck in "Preparing", unable to deliver power
- **Critical Behavior:** State persists in charger memory even after LMS disconnection
- **Resolution:**
  1. Identify source: Check for Load_Mgmt_Comm errors vs OCPP SetChargingProfile messages
  2. If LMS issue: Physically disconnect LMS → Factory reset → Test standalone
  3. If OCPP issue: Contact backend provider to adjust load management
- **Note:** NOT an error - informational event indicating external limiting is active
- **Related:** See [current_limiting.md](../patterns/current_limiting.md) and [modbus_registers.md](modbus_registers.md)
- **Known Cases:** [Federation University](../case-studies/federation_university.md) - 144 LIMIT_toNoPower events

### EV0104 - Emergency Stop
- **MCU Alarm:** 17 | **LED:** Solid Red
- **Cause:** External emergency button pressed
- **Root Cause:** User-initiated emergency stop
- **Fix:** Unplug gun, release emergency button

## Error Code Format Notes

- **Error Codes:** EVXXXX format (e.g., EV0081, EV0117)
- **Recovery Codes:** Set highest bit to 1 (e.g., EV0081 error → EV8081 recovery, EV0124 → EV1124)
- **Numeric Codes:** 6-digit codes (e.g., 111005, 111008) are recovery events
- **Event Files:** Located in Storage/EventLog/[YYYY.MM]SERIAL_FIRMWARE_Events.csv
- **Format:** `YYYY.MM.DD HH:MM:SS-CODE`
- **Example:** `2026.01.14 13:17:21-EV0123` = "Disconnect from AP through WiFi"

---

**Related Knowledge:**
- [Current Limiting Patterns](../patterns/current_limiting.md) - EV0082, EV0103 context
- [Modbus Registers](modbus_registers.md) - Configuration for EV0082, EV0103
- [Hardware Faults](../patterns/hardware_faults.md) - MCU, RFID patterns
- [OCPP Protocol](../patterns/ocpp_protocol.md) - Network error context
