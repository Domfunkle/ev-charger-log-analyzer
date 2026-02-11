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
from pathlib import Path
from multiprocessing import Pool, Manager, cpu_count
from rich.console import Console
from rich.progress import track
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
import time

console = Console()

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
    
    def extract_zips_wrapper(self, specific_files=None):
        """Wrapper for extract_zips utility function
        
        Returns:
            List of Path objects for extracted folders
        """
        return extract_zips(self.log_directory, specific_files)
    
    def analyze_charger_log(self, folder):
        """Analyze a single charger log folder"""
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
            'mcu_errors': 0,
            'mcu_error_examples': [],
            'error_count': 0,
            'logging_gaps': [],
            'issues': [],
            'status': 'Clean',
            'log_file': str(system_log),
            'events': [],
            'critical_events': [],
            'charging_profile_timeouts': {'count': 0, 'examples': []},
            'ocpp_rejections': {'total': 0, 'by_type': {}, 'examples': []},
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
        events = self.event_detector.parse_events(folder)
        analysis['events'] = events
        
        analysis['charging_profile_timeouts'] = self.ocpp_detector.detect_charging_profile_timeouts(folder)
        analysis['ocpp_rejections'] = self.ocpp_detector.detect_ocpp_rejections(folder)
        analysis['ng_flags'] = self.ocpp_detector.detect_ng_flags(folder)
        analysis['ocpp_timeouts'] = self.ocpp_detector.detect_ocpp_timeouts(folder)
        analysis['rfid_faults'] = self.hardware_detector.detect_rfid_faults(folder)
        analysis['system_reboots'] = self.hardware_detector.detect_system_reboots(folder)
        analysis['low_current_profiles'] = self.ocpp_detector.detect_low_current_profiles(folder)
        analysis['lms_issues'] = self.lms_detector.detect_lms_issues(folder, self.event_detector.parse_events)
        analysis['modbus_config'] = self.lms_detector.detect_modbus_config_issues(folder)
        analysis['state_transitions'] = self.state_detector.parse_ocpp_state_transitions(folder)
        
        # Phase 1: Critical OCPP detectors (data loss prevention)
        analysis['lost_transaction_id'] = self.ocpp_transaction_detector.detect_lost_transaction_id(folder)
        analysis['hard_reset_data_loss'] = self.ocpp_transaction_detector.detect_hard_reset_data_loss(folder)
        analysis['meter_register_tracking'] = self.ocpp_transaction_detector.detect_meter_register_tracking(folder)
        
        # Informational: Firmware update tracking
        analysis['firmware_updates'] = self.firmware_detector.detect_firmware_updates(folder)
        
        # Parse RTC syncs for accurate year inference
        rtc_syncs = self._parse_rtc_syncs(folder)
        
        # Identify critical events
        critical_codes = ['EV0081', 'EV0082', 'EV0083', 'EV0084', 'EV0085', 'EV0086', 'EV0087',
                         'EV0088', 'EV0089', 'EV0090', 'EV0091', 'EV0092', 'EV0093', 'EV0094',
                         'EV0095', 'EV0096', 'EV0097', 'EV0098', 'EV0099', 'EV0100', 'EV0101',
                         'EV0110', 'EV0114', 'EV0115', 'EV0116']
        critical_events = [e for e in events if e['code'] in critical_codes]
        
        # Get firmware history for correlation
        fw_history = analysis['firmware_updates'].get('firmware_history', [])
        
        # Add log context and firmware version for each critical event
        for event in critical_events:
            context = self.event_detector.get_log_context(folder, event['timestamp'], window_minutes=5)
            event['context'] = context
            
            # Determine which firmware version was active when this event occurred
            # Now using RTC syncs for accurate year inference
            event['firmware_at_event'] = self._get_firmware_at_timestamp(event['timestamp'], fw_history, rtc_syncs)
        
        analysis['critical_events'] = critical_events
        
        # Parse system log for baseline metrics
        try:
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
            
            if analysis['hard_reset_data_loss']['incomplete_transactions'] > 0:
                analysis['issues'].append(f"🔴 CRITICAL: Hard reset data loss: {analysis['hard_reset_data_loss']['incomplete_transactions']} incomplete transactions")
                analysis['status'] = 'Issue'
            
            if analysis['meter_register_tracking']['non_cumulative_count'] > 0:
                analysis['issues'].append(f"⚠️ Meter register issue: {analysis['meter_register_tracking']['non_cumulative_count']} non-cumulative transactions (audit failure)")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
        
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
            for folder in track(folders, description="[cyan]Analyzing chargers..."):
                analysis = self.analyze_charger_log(folder)
                if analysis:
                    self.results.append(analysis)
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
            progress_dict[charger_id] = {'status': 'Queued', 'progress': 0}
        
        # Prepare worker arguments
        worker_args = [
            (str(folder), str(self.log_directory), progress_dict, charger_id)
            for folder, charger_id in zip(folders, charger_ids)
        ]
        
        # Start parallel processing with live progress display
        results_map = {}
        
        with Live(_create_progress_table(progress_dict, charger_ids), refresh_per_second=2, console=console) as live:
            with Pool(processes=num_workers) as pool:
                # Submit all jobs
                async_results = pool.map_async(_analyze_single_charger_worker, worker_args)
                
                # Monitor progress and update display
                while not async_results.ready():
                    live.update(_create_progress_table(progress_dict, charger_ids))
                    time.sleep(0.5)
                
                # Get final results
                results = async_results.get()
                
                # Final update
                live.update(_create_progress_table(progress_dict, charger_ids))
        
        # Clear the progress table (as requested by user)
        console.print()
        
        # Process results
        for charger_id, analysis, error in results:
            if error:
                console.print(f"[red]✗ Error analyzing {charger_id}: {error}[/red]")
            elif analysis:
                self.results.append(analysis)
                # Display results immediately as they complete
                Reporter.generate_summary_report([analysis])
                console.print()
        
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
        # Update progress: Analyzing
        progress_dict[charger_id] = {'status': 'Analyzing', 'progress': 30}
        
        # Create analyzer instance (each worker needs its own)
        analyzer = ChargerAnalyzer(log_directory)
        
        # Analyze the charger
        progress_dict[charger_id] = {'status': 'Analyzing', 'progress': 50}
        analysis = analyzer.analyze_charger_log(Path(folder_path))
        
        progress_dict[charger_id] = {'status': 'Analyzing', 'progress': 90}
        
        # Mark as complete
        progress_dict[charger_id] = {'status': 'Complete', 'progress': 100}
        
        return (charger_id, analysis, None)
        
    except Exception as e:
        # Mark as failed
        progress_dict[charger_id] = {'status': 'Error', 'progress': 0}
        return (charger_id, None, str(e))


