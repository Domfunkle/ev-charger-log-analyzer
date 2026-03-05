# Wallbox 25kW DC Charger Analyzer

**Status:** Planned for future development

## Overview

This analyzer will be developed to handle Wallbox 25kW DC charger logs, similar to the Delta AC MAX analyzer.

## Planned Features

- Auto-extraction of log files
- Connection failure detection
- Hardware communication error detection
- Charging session analysis
- Firmware version tracking
- CSV export of results
- Cross-platform support

## Log Structure

Observed extracted structure (field logs):

```
Storage/
├── ChargingInfo/
├── Events/                        # NOTE: not EventLog/
└── SystemLog/
		├── [YYYY.MM]SystemLog
		├── [YYYY.MM]OCPP16J_Log.csv
		└── messages
```

Password-protected ZIP pattern observed:
- Password format: `SERIAL@delta`
- Example: `APG223100203W0@delta`

Model detection clues seen in SystemLog:
- Wallbox 25kW logs typically include `Storage/Events` and monthly file prefixes (`[YYYY.MM]...`).
- Modem strings observed in field:
	- `MU709s-6` (3G/HSPA family)
	- `PLS83-W` (LTE Cat.4 capable module with legacy 3G fallback)

Important:
- Existing `delta-ac-max-analyzer` now skips these logs with an explicit "unsupported model" warning.
- A dedicated wallbox 25kW analyzer is still pending.

## Development Notes

When implementing this analyzer, consider:
- Log file format and structure specific to Wallbox 25kW DC
- Password protection mechanism (if any)
- Common failure patterns for DC chargers
- OCPP 1.6/2.0.1 message analysis
- Charging session metrics (kWh delivered, duration, etc.)

## Placeholder

This is a placeholder for future development. If you need this analyzer urgently, please contact the development team.

---

**Status:** Not Started  
**Priority:** Low  
**Target Date:** TBD
