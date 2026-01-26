# How to Add New Pattern Detection

**Audience:** Developers extending the analyzer  
**Scope:** Step-by-step guide for adding new detection capabilities  
**Prerequisites:** Python 3.6+, understanding of log analysis, basic regex

---

## Decision Tree: Where Does This Pattern Go?

**Before adding a new pattern, determine the correct module:**

```
Is it related to OCPP protocol messages?
└─ YES → detectors/ocpp.py (RemoteStart, SetChargingProfile, etc.)
   NO  → Continue...

Is it a hardware component fault?
└─ YES → detectors/hardware.py (RFID, MCU, sensors, relays)
   NO  → Continue...

Is it related to Load Management System (Modbus)?
└─ YES → detectors/lms.py (Modbus communication, power limiting)
   NO  → Continue...

Is it related to OCPP state machine transitions?
└─ YES → detectors/state_machine.py (State validation, transitions)
   NO  → Continue...

Is it related to event code parsing?
└─ YES → detectors/events.py (Event log parsing, context extraction)
   NO  → Create new detector module (see "Creating New Module" below)
```

---

## Adding to Existing Module

### Step 1: Understand the Pattern

**Ask yourself:**
1. What exact log pattern indicates this issue?
2. What regex or string match will reliably detect it?
3. What threshold indicates a problem? (e.g., >10 occurrences)
4. What does this pattern indicate? (root cause, severity)
5. Where in the logs does this appear? (SystemLog, OCPP16J_Log.csv, EventLog)

**Example:**
- Pattern: `"Emergency shutdown detected"`
- Location: SystemLog
- Threshold: >0 (any occurrence is critical)
- Indicates: Power loss, safety trip, critical fault

### Step 2: Design the Detection Method

**Template:**
```python
def detect_new_pattern(self, folder):
    """Detect [PATTERN_NAME] in charger logs
    
    Pattern indicates: [WHAT IT MEANS]
    Example: [EXAMPLE LOG LINE]
    
    Args:
        folder (Path): Path to extracted charger log folder
        
    Returns:
        dict: {'count': int, 'examples': list, 'severity': str}
    """
    pattern = r'Emergency shutdown detected'  # Exact string or regex
    results = {'count': 0, 'examples': [], 'severity': 'critical'}
    
    # Search SystemLog and rotations
    for log_file in ['SystemLog'] + [f'SystemLog.{i}' for i in range(1, 10)]:
        log_path = folder / 'Storage' / log_file
        if not log_path.exists():
            continue
            
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if re.search(pattern, line, re.IGNORECASE):
                        results['count'] += 1
                        if len(results['examples']) < 10:  # Keep first 10 examples
                            results['examples'].append(line.strip())
        except Exception as e:
            # Gracefully handle missing/corrupt files
            continue
    
    return results
```

### Step 3: Add Method to Appropriate Detector Class

**Example: Adding to OcppDetector (detectors/ocpp.py):**
```python
class OcppDetector:
    """Detects OCPP protocol issues in charger logs"""
    
    # ... existing methods ...
    
    def detect_emergency_shutdown(self, folder):
        """Detect emergency shutdown events
        
        Pattern indicates: Power loss or safety trip
        Example: Jul 20 10:30:45.123 OpenWrt user.crit : Emergency shutdown detected
        
        Args:
            folder (Path): Path to extracted charger log folder
            
        Returns:
            dict: {'count': int, 'examples': list, 'severity': str}
        """
        # Detection logic here...
        return results
```

### Step 4: Integrate into Analysis Pipeline

**Update `analyzers/delta_ac_max/analyze.py`:**

```python
def analyze_charger_log(self, folder):
    """Analyze a single charger log folder"""
    analysis = {
        'charger_id': self._extract_charger_id(folder),
        'firmware_version': self._extract_firmware_version(folder),
        # ... existing detections ...
    }
    
    # Add new detection
    emergency_shutdown = self.ocpp_detector.detect_emergency_shutdown(folder)
    analysis['emergency_shutdown'] = emergency_shutdown
    
    return analysis
```

