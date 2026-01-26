#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCPP-related detection for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Any


class OcppDetector:
    """Detector for OCPP protocol issues"""
    
    @staticmethod
    def detect_charging_profile_timeouts(folder: Path) -> Dict[str, Any]:
        """Detect SetChargingProfile timeout errors in OCPP logs
        
        This pattern indicates a critical firmware bug where chargers advertise
        support for 20 periods in ChargingScheduleMaxPeriods but can only handle 10.
        Results in backend disconnects and failed load management.
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'count' (int) and 'examples' (list of str)
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {'count': 0, 'examples': []}
        
        timeout_lines = []
        pattern = "SetChargingProfileConf process time out"
        
        # Check OCPP16J_Log.csv and all rotations (.0, .1, .2, etc.)
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        # Add rotated logs
        for i in range(10):  # Check up to .9
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        # Search all OCPP log files
        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if pattern in line:
                            timeout_lines.append(line.strip())
            except Exception as e:
                print(f"  ⚠ Could not read {ocpp_file.name}: {e}")
        
        return {
            'count': len(timeout_lines),
            'examples': timeout_lines[:5]  # First 5 examples
        }
    
    @staticmethod
    def detect_ocpp_rejections(folder: Path) -> Dict[str, Any]:
        """Detect OCPP Rejected responses, especially RemoteStartTransaction
        
        RemoteStartTransaction Rejected often indicates:
        - Vehicle not connected (state: Available instead of Preparing)
        - User attempting app unlock before plugging in
        - Malformed request or invalid data
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'total' (int), 'by_type' (dict), 'examples' (list)
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {'total': 0, 'by_type': {}, 'examples': []}
        
        rejections = {
            'total': 0,
            'by_type': {},
            'examples': []
        }
        
        # Get all OCPP log files
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        for i in range(10):
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        # Search for rejection patterns
        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Look for "Rejected" in OCPP responses
                        if '"status":"Rejected"' in line or 'status":"Rejected"' in line:
                            rejections['total'] += 1
                            
                            # Try to identify the message type
                            if 'RemoteStartTransaction' in line:
                                rejections['by_type']['RemoteStartTransaction'] = \
                                    rejections['by_type'].get('RemoteStartTransaction', 0) + 1
                            elif 'RemoteStopTransaction' in line:
                                rejections['by_type']['RemoteStopTransaction'] = \
                                    rejections['by_type'].get('RemoteStopTransaction', 0) + 1
                            elif 'UnlockConnector' in line:
                                rejections['by_type']['UnlockConnector'] = \
                                    rejections['by_type'].get('UnlockConnector', 0) + 1
                            elif 'ChangeConfiguration' in line:
                                rejections['by_type']['ChangeConfiguration'] = \
                                    rejections['by_type'].get('ChangeConfiguration', 0) + 1
                            else:
                                rejections['by_type']['Other'] = \
                                    rejections['by_type'].get('Other', 0) + 1
                            
                            # Store examples (first 10)
                            if len(rejections['examples']) < 10:
                                rejections['examples'].append(line.strip())
            except Exception as e:
                print(f"  ⚠ Could not read {ocpp_file.name}: {e}")
        
        return rejections
    
    @staticmethod
    def detect_ng_flags(folder: Path) -> Dict[str, Any]:
        """Detect NG (Not Good) flags in system logs
        
        NG flags indicate message processing failures or invalid data.
        Common patterns: "result: NG", "[NG]", etc.
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'count' (int) and 'examples' (list of str)
        """
        system_log_dir = folder / "Storage" / "SystemLog"
        if not system_log_dir.exists():
            return {'count': 0, 'examples': []}
        
        ng_lines = []
        
        # Check SystemLog and rotations
        system_files = []
        system_base = system_log_dir / "SystemLog"
        if system_base.exists():
            system_files.append(system_base)
        
        for i in range(10):
            rotated = system_log_dir / f"SystemLog.{i}"
            if rotated.exists():
                system_files.append(rotated)
        
        # Search for NG patterns
        for sys_file in system_files:
            try:
                with open(sys_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Look for NG indicators
                        if re.search(r'\bNG\b|result:\s*NG|\[NG\]', line, re.IGNORECASE):
                            ng_lines.append(line.strip())
            except Exception as e:
                print(f"  ⚠ Could not read {sys_file.name}: {e}")
        
        return {
            'count': len(ng_lines),
            'examples': ng_lines[:5]  # First 5 examples
        }
    
    @staticmethod
    def detect_ocpp_timeouts(folder: Path) -> Dict[str, Any]:
        """Detect general OCPP timeout errors (beyond SetChargingProfile)
        
        Looks for timeout patterns in OCPP logs that indicate communication issues.
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'count' (int) and 'examples' (list of str)
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {'count': 0, 'examples': []}
        
        timeout_lines = []
        # Pattern for timeouts (but exclude SetChargingProfile which is tracked separately)
        pattern = re.compile(r'time\s*out|timeout', re.IGNORECASE)
        exclude_pattern = "SetChargingProfileConf process time out"
        
        # Get all OCPP log files
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        for i in range(10):
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        # Search for timeout patterns
        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if pattern.search(line) and exclude_pattern not in line:
                            timeout_lines.append(line.strip())
            except Exception as e:
                print(f"  ⚠ Could not read {ocpp_file.name}: {e}")
        
        return {
            'count': len(timeout_lines),
            'examples': timeout_lines[:5]  # First 5 examples
        }
    
    @staticmethod
    def detect_low_current_profiles(folder: Path) -> Dict[str, Any]:
        """Detect SetChargingProfile commands with current limits <6A
        
        Per IEC 61851-1, Mode 3 AC charging requires the vehicle to stop charging
        when current limit is below 6A. This causes the charger to suspend and
        report "Preparing" state while vehicle remains connected.
        
        Common cause: Backend sending 0A profiles (unintentional or load management)
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'count' (int), 'zero_current' (int), 'examples' (list)
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {'count': 0, 'zero_current': 0, 'examples': []}
        
        low_current_profiles = []
        zero_current_count = 0
        
        # Get all OCPP log files
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        for i in range(10):
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        # Pattern: SetChargingProfile with limit value
        # Example: limit=0.100000 or limit=5.500000
        profile_pattern = re.compile(r'SetChargingProfile.*limit=([\d\.]+)', re.IGNORECASE)
        
        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if 'SetChargingProfile' not in line:
                            continue
                        
                        match = profile_pattern.search(line)
                        if match:
                            limit = float(match.group(1))
                            
                            # Detect profiles below 6A threshold
                            if limit < 6.0:
                                # Extract timestamp
                                timestamp_match = re.match(r'(\w+ +\d+ \d+:\d+:\d+\.\d+)', line)
                                timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                                
                                # Extract connector ID
                                connector_match = re.search(r'connectorId[=:](\d+)', line)
                                connector_id = int(connector_match.group(1)) if connector_match else 0
                                
                                low_current_profiles.append({
                                    'timestamp': timestamp,
                                    'connector': connector_id,
                                    'limit': limit,
                                    'line': line.strip()
                                })
                                
                                if limit < 1.0:
                                    zero_current_count += 1
            
            except Exception as e:
                print(f"  ⚠ Could not parse charging profiles from {ocpp_file.name}: {e}")
        
        return {
            'count': len(low_current_profiles),
            'zero_current': zero_current_count,
            'examples': low_current_profiles[:10]  # First 10 examples
        }
