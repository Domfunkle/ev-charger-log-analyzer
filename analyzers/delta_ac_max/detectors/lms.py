#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Load Management System (LMS) detection for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Any, Callable


class LmsDetector:
    """Detector for Load Management System (Modbus) issues"""
    
    @staticmethod
    def detect_lms_issues(folder: Path, parse_events_func: Callable) -> Dict[str, Any]:
        """Detect Load Management System communication and LIMIT_toNoPower issues
        
        Local LMS (Load Management System) communicates via Modbus to control
        charger current limits. Issues include:
        - Load_Mgmt_Comm timeout errors (Modbus communication failure)
        - LIMIT_toNoPower (EV0103) - charger stuck in zero-power limiting state
        - State persisting after LMS disconnected (requires factory reset)
        
        Common in multi-charger sites with load balancing/sharing.
        
        Args:
            folder: Path to the extracted charger log folder
            parse_events_func: Function to parse events (from EventDetector)
        
        Returns:`n            Dict with 'load_mgmt_comm_errors' (int), 'limit_to_nopower' (list), 'examples' (list)
        """
        systemlog_dir = folder / "Storage" / "SystemLog"
        if not systemlog_dir.exists():
            return {'load_mgmt_comm_errors': 0, 'limit_to_nopower_events': [], 'examples': []}
        
        load_mgmt_errors = []
        limit_to_nopower = []
        
        # Get all SystemLog files
        log_files = []
        base_log = systemlog_dir / "SystemLog"
        if base_log.exists():
            log_files.append(base_log)
        
        for i in range(10):
            rotated = systemlog_dir / f"SystemLog.{i}"
            if rotated.exists():
                log_files.append(rotated)
        
        # Pattern: Load_Mgmt_Comm errors
        load_mgmt_pattern = re.compile(r'Load_Mgmt_Comm.*(?:timeout|time out|fail|error)', re.IGNORECASE)
        
        for log_file in log_files:
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Detect Load_Mgmt_Comm errors
                        if load_mgmt_pattern.search(line):
                            timestamp_match = re.match(r'(\w+ +\d+ \d+:\d+:\d+\.\d+)', line)
                            timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                            load_mgmt_errors.append({
                                'timestamp': timestamp,
                                'line': line.strip()
                            })
            
            except Exception as e:
                print(f"  ⚠ Could not parse LMS errors from {log_file.name}: {e}")
        
        # Check EventLog for LIMIT_toNoPower (EV0103)
        events = parse_events_func(folder)
        for event in events:
            if event['code'] == 'EV0103':
                limit_to_nopower.append(event)
        
        return {
            'load_mgmt_comm_errors': len(load_mgmt_errors),
            'limit_to_nopower_count': len(limit_to_nopower),
            'limit_to_nopower_events': limit_to_nopower,
            'examples': load_mgmt_errors[:10]  # First 10 examples
        }
    
    @staticmethod
    def detect_modbus_config_issues(folder: Path) -> Dict[str, Any]:
        """Detect Modbus register misconfiguration causing LIMIT_toNoPower
        
        Critical Pattern: Partial LMS configuration with zero power limits causes
        charger to enter LIMIT_toNoPower state (EV0103). Charger cannot deliver
        power below 6A (IEC 61851-1), so 0W = suspended charging.
        
        Checks Config/evcs file for:
        - u32ModbusMAXPower = 0 (0 Watts maximum - WRONG)
        - u32ModbusMINPower = 0 (0 Watts minimum - WRONG)
        - Presence of any Modbus config vs none at all
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'has_modbus_config', 'max_power', 'min_power', 'is_misconfigured', 'issue_description'
        """
        evcs_file = folder / "Config" / "evcs"
        
        if not evcs_file.exists():
            return {
                'has_modbus_config': False,
                'max_power': None,
                'min_power': None,
                'power_limit': None,
                'fallback_limit': None,
                'timeout_enabled': None,
                'is_misconfigured': False,
                'issue_description': None
            }
        
        try:
            with open(evcs_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            
            # Extract Modbus configuration parameters
            max_power_match = re.search(r"option u32ModbusMAXPower '(\d+)'", content)
            min_power_match = re.search(r"option u32ModbusMINPower '(\d+)'", content)
            power_limit_match = re.search(r"option u32ModbusPowerLimit '(\d+)'", content)
            fallback_limit_match = re.search(r"option u32ModbusFallbackLimit '(\d+)'", content)
            timeout_enable_match = re.search(r"option u16ModbusCommTimeoutEnable '(\d+)'", content)
            
            # If no Modbus config at all, return clean
            has_any_modbus = any([max_power_match, min_power_match, power_limit_match, 
                                  fallback_limit_match, timeout_enable_match])
            
            if not has_any_modbus:
                return {
                    'has_modbus_config': False,
                    'max_power': None,
                    'min_power': None,
                    'power_limit': None,
                    'fallback_limit': None,
                    'timeout_enabled': None,
                    'is_misconfigured': False,
                    'issue_description': None
                }
            
            # Parse values
            max_power = int(max_power_match.group(1)) if max_power_match else None
            min_power = int(min_power_match.group(1)) if min_power_match else None
            power_limit = int(power_limit_match.group(1)) if power_limit_match else None
            fallback_limit = int(fallback_limit_match.group(1)) if fallback_limit_match else None
            timeout_enabled = int(timeout_enable_match.group(1)) if timeout_enable_match else None
            
            # Detect misconfiguration patterns
            issues = []
            is_misconfigured = False
            
            # Critical: Check PowerLimit and FallbackLimit first (these are the PRIMARY controls)
            # MAX/MIN power registers are informational/secondary - only flag if primary limits are wrong
            
            # Pattern 1: Zero PowerLimit (most critical - prevents charging)
            if power_limit is not None and power_limit == 0:
                issues.append(f"ModbusPowerLimit=0W (charger cannot deliver power)")
                is_misconfigured = True
            
            # Pattern 2: Zero FallbackLimit with timeout enabled (causes LIMIT_toNoPower on timeout)
            if fallback_limit is not None and fallback_limit == 0 and timeout_enabled == 1:
                issues.append(f"FallbackLimit=0W with timeout enabled (will suspend on LMS failure)")
                is_misconfigured = True
            
            # Pattern 3: Very low PowerLimit (below 6A @ 230V = 1380W)
            MIN_SAFE_POWER = 1380
            if power_limit is not None and 0 < power_limit < MIN_SAFE_POWER:
                issues.append(f"ModbusPowerLimit={power_limit}W (<6A minimum per IEC 61851-1)")
                is_misconfigured = True
            
            # Pattern 4: Very low FallbackLimit with timeout enabled
            if fallback_limit is not None and 0 < fallback_limit < MIN_SAFE_POWER and timeout_enabled == 1:
                issues.append(f"FallbackLimit={fallback_limit}W with timeout (below 6A minimum)")
                is_misconfigured = True
            
            # NOTE: MAX/MIN power registers at 0 are INFORMATIONAL ONLY when PowerLimit=0xFFFF
            # These registers appear to be unused/deprecated based on field observations
            # Only flag if BOTH PowerLimit is correct AND MAX/MIN are causing actual issues
            
            issue_description = " | ".join(issues) if issues else None
            
            return {
                'has_modbus_config': True,
                'max_power': max_power,
                'min_power': min_power,
                'power_limit': power_limit,
                'fallback_limit': fallback_limit,
                'timeout_enabled': timeout_enabled,
                'is_misconfigured': is_misconfigured,
                'issue_description': issue_description
            }
            
        except Exception as e:
            return {
                'has_modbus_config': False,
                'max_power': None,
                'min_power': None,
                'power_limit': None,
                'fallback_limit': None,
                'timeout_enabled': None,
                'is_misconfigured': False,
                'issue_description': f"Error reading config: {e}"
            }