### Step 5: Add Reporting Logic

**Update `analyzers/delta_ac_max/reporter.py`:**

```python
def generate_summary_report(self, results):
    """Generate TUI summary report"""
    for charger in results:
        # ... existing reporting ...
        
        # Add new pattern reporting
        if charger['emergency_shutdown']['count'] > 0:
            severity = charger['emergency_shutdown']['severity']
            count = charger['emergency_shutdown']['count']
            print(f"    🚨 Emergency Shutdown Events: {count} (CRITICAL)")
            print(f"       → Power loss or safety trip detected")
            if charger['emergency_shutdown']['examples']:
                print(f"       Example: {charger['emergency_shutdown']['examples'][0]}")
```

### Step 6: Update CSV Export (if needed)

**Update `analyzers/delta_ac_max/analyze.py` - CSV export section:**

```python
def export_to_csv(self, results, output_path):
    """Export analysis results to CSV"""
    fieldnames = [
        'charger_id',
        'firmware_version',
        # ... existing fields ...
        'emergency_shutdown_count',  # Add new field
    ]
    
    with open(output_path, 'w', newline='') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for charger in results:
            row = {
                'charger_id': charger['charger_id'],
                # ... existing fields ...
                'emergency_shutdown_count': charger['emergency_shutdown']['count'],
            }
            writer.writerow(row)
```

### Step 7: Document the Pattern

**Add to knowledge base:**

Create or update: `.github/knowledge-base/patterns/[category].md`

Include:
- Pattern description
- Example log lines
- Detection thresholds
- What it indicates
- Resolution steps
- Related error codes

**Update master index:** `.github/copilot-instructions.md`
- Add brief reference with link to detailed knowledge doc

---

## Creating New Detector Module

**When to create new module:**
- Pattern fundamentally different from existing categories
- Existing module approaching 300 lines
- Pattern requires significant new detection logic

### Step 1: Create New Detector File

**File:** `analyzers/delta_ac_max/detectors/[category].py`

**Template:**
```python
"""
Detects [CATEGORY] issues in charger logs
"""
import re
from pathlib import Path


class CategoryDetector:
    """Detects [CATEGORY] related issues in charger logs"""
    
    def __init__(self):
        """Initialize detector"""
        pass
    
    def detect_pattern_one(self, folder):
        """Detect [PATTERN_ONE] in charger logs
        
        Pattern indicates: [WHAT IT MEANS]
        Example: [EXAMPLE LOG LINE]
        
        Args:
            folder (Path): Path to extracted charger log folder
            
        Returns:
            dict: Detection results
        """
        # Detection logic
        return {'count': 0, 'examples': []}
    
    def detect_pattern_two(self, folder):
        """Detect [PATTERN_TWO] in charger logs"""
        # Detection logic
        return {'count': 0, 'examples': []}
```

### Step 2: Export Detector Class

**Update `analyzers/delta_ac_max/detectors/__init__.py`:**

```python
from .events import EventDetector
from .ocpp import OcppDetector
from .hardware import HardwareDetector
from .lms import LmsDetector
from .state_machine import StateMachineDetector
from .category import CategoryDetector  # Add new detector

__all__ = [
    'EventDetector',
    'OcppDetector',
    'HardwareDetector',
    'LmsDetector',
    'StateMachineDetector',
    'CategoryDetector',  # Add to exports
]
```

### Step 3: Initialize Detector in Analyzer

**Update `analyzers/delta_ac_max/analyze.py`:**

```python
from .detectors import (
    EventDetector,
    OcppDetector,
    HardwareDetector,
    LmsDetector,
    StateMachineDetector,
    CategoryDetector,  # Import new detector
)

class ChargerAnalyzer:
    def __init__(self):
        self.event_detector = EventDetector()
        self.ocpp_detector = OcppDetector()
        self.hardware_detector = HardwareDetector()
        self.lms_detector = LmsDetector()
        self.state_machine_detector = StateMachineDetector()
        self.category_detector = CategoryDetector()  # Initialize new detector
```

### Step 4: Call Detector Methods

