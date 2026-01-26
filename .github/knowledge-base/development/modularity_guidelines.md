# Modularity Guidelines

**Purpose:** Maintain clean, focused, maintainable code and documentation  
**Principles:** Single responsibility, file size limits, clear boundaries

---

## Code Modularity

### File Size Limits (Soft Guidelines)

**Individual Modules:**
- **Detector modules:** ~300 lines max (e.g., `detectors/ocpp.py`)
- **Main orchestrator:** ~400 lines max (`analyze.py`)
- **Reporter:** ~300 lines max (`reporter.py`)
- **Utilities:** ~200 lines max (`utils.py`)

**When to Split:**
- Module exceeds size limit
- Module has multiple distinct responsibilities
- Adding new feature would significantly exceed limit

### How to Split a Module

**Example: Split `hardware.py` into multiple modules:**

**Before:**
```
detectors/
├── hardware.py  (400 lines - too large!)
```

**After:**
```
detectors/
├── hardware/
│   ├── __init__.py       (export all hardware detectors)
│   ├── rfid.py           (~150 lines - RFID-specific)
│   ├── mcu.py            (~120 lines - MCU communication)
│   └── sensors.py        (~130 lines - Temperature, metering)
```

**Update `detectors/hardware/__init__.py`:**
```python
from .rfid import RfidDetector
from .mcu import McuDetector
from .sensors import SensorDetector

__all__ = ['RfidDetector', 'McuDetector', 'SensorDetector']
```

**Update imports in main code:**
```python
from .detectors.hardware import RfidDetector, McuDetector, SensorDetector
```

### Single Responsibility Principle

**Each module should focus on ONE category:**
- ✅ `ocpp.py` - OCPP protocol issues
- ✅ `hardware.py` - Hardware faults
- ✅ `lms.py` - Load Management System
- ✅ `state_machine.py` - State transitions
- ✅ `events.py` - Event log parsing

**Anti-patterns:**
- ✗ `misc.py` - Catch-all for unrelated patterns
- ✗ `utils.py` containing detection logic (should only be utilities)
- ✗ `all_patterns.py` - Mixing unrelated detections

### Naming Conventions

**Module Naming:**
- Use descriptive names reflecting category (e.g., `vehicle.py`, `network.py`, `metering.py`)
- Lowercase with underscores for multi-word names (e.g., `state_machine.py`)

**Class Naming:**
- CategoryDetector pattern (e.g., `VehicleDetector`, `NetworkDetector`)
- CamelCase, no underscores

**Method Naming:**
- detect_specific_issue (e.g., `detect_battery_degradation()`, `detect_rfid_timeout()`)
- lowercase_with_underscores

---

## Knowledge Base Modularity

### File Size Limits (Soft Guidelines)

**Master Index:**
- **copilot-instructions.md:** ~300 lines max
- Core principles, quick links, self-maintenance instructions

**Knowledge Documents:**
- **Individual docs:** ~500 lines max
- Focused, organized, cross-linked

**When to Split:**
- Knowledge doc approaching 500 lines
- Document covers multiple distinct topics
- Document becoming difficult to navigate

### How to Split Knowledge

**Example: Split `patterns.md` (hypothetical monolithic file):**

**Before:**
```
knowledge-base/
├── patterns.md  (1200 lines - too large!)
```

**After:**
```
knowledge-base/patterns/
├── ocpp_protocol.md      (~290 lines)
├── current_limiting.md   (~340 lines)
├── hardware_faults.md    (~400 lines)
└── state_transitions.md  (~150 lines)
```

**Update master index with links:**
```markdown
## Quick Reference

**For OCPP protocol issues:**  
→ See [knowledge-base/patterns/ocpp_protocol.md](knowledge-base/patterns/ocpp_protocol.md)

**For current limiting:**  
→ See [knowledge-base/patterns/current_limiting.md](knowledge-base/patterns/current_limiting.md)
```

### Cross-Linking Best Practices

**Within Knowledge Base:**
- Use relative paths: `[Error Codes](../reference/error_codes.md)`
- Link to related docs at end of each file
- Keep links current when reorganizing

**From Master Index:**
- Link to all knowledge docs
- Group by category (patterns, reference, case studies, development)
- Provide one-sentence description per link

### Knowledge Organization Categories

**Reference Material:**
- `reference/error_codes.md` - Error code catalog
- `reference/modbus_registers.md` - Register map
- `reference/firmware_bugs.md` - Known bugs

**Pattern Knowledge:**
- `patterns/ocpp_protocol.md` - Protocol understanding
- `patterns/current_limiting.md` - Limiting behavior
- `patterns/hardware_faults.md` - Hardware issues
- `patterns/state_transitions.md` - State machine

**Case Studies:**
- `case-studies/federation_university.md` - Real-world case
- One file per major case or multi-issue scenario

**Development:**
- `development/pattern_detection.md` - How to add patterns
- `development/modularity_guidelines.md` - This file
- `development/learning_history.md` - Changelog

---

## Maintaining Modularity

### Regular Reviews

**Quarterly (or after major additions):**
1. Check file sizes: `wc -l analyzers/**/*.py`
2. Check knowledge doc sizes: `wc -l .github/knowledge-base/**/*.md`
3. Identify files approaching limits
4. Plan splits if needed

### When Adding New Features

**Before adding:**
1. Check current file size
2. Estimate addition size
3. If would exceed limit → split first, then add

**After adding:**
1. Verify file size
2. Update documentation
3. Update knowledge base

### Refactoring Checklist

When splitting a module:
- [ ] Create new module(s) with focused responsibilities
- [ ] Move code to appropriate new modules
- [ ] Update `__init__.py` exports
- [ ] Update imports in main code
- [ ] Run tests to verify no regressions
- [ ] Update documentation (structure diagrams, etc.)
- [ ] Update knowledge base cross-links

---

## Benefits of Modularity

**Code:**
- ✅ Easier to navigate and understand
- ✅ Easier to test (focused units)
- ✅ Easier to extend (clear boundaries)
- ✅ Reduces merge conflicts (separate files)
- ✅ Faster code reviews (smaller diffs)

**Knowledge:**
- ✅ Easier to find information (focused docs)
- ✅ Easier to maintain (update one doc, not monolithic file)
- ✅ Easier to learn (progressive reading)
- ✅ Better searchability (grep across focused files)

---

## Anti-Patterns to Avoid

**Code:**
- ✗ "God class" - One class doing everything
- ✗ "God file" - One file containing all detections
- ✗ Mixed responsibilities - OCPP + hardware in same module
- ✗ Circular dependencies - Module A imports B, B imports A

**Knowledge:**
- ✗ Monolithic file - All knowledge in copilot-instructions.md
- ✗ Duplicate information - Same content in multiple docs
- ✗ Broken links - Links to non-existent files
- ✗ Orphan docs - Knowledge docs not linked from master index

---

**Related:**
- [Pattern Detection Guide](pattern_detection.md) - How to add new patterns
- [Learning History](learning_history.md) - Changelog
- Main Project README - Project structure

---

**Last Updated:** 2026-01-26  
**Philosophy:** "Modularity first - no single file should exceed reasonable limits"
