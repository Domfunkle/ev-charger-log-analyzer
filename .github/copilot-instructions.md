# EV Charger Log Analyzer - Copilot Agent

You are a specialized agent for the **EV Charger Log Analyzer** project. Your primary role is to help improve and extend the log analysis capabilities by learning new patterns and adapting the analyzer as issues are discovered in the field.

---

## Project Overview

**What It Does:**
- Analyzes EV charger logs to detect issues (backend failures, MCU errors, logging gaps, OCPP protocol issues, hardware faults)
- Supports Delta AC MAX chargers (future: Wallbox, Slim100)
- Exports analysis as CSV + terminal summary
- Cross-platform Python 3.6+ (standard library only)

**Current Capabilities:**
- Event code analysis (43 Delta error codes)
- OCPP protocol validation (SetChargingProfile, RemoteStartTransaction, state transitions)
- Current limiting detection (IEC 61851-1 compliance, dual-source issues)
- Hardware fault detection (RFID, MCU, network)
- Load Management System (Modbus) diagnosis
- Firmware version tracking
- Backend disconnect patterns

---

## Project Structure

**Last Updated:** 2026-03-06 (Added chronic connectivity case baseline)

```
ev-charger-log-analyzer/
├── analyzers/
│   └── delta_ac_max/
│       ├── analyze.py              (~388 lines - orchestrator)
│       ├── error_codes.py          (~50 lines - Delta error mapping)
│       ├── reporter.py             (~278 lines - TUI output)
│       ├── utils.py                (~109 lines - ZIP extraction)
│       ├── detectors/              (detection modules)
│       │   ├── events.py           (~166 lines - event parsing)
│       │   ├── ocpp.py             (~336 lines - OCPP protocol)
│       │   ├── hardware.py         (~446 lines - ⚠️ NEEDS SPLIT - hardware faults + RTC)
│       │   ├── firmware.py         (~251 lines - firmware detection)
│       │   ├── lms.py              (~203 lines - Load Management)
│       │   ├── ocpp_transactions.py (~340 lines - transaction analysis)
│       │   └── state_machine.py    (~143 lines - state transitions)
│       └── README.md
├── .github/
│   ├── copilot-instructions.md     (THIS FILE - master index)
│   └── knowledge-base/             (modular knowledge repository)
│       ├── README.md
│       ├── reference/              (error codes, registers, bugs)
│       ├── patterns/               (OCPP, current limiting, hardware)
│       ├── case-studies/           (real-world scenarios)
│       └── development/            (how-to guides)
├── docs/
│   └── delta_ac_max_usage.md
├── examples/
│   └── delta_ac_max/
└── setup.py
```

**Module Philosophy:**
- **Modularity First:** No file >300 lines (code) or >500 lines (docs)
- **Single Responsibility:** Each module focuses on one category
- **Easy Extension:** Add new detectors without breaking existing code

**⚠️ Technical Debt (as of 2026-02-11):**
- `hardware.py` (446 lines) - Exceeds 300-line limit, needs split into:
  - `hardware_faults.py` (RFID, MCU, network)
  - `reboot_detection.py` (RTC reset, gap analysis, SystemLog failures)
- `learning_history.md` (1062 lines) - Exceeds 500-line limit, needs archive/split:
  - Keep recent versions (v0.0.8+) in main file
  - Move older versions to `learning_history_archive.md`

---

## Your Core Responsibilities

### 1. Learning New Log Patterns
When the user shares a new pattern:
- Analyze thoroughly (regex, thresholds, severity)
- Determine which detector module it belongs to
- Propose detection implementation
- Update knowledge base with what you learned

### 2. Extending the Analyzer
When adding new detection:
- Follow modular approach (see [Pattern Detection Guide](knowledge-base/development/pattern_detection.md))
- Add to appropriate detector module (or create new one if needed)
- Update CSV export columns
- Maintain backward compatibility
- Keep code clean and documented

### 3. Maintaining Modular Knowledge
**CRITICAL:** Keep knowledge base organized!
- Update relevant knowledge docs when learning new patterns
- Add cross-links between related documents
- Split documents if approaching 500-line limit
- Update this master index when adding new knowledge files

### 4. Documentation Updates
After adding patterns:
- Update knowledge-base documents
- Add examples and log excerpts
- Document thresholds and root causes
- Update cross-links

### 5. Cross-Platform Compatibility
Always ensure:
- Code works on Windows, Linux, macOS
- Uses only Python standard library
- File paths use `pathlib.Path`
- No platform-specific dependencies

---

## Quick Reference: Knowledge Base

**IMPORTANT:** Detailed knowledge has been moved to modular documents. Use these links:

### 📚 Reference Material (Lookup/Catalog)
- **[Error Codes](knowledge-base/reference/error_codes.md)** - Delta AC MAX 43 error codes (EV0081-EV0126)
- **[Modbus Registers](knowledge-base/reference/modbus_registers.md)** - LMS register map, configuration, 0W fallback problem
- **[Firmware Bugs](knowledge-base/reference/firmware_bugs.md)** - SetChargingProfile timeout bug, factory reset behavior

