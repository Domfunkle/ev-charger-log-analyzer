#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for charger model detection in analyzer."""

from __future__ import annotations
import shutil
import tempfile
import unittest
from pathlib import Path

from analyzers.delta_ac_max.analyze import ChargerAnalyzer


class TestModelDetection(unittest.TestCase):
    """Validate folder-layout based charger model detection."""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())
        self.analyzer = ChargerAnalyzer(log_directory=self.test_dir)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_detect_delta_ac_max_layout(self):
        folder = self.test_dir / "[2026.01.01-00.00]KKB000000000001"
        (folder / "Storage" / "EventLog").mkdir(parents=True)
        (folder / "Storage" / "SystemLog").mkdir(parents=True)
        (folder / "Storage" / "SystemLog" / "SystemLog").write_text("Jan 1 00:00:00 Test\n", encoding="utf-8")

        model, evidence = self.analyzer.detect_charger_model(folder)

        self.assertEqual(model, "delta_ac_max")
        self.assertTrue(any("Storage/EventLog" in item for item in evidence))

    def test_detect_wallbox_25kw_layout(self):
        folder = self.test_dir / "[2024.06.24-00.43]APG223100203W0"
        (folder / "Storage" / "Events").mkdir(parents=True)
        (folder / "Storage" / "SystemLog").mkdir(parents=True)
        (folder / "Storage" / "SystemLog" / "[2024.06]SystemLog").write_text("2024.06.01 00:00:00 - test\n", encoding="utf-8")
        (folder / "Storage" / "SystemLog" / "[2024.06]OCPP16J_Log.csv").write_text("2024.06.01 00:00:00-test\n", encoding="utf-8")

        model, evidence = self.analyzer.detect_charger_model(folder)

        self.assertEqual(model, "delta_wallbox_25kw_dc")
        self.assertTrue(any("Storage/Events" in item for item in evidence))

    def test_detect_unknown_layout(self):
        folder = self.test_dir / "[2024.01.01-00.00]UNKNOWN"
        (folder / "Storage" / "Misc").mkdir(parents=True)

        model, _ = self.analyzer.detect_charger_model(folder)

        self.assertEqual(model, "unknown")


if __name__ == '__main__':
    unittest.main()
