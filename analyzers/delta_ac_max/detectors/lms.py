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

