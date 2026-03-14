# EVS09 Replacement (KKB251700192WE) - Offline Policy Misconfiguration (Feb-Mar 2026)

**Date:** February 26 - March 13, 2026  
**Charger:** KKB251700192WE (EVS09 replacement)  
**Site:** DoCs Joondalup, 5 Clarke Cres, Joondalup WA 6027  
**Model:** Delta AC MAX Smart 7-22kW (EIAW-E22KTSE5A04)  
**Firmware:** Fw1Ver 01.00.38.07, Fw2Ver 01.26.39.00  
**Issue:** Replacement charger unable to authorize sessions — misconfiguration, not hardware  
**Status:** CLOSED - Resolved March 13 by correcting offline policy  
**Root Cause:** Offline authorization policy incompatible with disconnected backend

---

## Executive Summary

After the original EVS09 (KKB233100447WE) was replaced due to a [SystemLog failure](evs09_systemlog_failure.md), the replacement unit (KKB251700192WE) appeared to not charge. Investigation revealed the issue was **misconfiguration**: the charger's offline authorization policy was set to require local list / authorize cache, but the fresh replacement unit had **no cached credentials** and **no backend connectivity** to populate them. Setting the offline policy to "Plug and Charge" resolved the issue.

---

## Site Context

**DoCs Joondalup** has 15 Delta AC MAX chargers managed by a local LMS/gateway at `192.168.21.21`. Backend connectivity (OCPP over Ethernet) has been unavailable since approximately Feb 9, 2026 — the chargers operate in offline mode with no OCPP session to the CSMS.

Key site configuration:
- OCPP endpoint: `ws://192.168.21.21/ws/ocpp` (port 80, local gateway)
- Network: Ethernet, static IPs on `192.168.21.x` subnet
- Gateway/DNS: `192.168.21.21`
- LMS/EVLM: Disconnected since Feb 9

---

## Timeline

### Feb 26, 2026 - Replacement Installed
- Original EVS09 (KKB233100447WE) physically replaced with KKB251700192WE
- Charger commissioned with default/initial configuration
- Offline authorization policy set to "Local list and Authorize cache"
- Backend (OCPP) unreachable — charger immediately operating offline

### Feb 26 - Mar 13 - Charger Appears Non-Functional
- Users report EVS09 won't charge
- OCPP logs show repeated `IsAuthOK_OCPP16J` failures (180 occurrences)
- Authorization rejected because:
  1. Backend unreachable → can't authorize via OCPP
  2. Local auth cache empty (fresh unit, never connected to backend)
  3. Offline policy requires cache hit → no sessions authorized

### Mar 13, 2026 - Configuration Corrected
- Tom (field tech) visited site
- Changed offline authorization policy to "Plug and Charge"
- Charger immediately began authorizing and charging normally

---

## Log Evidence

### Configuration (Config/evcs)
```
ChargBoxId = EVS09
Fw1Ver = 01.00.38.07
Fw2Ver = 01.26.39.00
OCPP_URI = ws://192.168.21.21/ws/ocpp
OCPP_Port = 80
network_mode = 0 (Ethernet)
network_ipmode = 1 (Static)
network_ip = 192.168.21.109
network_gw = 192.168.21.21
network_dns = 192.168.21.21
```

### OCPP Log - Authorization Failures
```
CLIENT_CONNECTION_ERROR: 36,537 occurrences
conn fail: 113 (No route to host): 25,523 occurrences
IsAuthOK_OCPP16J failures: 180 occurrences
```

The `CLIENT_CONNECTION_ERROR` and `conn fail: 113` entries are expected — the backend gateway is unreachable. The `IsAuthOK_OCPP16J` failures are the authorization rejections caused by the offline policy misconfiguration.

