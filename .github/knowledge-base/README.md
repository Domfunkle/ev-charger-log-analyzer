# EV Charger Log Analyzer - Knowledge Base

**Purpose:** Modular knowledge repository for the EV Charger Log Analyzer agent  
**Organization:** Focused documents, cross-linked, maintainable  
**Philosophy:** No single file should exceed ~500 lines - split when approaching limit

---

## Quick Navigation

### 📚 Reference Material
Lookup tables, configuration maps, error catalogs - the "what is it?" knowledge

- **[Error Codes](reference/error_codes.md)** - Delta AC MAX 43 error codes (EV0081-EV0126)
- **[Modbus Registers](reference/modbus_registers.md)** - LMS Modbus register map, configuration, troubleshooting
- **[Firmware Bugs](reference/firmware_bugs.md)** - Known firmware issues, workarounds, escalation status

### 🔍 Pattern Knowledge
Understanding log patterns, detection logic, root cause analysis - the "what does it mean?" knowledge

- **[OCPP Protocol](patterns/ocpp_protocol.md)** - OCPP 1.6 states, messages, expected flows
- **[Current Limiting](patterns/current_limiting.md)** - IEC 61851-1 behavior, configuration hierarchy, dual-source issues
- **[Hardware Faults](patterns/hardware_faults.md)** - RFID, MCU, network, sensor failures
- **[State Transitions](patterns/state_transitions.md)** - OCPP state machine validation, suspicious patterns

### 📖 Case Studies
Real-world scenarios, diagnosis walkthroughs, lessons learned - the "what happened?" knowledge

- **[Federation University](case-studies/federation_university.md)** - Dual-source current limiting + RFID hardware failure

### 🛠️ Development Guides
How to extend the analyzer, maintain modularity - the "how do I?" knowledge

- **[Pattern Detection](development/pattern_detection.md)** - Step-by-step guide to adding new patterns
- **[Modularity Guidelines](development/modularity_guidelines.md)** - File size limits, splitting modules, organization
- **[Learning History](development/learning_history.md)** - Version changelog, field cases analyzed, protocol learning

---

## Knowledge Organization Principles

### Size Limits
- **Master Index** (copilot-instructions.md): ~300 lines max
- **Individual Knowledge Docs**: ~500 lines max
- **Code Modules**: ~300 lines max

**Why:** Maintainability, readability, searchability

### Single Responsibility
Each knowledge document focuses on ONE category:
- Reference = lookup/catalog
- Patterns = detection/understanding
- Case Studies = real-world scenarios
- Development = how-to guides

### Cross-Linking
- Every document links to related docs
- Use relative paths: `[Error Codes](../reference/error_codes.md)`
- Master index links to ALL knowledge docs
- Related sections at end of each doc

### When to Split
- Document approaching 500 lines
- Document covers multiple distinct topics
- Document becoming difficult to navigate
- New knowledge doesn't fit existing structure

**See:** [Modularity Guidelines](development/modularity_guidelines.md)

---

## How to Use This Knowledge Base

### For Diagnosis
1. Start with **[Patterns](patterns/)** - Understand what log patterns mean
2. Cross-reference **[Error Codes](reference/error_codes.md)** - Lookup specific error codes
3. Check **[Case Studies](case-studies/)** - Similar issues resolved before?
4. Consult **[Reference](reference/)** - Configuration details, firmware bugs

### For Development
1. Read **[Pattern Detection Guide](development/pattern_detection.md)** - How to add new patterns
2. Follow **[Modularity Guidelines](development/modularity_guidelines.md)** - Keep code organized
3. Update **[Learning History](development/learning_history.md)** - Document what you learned

### For Learning
1. Start with **[OCPP Protocol](patterns/ocpp_protocol.md)** - Understand basics
2. Read **[Current Limiting](patterns/current_limiting.md)** - Complex but common issue
3. Study **[Federation University Case](case-studies/federation_university.md)** - Real-world complexity

---

## Maintaining This Knowledge Base

### When Learning New Patterns

**1. Determine which knowledge document to update:**
- OCPP protocol patterns → `patterns/ocpp_protocol.md`
- Current limiting issues → `patterns/current_limiting.md`
- Hardware faults → `patterns/hardware_faults.md`
- Error codes → `reference/error_codes.md`
- New case study → Create new file in `case-studies/`
- Development process → `development/`

**2. Update the relevant document(s):**
- Add new pattern/knowledge to appropriate section
- Include examples, thresholds, root causes
- Add timestamps and case references

**3. Update cross-links:**
- If pattern relates to other knowledge, add links
- Update master index if adding new knowledge file
- Keep navigation clear

**4. Check document size:**
- If document approaching ~500 lines → consider splitting
- If new knowledge fundamentally different → create new document
- Maintain focus and organization

**5. Update master index:**
- When adding new knowledge files
- When reorganizing existing files
- Keep quick reference links current

**See:** [Modularity Guidelines](development/modularity_guidelines.md) for detailed splitting guidance

---

## Knowledge Categories Explained

### Reference Material (Lookup/Catalog)
**What:** Static information, configurations, error catalogs  
**Examples:** Error code EV0082 means "AC Output OCP", Modbus register 40204 is "Fallback Power"  
**Use Case:** "What does this error code mean?" "What should this register be set to?"

### Pattern Knowledge (Detection/Understanding)
**What:** Log patterns, detection logic, behavior explanations  
**Examples:** Low-current OCPP profiles cause charging suspension, RFID errors indicate hardware fault  
**Use Case:** "Why is the charger stuck in Preparing?" "What does this log pattern indicate?"

### Case Studies (Real-World Scenarios)
**What:** Complete diagnosis walkthroughs, field cases, lessons learned  
**Examples:** Federation University dual-source issue, RFID hardware failure  
**Use Case:** "Has this been seen before?" "How was similar issue resolved?"

### Development Guides (How-To)
**What:** Step-by-step guides, development workflows, organization principles  
**Examples:** How to add new pattern detection, when to split modules  
**Use Case:** "How do I extend the analyzer?" "Where should I add this new detection?"

---

## Future Expansion

**Potential New Documents:**

- `case-studies/setcharging_timeout.md` - SetChargingProfile firmware bug case
- `patterns/network_issues.md` - Network diagnostics beyond basic disconnects
- `patterns/vehicle_diagnostics.md` - Vehicle-reported issues
- `reference/ocpp_spec.md` - OCPP 1.6 specification excerpts
- `development/testing_guide.md` - How to test new detections

**When to Add:**
- New pattern category emerges (e.g., metering/billing issues)
- Major field case warrants standalone documentation
- Development workflow becomes complex (e.g., CI/CD, automated testing)

---

## Contributing

When adding new knowledge:
1. ✅ Choose appropriate category (reference, patterns, case studies, development)
2. ✅ Keep documents focused and under 500 lines
3. ✅ Add cross-links to related docs
4. ✅ Update master index (copilot-instructions.md)
5. ✅ Use consistent formatting and structure
6. ✅ Include examples and real log excerpts
7. ✅ Update learning_history.md with what was learned

---

**Last Updated:** 2026-01-26  
**Total Documents:** 11 knowledge docs + master index  
**Total Lines:** ~1,900 lines (was 1,535 in monolithic file, now organized and cross-linked)  
**Philosophy:** "Modular knowledge is maintainable knowledge"