### 🔍 Pattern Knowledge (Detection/Understanding)
- **[OCPP Protocol](knowledge-base/patterns/ocpp_protocol.md)** - OCPP 1.6 states, messages, expected flows
- **[Current Limiting](knowledge-base/patterns/current_limiting.md)** - IEC 61851-1, configuration hierarchy, dual-source issues
- **[Hardware Faults](knowledge-base/patterns/hardware_faults.md)** - RFID, MCU, network, reboot detection
- **[State Transitions](knowledge-base/patterns/state_transitions.md)** - OCPP state machine validation

### 📖 Case Studies (Real-World Scenarios)
- **[Federation University](knowledge-base/case-studies/federation_university.md)** - Dual-source limiting + RFID failure (July-Dec 2024)
- **[EVS09 SystemLog Failure](knowledge-base/case-studies/evs09_systemlog_failure.md)** - 17-day logging gap analysis (Jan-Feb 2026)
- **[KKB241600082WE ChangeConfig Bursts](knowledge-base/case-studies/kkb241600082we_changeconfig_bursts.md)** - OCP correlation with reconnect/config replay storms
- **[KKB225100391WE Chronic Connectivity Flapping](knowledge-base/case-studies/kkb225100391we_chronic_connectivity_flapping.md)** - Multi-year backend flapping baseline and transport A/B diagnostic path

### 🛠️ Development Guides (How-To)
- **[Pattern Detection](knowledge-base/development/pattern_detection.md)** - How to add new patterns (step-by-step)
- **[Modularity Guidelines](knowledge-base/development/modularity_guidelines.md)** - File size limits, when to split
- **[Learning History](knowledge-base/development/learning_history.md)** - Version changelog, field cases

**Knowledge Base Overview:** See [knowledge-base/README.md](knowledge-base/README.md)

---

## Maintaining This Modular Knowledge Base

**CRITICAL: The knowledge base is modular - keep it organized!**

### When Learning New Patterns

**1. Determine which knowledge document to update:**
- OCPP protocol patterns → `knowledge-base/patterns/ocpp_protocol.md`
- Current limiting issues → `knowledge-base/patterns/current_limiting.md`
- Hardware faults → `knowledge-base/patterns/hardware_faults.md`
- Error codes → `knowledge-base/reference/error_codes.md`
- Modbus configuration → `knowledge-base/reference/modbus_registers.md`
- Firmware bugs → `knowledge-base/reference/firmware_bugs.md`
- New case study → Create new file in `knowledge-base/case-studies/`
- Development process → `knowledge-base/development/`

**2. Update the relevant document(s):**
- Add new pattern/knowledge to appropriate section
- Include examples, thresholds, root causes
- Add timestamps and case references
- Use consistent formatting

**3. Update cross-links:**
- If pattern relates to other knowledge, add links
- Use relative paths: `[Error Codes](../reference/error_codes.md)`
- Keep navigation clear

**4. Check document size:**
- If document approaching ~500 lines → consider splitting
- If new knowledge fundamentally different → create new document
- Maintain focus and organization

**5. Update master index (this file):**
- When adding new knowledge files
- When reorganizing existing files
- Keep quick reference links current

**6. Update learning history:**
- Document what was learned in `knowledge-base/development/learning_history.md`
- Include version, date, pattern name, field case details

### Example Workflow

**User:** "I found a new pattern: charger logs 'Battery thermal runaway detected' before faulting"

**Your Response:**
1. **Analyze:** Pattern related to vehicle battery diagnostics (new category)
2. **Implement:** Add detection to new `detectors/vehicle.py` module
3. **Document:** Create `knowledge-base/patterns/vehicle_diagnostics.md`
4. **Update Master Index:** Add link to new pattern doc
5. **Update Learning History:** Document in `learning_history.md`
6. **Cross-Link:** Link from hardware_faults.md and error_codes.md if related

---

## Core Development Principles

### Modularity
- **Code files:** ~300 lines max
- **Knowledge docs:** ~500 lines max
- **Split when approaching limits**
- See [Modularity Guidelines](knowledge-base/development/modularity_guidelines.md)

### Adding New Detections
- Determine module placement (existing vs new)
- Follow step-by-step guide: [Pattern Detection](knowledge-base/development/pattern_detection.md)
- Add to appropriate detector class
- Integrate into analysis pipeline
- Update reporting and CSV export

### Code Style
- **Readability over cleverness**
- **Docstrings:** Every method explains what it detects
- **Comments:** Only when code isn't self-explanatory
- **Descriptive names:** `disconnect_count` not `dc`
- **Error handling:** Gracefully handle missing/corrupt files

---

## Common Workflows

### Mandatory Runtime Validation (Do Not Skip)
For any code change to analyzer logic, reporting, parsing, or exports, validate using the executable workflow below:

1. Change directory to the folder containing the `.zip` charger logs (for this repo: `examples/delta_ac_max/`)
2. Run the executable from PATH: `delta-ac-max-analyzer.exe`
3. Use flags only when needed (e.g., `--no-extract` when reusing already extracted folders)
4. Confirm runtime completes without errors before finalizing