### EventLog - Fault Codes Observed
| Code | Description | Count | Notes |
|------|------------|-------|-------|
| EV0081 | AC Input OVP | Low | Transient grid events |
| EV0082 | AC Output OCP | Low | Transient |
| EV0083 | AC Input UVP | Low | Transient grid events |
| EV0085 | RCD | Low | Normal sensitivity |
| EV0088 | GMI | Low | Normal |
| EV0091 | PWMP (Pilot) | Few | **Test artifact** — see below |

### EV0091 / State D Events - Test Artifacts

Several EV0091 (PWM/pilot) events and State D transitions were observed. These are **NOT real faults** — they are artifacts from the field technician's **charger checker tool**, which tests State D (ventilation request). Delta AC MAX does not support State D, so the charger correctly faults and recovers.

**Pattern:**
```
State D detected → EV0091 fault → charger recovers → normal operation
```

**Implication for analyzer:** EV0091 events coinciding with State D transitions should be flagged as potential test artifacts rather than genuine pilot instability.

---

## Root Cause Analysis

### The Offline Policy Problem

Delta AC MAX chargers have an offline authorization policy that determines how to handle RFID/authorization when the OCPP backend is unreachable:

| Policy | Behavior When Offline |
|--------|----------------------|
| **Plug and Charge** | Allow all sessions without authorization |
| **Local list and Authorize cache** | Only authorize IDs found in local cache |
| **Reject all** | No sessions authorized |

A **freshly installed replacement unit** has:
- No local authorization list (never provisioned)
- No authorize cache (never connected to backend)
- No OCPP connection to populate either

Setting the policy to "Local list and Authorize cache" on such a unit is functionally equivalent to "Reject all" until the backend comes online and populates the cache.

### Why This Was Missed

1. The original unit had accumulated authorization cache from months of operation
2. The replacement was assumed to inherit the same effective behavior
3. The site's backend being offline masked the usual auto-population path
4. Commissioning checklist did not include offline policy verification

---

## Lessons Learned

### 1. Replacement Unit Commissioning Checklist
When replacing a charger at a site with no backend connectivity:
- ✅ Verify offline authorization policy is set to "Plug and Charge"
- ✅ Verify ChargBox ID matches site records
- ✅ Verify network configuration (IP, gateway, DNS)
- ✅ Verify OCPP endpoint URL
- ✅ Test at least one charge session before leaving site

### 2. Offline Policy Fleet Audit
All chargers at a site should have consistent offline policies. When backend connectivity is lost site-wide, any charger not set to "Plug and Charge" will fail to authorize.

### 3. Charger Checker State D Artifacts
Field technician test tools that exercise State D produce EV0091 and state transition events in the logs. These should be recognized as test artifacts, not genuine faults, when:
- State D transitions appear in isolation
- EV0091 events cluster with State D
- Normal operation resumes immediately after
- Events coincide with known site visit dates

### 4. Backend Connectivity Masking
When a site has no backend, many charger issues are masked or amplified:
- Authorization failures may appear as hardware faults
- OCPP connection errors (36K+ `CLIENT_CONNECTION_ERROR`) are expected noise, not diagnostic
- True hardware faults may be hidden in the noise

---

## Broader Site Status (DoCs Joondalup, as of Mar 2026)

| Item | Status |
|------|--------|
| EVS09 (KKB251700192WE) | ✅ Fixed — offline policy corrected |
| EVS08 | ⚠️ Needs investigation — recurring MCU comm failure, logs not yet pulled |
| LMS/EVLM | ❌ Disconnected since Feb 9 — reconnection plan needed |
| Fleet offline policy | ⚠️ Audit recommended for all 15 chargers |
| Backend connectivity | ❌ All chargers offline from CSMS |

---

## Related Knowledge

- [EVS09 SystemLog Failure](evs09_systemlog_failure.md) - Original unit's logging failure (predecessor to this replacement)
- [Hardware Faults](../patterns/hardware_faults.md) - RFID, MCU, network fault patterns
- [OCPP Protocol](../patterns/ocpp_protocol.md) - OCPP 1.6 authorization flow
- [Current Limiting](../patterns/current_limiting.md) - LMS/Modbus configuration
