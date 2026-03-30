# KKB251100063WE — Flash-Cached MeterValues Deadlock (Andrew Carr Demo Unit)

**Charger ID:** DeltaSA1 (KKB251100063WE)  
**Site:** Demo / test unit (Andrew Carr)  
**Date:** March 20 2026 (deadlock active), March 26 2026 (logs captured)  
**Firmware:** v01.26.37.00  
**Status:** Resolved by factory reset + recommission  

---

## Summary

Demo charger entered an unrecoverable connect/disconnect loop after a charging session was
left running when the backend connection was interrupted. The charger cached unsent
MeterValues to flash (correct per OCPP spec). On every subsequent reconnect, a firmware
write race condition prevented the MeterValues from ever being transmitted, causing the
charger's OCPP state machine to block indefinitely waiting for an ACK that never arrived.
The server's downstream commands (ClearChargingProfile) were answered with "CS Cmd busy"
until timeout, then the connection dropped and the cycle repeated every ~40 seconds for
over two hours. No RemoteStartTransaction was ever delivered to the charger.

---

## Timeline

| UTC Timestamp | Event |
|---|---|
| Mar 20 00:58:33 | txId 4101 StartTransaction accepted |
| Mar 20 00:59:58 | StopTransaction ACKed by server (server-side closed) |
| Mar 20 ~01:00 | MeterValues for txId 4101 NOT ACKed — frozen in flash at 00:59:32Z, 456 Wh |
| Mar 20 03:32 | Deadlock loop begins (2h17m duration, 206 cycles confirmed in server log) |
| Mar 19 06:34 UTC | Andrew's RFID demo (5:34 PM AEDT) — RemoteStartTransaction never arrived |
| Mar 26 03:23 | Log ZIP captured; charger EHOSTUNREACH (separate network issue) |

---

## Root Cause

### The Write Race Condition (Firmware Bug)

On every reconnect the charger logs `MeterValuesReq:pu8SendBuf=[2,...]` — this is a
pre-send log, written before the `lws_write()` call to libwebsockets. The server
unconditionally logs all received OCPP frames; MeterValues count in both server logs = 0.
The MeterValues frame never reaches the wire.

The trigger: the server sends SetChargingProfile immediately on connect, and on ACK
(~1 second) immediately sends ClearChargingProfile. The ClearChargingProfile arrives at
the charger at the **exact same millisecond** the charger's write callback is attempting
to write MeterValues. The libwebsockets write is silently dropped or delayed past
connection close.

### The Resulting OCPP State Machine Block

With MeterValues queued but not transmitted, the charger's state machine is waiting for
a call result. While waiting, it responds "CS Cmd busy" to all incoming CS commands. The
server retries ClearChargingProfile at 3-second intervals, receives "CS Cmd busy" each
time, then drops the message after ~9 seconds (`Removed message from DeltaSA1 queue`).
The charger's `[IsTxCmdOK]` timer fires after ~30 seconds → `MeterValuesReq NG`. The
server's Ping-Pong timeout fires at ~33-40 seconds → `LWS_CALLBACK_CLOSED`. Disconnect.

### The Stale Response Carry-Over

On each new connection the charger's first write is the **previous cycle's**
`ClearChargingProfileConf [3, OLD-UUID, {"status":"Unknown"}]` — a response buffered from
the dead connection. The server receives this and logs `BACKEND ERROR: Received message
with UniqueId: X cannot be matched`. This confirms the charger's write queue carries
stale data across connections, further delaying MeterValues.

### Full Per-Cycle Sequence

```
t+0.0s   Connection established
t+0.0s   Charger sends stale ClearChargingProfileConf [status:Unknown] from PREV cycle
t+0.0s   Server sends SetChargingProfile (queued)
t+1.0s   Charger ACKs SetChargingProfile
t+1.0s   Server sends ClearChargingProfile (0ms after ACK)
t+1.0s   Charger logs MeterValuesReq pu8SendBuf — SAME MILLISECOND as ClearChargingProfile
t+1.0s   MeterValues write FAILS SILENTLY (lws write race)
t+4.0s   Charger: CS Cmd busy (ClearChargingProfile retry 1)
t+7.0s   Charger: CS Cmd busy (retry 2)
t+10.0s  Charger: CS Cmd busy (retry 3)
...      (server retries every 3s for ~9s then drops)
t+31.0s  Charger: [IsTxCmdOK] Time out → MeterValuesReq NG → retry MeterValues (new UUID)
t+31.0s  New MeterValuesReq logged — also fails silently
t+33.0s  Server: Ping-Pong timeout → LWS_CALLBACK_CLOSED (code 1006)
t+33.0s  Charger: [IsTxCmdOK] Disconnection → MeterValuesReq NG
t+33.4s  Charger reconnects → go to t+0.0s (206 cycles total)
```

---

## Evidence

**CS Cmd busy count:** 2,457 in OCPP16J_Log.csv.0 (475 unique UUIDs)
- ClearChargingProfile: 380 (80%)
- SetChargingProfile: 84 (18%)
- TriggerMessage: 11 (2%)

**MeterValues in server logs:** 0 (both evlm2 server log files confirmed)

**Server BACKEND ERROR count:** 206 (log1) / 205 (log2) — all are stale
ClearChargingProfileConf responses from previous cycles, NOT MeterValues

**Zombie transaction:** txId 4101, MeterValues frozen at `2026-03-20T00:59:32Z`, 456 Wh

**Server confirmed:**
- 412 messages removed from DeltaSA1 queue (2 per cycle: ClearChargingProfile +
  TriggerMessage)
- 0 RemoteStartTransaction sent in entire 2h17m window
- Clock offset: charger ~1.4 seconds behind server UTC

---

## Detection Signatures

Look for these patterns in OCPP16J_Log.csv / OCPP16J_Log.csv.0:

```
[OCPP16J]MeterValuesReq:pu8SendBuf=[2,"<id>","MeterValues",{...transactionId...}]
[OCPP16J]OCPP16Callback:CS Cmd busy, unique ID=<same id as ClearChargingProfile>
[IsTxCmdOK] Time out
[OCPP16J] MeterValuesReq NG
```

Repeating in a ~40-second cycle with the same frozen MeterValues payload (same timestamp,
same energy value) is the definitive indicator.

**Key check:** Search server logs for `"MeterValues"` from this charger. If CS Cmd busy
is happening in the charger log but MeterValues never appear in the server log, this is
the write race bug, not a true two-party deadlock.

---

## Resolution

1. **Factory reset** the charger — clears flash transaction cache (txId 4101 MeterValues)
2. **Recommission** to test server — factory reset wipes OCPP and network settings
3. **Verify clean close:** start a session, stop it via server, confirm "Available" status
   before disconnecting

---

## Prevention

**Operational rule:** Always stop charging sessions cleanly via the server before
disconnecting. If backend connection is lost mid-session, reconnect and stop the session
before the charger is powered down or left disconnected for an extended period.

**Demo discipline:**
- Online demo: stop session → wait for "Available" → then disconnect from server
- Offline demo: switch charger to offline-only config before demoing without server

---

## Related Knowledge

- [Firmware Bugs](../reference/firmware_bugs.md) — MeterValues Write Race Condition entry
- [OCPP Protocol](../patterns/ocpp_protocol.md) — transaction message replay on reconnect
- [KKB241600082WE ChangeConfig Bursts](kkb241600082we_changeconfig_bursts.md) — different
  OCPP deadlock pattern for comparison

---

**Last Updated:** 2026-03-26  
**Analyst:** Copilot diagnostic session
