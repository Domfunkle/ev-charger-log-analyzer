#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Test README - explains how to run tests and add new ones
"""

# EV Charger Log Analyzer - Unit Tests

## Running Tests

### Run All Tests
```bash
python -m unittest discover tests
```

### Run Specific Test Module
```bash
python -m unittest tests.test_ocpp_detector
python -m unittest tests.test_hardware_detector
```

### Run Specific Test Case
```bash
python -m unittest tests.test_ocpp_detector.TestOcppDetector.test_detect_low_current_profiles_zero_current
```

### Run with Verbose Output
```bash
python -m unittest discover tests -v
```

## Test Coverage

Currently implemented:
- **test_ocpp_detector.py** - OCPP protocol detection (9 test cases)
  - Low-current profiles (0A, <6A, ≥6A)
  - SetChargingProfile timeouts
  - RemoteStartTransaction rejections
  - NG flags
  - General OCPP timeouts
  - Missing log directory handling

- **test_hardware_detector.py** - Hardware fault detection (4 test cases)
  - RFID module (RYRR20I) errors
  - Rotated log files
  - No errors scenario
  - Missing log directory handling

## Adding New Tests

### 1. Create Test File
```python
# tests/test_new_detector.py
from __future__ import annotations
import unittest
from pathlib import Path
import tempfile
import shutil
from analyzers.delta_ac_max.detectors.new_detector import NewDetector

class TestNewDetector(unittest.TestCase):
    def setUp(self):
        """Create temporary test directory"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.storage_dir = self.test_dir / "Storage" / "SystemLog"
        self.storage_dir.mkdir(parents=True)
    
    def tearDown(self):
        """Clean up"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_something(self):
        """Test description"""
        # Create fixture log file
        log_file = self.storage_dir / "SystemLog"
        log_file.write_text("Test log content\n")
        
        # Run detector
        result = NewDetector.detect_something(self.test_dir)
        
        # Assert expected behavior
        self.assertEqual(result['count'], 1)
```

### 2. Use Real Log Excerpts as Fixtures
Store sanitized log excerpts in `tests/fixtures/`:
```bash
tests/fixtures/
├── ocpp_low_current_profile.txt
├── rfid_fault_log.txt
└── lms_timeout_log.txt
```

### 3. Test Edge Cases
- Missing log files
- Empty log files
- Malformed log entries
- Rotated log files (.0, .1, etc.)
- Very large log files (performance)

## Test Patterns

### Pattern 1: File-based Fixture
```python
def test_with_fixture_file(self):
    # Copy fixture to test directory
    fixture = Path("tests/fixtures/example.log")
    dest = self.storage_dir / "SystemLog"
    shutil.copy(fixture, dest)
    
    result = Detector.detect(self.test_dir)
    self.assertEqual(result['count'], expected_value)
```

### Pattern 2: In-memory Fixture
```python
def test_with_inline_log(self):
    log_file = self.storage_dir / "OCPP16J_Log.csv"
    log_file.write_text(
        "Line 1 with pattern\n"
        "Line 2 normal\n"
    )
    
    result = Detector.detect(self.test_dir)
    self.assertGreater(result['count'], 0)
```

### Pattern 3: Parameterized Tests
```python
def test_multiple_scenarios(self):
    scenarios = [
        ("limit=0.100000", 1, 1),  # (input, expected_count, expected_zero)
        ("limit=5.500000", 1, 0),
        ("limit=16.000000", 0, 0),
    ]
    
    for log_line, exp_count, exp_zero in scenarios:
        with self.subTest(log_line=log_line):
            # Test each scenario
            pass
```

## Continuous Integration

To add CI/CD testing (GitHub Actions example):
``yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.8'
      - run: python -m unittest discover tests -v
```

## Future Test Additions

Recommended tests to add:
- [ ] test_lms_detector.py - Load Management System detection
- [ ] test_state_machine_detector.py - OCPP state transitions
- [ ] test_events_detector.py - Event parsing and log context
- [ ] test_reporter.py - TUI output formatting
- [ ] test_analyze.py - End-to-end integration tests
- [ ] test_utils.py - ZIP extraction utilities

## Performance Testing

For large log sets:
```python
import time

def test_performance_large_log(self):
    # Create large log file (1000 lines)
    log_file = self.storage_dir / "SystemLog"
    with open(log_file, 'w') as f:
        for i in range(1000):
            f.write(f"Line {i} with RYRR20I error\n")
    
    start = time.time()
    result = HardwareDetector.detect_rfid_faults(self.test_dir)
    elapsed = time.time() - start
    
    self.assertEqual(result['count'], 1000)
    self.assertLess(elapsed, 1.0, "Should process 1000 lines in <1 second")
```

---

**Last Updated:** 2026-01-26
**Test Framework:** Python unittest (stdlib)
**Test Count:** 13 tests across 2 modules
