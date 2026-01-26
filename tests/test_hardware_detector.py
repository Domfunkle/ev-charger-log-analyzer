#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Unit tests for Hardware detector module
"""

from __future__ import annotations
import unittest
from pathlib import Path
import tempfile
import shutil
from analyzers.delta_ac_max.detectors.hardware import HardwareDetector


class TestHardwareDetector(unittest.TestCase):
    """Test cases for HardwareDetector class"""
    
    def setUp(self):
        """Create temporary test directory and fixture files"""
        self.test_dir = Path(tempfile.mkdtemp())
        self.storage_dir = self.test_dir / "Storage" / "SystemLog"
        self.storage_dir.mkdir(parents=True)
    
    def tearDown(self):
        """Clean up temporary test directory"""
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
    
    def test_detect_rfid_faults_multiple_errors(self):
        """Test detection of multiple RFID errors indicating hardware fault"""
        system_log = self.storage_dir / "SystemLog"
        system_log.write_text(
            "Jan 10 12:00:00 [Error] RYRR20I Register write request fail\n"
            "Jan 10 12:00:05 [Error] RYRR20I Set StandBy Mode fail\n"
            "Jan 10 12:00:10 [Error] RYRR20I Reset fail\n"
            "Jan 10 12:00:15 [Error] [RYRR20I_Check_Request] Time Out\n"
        )
        
        result = HardwareDetector.detect_rfid_faults(self.test_dir)
        
        self.assertEqual(result['count'], 4, "Should detect 4 RFID errors")
        self.assertEqual(len(result['examples']), 4, "Should have 4 examples")
    
    def test_detect_rfid_faults_no_errors(self):
        """Test when no RFID errors are present"""
        system_log = self.storage_dir / "SystemLog"
        system_log.write_text(
            "Jan 10 12:00:00 [Info] Normal operation\n"
            "Jan 10 12:00:05 [Info] Charging session started\n"
        )
        
        result = HardwareDetector.detect_rfid_faults(self.test_dir)
        
        self.assertEqual(result['count'], 0, "Should detect 0 RFID errors")
        self.assertEqual(len(result['examples']), 0)
    
    def test_detect_rfid_faults_rotated_logs(self):
        """Test detection across rotated log files"""
        system_log = self.storage_dir / "SystemLog"
        system_log.write_text("Jan 12 10:00:00 [Error] RYRR20I Register write request fail\n")
        
        rotated_log = self.storage_dir / "SystemLog.0"
        rotated_log.write_text("Jan 11 08:00:00 [Error] RYRR20I Set StandBy Mode fail\n")
        
        result = HardwareDetector.detect_rfid_faults(self.test_dir)
        
        self.assertEqual(result['count'], 2, "Should detect errors from both main and rotated logs")
    
    def test_missing_log_directory(self):
        """Test behavior when log directory doesn't exist"""
        non_existent = Path("/nonexistent/path")
        
        result = HardwareDetector.detect_rfid_faults(non_existent)
        
        self.assertEqual(result['count'], 0)
        self.assertEqual(len(result['examples']), 0)


if __name__ == '__main__':
    unittest.main()
