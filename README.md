# EV Charger Log Analyzer

Automated log analysis tools for various EV charger models. This toolkit helps diagnose common issues by extracting and analyzing charger logs for connection failures, communication errors, logging gaps, and firmware versions.

## Project Structure

```
ev-charger-log-analyzer/
├── README.md                    # This file
├── analyzers/                   # Model-specific analyzers
│   ├── delta_ac_max/           # Delta AC MAX charger analyzer
│   │   └── analyze.py          # Python script for Delta AC MAX logs
│   ├── wallbox_25kw_dc/        # Wallbox 25kW DC charger (future)
│   ├── wallbox_50kw/           # Wallbox 50kW charger (future)
│   └── slim100/                # Slim100 charger (future)
├── docs/                        # Documentation
│   └── delta_ac_max_usage.md   # Delta AC MAX usage guide
└── examples/                    # Example outputs and test data
    └── delta_ac_max/           # Delta AC MAX examples
```

## Supported Chargers

### 🚧 Delta AC MAX
**Status:** In Development (v0.0.1)  
**Script:** `analyzers/delta_ac_max/analyze.py`  
**Documentation:** `docs/delta_ac_max_usage.md`

**Features:**
- Auto-extracts password-protected logs (SERIAL@delta pattern)
- Detects backend connection failures
- Identifies MCU communication errors
- Finds logging gaps (missing log entries)
- Extracts firmware versions and ChargBox IDs
- Flags high error counts
- Exports results to CSV

**Platforms:** Windows, Linux, macOS  
**Requirements:** Python 3.6+ (no external dependencies)

**Note:** Still in active development, not production ready.

### 🔜 Wallbox 25kW DC
**Status:** Planned  
**Notes:** Placeholder for future development

### 🔜 Wallbox 50kW
**Status:** Planned  
**Notes:** Placeholder for future development

### 🔜 Slim100
**Status:** Planned  
**Notes:** Placeholder for future development

## Quick Start

### Installation

Install the analyzer to make it available system-wide:

```bash
# Clone or navigate to the repository
cd /path/to/ev-charger-log-analyzer

# Install in editable/development mode
pip install -e .

# Or install normally
pip install .
```

After installation, the `delta-ac-max-analyzer` command will be available from anywhere.

### Delta AC MAX Chargers

```bash
# Analyze all ZIP files in current directory
delta-ac-max-analyzer

# Analyze a specific ZIP file
delta-ac-max-analyzer -z EV01_before.zip

# Analyze multiple specific ZIP files
delta-ac-max-analyzer -z EV01.zip EV02.zip EV05.zip

# Analyze logs in a specific directory
delta-ac-max-analyzer --directory /path/to/charger/logs

# Analyze specific ZIP in specific directory
delta-ac-max-analyzer -d /path/to/logs -z EV01.zip

# Analyze already-extracted logs (skip extraction)
delta-ac-max-analyzer --skip-extraction

# Don't move ZIPs to archive after extraction
delta-ac-max-analyzer --no-archive
```

**Legacy Method (still works):**
```bash
python /path/to/ev-charger-log-analyzer/analyzers/delta_ac_max/analyze.py
```

Full documentation: [Delta AC MAX Usage Guide](docs/delta_ac_max_usage.md)

## Development

### Custom Copilot Agent

This project includes a custom GitHub Copilot agent that helps you:
- Learn and add new log patterns as you discover them
- Extend the analyzer with new detection capabilities
- Maintain code quality and documentation

**Location:** `.github/copilot-instructions.md`  
**Usage Guide:** `.github/README.md`

Simply describe new patterns you find, and the agent will help integrate them into the analyzer!

### Adding a New Charger Model

1. Create a new directory under `analyzers/`:
   ```bash
   mkdir analyzers/new_charger_model
   ```

2. Create the analyzer script:
   ```bash
   touch analyzers/new_charger_model/analyze.py
   ```

3. Document the usage:
   ```bash
   touch docs/new_charger_model_usage.md
   ```

4. Add example outputs:
   ```bash
   mkdir examples/new_charger_model
   ```

5. Update this README with the new model

## Common Issues Detected

All analyzers (current and future) aim to detect:
- ✅ Connection failures (backend, network, cloud)
- ✅ Hardware communication errors (MCU, controller)
- ✅ Missing or corrupted log entries
- ✅ Firmware version mismatches
- ✅ Abnormal error rates
- ✅ Reboot loops or crashes
- ✅ Authentication failures
- ✅ Charging session anomalies

## Contributing

When adding new analyzers:
- Follow the established directory structure
- Use Python 3.6+ with standard library only (for portability)
- Include comprehensive documentation
- Add usage examples
- Support cross-platform operation (Windows, Linux, macOS)

## Version History

### v0.0.1 (January 2026) - Development Release
**Status: In Development - Not Production Ready**

- Initial development release
- Delta AC MAX analyzer (in development)
- System-wide installation via pip (`delta-ac-max-analyzer` command)
- Selective ZIP file analysis with `-z/--zip` option
- ChargBox ID extraction from Config/evcs file
- Auto-extraction of password-protected logs
- Backend disconnect, MCU error, and logging gap detection
- Firmware version extraction
- CSV export functionality
- Color-coded console output
- Cross-platform Python implementation (Windows, Linux, macOS)

**Known Limitations:**
- Still in active development
- Limited production testing
- May require adjustments based on field usage

## Author

Daniel Nathanson  
January 2026

## License

Internal use only