def _create_progress_table(progress_dict, charger_ids):
    """Create Rich table showing analysis progress
    
    Args:
        progress_dict: Shared dict with progress info
        charger_ids: List of charger IDs to display
        
    Returns:
        Rich Table object
    """
    table = Table(title="Analysis Progress", show_header=True, header_style="bold cyan")
    table.add_column("Charger ID", style="cyan", width=20)
    table.add_column("Status", width=12)
    table.add_column("Progress", width=30)
    
    for charger_id in charger_ids:
        info = progress_dict.get(charger_id, {'status': 'Queued', 'progress': 0})
        status = info['status']
        progress = info['progress']
        
        # Color code status
        if status == 'Complete':
            status_text = "[green]✓ Complete[/green]"
        elif status == 'Error':
            status_text = "[red]✗ Error[/red]"
        elif status == 'Analyzing':
            status_text = "[yellow]⚙ Analyzing[/yellow]"
        elif status == 'Extracting':
            status_text = "[blue]📦 Extracting[/blue]"
        else:  # Queued
            status_text = "[dim]⏳ Queued[/dim]"
        
        # Create progress bar
        bar_width = 20
        filled = int(bar_width * progress / 100)
        bar = "█" * filled + "░" * (bar_width - filled)
        progress_text = f"[cyan]{bar}[/cyan] {progress}%"
        
        table.add_row(charger_id, status_text, progress_text)
    
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
    
    # For single charger analysis, generate combined report
    # (Parallel analysis already displays results as they complete)
    if len(analyzer.results) == 1 or (folders_to_analyze and len(folders_to_analyze) == 1):
        analyzer.generate_summary_report()
    
    console.print("[bold green]✓ Analysis complete![/bold green]\n")


if __name__ == "__main__":
    main()
