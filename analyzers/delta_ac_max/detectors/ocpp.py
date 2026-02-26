#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCPP-related detection for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
import json
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set, Tuple
from collections import OrderedDict


class OcppDetector:
    """Detector for OCPP protocol issues"""
    
    @staticmethod
    def _infer_year_from_rtc_static(month, day, rtc_syncs):
        """Static helper to infer year from RTC syncs
        
        Args:
            month: Month number (1-12)
            day: Day of month
            rtc_syncs: List of RTC sync anchor points
            
        Returns:
            Inferred year
        """
        from datetime import datetime
        
        if not rtc_syncs:
            # Fallback: assume recent log (within last 2 years)
            current_year = datetime.now().year
            return current_year
        
        # Find nearest RTC sync
        best_match = None
        for sync in rtc_syncs:
            if sync['log_month'] == month and sync['log_day'] == day:
                best_match = sync
                break
            elif sync['log_month'] < month or (sync['log_month'] == month and sync['log_day'] <= day):
                best_match = sync
        
        if best_match:
            return best_match['actual_year']
        
        # Use earliest RTC sync year as baseline
        return rtc_syncs[0]['actual_year']
    
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

    @staticmethod
    def detect_change_configuration_bursts(folder: Path) -> Dict[str, Any]:
        """Detect clustered ChangeConfiguration command bursts and related patterns.

        Field pattern: backend reconnects can be followed by rapid ChangeConfiguration
        storms (many keys in seconds), often mirrored by ConfigTable writes and sometimes
        overlapping OCP/OCPP fault windows.

        Args:
            folder: Path to charger log folder

        Returns:
            Dict with aggregate counts and burst examples.
        """
        log_dir = folder / "Storage" / "SystemLog"
        if not log_dir.exists():
            return {
                'total_changes': 0,
                'unique_keys': 0,
                'burst_count': 0,
                'largest_burst_size': 0,
                'bursts_with_ocp': 0,
                'bursts_with_backend_reconnect': 0,
                'examples': []
            }

        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }

        timestamp_re = re.compile(
            r'^(?P<mon>[A-Z][a-z]{2})\s+(?P<day>\d{1,2})\s+(?P<time>\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?)'
        )

        def parse_ts(line: str, year: int = 2026):
            match = timestamp_re.match(line)
            if not match:
                return None
            month = month_map.get(match.group('mon'))
            if not month:
                return None
            day = int(match.group('day'))
            time_part = match.group('time')
            fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in time_part else '%Y-%m-%d %H:%M:%S'
            try:
                return datetime.strptime(f"{year}-{month:02d}-{day:02d} {time_part}", fmt)
            except ValueError:
                return None

        ocpp_files = []
        base_ocpp = log_dir / "OCPP16J_Log.csv"
        if base_ocpp.exists():
            ocpp_files.append(base_ocpp)
        for i in range(10):
            rotated = log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)

        system_files = []
        base_system = log_dir / "SystemLog"
        if base_system.exists():
            system_files.append(base_system)
        for i in range(10):
            rotated = log_dir / f"SystemLog.{i}"
            if rotated.exists():
                system_files.append(rotated)

        change_entries = []
        all_keys = set()
        key_pattern = re.compile(
            r'CommandParsing:tReg\.tMsgCS\.pu8Action=ChangeConfiguration.*?key=([^,\s]+)',
            re.IGNORECASE
        )

        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as file_handle:
                    for line in file_handle:
                        if 'pu8Action=ChangeConfiguration' not in line:
                            continue
                        timestamp = parse_ts(line)
                        if not timestamp:
                            continue
                        key_match = key_pattern.search(line)
                        key_name = key_match.group(1) if key_match else 'Unknown'
                        change_entries.append({'timestamp': timestamp, 'key': key_name, 'line': line.strip()})
                        all_keys.add(key_name)
            except Exception:
                continue

        change_entries.sort(key=lambda item: item['timestamp'])

        if not change_entries:
            return {
                'total_changes': 0,
                'unique_keys': 0,
                'burst_count': 0,
                'largest_burst_size': 0,
                'bursts_with_ocp': 0,
                'bursts_with_backend_reconnect': 0,
                'examples': []
            }

        config_write_times = []
        backend_times = []
        ocp_times = []

        for sys_file in system_files:
            try:
                with open(sys_file, 'r', encoding='utf-8', errors='ignore') as file_handle:
                    for line in file_handle:
                        timestamp = parse_ts(line)
                        if not timestamp:
                            continue
                        if '[OCPP16J][ConfigTable] Write Success' in line:
                            config_write_times.append(timestamp)
                        if 'Backend connection fail' in line or 'Backend connection success' in line:
                            backend_times.append(timestamp)
                        if '[IntComm] AC output OCP' in line and 'recover' not in line.lower():
                            ocp_times.append(timestamp)
            except Exception:
                continue

        config_write_times.sort()
        backend_times.sort()
        ocp_times.sort()

        burst_max_gap_seconds = 3
        minimum_burst_size = 8
        bursts = []
        current_burst = [change_entries[0]]

        for entry in change_entries[1:]:
            previous = current_burst[-1]
            gap_seconds = (entry['timestamp'] - previous['timestamp']).total_seconds()
            if gap_seconds <= burst_max_gap_seconds:
                current_burst.append(entry)
            else:
                if len(current_burst) >= minimum_burst_size:
                    bursts.append(current_burst)
                current_burst = [entry]

        if len(current_burst) >= minimum_burst_size:
            bursts.append(current_burst)

        def count_between(series, start, end):
            return sum(1 for timestamp in series if start <= timestamp <= end)

        burst_examples = []
        bursts_with_ocp = 0
        bursts_with_reconnect = 0
        largest_burst_size = 0

        for burst in bursts:
            start_time = burst[0]['timestamp']
            end_time = burst[-1]['timestamp']
            burst_size = len(burst)
            largest_burst_size = max(largest_burst_size, burst_size)

            burst_keys = []
            seen_keys = set()
            for item in burst:
                if item['key'] not in seen_keys:
                    burst_keys.append(item['key'])
                    seen_keys.add(item['key'])

            config_window_start = start_time - timedelta(seconds=10)
            config_window_end = end_time + timedelta(seconds=10)
            reconnect_window_start = start_time - timedelta(seconds=30)
            reconnect_window_end = end_time + timedelta(seconds=30)
            ocp_window_start = start_time - timedelta(seconds=45)
            ocp_window_end = end_time + timedelta(seconds=45)

            config_writes = count_between(config_write_times, config_window_start, config_window_end)
            backend_reconnects = count_between(backend_times, reconnect_window_start, reconnect_window_end)
            ocp_count = count_between(ocp_times, ocp_window_start, ocp_window_end)

            if backend_reconnects > 0:
                bursts_with_reconnect += 1
            if ocp_count > 0:
                bursts_with_ocp += 1

            if len(burst_examples) < 5:
                burst_examples.append({
                    'start': start_time.strftime('%Y.%m.%d %H:%M:%S'),
                    'end': end_time.strftime('%Y.%m.%d %H:%M:%S'),
                    'duration_seconds': round((end_time - start_time).total_seconds(), 3),
                    'change_count': burst_size,
                    'unique_key_count': len(burst_keys),
                    'keys': burst_keys[:15],
                    'configtable_writes': config_writes,
                    'backend_reconnect_events': backend_reconnects,
                    'ocp_events_nearby': ocp_count
                })

        return {
            'total_changes': len(change_entries),
            'unique_keys': len(all_keys),
            'burst_count': len(bursts),
            'largest_burst_size': largest_burst_size,
            'bursts_with_ocp': bursts_with_ocp,
            'bursts_with_backend_reconnect': bursts_with_reconnect,
            'examples': burst_examples
        }
