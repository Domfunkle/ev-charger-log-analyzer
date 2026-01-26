# Delta AC MAX Charger Analyzer

Python script for automated analysis of Delta AC MAX charger logs.

## Features

- Auto-extracts password-protected ZIP files (pattern: `SERIAL@delta`)
- Detects backend connection failures
- Identifies MCU communication errors
- Finds logging gaps (multi-day missing entries)
- Extracts firmware versions
- Flags chargers with high error counts
- Exports detailed results to CSV
- Cross-platform (Windows, Linux, macOS)

## Requirements

- Python 3.6 or higher
- No external dependencies (uses Python standard library only)

## Usage

### Basic Usage
```bash
# Navigate to directory containing charger log ZIPs
cd /path/to/logs

# Run the analyzer
python ~/dev/ev-charger-log-analyzer/analyzers/delta_ac_max/analyze.py
```

### Command Line Options
```bash
# Skip extraction if logs already extracted
python analyze.py --skip-extraction

# Specify custom directory
python analyze.py --directory /path/to/logs

# Don't move ZIPs to archive folder
python analyze.py --no-archive

# Show help
python analyze.py --help
```

## Log File Structure

Delta AC MAX logs are typically structured as:
```
[YYYY.MM.DD-HH.MM]SERIALNUMBEREVXX.zip
  └── Storage/
      └── SystemLog/
          ├── SystemLog              # Main system log
          └── OCPP16J_Log.csv       # OCPP events log
```

**Password Pattern:** `SERIALNUMBER@delta`  
Example: For serial `KKB233100447WE`, password is `KKB233100447WE@delta`

## What Gets Detected

### Backend Disconnects
Searches for: `"Backend connection fail"`  
**Threshold:** Flags if >10 disconnects found  
**Indicates:** Network issues, cable damage, or upstream connectivity problems

### MCU Communication Errors
Searches for: `"Send Command 0x### to MCU False, Resend Command"`  
**Threshold:** Flags any occurrence  
**Indicates:** Hardware communication issues, possible MCU fault

### Logging Gaps
Detects: Multi-day gaps in log timestamps  
**Threshold:** Flags if gap >1 day  
**Indicates:** System crashes, power loss, or logging system failure

### Firmware Version
Extracts: `"Fw2Ver: XX.XX.XX.XX"`  
**Purpose:** Verify firmware updates, identify version mismatches

### High Error Counts
Counts: Total lines containing "error" or "fail"  
**Threshold:** Flags if >100 errors  
**Indicates:** Systemic issues requiring investigation

## Output

### Console Output
- Color-coded analysis results (green=clean, yellow=issues)
- Summary by charger (groups BEFORE/AFTER update logs)
- Final statistics (total chargers, clean vs. issues)

### CSV Export
File: `ChargerAnalysisResults_YYYYMMDD_HHMMSS.csv`

Columns:
- EV Number
- Serial Number
- Firmware Version
- Backend Disconnects
- MCU Errors
- Logging Gaps
- Total Errors
- Issue Descriptions
- Status (Clean/Issue)

## Example Output

```
╔═══════════════════════════════════════════════════════════════╗
║          EV CHARGER LOG ANALYSIS TOOL v1.0                   ║
╚═══════════════════════════════════════════════════════════════╝

Working Directory: /path/to/charger_logs

================================================================================
EXTRACTING PASSWORD-PROTECTED ZIP FILES
================================================================================

Found 28 ZIP files

Processing: [2026.01.22-02.02]KKB233100447WEEV9.zip
  Serial: KKB233100447WE
  Password: KKB233100447WE@delta
  ✓ Extracted successfully

...

================================================================================
ANALYZING CHARGER LOGS
================================================================================

Analyzing: EV03 [AFTER UPDATE]
    Firmware: 01.26.39.00
    Backend Disconnects: 15
    MCU Errors: 0
    ✓ Status: Issue (high backend disconnects)

...

================================================================================
FINAL SUMMARY
================================================================================
Total Chargers Analyzed: 15
Clean: 14
With Issues: 1

Detailed results exported to: ChargerAnalysisResults_20260126_025530.csv
```

## Troubleshooting

### No ZIP files found
- Ensure you're in the correct directory
- Check ZIP files follow naming pattern: `[DATE]SERIALEVXX.zip`

### Password extraction failed
- Verify filename contains 14-character serial number
- Serial should be immediately after `]` in filename

### Permission errors (Linux/macOS)
```bash
chmod +x analyze.py
```

### No color output
- Windows: Use PowerShell or Windows Terminal (not cmd.exe)
- Colors are cosmetic only, functionality unaffected

## Known Patterns (Delta AC MAX)

### Reboot Detection
Pattern: `"BusyBox v1.28.4"` indicates system restart

### Normal Operation
Pattern: `"Backend connection success"` after brief disconnect is normal

### Critical Issues
- MCU errors: Communication hardware fault
- Logging gaps >1 day: System crash or power loss
- Backend disconnects >100/day: Network infrastructure issue

## Version

**Version:** 1.0  
**Last Updated:** January 26, 2026  
**Author:** Daniel Nathanson

## Full Documentation

See: `docs/delta_ac_max_usage.md` for complete usage guide