**In `analyze_charger_log()` method:**

```python
def analyze_charger_log(self, folder):
    """Analyze a single charger log folder"""
    # ... existing detections ...
    
    # Add new detector calls
    pattern_one = self.category_detector.detect_pattern_one(folder)
    pattern_two = self.category_detector.detect_pattern_two(folder)
    
    analysis['pattern_one'] = pattern_one
    analysis['pattern_two'] = pattern_two
    
    return analysis
```

### Step 5: Update Documentation

**Update project structure in `.github/copilot-instructions.md`:**

```markdown
├── detectors/
│   ├── __init__.py
│   ├── events.py
│   ├── ocpp.py
│   ├── hardware.py
│   ├── lms.py
│   ├── state_machine.py
│   └── category.py          # NEW MODULE
```

---

## Example: Real Pattern Addition

**User Request:** "Track battery-related error messages from vehicle"

### Analysis
- **Category:** Vehicle diagnostics (new category)
- **Location:** SystemLog (vehicle communication logs)
- **Pattern:** `Battery.*(?:error|fault|fail|critical)`
- **Threshold:** >10 occurrences = flag for investigation

### Implementation

**1. Create new module:** `detectors/vehicle.py`

```python
class VehicleDetector:
    """Detects vehicle-related issues in charger logs"""
    
    def detect_battery_errors(self, folder):
        """Detect vehicle battery error messages
        
        Pattern indicates: Vehicle reporting battery issues to charger
        Example: Jul 20 14:32:11 OpenWrt user.warn : Vehicle: Battery temperature critical
        """
        pattern = r'Battery.*(?:error|fault|fail|critical)'
        results = {'count': 0, 'examples': []}
        
        for log_file in ['SystemLog'] + [f'SystemLog.{i}' for i in range(1, 10)]:
            log_path = folder / 'Storage' / log_file
            if not log_path.exists():
                continue
                
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    if re.search(pattern, line, re.IGNORECASE):
                        results['count'] += 1
                        if len(results['examples']) < 10:
                            results['examples'].append(line.strip())
        
        return results
```

**2. Export in `__init__.py`:**
```python
from .vehicle import VehicleDetector
__all__ = [..., 'VehicleDetector']
```

**3. Initialize and call in `analyze.py`:**
```python
self.vehicle_detector = VehicleDetector()
battery_errors = self.vehicle_detector.detect_battery_errors(folder)
analysis['battery_errors'] = battery_errors
```

**4. Add reporting in `reporter.py`:**
```python
if charger['battery_errors']['count'] > 10:
    print(f"    ⚠️  Vehicle Battery Errors: {charger['battery_errors']['count']}")
```

**5. Document in `.github/knowledge-base/patterns/vehicle.md`** (new file)

---

## Testing Your New Detection

### Manual Testing

```bash
# Run analyzer on test log folder
cd analyzers/delta_ac_max
python analyze.py /path/to/test/logs

# Verify:
# 1. Pattern detected correctly
# 2. Count matches expected
# 3. Examples captured
# 4. Reporting displays correctly
# 5. CSV export includes new column
```

### Test on Multiple Log Sets

- Test on logs with pattern present (positive test)
- Test on logs without pattern (negative test)
- Test on logs with edge cases (malformed pattern, high counts)

---

## Module Size Management

**Monitor file sizes:**
```bash
wc -l analyzers/delta_ac_max/detectors/*.py
```

**If module approaching 300 lines:**
1. **Evaluate:** Can it be split logically?
2. **Split Example:** `hardware.py` → `hardware/rfid.py`, `hardware/mcu.py`, `hardware/sensors.py`
3. **Update imports:** Adjust `__init__.py` to export from subdirectory

**See:** [Modularity Guidelines](modularity_guidelines.md)

---

**Related Knowledge:**
- [Modularity Guidelines](modularity_guidelines.md) - When to split modules
- [Current Patterns](../patterns/) - Existing pattern knowledge
- [Learning History](learning_history.md) - Version changelog

---

**Last Updated:** 2026-01-26  
**Maintainer:** Update as new patterns are added
