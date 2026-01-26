#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Event detection and parsing for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any
from ..error_codes import ERROR_CODES


class EventDetector:
    """Detector for event codes and related log context"""
    
    @staticmethod
    def parse_events(folder: Path) -> List[Dict[str, Any]]:
        """Parse Events CSV files from EventLog folder
        
        Args:
            folder: Path to the extracted charger log folder
            
        Returns:
            List of event dictionaries with timestamp, code, and details
        """
        events = []
        event_log_dir = folder / "Storage" / "EventLog"
        
        if not event_log_dir.exists():
            return events
        
        # Find all Events CSV files
        event_files = list(event_log_dir.glob("*_Events.csv"))
        
        for event_file in event_files:
            try:
                with open(event_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        
                        # Format: YYYY.MM.DD HH:MM:SS-CODE
                        match = re.match(r'([\d\.\s:]+)-([\w\d]+)', line)
                        if match:
                            timestamp = match.group(1).strip()
                            code = match.group(2)
                            
                            # Check if it's a recovery code (starts with 1) or error code (EV)
                            is_recovery = code.isdigit() and code.startswith('1')
                            
                            event = {
                                'timestamp': timestamp,
                                'code': code,
                                'is_recovery': is_recovery,
                                'file': event_file.name
                            }
                            
                            # Add error details if we have them
                            if code in ERROR_CODES:
                                event.update(ERROR_CODES[code])
                            
                            events.append(event)
            except Exception as e:
                print(f"  ⚠ Could not parse {event_file.name}: {e}")
        
        return events
    
    @staticmethod
    def get_log_context(folder: Path, event_timestamp: str, window_minutes: int = 5) -> Dict[str, List[str]]:
        """Get log entries around a specific timestamp for context
        
        Args:
            folder: Path to the extracted charger log folder
            event_timestamp: Timestamp string in format 'YYYY.MM.DD HH:MM:SS'
            window_minutes: Minutes before/after to search (default: 5)
            
        Returns:
            Dictionary with context from different log sources
        """
        context = {
            'system_log': [],
            'ocpp_log': []
        }
        
        try:
            # Parse the event timestamp
            dt = datetime.strptime(event_timestamp, '%Y.%m.%d %H:%M:%S')
            
            # Define search window
            start_time = dt - timedelta(minutes=window_minutes)
            end_time = dt + timedelta(minutes=window_minutes)
            
            # Search SystemLog
            system_log = folder / "Storage" / "SystemLog" / "SystemLog"
            if system_log.exists():
                with open(system_log, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Try to parse syslog timestamp (e.g., "Oct 24 13:59:42")
                        # Convert event month to syslog format
                        month_map = {
                            '01': 'Jan', '02': 'Feb', '03': 'Mar', '04': 'Apr',
                            '05': 'May', '06': 'Jun', '07': 'Jul', '08': 'Aug',
                            '09': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
                        }
                        
                        # Look for lines with timestamps matching our window
                        month_abbr = month_map.get(event_timestamp.split('.')[1])
                        day = event_timestamp.split('.')[2].split()[0]
                        
                        # Simple check: if line starts with the right month and day
                        if line.startswith(f"{month_abbr} {int(day)}"):
                            # Extract time from line (format: "Mon DD HH:MM:SS")
                            match = re.match(r'(\w+)\s+(\d+)\s+(\d+):(\d+):(\d+)', line)
                            if match:
                                log_month, log_day, log_hour, log_min, log_sec = match.groups()
                                # Create comparable datetime (use event year)
                                try:
                                    log_dt = datetime(dt.year, list(month_map.keys()).index(log_month) + 1,
                                                     int(log_day), int(log_hour), int(log_min), int(log_sec))
                                    
                                    if start_time <= log_dt <= end_time:
                                        context['system_log'].append(line.strip())
                                except:
                                    pass
            
            # Search OCPP Log
            ocpp_log = folder / "Storage" / "SystemLog" / "OCPP16J_Log.csv"
            if ocpp_log.exists():
                with open(ocpp_log, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # OCPP logs may have different timestamp format - look for date match
                        if event_timestamp[:10] in line:  # Match YYYY.MM.DD
                            context['ocpp_log'].append(line.strip())
            
        except Exception as e:
            # Silently fail - context is optional
            pass
        
        return context
    
    @staticmethod
    def get_chargebox_id(folder: Path) -> str:
        """Extract ChargBox ID from Config/evcs file
        
        Args:
            folder: Path to the extracted charger log folder
            
        Returns:
            ChargBox ID string, or None if not found
        """
        evcs_file = folder / "Config" / "evcs"
        
        if not evcs_file.exists():
            return None
        
        try:
            with open(evcs_file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for: option pu8ChgBoxID 'VALUE'
                match = re.search(r"option\s+pu8ChgBoxID\s+'([^']+)'", content)
                if match:
                    return match.group(1)
        except Exception as e:
            print(f"  ⚠ Could not read ChargBox ID from {evcs_file}: {e}")
        
        return None

