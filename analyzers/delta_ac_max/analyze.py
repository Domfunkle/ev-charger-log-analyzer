#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EV Charger Log Analysis Tool
Author: Daniel Nathanson
Version: 0.0.7 (Development)
Purpose: Automated analysis of EV charger logs for common issues

Analyzes EV charger logs for:
- Backend connection failures
- MCU communication errors
- Logging gaps
- Firmware versions
- High error counts
- Critical OCPP protocol violations (data loss, billing failures)
"""

import argparse
import re
import sys
import os
from collections import Counter
from pathlib import Path
from multiprocessing import Pool, Manager, cpu_count
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
import time

console = Console(highlight=False)

# Fix Windows encoding issues with Unicode characters
if sys.platform == 'win32':
    try:
        # Set UTF-8 encoding for stdout
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Import modular components
from .detectors import EventDetector, OcppDetector, OcppTransactionDetector, FirmwareDetector, HardwareDetector, LmsDetector, StateMachineDetector
from .error_codes import ERROR_CODES
from .reporter import Reporter
from .utils import extract_zips


class ChargerAnalyzer:
    """Analyzes EV charger logs for common issues"""
    
    def __init__(self, log_directory=None):
        self.log_directory = Path(log_directory) if log_directory else Path.cwd()
        self.results = []
        self.event_detector = EventDetector()
        self.ocpp_detector = OcppDetector()
        self.ocpp_transaction_detector = OcppTransactionDetector()
        self.firmware_detector = FirmwareDetector()
        self.hardware_detector = HardwareDetector()
        self.lms_detector = LmsDetector()
        self.state_detector = StateMachineDetector()
    
    def _parse_rtc_syncs(self, folder):
        """Parse RTC sync messages from all SystemLog files to build year timeline
        
        RTC sync messages reveal the actual date/time:
        Example: "Jul 20 03:30:44 ... Get RTC Info: 2026.01.12-03:32:30"
        This means the log timestamp "Jul 20 03:30:44" is actually "2026.01.12 03:32:30"
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            List of dicts: [{'log_timestamp': datetime, 'actual_datetime': datetime}, ...]
            Sorted chronologically by actual datetime (oldest first)
        """
        from datetime import datetime
        import re
        
        system_log_dir = folder / "Storage" / "SystemLog"
        if not system_log_dir.exists():
            return []
        
        # Collect all SystemLog files
        system_log_files = []
        main_log = system_log_dir / "SystemLog"
        if main_log.exists():
            system_log_files.append(main_log)
        
        for i in range(10):  # Check .0 through .9
            rotated_log = system_log_dir / f"SystemLog.{i}"
            if rotated_log.exists():
                system_log_files.append(rotated_log)
        
        rtc_syncs = []
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        # Parse RTC syncs from all log files (process oldest first)
        for log_file in reversed(system_log_files):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Look for: "Jan 12 03:32:30.123 ... Get RTC Info: 2026.01.12-03:32:30"
                        if 'Get RTC Info:' in line:
                            # Extract log timestamp: "Jan 12 03:32:30"
                            log_match = re.match(r'(\w+)\s+(\d+)\s+(\d+):(\d+):(\d+)', line)
                            # Extract actual RTC time: "2026.01.12-03:32:30"
                            rtc_match = re.search(r'Get RTC Info:\s*(\d{4})\.(\d{2})\.(\d{2})-(\d{2}):(\d{2}):(\d{2})', line)
                            
                            if log_match and rtc_match:
                                # Parse log timestamp (without year)
                                log_month = month_map.get(log_match.group(1))
                                log_day = int(log_match.group(2))
                                log_hour = int(log_match.group(3))
                                log_min = int(log_match.group(4))
                                log_sec = int(log_match.group(5))
                                
                                # Parse actual RTC timestamp (with year)
                                rtc_year = int(rtc_match.group(1))
                                rtc_month = int(rtc_match.group(2))
                                rtc_day = int(rtc_match.group(3))
                                rtc_hour = int(rtc_match.group(4))
                                rtc_min = int(rtc_match.group(5))
                                rtc_sec = int(rtc_match.group(6))
                                
                                actual_dt = datetime(rtc_year, rtc_month, rtc_day, rtc_hour, rtc_min, rtc_sec)
                                
                                # Store mapping: log format → actual datetime
                                rtc_syncs.append({
                                    'log_month': log_month,
                                    'log_day': log_day,
                                    'actual_datetime': actual_dt,
                                    'actual_year': rtc_year
                                })
            except Exception as e:
                continue
        
        # Sort by actual datetime (oldest first)
        rtc_syncs.sort(key=lambda x: x['actual_datetime'])
        
        return rtc_syncs
    
    def _infer_year_from_rtc(self, month, day, rtc_syncs):
        """Infer the year for a log timestamp based on nearby RTC syncs
        
        Args:
            month: Month number (1-12)
            day: Day of month
            rtc_syncs: List of RTC sync anchor points
            
        Returns:
            Inferred year, or current year if no RTC syncs available
        """
        from datetime import datetime
        
        if not rtc_syncs:
            # Fallback: use current year
            return datetime.now().year
        
        # Find the nearest RTC sync
        # Strategy: Find RTC sync with same month/day, or closest before it
        best_match = None
        for sync in rtc_syncs:
            if sync['log_month'] == month and sync['log_day'] == day:
                # Exact match on month/day
                best_match = sync
                break
            elif sync['log_month'] < month or (sync['log_month'] == month and sync['log_day'] <= day):
                # This sync is before our target date (same year)
                best_match = sync
        
        if best_match:
            return best_match['actual_year']
        
        # If no match found, use the earliest RTC sync year
        return rtc_syncs[0]['actual_year']
    
    def _get_firmware_at_timestamp(self, event_timestamp: str, firmware_history: list, rtc_syncs: list = None) -> str:
        """Determine which firmware version was active at a given event timestamp
        
        Args:
            event_timestamp: Event timestamp in format 'YYYY.MM.DD HH:MM:SS'
            firmware_history: List of firmware version changes with timestamps
            rtc_syncs: Optional list of RTC sync anchor points for year inference
            
        Returns:
            Firmware version string or 'Unknown'
        """
        from datetime import datetime
        
        if not firmware_history:
            return 'Unknown'
        
        try:
            # Parse event timestamp (format: '2023.10.24 13:59:43')
            event_dt = datetime.strptime(event_timestamp, '%Y.%m.%d %H:%M:%S')
            
            # Month name to number mapping
            month_map = {
                'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
            }
            
            # Find the firmware version active at event time
            active_version = None
            for fw_change in firmware_history:
                # Parse firmware timestamp (format: 'Oct 24 13:59:53')
                fw_timestamp = fw_change.get('timestamp', '')
                try:
                    # Parse: "Oct 24 13:59:53"
                    parts = fw_timestamp.split()
                    if len(parts) >= 3:
                        month = month_map.get(parts[0])
                        day = int(parts[1])
                        time_parts = parts[2].split(':')
                        hour = int(time_parts[0])
                        minute = int(time_parts[1])
                        second = int(time_parts[2])
                        
                        # Infer year using RTC syncs if available
                        if rtc_syncs:
                            year = self._infer_year_from_rtc(month, day, rtc_syncs)
                        else:
                            # Fallback: use event year
                            year = event_dt.year
                        
                        # Create datetime with inferred year
                        fw_dt = datetime(year, month, day, hour, minute, second)
                        
                        # If this firmware change happened before or at event time, it was active
                        if fw_dt <= event_dt:
                            active_version = fw_change.get('version')
                        else:
                            # This change happened after the event, so stop
                            break
                except:
                    continue
            
            return active_version if active_version else firmware_history[0].get('version', 'Unknown')
            
        except Exception as e:
            return 'Unknown'

    def _normalize_event_timestamp_year(self, event_timestamp: str, rtc_syncs: list = None) -> str:
        """Normalize stale EventLog year values using RTC sync anchors.

        Event CSV timestamps can occasionally carry stale years (e.g., 2024)
        while system logs and RTC anchors indicate current operation in 2026.
        When mismatch is large, preserve month/day/time and replace only year.
        """
        from datetime import datetime

        if not rtc_syncs:
            return event_timestamp

        try:
            event_dt = datetime.strptime(event_timestamp, '%Y.%m.%d %H:%M:%S')
        except Exception:
            return event_timestamp

        inferred_year = self._infer_year_from_rtc(event_dt.month, event_dt.day, rtc_syncs)
        if not inferred_year:
            return event_timestamp

        # Adjust only when mismatch is clearly stale/noisy
        if abs(event_dt.year - inferred_year) < 2:
            return event_timestamp

        try:
            normalized_dt = event_dt.replace(year=inferred_year)
            return normalized_dt.strftime('%Y.%m.%d %H:%M:%S')
        except Exception:
            return event_timestamp

    def _summarize_connectivity_events(self, events):
        """Summarize connectivity-related event and recovery codes from EventLog.

        Includes EV0117-EV0126 (connectivity faults) and their numeric recovery
        forms (111002-111011).
        """
        connectivity_fault_codes = [
            'EV0117', 'EV0118', 'EV0119', 'EV0120', 'EV0121',
            'EV0122', 'EV0123', 'EV0124', 'EV0125', 'EV0126'
        ]

        recovery_to_fault = {}
        for idx, fault_code in enumerate(connectivity_fault_codes):
            numeric_code = 11002 + idx
            recovery_code = f"1{numeric_code:05d}"
            recovery_to_fault[recovery_code] = fault_code

        fault_counter = Counter()
        recovery_counter = Counter()
        fault_type_counter = Counter()
        recovery_type_counter = Counter()
        examples = []

        for event in events:
            code = event.get('code', '')

            if code in connectivity_fault_codes:
                fault_counter[code] += 1
                fault_desc = ERROR_CODES.get(code, {}).get('desc', code)
                fault_type_counter[fault_desc] += 1
                if len(examples) < 8:
                    examples.append({
                        'timestamp': event.get('timestamp') or 'Unknown',
                        'code': code,
                        'description': fault_desc,
                        'kind': 'fault'
                    })
                continue

            mapped_fault = recovery_to_fault.get(code)
            if mapped_fault:
                recovery_counter[code] += 1
                recovery_desc = ERROR_CODES.get(mapped_fault, {}).get('desc', mapped_fault)
                recovery_type_counter[recovery_desc] += 1
                if len(examples) < 8:
                    examples.append({
                        'timestamp': event.get('timestamp') or 'Unknown',
                        'code': code,
                        'description': recovery_desc,
                        'kind': 'recovery'
                    })

        fault_by_code = dict(sorted(fault_counter.items(), key=lambda item: item[1], reverse=True))
        recovery_by_code = dict(sorted(recovery_counter.items(), key=lambda item: item[1], reverse=True))
        fault_by_type = dict(sorted(fault_type_counter.items(), key=lambda item: item[1], reverse=True))
        recovery_by_type = dict(sorted(recovery_type_counter.items(), key=lambda item: item[1], reverse=True))

        fault_total = sum(fault_counter.values())
        recovery_total = sum(recovery_counter.values())

        return {
            'fault_total': fault_total,
            'recovery_total': recovery_total,
            'total': fault_total + recovery_total,
            'fault_by_code': fault_by_code,
            'recovery_by_code': recovery_by_code,
            'fault_by_type': fault_by_type,
            'recovery_by_type': recovery_by_type,
            'examples': examples
        }

    def _collect_system_log_entries(self, folder):
        """Collect timestamped lines from SystemLog and rotated files."""
        from datetime import datetime

        system_log_dir = folder / "Storage" / "SystemLog"
        if not system_log_dir.exists():
            return []

        system_files = []
        system_base = system_log_dir / "SystemLog"
        if system_base.exists():
            system_files.append(system_base)

        for i in range(10):
            rotated = system_log_dir / f"SystemLog.{i}"
            if rotated.exists():
                system_files.append(rotated)

        timestamp_pattern = re.compile(r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\.\d+\s+')
        entries = []

        for sys_file in system_files:
            try:
                with open(sys_file, 'r', encoding='utf-8', errors='ignore') as file_handle:
                    for line in file_handle:
                        match = timestamp_pattern.match(line)
                        if not match:
                            continue
                        try:
                            timestamp = datetime.strptime(f"2000 {match.group(1)}", '%Y %b %d %H:%M:%S')
                            entries.append((timestamp, line.strip()))
                        except Exception:
                            continue
            except Exception:
                continue

        entries.sort(key=lambda item: item[0])
        return entries

    def _collect_ocpp_log_entries(self, folder):
        """Collect timestamped lines from OCPP16J logs and rotated files."""
        from datetime import datetime

        system_log_dir = folder / "Storage" / "SystemLog"
        if not system_log_dir.exists():
            return []

        ocpp_files = sorted(system_log_dir.glob("OCPP16J_Log.csv*"))
        if not ocpp_files:
            return []

        timestamp_pattern = re.compile(r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\.\d+\s+')
        entries = []

        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as file_handle:
                    for line in file_handle:
                        match = timestamp_pattern.match(line)
                        if not match:
                            continue
                        try:
                            timestamp = datetime.strptime(f"2000 {match.group(1)}", '%Y %b %d %H:%M:%S')
                            entries.append((timestamp, line.strip()))
                        except Exception:
                            continue
            except Exception:
                continue

        entries.sort(key=lambda item: item[0])
        return entries

    def _parse_to_systemlog_clock(self, timestamp_str):
        """Parse timestamp string into SystemLog comparable clock (fixed year)."""
        from datetime import datetime

        if not timestamp_str:
            return None

        parsed = None
        for fmt in ('%Y.%m.%d %H:%M:%S', '%b %d %H:%M:%S.%f', '%b %d %H:%M:%S'):
            try:
                parsed = datetime.strptime(timestamp_str, fmt)
                break
            except Exception:
                continue

        if not parsed:
            match = re.match(r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?)', str(timestamp_str))
            if match:
                return self._parse_to_systemlog_clock(match.group(1))
            return None

        try:
            return datetime(2000, parsed.month, parsed.day, parsed.hour, parsed.minute, parsed.second)
        except Exception:
            return None

    def _analyze_leadup_context(self, entries, event_points, window_seconds=60, sample_limit=2, max_events=None, ocpp_entries=None):
        """Analyze common log patterns before arbitrary event timestamps."""
        from bisect import bisect_left, bisect_right
        from datetime import timedelta

        if not entries or not event_points:
            return {
                'event_count': 0,
                'total_event_points': len(event_points) if event_points else 0,
                'window_seconds': window_seconds,
                'marker_counts': {},
                'marker_rates': {},
                'ocpp_marker_counts': {},
                'ocpp_marker_rates': {},
                'ocpp_top_operations': [],
                'immediate_previous': {},
                'samples': [],
                'ocpp_samples': []
            }

        total_event_points = len(event_points)
        if max_events and total_event_points > max_events:
            event_points = event_points[-max_events:]

        markers = {
            'suspend_charging': 'Schedule function suspend charging',
            'intcomm_get_time': '[IntComm] Get Date Time Command',
            'intcomm_write_time': '[IntComm] Write Date Time:',
            'wifi_scan_trigger': '[WiFi] Trigger WiFi STA Scan Action',
            'wifi_scan_no_ap': '[WiFi] Scan AP number is -1',
            'config_write_success': '[OCPP16J][ConfigTable] Write Success'
        }

        ocpp_markers = {
            'change_configuration': 'changeconfiguration',
            'rejected_response': '"status":"rejected"',
            'remote_start': 'remotestarttransaction',
            'set_charging_profile': 'setchargingprofile',
            'boot_notification': 'bootnotification',
            'heartbeat': 'heartbeat',
            'status_notification': 'statusnotification',
            'ocpp_timeout': 'time out'
        }

        marker_counts = Counter()
        ocpp_marker_counts = Counter()
        ocpp_operation_counts = Counter()
        previous_categories = Counter()
        samples = []
        ocpp_samples = []

        timeline = [item[0] for item in entries]
        ocpp_timeline = [item[0] for item in ocpp_entries] if ocpp_entries else []

        for point in event_points:
            event_time = point.get('timestamp')
            if not event_time:
                continue

            window_start = event_time - timedelta(seconds=window_seconds)
            window_start_idx = bisect_left(timeline, window_start)
            window_end_idx = bisect_left(timeline, event_time)
            window_entries = [line for _, line in entries[window_start_idx:window_end_idx]]

            ocpp_window_entries = []
            if ocpp_entries:
                ocpp_window_start_idx = bisect_left(ocpp_timeline, window_start)
                ocpp_window_end_idx = bisect_left(ocpp_timeline, event_time)
                ocpp_window_entries = [line for _, line in ocpp_entries[ocpp_window_start_idx:ocpp_window_end_idx]]

            for marker_name, marker_token in markers.items():
                if any(marker_token in line for line in window_entries):
                    marker_counts[marker_name] += 1

            if ocpp_window_entries:
                lowered_ocpp_entries = [line.lower() for line in ocpp_window_entries]
                for marker_name, marker_token in ocpp_markers.items():
                    if any(marker_token in line for line in lowered_ocpp_entries):
                        ocpp_marker_counts[marker_name] += 1

                operations_in_window = set()
                for line in ocpp_window_entries:
                    operation_match = re.search(r'\[OCPP16J\]\s*([A-Za-z0-9_]+)', line)
                    if not operation_match:
                        continue
                    operation_name = operation_match.group(1)
                    operation_name = re.sub(r'(Req|Conf|ResultParsing|Callback|CALLBACK)$', '', operation_name)
                    if operation_name and len(operation_name) <= 50:
                        operations_in_window.add(operation_name)

                for operation_name in operations_in_window:
                    ocpp_operation_counts[operation_name] += 1

            prev_index = bisect_right(timeline, event_time) - 1
            if prev_index >= 0:
                previous_line = entries[prev_index][1]
                if markers['suspend_charging'] in previous_line:
                    previous_categories['suspend_charging'] += 1
                elif markers['intcomm_write_time'] in previous_line:
                    previous_categories['intcomm_write_time'] += 1
                elif markers['wifi_scan_no_ap'] in previous_line:
                    previous_categories['wifi_scan_no_ap'] += 1
                elif markers['wifi_scan_trigger'] in previous_line:
                    previous_categories['wifi_scan_trigger'] += 1
                elif markers['config_write_success'] in previous_line:
                    previous_categories['config_write_success'] += 1
                else:
                    previous_categories['other'] += 1

            if len(samples) < sample_limit:
                samples.append({
                    'event_label': point.get('label', 'event'),
                    'event_line': point.get('line', ''),
                    'leadup_lines': window_entries[-5:]
                })

            if ocpp_window_entries and len(ocpp_samples) < sample_limit:
                ocpp_samples.append({
                    'event_label': point.get('label', 'event'),
                    'event_line': point.get('line', ''),
                    'leadup_lines': ocpp_window_entries[-5:]
                })

        event_count = len(event_points)
        marker_rates = {
            name: round((count / event_count) * 100, 1)
            for name, count in marker_counts.items()
        }
        ocpp_marker_rates = {
            name: round((count / event_count) * 100, 1)
            for name, count in ocpp_marker_counts.items()
        }
        top_ocpp_operations = []
        for operation_name, count in ocpp_operation_counts.most_common(5):
            top_ocpp_operations.append({
                'name': operation_name,
                'count': count,
                'rate': round((count / event_count) * 100, 1)
            })

        return {
            'event_count': event_count,
            'total_event_points': total_event_points,
            'window_seconds': window_seconds,
            'marker_counts': dict(marker_counts),
            'marker_rates': marker_rates,
            'ocpp_marker_counts': dict(ocpp_marker_counts),
            'ocpp_marker_rates': ocpp_marker_rates,
            'ocpp_top_operations': top_ocpp_operations,
            'immediate_previous': dict(previous_categories),
            'samples': samples,
            'ocpp_samples': ocpp_samples
        }

    def _analyze_backend_fail_leadup(self, folder, window_seconds=60, entries=None, ocpp_entries=None):
        """Analyze common log patterns immediately before backend disconnect events."""
        if entries is None:
            entries = self._collect_system_log_entries(folder)
        points = []
        for timestamp, line in entries:
            if '[Infra] Backend connection fail' in line:
                points.append({
                    'timestamp': timestamp,
                    'label': 'backend_connection_fail',
                    'line': line
                })

        summary = self._analyze_leadup_context(entries, points, window_seconds=window_seconds, sample_limit=3, ocpp_entries=ocpp_entries)
        summary['fail_count'] = summary.get('event_count', 0)
        return summary
    
    def extract_zips_wrapper(self, specific_files=None):
        """Wrapper for extract_zips utility function
        
        Returns:
            List of Path objects for extracted folders
        """
        return extract_zips(self.log_directory, specific_files)
    
    def analyze_charger_log(self, folder, progress_callback=None):
        """Analyze a single charger log folder"""
        def report_progress(percent, message=None):
            if progress_callback:
                try:
                    progress_callback(percent, message)
                except Exception:
                    pass

        report_progress(2, "Initializing")

        # Extract charger info from folder name
        match = re.search(r'\]([A-Z0-9]{14})(.*)$', folder.name)
        
        if not match:
            return None
        
        serial = match.group(1)
        suffix = match.group(2).strip()
        
        # Try to get ChargBox ID from Config/evcs file
        chargebox_id = self.event_detector.get_chargebox_id(folder)
        
        # Determine display ID
        if chargebox_id:
            ev_num = chargebox_id
        elif '[GetDiag]' in folder.name:
            ev_num = serial
        else:
            ev_match = re.search(r'EV(\d+)', suffix)
            ev_num = ev_match.group(1) if ev_match else serial
        
        system_log = folder / "Storage" / "SystemLog" / "SystemLog"
        
        if not system_log.exists():
            return None
        
        # Initialize analysis result structure
        analysis = {
            'ev_number': ev_num,
            'serial': serial,
            'folder_name': folder.name,
            'folder_path': str(folder),
            'firmware_version': None,
            'backend_disconnects': 0,
            'backend_disconnect_examples': [],
            'backend_fail_leadup': {
                'fail_count': 0,
                'window_seconds': 60,
                'marker_counts': {},
                'marker_rates': {},
                'immediate_previous': {},
                'samples': []
            },
            'event_leadup': {},
            'mcu_errors': 0,
            'mcu_error_examples': [],
            'error_count': 0,
            'logging_gaps': [],
            'issues': [],
            'status': 'Clean',
            'log_file': str(system_log),
            'events': [],
            'critical_events': [],
            'connectivity_events': {
                'fault_total': 0,
                'recovery_total': 0,
                'total': 0,
                'fault_by_code': {},
                'recovery_by_code': {},
                'fault_by_type': {},
                'recovery_by_type': {},
                'examples': []
            },
            'charging_profile_timeouts': {'count': 0, 'examples': []},
            'ocpp_rejections': {'total': 0, 'by_type': {}, 'examples': []},
            'change_config_bursts': {'total_changes': 0, 'unique_keys': 0, 'burst_count': 0, 'largest_burst_size': 0, 'bursts_with_ocp': 0, 'bursts_with_backend_reconnect': 0, 'examples': []},
            'ng_flags': {'count': 0, 'examples': []},
            'ocpp_timeouts': {'count': 0, 'examples': []},
            'rfid_faults': {'count': 0, 'examples': []},
            'state_transitions': {'transitions': [], 'invalid': [], 'suspicious': [], 'final_states': {}},
            'lost_transaction_id': {'lost_transaction_count': 0, 'invalid_transaction_ids': 0, 'total_issues': 0, 'examples': []},
            'hard_reset_data_loss': {'hard_reset_count': 0, 'soft_reset_count': 0, 'incomplete_transactions': 0, 'examples': []},
            'meter_register_tracking': {'transactions_analyzed': 0, 'non_cumulative_count': 0, 'meter_values': [], 'examples': []},
            'firmware_updates': {'update_count': 0, 'firmware_history': [], 'current_firmware': None, 'previous_firmware': None, 'mcu_firmware': None, 'update_events': []},
            'system_reboots': {'reboot_count': 0, 'power_loss_count': 0, 'firmware_update_count': 0, 'systemlog_failure_count': 0, 'max_gap_days': 0, 'events': []}
        }
        
        # Run all detectors
        report_progress(8, "Parsing event logs")
        events = self.event_detector.parse_events(folder)
        analysis['events'] = events
        
        report_progress(16, "Analyzing OCPP profile timeouts")
        analysis['charging_profile_timeouts'] = self.ocpp_detector.detect_charging_profile_timeouts(folder)
        report_progress(24, "Analyzing OCPP rejections")
        analysis['ocpp_rejections'] = self.ocpp_detector.detect_ocpp_rejections(folder)
        report_progress(32, "Detecting config bursts")
        analysis['change_config_bursts'] = self.ocpp_detector.detect_change_configuration_bursts(folder)
        report_progress(38, "Scanning NG flags and timeouts")
        analysis['ng_flags'] = self.ocpp_detector.detect_ng_flags(folder)
        analysis['ocpp_timeouts'] = self.ocpp_detector.detect_ocpp_timeouts(folder)
        report_progress(46, "Checking hardware faults and reboots")
        analysis['rfid_faults'] = self.hardware_detector.detect_rfid_faults(folder)
        analysis['system_reboots'] = self.hardware_detector.detect_system_reboots(folder)
        report_progress(54, "Analyzing smart charging profiles")
        analysis['low_current_profiles'] = self.ocpp_detector.detect_low_current_profiles(folder)
        report_progress(60, "Checking LMS and Modbus")
        analysis['lms_issues'] = self.lms_detector.detect_lms_issues(folder, self.event_detector.parse_events)
        analysis['modbus_config'] = self.lms_detector.detect_modbus_config_issues(folder)
        report_progress(66, "Validating state transitions")
        analysis['state_transitions'] = self.state_detector.parse_ocpp_state_transitions(folder)
        
        # Phase 1: Critical OCPP detectors (data loss prevention)
        report_progress(72, "Checking transaction integrity")
        analysis['lost_transaction_id'] = self.ocpp_transaction_detector.detect_lost_transaction_id(folder)
        analysis['precharging_aborts'] = self.ocpp_transaction_detector.detect_precharging_aborts(folder)
        analysis['hard_reset_data_loss'] = self.ocpp_transaction_detector.detect_hard_reset_data_loss(folder)
        analysis['meter_register_tracking'] = self.ocpp_transaction_detector.detect_meter_register_tracking(folder)
        
        # Informational: Firmware update tracking
        report_progress(80, "Tracking firmware history")
        analysis['firmware_updates'] = self.firmware_detector.detect_firmware_updates(folder)
        
        # Parse RTC syncs for accurate year inference
        report_progress(84, "Building RTC timeline")
        rtc_syncs = self._parse_rtc_syncs(folder)

        # Normalize event years when EventLog timestamps are stale vs RTC timeline
        for event in events:
            original_timestamp = event.get('timestamp', '')
            normalized_timestamp = self._normalize_event_timestamp_year(original_timestamp, rtc_syncs)
            if normalized_timestamp != original_timestamp:
                event['original_timestamp'] = original_timestamp
                event['timestamp'] = normalized_timestamp

        analysis['connectivity_events'] = self._summarize_connectivity_events(events)
        
        # Identify critical events
        critical_codes = ['EV0081', 'EV0082', 'EV0083', 'EV0084', 'EV0085', 'EV0086', 'EV0087',
                 'EV0088', 'EV0089', 'EV0090', 'EV0091', 'EV0092', 'EV0093', 'EV0094',
                 'EV0095', 'EV0096', 'EV0097', 'EV0098', 'EV0099', 'EV0100', 'EV0101',
                 'EV0105', 'EV0106', 'EV0107', 'EV0108', 'EV0109',
                 'EV0110', 'EV0114', 'EV0115', 'EV0116']
        critical_events = [e for e in events if e['code'] in critical_codes]
        
        # Get firmware history for correlation
        fw_history = analysis['firmware_updates'].get('firmware_history', [])
        
        # Determine firmware version for all critical events (cheap)
        for event in critical_events:
            event['context'] = {}
            event['firmware_at_event'] = self._get_firmware_at_timestamp(event['timestamp'], fw_history, rtc_syncs)

        # Expensive log context extraction: only for top events shown in report
        # (detailed report currently displays 5 most recent critical events)
        report_progress(85, "Collecting critical event context")
        context_targets = sorted(critical_events, key=lambda e: e.get('timestamp') or '', reverse=True)[:5]
        for event in context_targets:
            event['context'] = self.event_detector.get_log_context(folder, event['timestamp'], window_minutes=5)
        
        analysis['critical_events'] = critical_events

        # Build generalized lead-up summaries for reported event types
        report_progress(86, "Analyzing lead-up context")
        system_entries = self._collect_system_log_entries(folder)
        ocpp_entries = self._collect_ocpp_log_entries(folder)
        backend_leadup = self._analyze_backend_fail_leadup(folder, window_seconds=60, entries=system_entries, ocpp_entries=ocpp_entries)
        analysis['backend_fail_leadup'] = backend_leadup

        critical_points = []
        for event in critical_events:
            leadup_ts = self._parse_to_systemlog_clock(event.get('timestamp'))
            if leadup_ts:
                critical_points.append({
                    'timestamp': leadup_ts,
                    'label': event.get('code', 'critical_event'),
                    'line': f"{event.get('timestamp', '')} - {event.get('code', '')}"
                })

        connectivity_fault_codes = {'EV0117', 'EV0118', 'EV0119', 'EV0120', 'EV0121', 'EV0122', 'EV0123', 'EV0124', 'EV0125', 'EV0126'}
        connectivity_points = []
        for event in events:
            if event.get('code') not in connectivity_fault_codes:
                continue
            leadup_ts = self._parse_to_systemlog_clock(event.get('timestamp'))
            if leadup_ts:
                connectivity_points.append({
                    'timestamp': leadup_ts,
                    'label': event.get('code', 'connectivity_fault'),
                    'line': f"{event.get('timestamp', '')} - {event.get('code', '')}"
                })

        lost_tx_points = []
        for example in analysis['lost_transaction_id'].get('examples', []):
            leadup_ts = self._parse_to_systemlog_clock(example.get('timestamp'))
            if leadup_ts:
                lost_tx_points.append({
                    'timestamp': leadup_ts,
                    'label': 'lost_transaction_id',
                    'line': f"{example.get('timestamp', '')} - {example.get('message', '')}"
                })

        rejection_points = []
        for example in analysis['ocpp_rejections'].get('examples', []):
            leadup_ts = self._parse_to_systemlog_clock(example)
            if leadup_ts:
                rejection_points.append({
                    'timestamp': leadup_ts,
                    'label': 'ocpp_rejection',
                    'line': str(example)
                })

        analysis['event_leadup'] = {
            'backend_disconnect': backend_leadup,
            'critical_events': self._analyze_leadup_context(system_entries, critical_points, window_seconds=60, ocpp_entries=ocpp_entries),
            'connectivity_fault_events': self._analyze_leadup_context(system_entries, connectivity_points, window_seconds=60, max_events=1000, ocpp_entries=ocpp_entries),
            'lost_transaction_id': self._analyze_leadup_context(system_entries, lost_tx_points, window_seconds=60, ocpp_entries=ocpp_entries),
            'ocpp_rejections': self._analyze_leadup_context(system_entries, rejection_points, window_seconds=60, ocpp_entries=ocpp_entries),
        }
        
        # Parse system log for baseline metrics
        try:
            report_progress(88, "Computing baseline metrics")
            with open(system_log, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.splitlines()
            
            # Get firmware version
            fw_matches = re.findall(r'Fw2Ver:\s*([\d\.]+)', content)
            if fw_matches:
                analysis['firmware_version'] = fw_matches[-1]
            
            # Count backend disconnects and get examples
            backend_fail_lines = [line for line in lines if 'Backend connection fail' in line]
            analysis['backend_disconnects'] = len(backend_fail_lines)
            analysis['backend_disconnect_examples'] = backend_fail_lines[:3]
            
            # Count MCU errors and get examples
            mcu_error_lines = [line for line in lines if re.search(r'Send Command 0x[0-9A-Fa-f]+ to MCU False', line)]
            analysis['mcu_errors'] = len(mcu_error_lines)
            analysis['mcu_error_examples'] = mcu_error_lines[:3]
            
            # Count errors
            errors = re.findall(r'\bERROR\b|\berror\b', content)
            analysis['error_count'] = len(errors)
            
            # Check for logging gaps
            jan_dates = []
            for line in lines:
                match = re.match(r'^Jan (\d+)', line)
                if match:
                    jan_dates.append(int(match.group(1)))
            
            jan_dates = sorted(set(jan_dates))
            
            if len(jan_dates) > 1:
                for i in range(len(jan_dates) - 1):
                    diff = jan_dates[i + 1] - jan_dates[i]
                    if diff > 2:
                        gap = f"Jan {jan_dates[i]} to Jan {jan_dates[i + 1]} ({diff} days)"
                        analysis['logging_gaps'].append(gap)
            
            # Determine issues and status
            if analysis['backend_disconnects'] > 10:
                analysis['issues'].append(f"High backend disconnects: {analysis['backend_disconnects']}")
                analysis['status'] = 'Issue'
            
            if analysis['mcu_errors'] > 0:
                analysis['issues'].append(f"MCU communication errors: {analysis['mcu_errors']}")
                analysis['status'] = 'Issue'
            
            if analysis['logging_gaps']:
                analysis['issues'].append(f"Logging gaps: {', '.join(analysis['logging_gaps'])}")
                analysis['status'] = 'Issue'
            
            if analysis['error_count'] > 100:
                analysis['issues'].append(f"High error count: {analysis['error_count']}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['critical_events']:
                analysis['issues'].append(f"Critical hardware events: {len(analysis['critical_events'])}")
                analysis['status'] = 'Issue'

            connectivity = analysis.get('connectivity_events', {})
            if connectivity.get('total', 0) > 0:
                top_types = list(connectivity.get('fault_by_type', {}).items())[:3]
                top_text = ', '.join([f"{name}:{count}" for name, count in top_types])
                issue = (
                    f"Connectivity events: {connectivity.get('total', 0)} "
                    f"({connectivity.get('fault_total', 0)} faults, {connectivity.get('recovery_total', 0)} recoveries)"
                )
                if top_text:
                    issue += f" ({top_text})"
                analysis['issues'].append(issue)

                if connectivity.get('fault_total', 0) >= 20 and analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['charging_profile_timeouts']['count'] > 100:
                analysis['issues'].append(f"⚠️ CRITICAL: SetChargingProfile timeouts: {analysis['charging_profile_timeouts']['count']}")
                analysis['status'] = 'Issue'
            
            if analysis['ocpp_rejections']['total'] > 5:
                rejection_summary = ', '.join([f"{k}:{v}" for k, v in analysis['ocpp_rejections']['by_type'].items()])
                analysis['issues'].append(f"OCPP rejections: {analysis['ocpp_rejections']['total']} ({rejection_summary})")
                if analysis['ocpp_rejections']['total'] > 50:
                    analysis['status'] = 'Issue'
                elif analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'

            burst_data = analysis['change_config_bursts']
            if burst_data['burst_count'] > 0:
                issue_text = (
                    f"ChangeConfiguration bursts: {burst_data['burst_count']} "
                    f"(max {burst_data['largest_burst_size']} changes, "
                    f"{burst_data['bursts_with_ocp']} with nearby OCP, "
                    f"{burst_data['bursts_with_backend_reconnect']} with reconnect)"
                )
                analysis['issues'].append(issue_text)

                if burst_data['bursts_with_ocp'] > 0 or burst_data['largest_burst_size'] >= 20:
                    analysis['status'] = 'Issue'
                elif analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['ng_flags']['count'] > 10:
                analysis['issues'].append(f"NG flags (processing errors): {analysis['ng_flags']['count']}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['ocpp_timeouts']['count'] > 20:
                analysis['issues'].append(f"OCPP timeouts: {analysis['ocpp_timeouts']['count']}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['rfid_faults']['count'] > 100:
                analysis['issues'].append(f"⚠️ CRITICAL: RFID module fault: {analysis['rfid_faults']['count']} errors")
                analysis['status'] = 'Issue'
            
            # System reboots and power loss
            if analysis['system_reboots']['power_loss_count'] > 5:
                analysis['issues'].append(f"⚠️ Frequent power loss: {analysis['system_reboots']['power_loss_count']} events, {analysis['system_reboots']['max_gap_days']} max gap days")
                analysis['status'] = 'Issue'
            elif analysis['system_reboots']['power_loss_count'] > 2:
                analysis['issues'].append(f"Power instability: {analysis['system_reboots']['power_loss_count']} power loss events detected")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            # SystemLog failures (firmware bug, not hardware/site issue)
            if analysis['system_reboots']['systemlog_failure_count'] > 0:
                analysis['issues'].append(f"SystemLog failures: {analysis['system_reboots']['systemlog_failure_count']} events (charger operational, logging stopped)")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['low_current_profiles']['count'] > 10:
                analysis['issues'].append(f"⚠️ Backend issue: {analysis['low_current_profiles']['count']} low-current profiles (<6A), {analysis['low_current_profiles']['zero_current']} near-zero")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['lms_issues']['load_mgmt_comm_errors'] > 5 or analysis['lms_issues']['limit_to_nopower_count'] > 0:
                analysis['issues'].append(f"⚠️ LMS issue: {analysis['lms_issues']['load_mgmt_comm_errors']} comm errors, {analysis['lms_issues']['limit_to_nopower_count']} LIMIT_toNoPower events")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            # Modbus configuration issues
            if analysis['modbus_config']['is_misconfigured']:
                analysis['issues'].append(f"🔴 CRITICAL: Modbus misconfiguration: {analysis['modbus_config']['issue_description']}")
                analysis['status'] = 'Issue'
            
            if analysis['state_transitions']['invalid']:
                analysis['issues'].append(f"OCPP protocol violations: {len(analysis['state_transitions']['invalid'])}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if len(analysis['state_transitions']['suspicious']) > 5:
                analysis['issues'].append(f"Suspicious state transitions: {len(analysis['state_transitions']['suspicious'])}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            # Phase 1: Critical data loss detection
            if analysis['lost_transaction_id']['total_issues'] > 0:
                analysis['issues'].append(f"🔴 CRITICAL: Lost TransactionID: {analysis['lost_transaction_id']['total_issues']} failures (BILLING LOST)")
                analysis['status'] = 'Issue'
            
            # Pre-charging aborts (context-dependent severity)
            if analysis['precharging_aborts']['abort_count'] > 0:
                abort_data = analysis['precharging_aborts']
                if abort_data['severity'] == 'CRITICAL':
                    analysis['issues'].append(f"🔴 CRITICAL: Pre-charging aborts: {abort_data['abort_count']} (charger fault likely)")
                    analysis['status'] = 'Issue'
                elif abort_data['severity'] == 'WARNING':
                    analysis['issues'].append(f"⚠️ WARNING: Pre-charging aborts: {abort_data['abort_count']} (pattern emerging - monitor)")
                    if analysis['status'] == 'Clean':
                        analysis['status'] = 'Warning'
                else:  # INFO
                    analysis['issues'].append(f"ℹ️ INFO: Pre-charging aborts: {abort_data['abort_count']} (likely user error - connector not seated)")
                    # Don't change status for INFO level
            
            if analysis['hard_reset_data_loss']['incomplete_transactions'] > 0:
                analysis['issues'].append(f"🔴 CRITICAL: Hard reset data loss: {analysis['hard_reset_data_loss']['incomplete_transactions']} incomplete transactions")
                analysis['status'] = 'Issue'
            
            if analysis['meter_register_tracking']['non_cumulative_count'] > 0:
                analysis['issues'].append(f"⚠️ Meter register issue: {analysis['meter_register_tracking']['non_cumulative_count']} non-cumulative transactions (audit failure)")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'

            report_progress(100, "Completed")
        
        except Exception as e:
            print(f"Error analyzing {folder.name}: {e}")
            return None
        
        return analysis
    
    def analyze_all_chargers(self, specific_folders=None, parallel=True):
        """Analyze all charger log folders or specific folders
        
        Args:
            specific_folders: Optional list of Path objects to specific folders to analyze.
                            If None, analyzes all folders in log_directory.
            parallel: If True and multiple chargers, use parallel processing (default: True)
        """
        if specific_folders:
            # Analyze only the specified folders
            folders = [f for f in specific_folders if f.is_dir()]
        else:
            # Analyze all folders in directory
            folders = [f for f in self.log_directory.iterdir() 
                      if f.is_dir() and ']' in f.name]
        
        if not folders:
            console.print("[yellow]No charger log folders found in directory.[/yellow]")
            console.print("[dim]Looking for folders with format: [YYYY.MM.DD HH.MM.SS]SERIAL...[/dim]")
            return
        
        console.print(f"[bold]Found {len(folders)} charger log folder(s)[/bold]\n")
        
        # If only 1 charger or parallel disabled, use sequential processing
        if len(folders) == 1 or not parallel:
            with Progress(
                SpinnerColumn(style="cyan"),
                TextColumn("{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console,
                transient=False
            ) as progress:
                main_task = progress.add_task("[cyan]Analyzing chargers...", total=max(1, len(folders) * 100))

                for index, folder in enumerate(folders, 1):
                    base_progress = (index - 1) * 100
                    progress.update(main_task, completed=base_progress)

                    def folder_progress(percent, message=None):
                        description = f"[cyan]Analyzing {folder.name} ({index}/{len(folders)})..."
                        if message:
                            description = f"[cyan]Analyzing {folder.name} ({index}/{len(folders)}) - {message}..."
                        mapped_progress = base_progress + max(0, min(100, percent))
                        progress.update(main_task, completed=mapped_progress, description=description)

                    progress.update(
                        main_task,
                        description=f"[cyan]Analyzing {folder.name} ({index}/{len(folders)}) - Starting..."
                    )
                    analysis = self.analyze_charger_log(folder, progress_callback=folder_progress)
                    if analysis:
                        self.results.append(analysis)
                    progress.update(main_task, completed=index * 100)
            console.print()
            return
        
        # Parallel processing for multiple chargers
        self._analyze_parallel(folders)
    
    def _analyze_parallel(self, folders):
        """Analyze multiple chargers in parallel with live progress display
        
        Args:
            folders: List of Path objects to analyze
        """
        # Determine worker count (auto-detect CPU cores, max 8)
        num_workers = min(cpu_count(), 8, len(folders))
        console.print(f"[dim]Using {num_workers} parallel workers[/dim]\n")
        
        # Create charger IDs for display
        charger_ids = []
        for folder in folders:
            match = re.search(r'\]([A-Z0-9]{14})', folder.name)
            charger_id = match.group(1) if match else folder.name[:20]
            charger_ids.append(charger_id)
        
        # Shared progress dictionary (manager for cross-process sharing)
        manager = Manager()
        progress_dict = manager.dict()
        
        # Initialize all chargers as queued
        for charger_id in charger_ids:
            progress_dict[charger_id] = {'status': 'Queued', 'progress': 0, 'message': 'Queued'}
        
        # Prepare worker arguments
        worker_args = [
            (str(folder), str(self.log_directory), progress_dict, charger_id)
            for folder, charger_id in zip(folders, charger_ids)
        ]
        
        # Start parallel processing with live progress display
        results_map = {}
        
        spinner_frame = 0
        with Live(_create_progress_table(progress_dict, charger_ids, spinner_frame=spinner_frame), refresh_per_second=6, console=console) as live:
            with Pool(processes=num_workers) as pool:
                # Submit all jobs
                async_results = pool.map_async(_analyze_single_charger_worker, worker_args)
                
                # Monitor progress and update display
                while not async_results.ready():
                    spinner_frame += 1
                    live.update(_create_progress_table(progress_dict, charger_ids, spinner_frame=spinner_frame))
                    time.sleep(0.15)
                
                # Get final results
                results = async_results.get()
                
                # Final update
                live.update(_create_progress_table(progress_dict, charger_ids, spinner_frame=spinner_frame))
        
        # Clear the progress table (as requested by user)
        console.print()
        
        # Process results
        for charger_id, analysis, error in results:
            if error:
                console.print(f"[red]✗ Error analyzing {charger_id}: {error}[/red]")
            elif analysis:
                self.results.append(analysis)
                # Aggregate all results and render a single combined report later
        
        console.print()
    
    def generate_summary_report(self):
        """Generate and display summary report using Reporter"""
        Reporter.generate_summary_report(self.results)


# ========== Parallel Processing Support ==========

def _analyze_single_charger_worker(args):
    """Worker function for parallel charger analysis
    
    This function is designed to be pickable for multiprocessing.
    It creates its own ChargerAnalyzer instance to avoid sharing state.
    
    Args:
        args: Tuple of (folder_path, log_directory, progress_dict, charger_id)
        
    Returns:
        Tuple of (charger_id, analysis_result, error_message)
    """
    folder_path, log_directory, progress_dict, charger_id = args
    
    try:
        # Update progress: starting worker
        progress_dict[charger_id] = {'status': 'Analyzing', 'progress': 5, 'message': 'Starting'}
        
        # Create analyzer instance (each worker needs its own)
        analyzer = ChargerAnalyzer(log_directory)
        
        # Analyze the charger with phase-aware progress callback
        def worker_progress(percent, message=None):
            safe_percent = max(0, min(99, int(percent)))
            progress_dict[charger_id] = {
                'status': 'Analyzing',
                'progress': safe_percent,
                'message': message or 'Analyzing'
            }

        analysis = analyzer.analyze_charger_log(Path(folder_path), progress_callback=worker_progress)
        
        progress_dict[charger_id] = {'status': 'Analyzing', 'progress': 99, 'message': 'Finalizing'}
        
        # Mark as complete
        progress_dict[charger_id] = {'status': 'Complete', 'progress': 100, 'message': 'Completed'}
        
        return (charger_id, analysis, None)
        
    except Exception as e:
        # Mark as failed
        progress_dict[charger_id] = {'status': 'Error', 'progress': 0, 'message': 'Error'}
        return (charger_id, None, str(e))


def _create_progress_table(progress_dict, charger_ids, spinner_frame=0):
    """Create Rich table showing analysis progress
    
    Args:
        progress_dict: Shared dict with progress info
        charger_ids: List of charger IDs to display
        
    Returns:
        Rich Table object
    """
    spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    spinner = spinner_frames[spinner_frame % len(spinner_frames)]

    table = Table(title="Analysis Progress", show_header=True, header_style="bold cyan")
    table.add_column("Charger ID", style="cyan", width=20)
    table.add_column("Status", width=12)
    table.add_column("Phase", width=34)
    table.add_column("Progress", width=30)
    
    for charger_id in charger_ids:
        info = progress_dict.get(charger_id, {'status': 'Queued', 'progress': 0, 'message': ''})
        status = info['status']
        progress = info['progress']
        phase = info.get('message', '')
        
        # Color code status
        if status == 'Complete':
            status_text = "[green]✓ Complete[/green]"
        elif status == 'Error':
            status_text = "[red]✗ Error[/red]"
        elif status == 'Analyzing':
            status_text = f"[yellow]{spinner} Analyzing[/yellow]"
        elif status == 'Extracting':
            status_text = "[blue]📦 Extracting[/blue]"
        else:  # Queued
            status_text = "[dim]⏳ Queued[/dim]"
        
        # Create progress bar
        bar_width = 20
        filled = int(bar_width * progress / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        progress_text = f"[cyan]{bar}[/cyan] {progress}%"
        
        phase_text = phase if phase else '-'
        if len(phase_text) > 32:
            phase_text = phase_text[:29] + '...'

        table.add_row(charger_id, status_text, phase_text, progress_text)
    
    return table


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Analyze EV charger logs for common issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                                    # Extract all ZIPs and analyze in current directory
  %(prog)s -z EV01_before.zip                 # Extract and analyze a specific ZIP file
  %(prog)s -z EV01.zip EV02.zip               # Extract and analyze multiple specific ZIPs
  %(prog)s --skip-extraction                  # Analyze already-extracted logs only
  %(prog)s --directory /path/to/logs          # Use specific directory
  %(prog)s -d /path/to/logs -z EV01.zip       # Analyze specific ZIP in specific directory
        '''
    )
    
    parser.add_argument('-d', '--directory', 
                       help='Directory containing log ZIP files (default: current directory)')
    parser.add_argument('-z', '--zip', nargs='*', metavar='FILE',
                       help='Specific ZIP file(s) to extract and analyze. Can be relative or absolute paths.')
    parser.add_argument('--skip-extraction', action='store_true',
                       help='Skip ZIP extraction, analyze existing folders only')
    
    args = parser.parse_args()
    
    # Print header with rich
    console.print()
    console.rule("[bold cyan]EV CHARGER LOG ANALYSIS TOOL v0.0.7[/bold cyan]", style="cyan")
    console.print("[dim]Automated detection of OCPP protocol violations, billing failures, and hardware faults[/dim]")
    console.print()
    
    # Initialize analyzer
    analyzer = ChargerAnalyzer(args.directory)
    
    console.print(f"[bold]Working Directory:[/bold] {analyzer.log_directory}\n")
    
    # Track which folders to analyze
    folders_to_analyze = None
    
    # Extract ZIPs if not skipped
    if not args.skip_extraction:
        if args.zip is not None:
            # User specified specific zip file(s)
            if len(args.zip) == 0:
                print("Error: --zip requires at least one file argument")
                print("Usage: --zip FILE1.zip [FILE2.zip ...]")
                sys.exit(1)
            folders_to_analyze = analyzer.extract_zips_wrapper(specific_files=args.zip)
        else:
            # Default behavior: extract all zips in directory
            zip_files = list(analyzer.log_directory.glob("*.zip"))
            if zip_files:
                analyzer.extract_zips_wrapper()
    
    # Analyze chargers (specific folders if -z was used, otherwise all)
    analyzer.analyze_all_chargers(specific_folders=folders_to_analyze)
    
    # Generate a single combined report for all analyzed chargers
    if analyzer.results:
        analyzer.generate_summary_report()
    
    console.print("[bold green]✓ Analysis complete![/bold green]\n")


if __name__ == "__main__":
    main()
