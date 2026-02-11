#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hardware fault detection for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Any
from datetime import datetime, timedelta


class HardwareDetector:
    """Detector for hardware-related faults"""
    
    @staticmethod
    def detect_rfid_faults(folder: Path) -> Dict[str, Any]:
        """Detect RFID module (RYRR20I) faults in system logs
        
        RYRR20I is the RFID reader module. Persistent errors indicate hardware failure.
        Common patterns:
        - RYRR20I Register write request fail
        - RYRR20I Set StandBy Mode fail
        - RYRR20I Reset fail
        - RYRR20I_Check_Request] Time Out
        
        High error counts (>100) indicate faulty RFID module requiring charger replacement.
        
        Args:`n            folder: Path to charger log folder`n            `n        Returns:`n            Dict with 'count' (int) and 'examples' (list of str)
        """
        system_log_dir = folder / "Storage" / "SystemLog"
        if not system_log_dir.exists():
            return {'count': 0, 'examples': []}
        
        rfid_error_lines = []
        
        # Check SystemLog and rotations
        system_files = []
        system_base = system_log_dir / "SystemLog"
        if system_base.exists():
            system_files.append(system_base)
        
        for i in range(10):
            rotated = system_log_dir / f"SystemLog.{i}"
            if rotated.exists():
                system_files.append(rotated)
        
        # Search for RYRR20I error patterns
        for sys_file in system_files:
            try:
                with open(sys_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if 'RYRR20I' in line and ('fail' in line.lower() or 'time out' in line.lower()):
                            rfid_error_lines.append(line.strip())
            except Exception as e:
                print(f"  ⚠ Could not read {sys_file.name}: {e}")
        
        return {
            'count': len(rfid_error_lines),
            'examples': rfid_error_lines[:5]  # First 5 examples
        }
    
    @staticmethod
    def _check_ocpp_activity_during_gap(folder: Path, gap_start_month: int, gap_end_month: int) -> bool:
        """Check if OCPP messages were logged during a SystemLog gap.
        
        This helps distinguish between true power loss (no OCPP messages) and
        SystemLog-specific logging failures (OCPP still active).
        
        Args:
            folder: Path to charger log folder
            gap_start_month: Month number when gap started (1-12)
            gap_end_month: Month number when gap ended (1-12)
            
        Returns:
            True if OCPP activity found during gap, False otherwise
        """
        # OCPP logs can be in multiple locations depending on extraction method
        ocpp_dirs_to_check = [
            folder / "Storage" / "OCPP16J_Log",  # Older structure
            folder / "Storage" / "SystemLog",    # Common location (alongside SystemLog files)
            folder  # Root level (some extraction methods)
        ]
        
        ocpp_files = []
        for ocpp_dir in ocpp_dirs_to_check:
            if not ocpp_dir.exists():
                continue
            
            ocpp_base = ocpp_dir / "OCPP16J_Log.csv"
            if ocpp_base.exists():
                ocpp_files.append(ocpp_base)
            
            for i in range(10):
                rotated = ocpp_dir / f"OCPP16J_Log.csv.{i}"
                if rotated.exists():
                    ocpp_files.append(rotated)
        
        if not ocpp_files:
            return False
        
        # Month names for pattern matching
        month_names = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 
                      'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
        
        # Build search pattern for months in gap period
        # Handle year wraparound (e.g., Dec -> Jan)
        search_months = []
        if gap_start_month <= gap_end_month:
            search_months = month_names[gap_start_month-1:gap_end_month]
        else:
            # Year wraparound
            search_months = month_names[gap_start_month-1:] + month_names[:gap_end_month]
        
        month_pattern = '|'.join(search_months)
        try:
            for ocpp_file in ocpp_files:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    # Scan entire file for any matching month
                    # (OCPP logs are typically small, ~3MB each)
                    for line in f:
                        if re.search(rf'^({month_pattern})\s+\d+\s+', line):
                            return True
        except:
            pass
        
        return False
    
    @staticmethod
    def _extract_rtc_corrected_time(log_entries: List[Dict], start_idx: int, max_lookahead: int = 20) -> tuple:
        """Extract the real time from 'Get RTC Info' log line after RTC reset.
        
        When charger reboots after power loss, the RTC may reset to factory default  
        (Jul 20 03:30:XX, Oct 15 04:39:XX, Jan 1 00:00:XX), then get corrected
        by MCU within ~10 seconds via "Get RTC Info: YYYY.MM.DD-HH:MM:SS".
        
        Args:
            log_entries: List of all log entries
            start_idx: Index where suspected RTC reset occurred
            max_lookahead: How many lines ahead to search for RTC correction
            
        Returns:
            Tuple of (real_timestamp_str, real_datetime) if found, else (None, None)
        """
        # Pattern: "Get RTC Info: 2024.08.13-20:40:57"
        rtc_info_pattern = re.compile(r'Get RTC Info:\s*(\d{4})\.(\d{2})\.(\d{2})-(\d{2}):(\d{2}):(\d{2})')
        
        # Search next N entries for RTC correction (inclusive of max_lookahead)
        for offset in range(1, min(max_lookahead + 1, len(log_entries) - start_idx)):
            entry = log_entries[start_idx + offset]
            match = rtc_info_pattern.search(entry['line'])
            if match:
                year, month, day, hour, minute, second = match.groups()
                try:
                    real_dt = datetime(int(year), int(month), int(day), 
                                      int(hour), int(minute), int(second))
                    # Format as "MMM DD HH:MM:SS" to match other timestamps
                    real_str = real_dt.strftime("%b %d %H:%M:%S")
                    return (real_str, real_dt)
                except:
                    pass
        
        return (None, None)
    
    @staticmethod
    def _is_rtc_reset_timestamp(timestamp_str: str) -> bool:
        """Check if timestamp matches known RTC reset default values.
        
        Common RTC reset timestamps observed in Delta AC MAX chargers:
        - Jul 20 03:30:XX (most common - likely firmware build timestamp)
        - Oct 15 04:39:XX (alternative default)
        - Jan 1 00:00:XX (Unix epoch style reset)
        
        Args:
            timestamp_str: Timestamp string in "MMM DD HH:MM:SS" format
            
        Returns:
            True if timestamp matches known RTC reset pattern
        """
        # Jul 20 03:30:XX pattern
        if re.match(r'Jul\s+20\s+03:30:\d{2}', timestamp_str):
            return True
        
        # Oct 15 04:39:XX pattern
        if re.match(r'Oct\s+15\s+04:39:\d{2}', timestamp_str):
            return True
        
        # Jan 1 00:00:XX pattern
        if re.match(r'Jan\s+1\s+00:00:\d{2}', timestamp_str):
            return True
        
        return False
    
    @staticmethod
    def detect_system_reboots(folder: Path) -> Dict[str, Any]:
        """Detect logging gaps, reboots, and power loss events in system logs
        
        Analyzes SystemLog files for:
        - Logging gaps (abrupt stops in log entries)
        - Reboot indicators (System Start, syslogd started)
        - Power loss patterns (RTC reset to Jul 20 2025)
        - Firmware update events (dual-bank switching)
        
        Cross-checks OCPP logs to distinguish between:
        - True power loss (no OCPP activity)
        - SystemLog-specific failures (OCPP still active)
        
        Returns detailed information on each reboot event including:
        - Type (power_loss, firmware_update, systemlog_failure, unknown)
        - Gap duration
        - Timestamps before/after gap
        - Indicators found
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'reboot_count', 'power_loss_count', 'firmware_update_count',
            'systemlog_failure_count', 'max_gap_days', 'events' (list of reboot details)
        """
        system_log_dir = folder / "Storage" / "SystemLog"
        if not system_log_dir.exists():
            return {
                'reboot_count': 0,
                'power_loss_count': 0,
                'firmware_update_count': 0,
                'systemlog_failure_count': 0,
                'max_gap_days': 0,
                'events': []
            }
        
        # Collect all SystemLog files
        system_files = []
        system_base = system_log_dir / "SystemLog"
        if system_base.exists():
            system_files.append(system_base)
        
        for i in range(10):
            rotated = system_log_dir / f"SystemLog.{i}"
            if rotated.exists():
                system_files.append(rotated)
        
        # Parse log entries chronologically
        log_entries = []
        reboot_indicators = ['System Start', 'syslogd started', 'WEB_Reboot_System', 
                            'dual-bank switch', 'Dual-bank switch']
        rtc_reset_pattern = re.compile(r'Jul\s+20\s+2025\s+03:30:\d{2}')
        # Pattern matches: "Dec 21 08:21:43.109" or "Dec 21 08:21:43"
        timestamp_pattern = re.compile(r'^(\w{3}\s+\d+\s+\d{2}:\d{2}:\d{2})\.?\d*\s+')
        
        for sys_file in system_files:
            try:
                with open(sys_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        ts_match = timestamp_pattern.match(line)
                        if ts_match:
                            timestamp_str = ts_match.group(1)
                            log_entries.append({
                                'timestamp_str': timestamp_str,
                                'line': line.strip(),
                                'file': sys_file.name,
                                'line_num': line_num
                            })
            except Exception as e:
                print(f"  ⚠ Could not read {sys_file.name}: {e}")
        
        # Sort entries by log rotation (newer files first, then by line number)
        # SystemLog is newest, SystemLog.0 is older, etc.
        def rotation_key(entry):
            filename = entry['file']
            if filename == 'SystemLog':
                return (0, entry['line_num'])
            elif filename.startswith('SystemLog.'):
                try:
                    rotation = int(filename.split('.')[-1])
                    return (rotation + 1, entry['line_num'])
                except:
                    return (999, entry['line_num'])
            return (999, entry['line_num'])
        
        log_entries.sort(key=rotation_key)
        
        # Detect gaps and reboots
        reboot_events = []
        power_loss_count = 0
        firmware_update_count = 0
        systemlog_failure_count = 0
        max_gap_days = 0
        
        # Track the current year for timestamp parsing (updated when RTC corrections found)
        current_inferred_year = 2025  # Default starting year
        
        # Use a simple date parser (year-less logs require inference)
        def parse_timestamp(ts_str, year=None):
            """Parse 'MMM DD HH:MM:SS' format with specified or default year"""
            try:
                # Use provided year or current inferred year
                use_year = year if year is not None else current_inferred_year
                ts_with_year = f"{ts_str} {use_year}"
                return datetime.strptime(ts_with_year, "%b %d %H:%M:%S %Y")
            except:
                return None
        
        prev_entry = None
        prev_entry_ts = None
        for i, entry in enumerate(log_entries):
            current_ts = parse_timestamp(entry['timestamp_str'])
            if not current_ts:
                continue
            
            # Check for reboot indicators in current line
            is_reboot_line = any(indicator in entry['line'] for indicator in reboot_indicators)
            is_rtc_reset = rtc_reset_pattern.search(entry['line']) is not None
            
            # Check if this timestamp matches RTC reset pattern
            is_rtc_reset_timestamp = HardwareDetector._is_rtc_reset_timestamp(entry['timestamp_str'])
            
            # If RTC reset detected, try to find real time from subsequent RTC correction
            # Note: Don't require is_reboot_line here - RTC reset timestamp alone is sufficient
            real_timestamp_str = None
            real_timestamp_dt = None
            if is_rtc_reset_timestamp:  # Changed: removed "and is_reboot_line" requirement
                real_timestamp_str, real_timestamp_dt = HardwareDetector._extract_rtc_corrected_time(
                    log_entries, i, max_lookahead=20)
                # Update inferred year for future timestamp parsing
                if real_timestamp_dt:
                    current_inferred_year = real_timestamp_dt.year
                else:
                    # RTC reset without correction - skip this entry for gap analysis
                    # We don't know the real timestamp, so can't calculate meaningful gaps
                    continue
            
            # Use corrected timestamp if available, otherwise use parsed timestamp
            effective_ts = real_timestamp_dt if real_timestamp_dt else current_ts
            effective_ts_str = real_timestamp_str if real_timestamp_str else entry['timestamp_str']
            
            # If RTC was corrected, we need to also fix prev_entry_ts year to match
            # (prev entries may have used wrong year before RTC correction)
            corrected_prev_ts = prev_entry_ts
            corrected_prev_ts_str = prev_entry['timestamp_str'] if prev_entry else None
            
            if prev_entry_ts and real_timestamp_dt and prev_entry_ts.year != real_timestamp_dt.year:
                # Adjust prev_entry year to match corrected year
                corrected_prev_ts = prev_entry_ts.replace(year=real_timestamp_dt.year)
                # Also create corrected timestamp string for display
                corrected_prev_ts_str = corrected_prev_ts.strftime('%b %d %H:%M:%S')
            
            # Check for logging gap since last entry
            if prev_entry and (corrected_prev_ts or prev_entry_ts):
                time_diff = effective_ts - (corrected_prev_ts if corrected_prev_ts else prev_entry_ts)
                gap_hours = time_diff.total_seconds() / 3600
                gap_days = time_diff.total_seconds() / 86400
                
                # Filter criteria:
                # 1. Minimum gap: 2 hours (avoid normal quiet periods)
                # 2. Maximum gap: 30 days (avoid year inference errors in rotated logs)
                # 3. For reboot indicators without gap: require >0.01 hours (36 seconds)
                
                significant_gap = gap_hours > 2 and gap_days < 30
                reboot_with_gap = is_reboot_line and gap_hours > 0.01 and gap_days < 30
                
                # Detect significant gap or reboot indicator with gap
                if significant_gap or reboot_with_gap:
                    max_gap_days = max(max_gap_days, gap_days)
                    
                    # Determine reboot type
                    reboot_type = 'unknown'
                    evidence = []
                    
                    # If RTC was reset and corrected, this is likely a power loss event
                    # Only count if actual gap is significant (>= 3 minutes)
                    if is_rtc_reset_timestamp and real_timestamp_dt:
                        if gap_hours >= 0.05:  # 3 minutes minimum
                            reboot_type = 'power_loss'
                            evidence.append(f'RTC reset detected (was {entry["timestamp_str"]}, corrected to {real_timestamp_str})')
                            evidence.append(f'Actual gap: {gap_hours:.1f} hours')
                            power_loss_count += 1
                        else:
                            # Skip - RTC correction during boot, not meaningful power loss
                            continue
                    elif is_rtc_reset:
                        reboot_type = 'power_loss'
                        evidence.append('RTC reset to Jul 20 2025')
                        power_loss_count += 1
                    elif 'dual-bank switch' in entry['line'].lower() or 'Dual-bank switch' in entry['line']:
                        reboot_type = 'firmware_update'
                        evidence.append('Dual-bank firmware switch detected')
                        firmware_update_count += 1
                    elif gap_hours > 24:
                        # Long gap - check OCPP logs to distinguish power loss from SystemLog failure
                        # Use EFFECTIVE timestamps for OCPP checking
                        month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
                        
                        # Use effective timestamps (RTC-corrected if available)
                        prev_month = month_map.get(prev_entry['timestamp_str'].split()[0], 1)
                        curr_month = month_map.get(effective_ts_str.split()[0], 1)
                        
                        has_ocpp_activity = HardwareDetector._check_ocpp_activity_during_gap(
                            folder, prev_month, curr_month)
                        
                        if has_ocpp_activity:
                            reboot_type = 'systemlog_failure'
                            evidence.append(f'SystemLog gap ({gap_days:.1f} days) but OCPP still active')
                            evidence.append('Charger was powered and operational')
                            systemlog_failure_count += 1
                        else:
                            reboot_type = 'power_loss'
                            evidence.append(f'Long gap ({gap_days:.1f} days) suggests power loss')
                            power_loss_count += 1
                    elif is_reboot_line:
                        evidence.append('Reboot indicator found')
                        if gap_hours < 0.1:  # Very short gap = controlled reboot
                            reboot_type = 'firmware_update'
                            firmware_update_count += 1
                        else:
                            reboot_type = 'power_loss'
                            power_loss_count += 1
                    
                    reboot_events.append({
                        'type': reboot_type,
                        'gap_days': round(gap_days, 2),
                        'gap_hours': round(gap_hours, 2),
                        'last_timestamp': corrected_prev_ts_str if corrected_prev_ts_str else prev_entry['timestamp_str'],
                        'last_line': prev_entry['line'][:100],  # Truncate for readability
                        'first_timestamp': effective_ts_str,  # Use corrected timestamp if available
                        'first_line': entry['line'][:100],
                        'evidence': evidence,
                        'file_transition': f"{prev_entry['file']} → {entry['file']}"
                    })
            
            # Update prev_entry for next iteration
            # If timestamp was RTC-corrected, use corrected string
            prev_entry = entry
            if effective_ts_str != entry['timestamp_str']:
                # RTC was corrected, store corrected timestamp
                prev_entry = entry.copy()
                prev_entry['timestamp_str'] = effective_ts_str
            prev_entry_ts = effective_ts  # Use corrected timestamp for next iteration
        
        return {
            'reboot_count': len(reboot_events),
            'power_loss_count': power_loss_count,
            'firmware_update_count': firmware_update_count,
            'systemlog_failure_count': systemlog_failure_count,
            'max_gap_days': round(max_gap_days, 2),
            'events': reboot_events
        }
