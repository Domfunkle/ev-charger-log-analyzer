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

## Installation

### Recommended: Install System-Wide

```bash
# Navigate to project root
cd /path/to/ev-charger-log-analyzer

# Install in editable mode (recommended for development)
pip install -e .

# OR install normally
pip install .
```

After installation, use the `delta-ac-max-analyzer` command from anywhere.

### Alternative: Direct Script Execution

```bash
# Run script directly (no installation needed)
python ~/dev/ev-charger-log-analyzer/analyzers/delta_ac_max/analyze.py
```

## Usage

### Basic Usage

```bash
# Extract and analyze all ZIPs in current directory
delta-ac-max-analyzer

# Navigate to directory containing charger log ZIPs first
cd /path/to/logs
delta-ac-max-analyzer
```

### Analyze Specific ZIP Files

```bash
# Analyze a single specific ZIP file
delta-ac-max-analyzer -z EV01_before.zip

# Analyze multiple specific ZIP files
delta-ac-max-analyzer -z EV01_before.zip EV01_after.zip EV05_before.zip

# Analyze specific ZIP in a different directory
delta-ac-max-analyzer -d /path/to/logs -z EV01_before.zip
```

### Command Line Options

```bash
# Skip extraction if logs already extracted
delta-ac-max-analyzer --skip-extraction

# Specify custom directory
delta-ac-max-analyzer --directory /path/to/logs
delta-ac-max-analyzer -d /path/to/logs

# Analyze specific ZIP file(s)
delta-ac-max-analyzer -z FILE1.zip [FILE2.zip ...]

# Don't move ZIPs to archive folder
delta-ac-max-analyzer --no-archive

# Show help
delta-ac-max-analyzer --help
```

### Examples

```bash
# Compare before/after firmware update for one charger
delta-ac-max-analyzer -z EV01_before.zip EV01_after.zip

# Analyze only chargers with known issues
delta-ac-max-analyzer -z EV03.zip EV07.zip EV12.zip

# Batch analyze all ZIPs in a specific directory
delta-ac-max-analyzer -d /mnt/charger_logs

# Analyze already extracted logs without re-extracting
delta-ac-max-analyzer --skip-extraction
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
║          EV CHARGER LOG ANALYSIS TOOL v1.1                    ║
╚═══════════════════════════════════════════════════════════════╝

Working Directory: /path/to/charger_logs

================================================================================
EXTRACTING PASSWORD-PROTECTED ZIP FILES
================================================================================

Found 2 ZIP file(s) to extract

Processing: [2026.01.22-02.02]KKB233100447WEEV9.zip
  Serial: KKB233100447WE
  Password: KKB233100447WE@delta
  Destination: /path/to/charger_logs/[2026.01.22-02.02]KKB233100447WEEV9
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

**Version:** 0.0.1 (Development)  
**Last Updated:** January 26, 2026  
**Author:** Daniel Nathanson  
**Status:** In Development - Not Production Ready

**Current Features:**
- ChargBox ID extraction from Config/evcs
- System-wide installation via pip
- Selective ZIP file analysis
- Backend disconnect detection
- MCU error detection
- Logging gap detection
- Firmware version extraction
- CSV export

**Known Limitations:**
- Still in active development
- Limited production testing
- May require refinements based on field usage

## Full Documentation

See: `docs/delta_ac_max_usage.md` for complete usage guide
