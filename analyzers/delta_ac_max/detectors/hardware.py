#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hardware fault detection for Delta AC MAX charger logs
"""

from __future__ import annotations
import re
from pathlib import Path
from typing import Dict, List, Any


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

