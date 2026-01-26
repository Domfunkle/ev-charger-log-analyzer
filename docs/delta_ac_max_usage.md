# EV Charger Log Analysis Tool - Usage Guide

## Overview
This Python script automates the analysis of EV charger logs, extracting password-protected ZIP files and analyzing for common issues.

**Cross-Platform:** Works on Windows, Linux, and macOS!

## Prerequisites
- **Python 3.6 or higher** (comes with built-in ZIP support)
- No additional packages required - uses only Python standard library!

## Installation

### Linux/macOS
```bash
# Make script executable
chmod +x analyze_charger_logs.py

# Run directly
./analyze_charger_logs.py
```

### Windows
```powershell
# Run with Python
python analyze_charger_logs.py
```

## Quick Start

### Basic Usage (Extract and Analyze)
```bash
# Navigate to folder containing ZIP files
cd /path/to/charger/logs

# Run the script
python analyze_charger_logs.py
```

This will:
1. Automatically extract all ZIP files using the pattern `SERIAL@delta` as password
2. Move ZIPs to "Original Zips" folder
3. Analyze all extracted logs
4. Display summary report
5. Export detailed results to CSV

### Analyze Already-Extracted Logs
```bash
# If logs are already extracted, skip extraction
python analyze_charger_logs.py --skip-extraction
```

### Specify Custom Directory
```bash
# Analyze logs in a specific directory
python analyze_charger_logs.py --directory /path/to/logs
```

### Keep Original ZIPs in Place
```bash
# Extract but don't move ZIPs to archive folder
python analyze_charger_logs.py --no-archive
```

## Command Line Options

```
usage: analyze_charger_logs.py [-h] [-d DIRECTORY] [--skip-extraction] [--no-archive]

Options:
  -h, --help            Show help message and exit
  -d, --directory DIR   Directory containing log ZIP files (default: current directory)
  --skip-extraction     Skip ZIP extraction, analyze existing folders only
  --no-archive          Do not move ZIP files to archive folder after extraction
```

## What the Script Detects

The script automatically checks for:

✅ **Backend Connection Issues**
- Counts "Backend connection fail" events
- Flags chargers with >10 disconnects

✅ **MCU Communication Errors**
- Detects "Send Command 0x### to MCU False" patterns
- Flags any charger with MCU errors

✅ **Logging Gaps**
- Identifies multi-day gaps in SystemLog entries
- Reports date ranges of missing logs

✅ **Firmware Versions**
- Extracts current firmware version (Fw2Ver)
- Useful for verifying updates

✅ **High Error Counts**
- Flags chargers with >100 error entries
- May indicate developing issues

## Output

### Console Output
The script displays:
1. **Extraction Progress** - Shows each ZIP being extracted
2. **Analysis Progress** - Shows each charger being analyzed with color-coded status
3. **Summary by Charger** - Groups BEFORE/AFTER logs for easy comparison
4. **Final Summary** - Total count of clean vs. problematic chargers

Color coding:
- 🟢 **Green** = Clean, no issues
- 🟡 **Yellow** = Warning or has issues
- 🔴 **Red** = Issue status

### CSV Export
Detailed results exported to: `ChargerAnalysisResults_YYYYMMDD_HHMMSS.csv`

Contains:
- EV Number
- Serial Number
- Firmware Version
- Disconnect Counts
- MCU Error Counts
- Logging Gaps
- Issue Descriptions
- Status

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
  Destination: [2026.01.22-02.02]KKB233100447WEEV9
  ✓ Extracted successfully

...

================================================================================
ANALYZING CHARGER LOGS
================================================================================

Found 28 log folders to analyze

Analyzing: [2026.01.22-04.01]KKB233100027WEEV3 -UP
  EV3: Issue
    - High backend disconnects: 1944

...

================================================================================
SUMMARY REPORT
================================================================================

EV03
  [AFTER UPDATE]
    Firmware: 01.26.39.00
    Backend Disconnects: 1944
    MCU Errors: 0
    Issues:
      - High backend disconnects: 1944

EV08
  [AFTER UPDATE]
    Firmware: 01.26.39.00
    Backend Disconnects: 0
    MCU Errors: 0

...

================================================================================
FINAL SUMMARY
================================================================================
Total Chargers Analyzed: 15
Clean: 14
With Issues: 1

Detailed results exported to: ChargerAnalysisResults_20260126_025530.csv

Analysis complete!
```

## Platform-Specific Notes

### Linux
- Script uses native Python zipfile module (no external dependencies)
- Color output works in standard terminals
- Use forward slashes in paths: `/path/to/logs`

### macOS
- Same as Linux
- Works with default Python 3 installation

### Windows
- Use backslashes or forward slashes: `C:\Logs` or `C:/Logs`
- Color output works in Windows Terminal and PowerShell
- May show plain text in old cmd.exe

## Troubleshooting

### "No module named zipfile"
This shouldn't happen - zipfile is part of Python's standard library. Ensure you're using Python 3.6+:
```bash
python --version  # Should show 3.6 or higher
```

### "Password incorrect" errors
- Verify ZIP filename follows pattern: `[DATE]SERIALEVXX.zip`
- Serial must be exactly 14 characters after the `]`
- Password format is `SERIAL@delta` (case-sensitive)

### Permission Errors (Linux/macOS)
```bash
# Make script executable
chmod +x analyze_charger_logs.py

# Or run with python directly
python3 analyze_charger_logs.py
```

### No Color Output
If colors don't work:
- Windows: Use Windows Terminal or PowerShell (not cmd.exe)
- Linux/macOS: Most terminals support ANSI colors by default
- Colors are cosmetic only - functionality is unaffected

## Tips

1. **First Time Setup**: Drop the script in the folder with your ZIPs and run it
2. **Repeat Analysis**: Use `--skip-extraction` if you've already extracted the ZIPs
3. **Keep ZIPs**: Use `--no-archive` if you don't want ZIPs moved
4. **CSV for Excel**: Open the CSV file in Excel/LibreOffice for detailed filtering

## Advantages Over PowerShell Version

✅ **Cross-Platform** - Works on Windows, Linux, macOS  
✅ **No Dependencies** - Uses only Python standard library  
✅ **Portable** - Single file, easy to distribute  
✅ **Standard Tools** - Python is commonly available on most systems  

## Future Enhancements

Potential additions:
- OCPP event analysis
- Charging session statistics  
- Pilot state change tracking
- Automatic report generation (PDF/HTML)
- Historical trend comparison
- Email notifications

---

**Version:** 1.0  
**Author:** Daniel Nathanson  
**Last Updated:** January 26, 2026  
**Language:** Python 3.6+