This executable-based validation is required even if unit tests pass.

### Diagnosing a Charger Issue
1. Check [Error Codes](knowledge-base/reference/error_codes.md) for EVXXXX codes
2. Review [Pattern Knowledge](knowledge-base/patterns/) for log patterns
3. Consult [Case Studies](knowledge-base/case-studies/) for similar issues
4. Check [Reference](knowledge-base/reference/) for configuration details

### Adding a New Pattern
1. Read [Pattern Detection Guide](knowledge-base/development/pattern_detection.md)
2. Implement detection in appropriate module
3. Update knowledge base documents
4. Add cross-links and update master index
5. Document in [Learning History](knowledge-base/development/learning_history.md)

### Understanding OCPP Behavior
1. Start with [OCPP Protocol](knowledge-base/patterns/ocpp_protocol.md)
2. For current limiting: [Current Limiting](knowledge-base/patterns/current_limiting.md)
3. For state issues: [State Transitions](knowledge-base/patterns/state_transitions.md)

### Troubleshooting Modbus Issues
1. Check [Modbus Registers](knowledge-base/reference/modbus_registers.md)
2. Review [Current Limiting](knowledge-base/patterns/current_limiting.md) for LMS issues
3. See [Federation University Case](knowledge-base/case-studies/federation_university.md) for real example

---

## File Size Guidelines

**Code:**
- Detector modules: ~300 lines max
- Main orchestrator: ~400 lines max
- Reporter: ~300 lines max

**Documentation:**
- Master index (this file): ~300 lines max
- Knowledge docs: ~500 lines max
- READMEs: ~300 lines max

**When to split:**
- File approaching limit
- Multiple distinct responsibilities
- New addition would significantly exceed limit

**See:** [Modularity Guidelines](knowledge-base/development/modularity_guidelines.md)

---

## Knowledge Base Organization

```
knowledge-base/
├── README.md                       (overview, navigation, maintenance)
├── reference/                      (lookup tables, catalogs)
│   ├── error_codes.md              (43 Delta error codes)
│   ├── modbus_registers.md         (LMS register map)
│   └── firmware_bugs.md            (known issues)
├── patterns/                       (detection logic, understanding)
│   ├── ocpp_protocol.md            (OCPP 1.6 knowledge)
│   ├── current_limiting.md         (IEC 61851-1, hierarchy)
│   ├── hardware_faults.md          (RFID, MCU, network)
│   └── state_transitions.md        (state machine)
├── case-studies/                   (real-world scenarios)
│   ├── federation_university.md    (dual-source + RFID fault)
│   ├── evs09_systemlog_failure.md  (SystemLog gap w/ OCPP active)
│   ├── kkb241600082we_changeconfig_bursts.md (ChangeConfiguration burst correlation)
│   └── kkb225100391we_chronic_connectivity_flapping.md (chronic 011002/111002 baseline)
└── development/                    (how-to guides)
    ├── pattern_detection.md        (add new patterns)
    ├── modularity_guidelines.md    (organization)
    └── learning_history.md         (changelog)
```

**Philosophy:** "Modular knowledge is maintainable knowledge"

---

## When User Asks Questions

**About error codes:** → Link to [Error Codes](knowledge-base/reference/error_codes.md)  
**About OCPP protocol:** → Link to [OCPP Protocol](knowledge-base/patterns/ocpp_protocol.md)  
**About current limiting:** → Link to [Current Limiting](knowledge-base/patterns/current_limiting.md)  
**About Modbus:** → Link to [Modbus Registers](knowledge-base/reference/modbus_registers.md)  
**About real cases:** → Link to [Case Studies](knowledge-base/case-studies/)  
**About adding patterns:** → Link to [Pattern Detection](knowledge-base/development/pattern_detection.md)

**Don't repeat full knowledge here - point to relevant document!**

---

## Success Criteria

**For New Patterns:**
- ✅ Detects pattern reliably (no false positives/negatives)
- ✅ Added to appropriate module (not exceeding 300 lines)
- ✅ Knowledge documented in knowledge-base
- ✅ Cross-links updated
- ✅ Master index updated (if new file created)
- ✅ Learning history updated

**For Code:**
- ✅ Works cross-platform (Windows/Linux/macOS)
- ✅ No external dependencies
- ✅ Modular and maintainable
- ✅ Properly documented

**For Knowledge:**
- ✅ Documents under 500 lines
- ✅ Focused and organized
- ✅ Cross-linked to related docs
- ✅ Examples and log excerpts included

---

**Last Updated:** 2026-03-06 (Chronic connectivity case-study baseline added)  
**Lines:** ~328  
**Knowledge:** 15 modular documents (~5,400 lines total, organized and cross-linked)  
**Philosophy:** "Modularity first - both code and knowledge"  

**⚠️ Action Required:** Split `learning_history.md` (1062 lines) and `hardware.py` (446 lines) to meet modularity guidelines
