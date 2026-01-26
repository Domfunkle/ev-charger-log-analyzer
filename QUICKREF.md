# EV Charger Log Analyzer - Quick Reference

## Project Location
```
C:\path\to\ev-charger-log-analyzer
```

## Quick Usage

### Delta AC MAX Chargers
```bash
# Navigate to your log directory
cd "C:\path\to\charger\logs"

# Run the analyzer
python C:\path\to\ev-charger-log-analyzer\analyzers\delta_ac_max\analyze.py

# Or if already extracted
python C:\path\to\ev-charger-log-analyzer\analyzers\delta_ac_max\analyze.py --skip-extraction
```

### Linux/macOS
```bash
cd /path/to/charger/logs
python ~/ev-charger-log-analyzer/analyzers/delta_ac_max/analyze.py
```

## Output Files
- `ChargerAnalysisResults_YYYYMMDD_HHMMSS.csv` - Detailed results
- `Original Zips/` - Archive of original ZIP files

## Common Commands

```bash
# View project structure
cd ~/ev-charger-log-analyzer
tree

# Check git status
git status

# View commit history
git log --oneline

# Pull latest changes (if remote configured)
git pull

# Create a new analyzer (template)
mkdir analyzers/new_model
cp analyzers/delta_ac_max/README.md analyzers/new_model/
```

## Documentation
- Main README: `README.md`
- Delta AC MAX Guide: `docs/delta_ac_max_usage.md`
- Delta AC MAX README: `analyzers/delta_ac_max/README.md`

## Version
**Current Version:** 1.0.0  
**Last Updated:** January 26, 2026
