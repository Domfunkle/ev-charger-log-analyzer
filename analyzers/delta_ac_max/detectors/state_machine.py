#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCPP state machine analysis for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Any


class StateMachineDetector:
    """Detector for OCPP state transition anomalies"""
    
    @staticmethod
    def parse_ocpp_state_transitions(folder: Path) -> Dict[str, Any]:
        """Parse StatusNotification messages to track connector state changes
        
        OCPP 1.6 defines valid connector states and transitions.
        This method extracts state changes to detect anomalies.
        
        Valid states: Available, Preparing, Charging, SuspendedEVSE, SuspendedEV,
                      Finishing, Reserved, Unavailable, Faulted
        
        Args:`n            folder: Path to charger log folder`n            `n        Returns:`n            Dict with 'transitions' (list), 'invalid' (list), 'suspicious' (list), 'final_states' (dict)
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {'transitions': [], 'invalid': [], 'suspicious': []}
        
        transitions = []
        invalid_transitions = []
        suspicious_patterns = []
        
        # Valid OCPP 1.6 states
        valid_states = {
            'Available', 'Preparing', 'Charging', 'SuspendedEVSE', 'SuspendedEV',
            'Finishing', 'Reserved', 'Unavailable', 'Faulted'
        }
        
        # Track current state per connector
        connector_states = {}
        
        # Get all OCPP log files
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        for i in range(10):
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        # Parse StatusNotification messages
        # Pattern: StatusNotification with connectorId and status in JSON format
        # Example: "StatusNotification",{"connectorId":1,"errorCode":"NoError","status":"Charging"
        status_pattern = re.compile(r'"connectorId"\s*:\s*(\d+).*?"status"\s*:\s*"(\w+)"', re.IGNORECASE)
        
        for ocpp_file in sorted(ocpp_files, reverse=True):  # Process oldest first (.9 → .0 → base)
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if 'StatusNotification' not in line:
                            continue
                        
                        match = status_pattern.search(line)
                        if match:
                            connector_id = int(match.group(1))
                            new_state = match.group(2)
                            
                            # Extract timestamp
                            timestamp_match = re.match(r'(\w+ +\d+ \d+:\d+:\d+\.\d+)', line)
                            timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                            
                            # Validate state is in OCPP spec
                            if new_state not in valid_states:
                                invalid_transitions.append({
                                    'timestamp': timestamp,
                                    'connector': connector_id,
                                    'state': new_state,
                                    'reason': f'Invalid OCPP state: {new_state}'
                                })
                            
                            # Track transition
                            old_state = connector_states.get(connector_id, 'Unknown')
                            transitions.append({
                                'timestamp': timestamp,
                                'connector': connector_id,
                                'from': old_state,
                                'to': new_state
                            })
                            
                            # Detect suspicious transitions
                            # Available → Charging without Preparing (vehicle not connected properly?)
                            if old_state == 'Available' and new_state == 'Charging':
                                suspicious_patterns.append({
                                    'timestamp': timestamp,
                                    'connector': connector_id,
                                    'pattern': 'Available → Charging (skipped Preparing)',
                                    'concern': 'Vehicle connection may not have been detected'
                                })
                            
                            # Charging → Available without Finishing (abrupt stop?)
                            if old_state == 'Charging' and new_state == 'Available':
                                suspicious_patterns.append({
                                    'timestamp': timestamp,
                                    'connector': connector_id,
                                    'pattern': 'Charging → Available (skipped Finishing)',
                                    'concern': 'Abrupt session end, possible disconnect or error'
                                })
                            
                            # Charging → Preparing (ABNORMAL - charger restarting session)
                            # NOTE: This can be EXPECTED if backend sent <6A charging profile
                            # Check for correlation with low-current profiles
                            if old_state == 'Charging' and new_state == 'Preparing':
                                suspicious_patterns.append({
                                    'timestamp': timestamp,
                                    'connector': connector_id,
                                    'pattern': 'Charging → Preparing (session restart)',
                                    'concern': 'Charger suspended charging - check for <6A charging profiles (IEC 61851-1)'
                                })
                            
                            # SuspendedEVSE → Preparing (ABNORMAL - should resume or finish)
                            # NOTE: This can be EXPECTED if backend sent <6A charging profile
                            if old_state == 'SuspendedEVSE' and new_state == 'Preparing':
                                suspicious_patterns.append({
                                    'timestamp': timestamp,
                                    'connector': connector_id,
                                    'pattern': 'SuspendedEVSE → Preparing (abnormal resume)',
                                    'concern': 'Charger not resuming - check for <6A charging profiles (IEC 61851-1)'
                                })
                            
                            # Update state
                            connector_states[connector_id] = new_state
            
            except Exception as e:
                print(f"  ⚠ Could not parse state transitions from {ocpp_file.name}: {e}")
        
        return {
            'transitions': transitions[-50:],  # Last 50 transitions
            'invalid': invalid_transitions,
            'suspicious': suspicious_patterns,
            'final_states': connector_states
        }

