#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Firmware tracking and version detection for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Any
from collections import OrderedDict
from datetime import datetime


class FirmwareDetector:
    """Detector for firmware version tracking and update events"""
    
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
    def detect_firmware_updates(folder: Path) -> Dict[str, Any]:
        """Detect firmware version changes (informational tracking)
        
        Tracks firmware updates to help troubleshoot:
        - Whether firmware update succeeded
        - What versions were involved
        - When updates occurred
        - MCU firmware updates
        
        This is INFO level (not ERROR) - firmware updates are normal operations.
        Useful for correlating issues with recent firmware changes.
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with firmware history, update count, latest versions
        """
        system_log_dir = folder / "Storage" / "SystemLog"
        if not system_log_dir.exists():
            return {
                'update_count': 0,
                'firmware_history': [],
                'current_firmware': None,
                'previous_firmware': None,
                'mcu_firmware': None
            }
        
        # Collect all SystemLog files (main + rotated .0, .1, .2, etc.)
        system_log_files = []
        main_log = system_log_dir / "SystemLog"
        if main_log.exists():
            system_log_files.append(main_log)
        
        # Add rotated logs
        for i in range(10):  # Check .0 through .9
            rotated_log = system_log_dir / f"SystemLog.{i}"
            if rotated_log.exists():
                system_log_files.append(rotated_log)
        
        if not system_log_files:
            return {
                'update_count': 0,
                'firmware_history': [],
                'current_firmware': None,
                'previous_firmware': None,
                'mcu_firmware': None
            }
        
        # Parse RTC syncs first to build year timeline
        rtc_syncs = []
        month_map = {
            'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
            'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
        }
        
        for log_file in reversed(system_log_files):
            try:
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        if 'Get RTC Info:' in line:
                            # Extract log timestamp and RTC timestamp
                            log_match = re.match(r'(\w+)\s+(\d+)\s+(\d+):(\d+):(\d+)', line)
                            rtc_match = re.search(r'Get RTC Info:\s*(\d{4})\.(\d{2})\.(\d{2})-(\d{2}):(\d{2}):(\d{2})', line)
                            
                            if log_match and rtc_match:
                                log_month = month_map.get(log_match.group(1))
                                log_day = int(log_match.group(2))
                                rtc_year = int(rtc_match.group(1))
                                
                                # Skip invalid years (2000 indicates RTC not synced yet)
                                if rtc_year < 2020 or rtc_year > 2030:
                                    continue
                                
                                rtc_syncs.append({
                                    'log_month': log_month,
                                    'log_day': log_day,
                                    'actual_year': rtc_year
                                })
            except:
                continue
        
        firmware_versions = OrderedDict()  # timestamp -> (version, year)
        mcu_versions = OrderedDict()  # timestamp -> MCU version
        update_events = []
        
        try:
            # Process all log files (oldest rotated logs first for chronological order)
            for log_file in reversed(system_log_files):
                last_rtc_sync_time = None  # Track when RTC was last synced
                
                with open(log_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Extract timestamp
                        timestamp_match = re.match(r'(\w+) +(\d+) (\d+:\d+:\d+)', line)
                        if timestamp_match:
                            month_name = timestamp_match.group(1)
                            day = int(timestamp_match.group(2))
                            time = timestamp_match.group(3)
                            timestamp = f"{month_name} {day} {time}"
                            
                            # Check if this is an RTC sync
                            if 'Get RTC Info:' in line:
                                rtc_match = re.search(r'Get RTC Info:\s*(\d{4})\.(\d{2})\.(\d{2})', line)
                                if rtc_match:
                                    rtc_year = int(rtc_match.group(1))
                                    if 2020 <= rtc_year <= 2030:  # Valid year
                                        last_rtc_sync_time = timestamp
                            
                            # Infer year from RTC syncs
                            month = month_map.get(month_name, 1)
                            year = FirmwareDetector._infer_year_from_rtc_static(month, day, rtc_syncs)
                            
                            # Track Fw2Ver (application firmware) - only if RTC synced recently
                            fw2_match = re.search(r'Fw2Ver:\s*([\d\.]+)', line)
                            if fw2_match and last_rtc_sync_time:
                                version = fw2_match.group(1)
                                firmware_versions[timestamp] = (version, year)
                            
                            # Track Fw1Ver (MCU firmware)
                            fw1_match = re.search(r'Get Fw1Ver:\s*([\d\.]+)', line)
                            if fw1_match:
                                mcu_version = fw1_match.group(1)
                                mcu_versions[timestamp] = mcu_version
                            
                            # Detect firmware update process
                            if 'EVCS_UnpackZipFW' in line and 'ACMAX_FW' in line:
                                fw_match = re.search(r'ACMAX_FW_v([\d\.]+)', line)
                                if fw_match:
                                    update_events.append({
                                        'timestamp': f"{year} {timestamp}",
                                        'target_version': fw_match.group(1),
                                        'type': 'Firmware Update Initiated'
                                    })
                            
                            if 'WEB_Reboot_System.*Update system done' in line or \
                               'Update system done, reboot system now' in line:
                                update_events.append({
                                    'timestamp': f"{year} {timestamp}",
                                    'type': 'Firmware Update Completed - Rebooting'
                                })
        
        except Exception as e:
            print(f"  ⚠ Could not parse firmware versions: {e}")
        
        # Build firmware history (track version changes)
        # First, convert to list with datetime objects for proper sorting
        firmware_entries = []
        for timestamp, (version, year) in firmware_versions.items():
            # Parse timestamp to datetime for sorting
            try:
                parts = timestamp.split()
                if len(parts) >= 3:
                    month = month_map.get(parts[0], 1)
                    day = int(parts[1])
                    time_parts = parts[2].split(':')
                    hour = int(time_parts[0])
                    minute = int(time_parts[1])
                    second = int(time_parts[2])
                    
                    dt = datetime(year, month, day, hour, minute, second)
                    firmware_entries.append({
                        'datetime': dt,
                        'timestamp': f"{year} {timestamp}",
                        'version': version
                    })
            except:
                continue
        
        # Sort by actual datetime
        firmware_entries.sort(key=lambda x: x['datetime'])
        
        # Build chronological history with version changes
        firmware_history = []
        prev_version = None
        for entry in firmware_entries:
            if entry['version'] != prev_version:
                firmware_history.append({
                    'timestamp': entry['timestamp'],
                    'version': entry['version'],
                    'change': 'Initial' if prev_version is None else f'Updated from {prev_version} to {entry["version"]}'
                })
                prev_version = entry['version']
        
        # Determine current and previous firmware
        firmware_list = [(v, y) for v, y in firmware_versions.values()]
        current_firmware = firmware_list[-1][0] if firmware_list else None
        previous_firmware = firmware_list[-2][0] if len(firmware_list) > 1 else None
        
        # Get latest MCU firmware
        mcu_list = list(mcu_versions.values())
        mcu_firmware = mcu_list[-1] if mcu_list else None
        
        # Count actual firmware changes (not just boot log entries)
        update_count = len(firmware_history) - 1 if len(firmware_history) > 1 else 0
        
        return {
            'update_count': update_count,
            'firmware_history': firmware_history,
            'current_firmware': current_firmware,
            'previous_firmware': previous_firmware,
            'mcu_firmware': mcu_firmware,
            'update_events': update_events
        }
