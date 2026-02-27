#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for generalized event lead-up analysis."""

from __future__ import annotations
import unittest
from datetime import datetime

try:
    from analyzers.delta_ac_max.analyze import ChargerAnalyzer
except Exception:
    ChargerAnalyzer = None


class TestEventLeadup(unittest.TestCase):
    """Test generalized lead-up context marker aggregation."""

    @unittest.skipIf(ChargerAnalyzer is None, "Analyzer dependencies not available in test environment")
    def test_analyze_leadup_context_detects_markers(self):
        analyzer = ChargerAnalyzer(log_directory='.')

        entries = [
            (datetime(2026, 2, 1, 10, 0, 5), 'Schedule function suspend charging'),
            (datetime(2026, 2, 1, 10, 0, 20), '[IntComm] Write Date Time:'),
            (datetime(2026, 2, 1, 10, 0, 35), '[WiFi] Trigger WiFi STA Scan Action'),
            (datetime(2026, 2, 1, 10, 0, 55), '[WiFi] Scan AP number is -1'),
        ]
        event_points = [
            {
                'timestamp': datetime(2026, 2, 1, 10, 1, 0),
                'label': 'test_event',
                'line': 'Backend connection fail'
            }
        ]

        summary = analyzer._analyze_leadup_context(entries, event_points, window_seconds=60)

        self.assertEqual(summary['event_count'], 1)
        self.assertEqual(summary['marker_counts'].get('suspend_charging', 0), 1)
        self.assertEqual(summary['marker_counts'].get('intcomm_write_time', 0), 1)
        self.assertEqual(summary['marker_counts'].get('wifi_scan_trigger', 0), 1)
        self.assertEqual(summary['marker_counts'].get('wifi_scan_no_ap', 0), 1)
        self.assertEqual(summary['marker_rates'].get('suspend_charging', 0.0), 100.0)
        self.assertTrue(summary.get('samples'))


if __name__ == '__main__':
    unittest.main()
