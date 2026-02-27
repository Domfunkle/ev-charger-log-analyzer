#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Unit tests for connectivity event summary in analyzer."""

from __future__ import annotations
import unittest

try:
    from analyzers.delta_ac_max.analyze import ChargerAnalyzer
except Exception:
    ChargerAnalyzer = None


class TestAnalyzeConnectivity(unittest.TestCase):
    """Test connectivity event aggregation logic."""

    @unittest.skipIf(ChargerAnalyzer is None, "Analyzer dependencies not available in test environment")
    def test_summarize_connectivity_events_fault_and_recovery(self):
        analyzer = ChargerAnalyzer(log_directory='.')
        events = [
            {'timestamp': '2026.02.01 05:05:24', 'code': 'EV0117'},
            {'timestamp': '2026.02.01 05:05:29', 'code': '111002'},
            {'timestamp': '2026.02.06 01:23:14', 'code': 'EV0120'},
            {'timestamp': '2026.02.06 01:24:49', 'code': '111005'},
            {'timestamp': '2026.02.06 01:24:50', 'code': 'EV0082'},  # Non-connectivity
        ]

        summary = analyzer._summarize_connectivity_events(events)

        self.assertEqual(summary['fault_total'], 2)
        self.assertEqual(summary['recovery_total'], 2)
        self.assertEqual(summary['total'], 4)
        self.assertEqual(summary['fault_by_code'].get('EV0117', 0), 1)
        self.assertEqual(summary['fault_by_code'].get('EV0120', 0), 1)
        self.assertEqual(summary['recovery_by_code'].get('111002', 0), 1)
        self.assertEqual(summary['recovery_by_code'].get('111005', 0), 1)
        self.assertIn('Backend Disconnect (Ethernet)', summary['fault_by_type'])
        self.assertIn('Internet Not OK (Ethernet)', summary['fault_by_type'])


if __name__ == '__main__':
    unittest.main()
