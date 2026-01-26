# Delta AC MAX Log Analyzer - Usage Guide

## Overview
This tool automates the analysis of Delta AC MAX charger logs, extracting password-protected ZIP files and analyzing for common issues.

**Cross-Platform:** Works on Windows, Linux, and macOS!

## Prerequisites
- **Python 3.6 or higher** (comes with built-in ZIP support)
- No additional packages required - uses only Python standard library!

## Installation

### Recommended: System-Wide Installation

Install once to use the `delta-ac-max-analyzer` command from anywhere:

```bash
# Clone or navigate to the repository
cd /path/to/ev-charger-log-analyzer

# Install in editable/development mode (recommended for development)
pip install -e .

# OR install normally
pip install .
```

After installation, the `delta-ac-max-analyzer` command will be available system-wide.

### Alternative: Direct Script Execution

You can also run the script directly without installation:

**Linux/macOS:**
```bash
chmod +x analyzers/delta_ac_max/analyze.py
./analyzers/delta_ac_max/analyze.py
```

**Windows:**
```powershell
python analyzers\delta_ac_max\analyze.py
```

## Quick Start

### Basic Usage (Extract and Analyze All ZIPs)
```bash
# Navigate to folder containing ZIP files
cd /path/to/charger/logs

# Run the analyzer
delta-ac-max-analyzer
```

This will:
1. Automatically extract all ZIP files using the pattern `SERIAL@delta` as password
2. Move ZIPs to "Original Zips" folder
3. Analyze all extracted logs
4. Display summary report
5. Export detailed results to CSV

### Analyze Specific ZIP File(s)
```bash
# Analyze a single specific ZIP file
delta-ac-max-analyzer -z EV01_before.zip

# Analyze multiple specific ZIP files
delta-ac-max-analyzer -z EV01_before.zip EV01_after.zip EV05_before.zip

# Analyze specific ZIP in a different directory
delta-ac-max-analyzer -d /path/to/logs -z EV01_before.zip
```

When using `-z`, only the specified ZIP files will be extracted and analyzed.

### Analyze Already-Extracted Logs
```bash
# If logs are already extracted, skip extraction
delta-ac-max-analyzer --skip-extraction
```

### Specify Custom Directory
```bash
# Analyze all ZIPs in a specific directory
delta-ac-max-analyzer --directory /path/to/logs

# Short form
delta-ac-max-analyzer -d /path/to/logs
```

### Keep Original ZIPs in Place
```bash
# Extract but don't move ZIPs to archive folder
delta-ac-max-analyzer --no-archive
```

## Command Line Options

```
usage: delta-ac-max-analyzer [-h] [-d DIRECTORY] [-z [FILE ...]] 
                              [--skip-extraction] [--no-archive]

Options:
  -h, --help            Show help message and exit
  -d, --directory DIR   Directory containing log ZIP files (default: current directory)
  -z, --zip FILE [...]  Specific ZIP file(s) to extract and analyze
  --skip-extraction     Skip ZIP extraction, analyze existing folders only
  --no-archive          Do not move ZIP files to archive folder after extraction
```

## Examples

```bash
# Extract and analyze all ZIPs in current directory
delta-ac-max-analyzer

# Analyze one specific charger's logs
delta-ac-max-analyzer -z EV01_before.zip

# Compare before/after update for one charger
delta-ac-max-analyzer -z EV01_before.zip EV01_after.zip

# Analyze specific chargers from a batch
delta-ac-max-analyzer -z EV01.zip EV05.zip EV12.zip

# Work with logs in different directory
delta-ac-max-analyzer -d C:\Charger_Logs

# Analyze specific file from different directory
delta-ac-max-analyzer -d /mnt/logs -z EV01_before.zip

# Extract specific ZIPs but keep them in place
delta-ac-max-analyzer -z EV01.zip EV02.zip --no-archive

# Analyze already-extracted folders only
delta-ac-max-analyzer --skip-extraction
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

