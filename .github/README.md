# Copilot Custom Agent for Log Analyzer

This directory contains configuration for a custom GitHub Copilot agent specialized for this project.

## Agent Purpose

The custom agent is designed to help you:
- Learn new log patterns as you discover them in the field
- Extend the analyzer with new detection capabilities
- Maintain code quality and cross-platform compatibility
- Keep documentation synchronized with code changes

## Using the Custom Agent

### With GitHub Copilot CLI

When working in this project, the agent will automatically understand the project context and help you add new pattern detection.

**Example Session:**
```bash
# Navigate to project
cd ~/dev/ev-charger-log-analyzer

# Start a Copilot session
# The agent will read .github/copilot-instructions.md automatically

# Tell the agent about a new pattern
> "I found a pattern: when OCPP disconnects, it logs 'OCPP WebSocket closed' 
> followed by reconnection attempts. I want to track how many times this happens."
```

The agent will:
1. Ask clarifying questions about the pattern
2. Propose a detection method
3. Implement the change in `analyzers/delta_ac_max/analyze.py`
4. Update documentation
5. Commit with descriptive message

### Teaching the Agent New Patterns

Simply describe what you found:

**Template:**
```
I found a new pattern in the logs: [DESCRIPTION]

Example log lines:
[PASTE LOG LINES HERE]

This happens when: [CONDITION]
This indicates: [WHAT IT MEANS]
Should flag if: [THRESHOLD]
```

**Example:**
```
I found a new pattern: The charger logs "Temperature warning" when it gets too hot.

Example log lines:
Jan 22 14:32:15.123 OpenWrt user.warn : [Thermal] Temperature warning: 75°C
Jan 22 14:32:45.456 OpenWrt user.warn : [Thermal] Temperature warning: 78°C

This happens when: Internal temperature exceeds safe threshold
This indicates: Possible cooling system issue or high ambient temperature
Should flag if: >5 warnings per log file
```

The agent will handle the rest!

## Agent Capabilities

### What It Can Do
- ✅ Add new pattern detection methods
- ✅ Update CSV export columns
- ✅ Maintain code quality and style
- ✅ Update all relevant documentation
- ✅ Preserve cross-platform compatibility
- ✅ Create descriptive git commits

### What It Won't Do
- ❌ Remove existing detection without approval
- ❌ Add external dependencies
- ❌ Break backward compatibility
- ❌ Use platform-specific code
- ❌ Make assumptions about patterns

## Configuration File

**File:** `.github/copilot-instructions.md`

This file contains:
- Project context and structure
- Current detection patterns
- Code style guidelines
- Step-by-step process for adding patterns
- Git workflow instructions
- Success criteria

## Modifying the Agent

To customize the agent's behavior:

1. Edit `.github/copilot-instructions.md`
2. Add/modify sections as needed
3. Commit changes
4. Agent will use updated instructions in next session

## Examples of Agent Usage

### Adding a New Detection Pattern

**You:**
```
The logs show "RTC sync failed" when the real-time clock can't synchronize.
This is important because it causes incorrect timestamps.

Example:
Oct 15 04:39:19.463 OpenWrt user.info InfraMgmt[2481]: [Infra] Get RTC Info: 2026.01.22-01:54:55
Oct 15 04:39:20.123 OpenWrt user.error InfraMgmt[2481]: [Infra] RTC sync failed

Should flag if it happens at all, as it's critical.
```

**Agent Will:**
1. Confirm understanding
2. Add `detect_rtc_sync_failures()` method
3. Add to CSV export
4. Update documentation
5. Commit: "Add detection for RTC sync failures"

### Updating Documentation

**You:**
```
Can you update the docs to clarify that MCU errors usually happen during reboot 
and might not be critical if they're only during system startup?
```

**Agent Will:**
1. Update relevant README files
2. Add context about when MCU errors are expected vs. problematic
3. Commit: "Clarify MCU error detection context"

## Tips for Working with the Agent

1. **Be Specific**: Provide actual log lines when possible
2. **Explain Context**: Say what causes the pattern and why it matters
3. **Set Thresholds**: Indicate when it should flag (always, >N times, etc.)
4. **Review Changes**: Agent will propose changes before implementing
5. **Test**: Always test on real logs after changes

## Future Enhancements

As the project grows, the agent can help with:
- Adding analyzers for new charger models
- Creating shared pattern libraries
- Generating analysis reports
- Building visualization tools
- Automating testing

## Agent Self-Improvement

**CRITICAL:** This agent is designed to **update itself** as it learns new patterns and behaviors!

### The Self-Updating Process

When the agent successfully adds a new pattern, it will:

1. **Update Code** - Add detection method to `analyzers/delta_ac_max/analyze.py`
2. **Update Docs** - Update README files and usage guides
3. **Update Itself** - Modify `.github/copilot-instructions.md` to include:
   - New pattern in "Current Patterns Detected" section
   - Real examples and thresholds
   - Edge cases and context in "Pattern Library"
   - Entry in "Learning History & Changelog"

### Why This Matters

The agent builds **institutional knowledge** that persists across sessions:
- ✅ Future sessions know about all previously learned patterns
- ✅ Context and edge cases are preserved
- ✅ The analyzer gets smarter over time
- ✅ Knowledge doesn't disappear between sessions

### What Gets Recorded

When you teach the agent a pattern like:
```
"I found 'Emergency Stop activated' in the logs when someone hits the e-stop.
This is critical and should always be flagged."
```

The agent will update its own instructions with:
- Pattern details and regex
- What it indicates (safety issue)
- Threshold (always flag)
- Real log example
- Date learned and context

### Example Self-Update

After adding a new pattern, the agent commits:
```
Add detection for emergency stop activation

- New method: detect_emergency_stops()
- Detects: Emergency stop button activation
- Threshold: Always flag (safety critical)
- Updated CSV export with new column
- Updated documentation (README, usage guide)
- Updated agent instructions with pattern knowledge
  └─ Added to Current Patterns Detected
  └─ Added to Learning History
```

This creates a **living knowledge base** that grows with every use!

---

**Note:** The agent learns from the instructions in `copilot-instructions.md`. Keep that file updated as the project evolves!
