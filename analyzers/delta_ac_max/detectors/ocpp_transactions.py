#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
OCPP transaction and billing detection for Delta AC MAX charger logs

Detects critical data loss patterns related to OCPP transactions:
- Lost transaction IDs (StartTransaction timeout)
- Hard reset data loss (incomplete transactions)
- Meter register tracking (billing accuracy)
"""

from __future__ import annotations
import re
import json
from pathlib import Path
from typing import Dict, List, Any


class OcppTransactionDetector:
    """Detector for OCPP transaction and billing issues"""
    
    
    @staticmethod
    def detect_lost_transaction_id(folder: Path) -> Dict[str, Any]:
        """Detect lost transactionId from StartTransaction timeouts
        
        CRITICAL PATTERN: When StartTransaction.req is sent but .conf never received,
        charger has no transactionId. Results in:
        - MeterValues sent with transactionId=-1 or 0
        - StopTransaction corrupted
        - Complete billing failure
        
        From OCPP 1.6 Errata Section 3.18: Common backend timeout issue.
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'lost_transaction_count', 'invalid_transaction_ids', 'examples'
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {'lost_transaction_count': 0, 'invalid_transaction_ids': 0, 'examples': []}
        
        # Track message IDs for CALL/CALLRESULT pairing
        pending_start_transactions: Dict[str, str] = {}  # msgId -> timestamp
        lost_transactions = []
        invalid_transaction_ids = 0
        
        # Get all OCPP log files
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        for i in range(10):
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        # Parse OCPP16J messages
        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Extract timestamp
                        timestamp_match = re.match(r'(\w+ +\d+ \d+:\d+:\d+\.\d+)', line)
                        timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                        
                        # OCPP-J format: [MessageType, MessageId, ...]
                        # MessageType: 2=CALL, 3=CALLRESULT, 4=CALLERROR
                        
                        # Look for StartTransaction CALL [2, "msgId", "StartTransaction", {...}]
                        start_call_match = re.search(r'\[2,\s*"([^"]+)",\s*"StartTransaction"', line)
                        if start_call_match:
                            msg_id = start_call_match.group(1)
                            pending_start_transactions[msg_id] = timestamp
                        
                        # Look for StartTransaction CALLRESULT [3, "msgId", {...}]
                        # Must contain "transactionId" field
                        start_result_match = re.search(r'\[3,\s*"([^"]+)",\s*\{[^}]*"transactionId"', line)
                        if start_result_match:
                            msg_id = start_result_match.group(1)
                            # Clear from pending (transaction started successfully)
                            pending_start_transactions.pop(msg_id, None)
                        
                        # Detect invalid transactionId values (-1, 0, null)
                        if 'transactionId' in line:
                            invalid_match = re.search(r'"transactionId"\s*:\s*(-1|0|null)', line)
                            if invalid_match:
                                invalid_transaction_ids += 1
                                if len(lost_transactions) < 10:
                                    lost_transactions.append({
                                        'timestamp': timestamp,
                                        'issue': f'Invalid transactionId={invalid_match.group(1)}',
                                        'line': line.strip()[:200]  # Truncate for readability
                                    })
            
            except Exception as e:
                print(f"  ⚠ Could not parse lost transactions from {ocpp_file.name}: {e}")
        
        # Remaining pending transactions = lost (never got confirmation)
        for msg_id, timestamp in pending_start_transactions.items():
            if len(lost_transactions) < 10:
                lost_transactions.append({
                    'timestamp': timestamp,
                    'issue': f'StartTransaction.req sent but no .conf received (msgId={msg_id})',
                    'line': 'TIMEOUT - No CALLRESULT received'
                })
        
        return {
            'lost_transaction_count': len(pending_start_transactions),
            'invalid_transaction_ids': invalid_transaction_ids,
            'total_issues': len(pending_start_transactions) + invalid_transaction_ids,
            'examples': lost_transactions[:10]
        }
    
    @staticmethod
    def detect_hard_reset_data_loss(folder: Path) -> Dict[str, Any]:
        """Detect hard reset events that cause transaction data loss
        
        CRITICAL PATTERN: Hard reset reboots immediately WITHOUT queuing StopTransaction.
        Active transaction data is lost, billing incomplete.
        
        Soft reset queues StopTransaction gracefully before rebooting.
        
        From OCPP 1.6 Errata Section 3.36: Hard vs Soft Reset behavior.
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'hard_reset_count', 'soft_reset_count', 'incomplete_transactions', 'examples'
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {
                'hard_reset_count': 0,
                'soft_reset_count': 0,
                'incomplete_transactions': 0,
                'examples': []
            }
        
        hard_resets = []
        soft_resets = []
        active_transactions: Set[int] = set()  # transactionIds currently active
        incomplete_transactions = []
        
        # Get all OCPP log files
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        for i in range(10):
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        timestamp_match = re.match(r'(\w+ +\d+ \d+:\d+:\d+\.\d+)', line)
                        timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                        
                        # Track StartTransaction (transaction begins)
                        if 'StartTransaction' in line and '"transactionId"' in line:
                            tx_match = re.search(r'"transactionId"\s*:\s*(\d+)', line)
                            if tx_match:
                                tx_id = int(tx_match.group(1))
                                if tx_id > 0:  # Valid transaction ID
                                    active_transactions.add(tx_id)
                        
                        # Track StopTransaction (transaction ends)
                        if 'StopTransaction' in line:
                            tx_match = re.search(r'"transactionId"\s*:\s*(\d+)', line)
                            if tx_match:
                                tx_id = int(tx_match.group(1))
                                active_transactions.discard(tx_id)
                        
                        # Detect Reset.req messages
                        if 'Reset.req' in line or '"Reset"' in line:
                            # Parse reset type from JSON
                            reset_type = 'Unknown'
                            if '"type":"Hard"' in line or 'type":"Hard"' in line:
                                reset_type = 'Hard'
                                hard_resets.append({
                                    'timestamp': timestamp,
                                    'active_transactions': len(active_transactions),
                                    'line': line.strip()[:200]
                                })
                                
                                # If there are active transactions during hard reset = data loss
                                if active_transactions:
                                    incomplete_transactions.append({
                                        'timestamp': timestamp,
                                        'transaction_ids': list(active_transactions),
                                        'issue': f'Hard reset during {len(active_transactions)} active transaction(s)',
                                        'line': line.strip()[:200]
                                    })
                            
                            elif '"type":"Soft"' in line or 'type":"Soft"' in line:
                                reset_type = 'Soft'
                                soft_resets.append({
                                    'timestamp': timestamp,
                                    'active_transactions': len(active_transactions),
                                    'line': line.strip()[:200]
                                })
                        
                        # BootNotification after reset clears transaction tracking
                        # (charger rebooted - previous transactions lost if not stopped)
                        if 'BootNotification' in line:
                            # Check if we had active transactions (were never stopped)
                            if active_transactions and len(incomplete_transactions) < 10:
                                incomplete_transactions.append({
                                    'timestamp': timestamp,
                                    'transaction_ids': list(active_transactions),
                                    'issue': f'Reboot with {len(active_transactions)} unclosed transaction(s)',
                                    'line': 'INCOMPLETE - Transaction never received StopTransaction'
                                })
                            active_transactions.clear()  # Reset tracking after reboot
            
            except Exception as e:
                print(f"  ⚠ Could not parse resets from {ocpp_file.name}: {e}")
        
        return {
            'hard_reset_count': len(hard_resets),
            'soft_reset_count': len(soft_resets),
            'incomplete_transactions': len(incomplete_transactions),
            'examples': incomplete_transactions[:10]
        }
    
    @staticmethod
    def detect_meter_register_tracking(folder: Path) -> Dict[str, Any]:
        """Detect meter register issues (non-cumulative values)
        
        BEST PRACTICE: meterStart/meterStop should use cumulative lifetime register,
        not reset to 0 each transaction.
        
        Issue: If meterStart always =0, cannot audit total charger energy over lifetime.
        
        From OCPP 1.6 Errata Section 3.9: Energy.Active.Import.Register should be
        cumulative (lifetime Wh), not session-based.
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'transactions_analyzed', 'non_cumulative_count', 'meter_values', 'examples'
        """
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {
                'transactions_analyzed': 0,
                'non_cumulative_count': 0,
                'meter_values': [],
                'examples': []
            }
        
        meter_values = []  # List of (timestamp, meterStart, meterStop)
        transactions_analyzed = 0
        
        # Get all OCPP log files
        ocpp_files = []
        ocpp_base = ocpp_log_dir / "OCPP16J_Log.csv"
        if ocpp_base.exists():
            ocpp_files.append(ocpp_base)
        
        for i in range(10):
            rotated = ocpp_log_dir / f"OCPP16J_Log.csv.{i}"
            if rotated.exists():
                ocpp_files.append(rotated)
        
        for ocpp_file in ocpp_files:
            try:
                with open(ocpp_file, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        timestamp_match = re.match(r'(\w+ +\d+ \d+:\d+:\d+\.\d+)', line)
                        timestamp = timestamp_match.group(1) if timestamp_match else "Unknown"
                        
                        # Parse StartTransaction for meterStart
                        if 'StartTransaction' in line and '"meterStart"' in line:
                            meter_match = re.search(r'"meterStart"\s*:\s*(\d+)', line)
                            if meter_match:
                                transactions_analyzed += 1
                                meter_start = int(meter_match.group(1))
                                meter_values.append({
                                    'timestamp': timestamp,
                                    'type': 'meterStart',
                                    'value': meter_start,
                                    'line': line.strip()[:200]
                                })
                        
                        # Parse StopTransaction for meterStop
                        if 'StopTransaction' in line and '"meterStop"' in line:
                            meter_match = re.search(r'"meterStop"\s*:\s*(\d+)', line)
                            if meter_match:
                                meter_stop = int(meter_match.group(1))
                                meter_values.append({
                                    'timestamp': timestamp,
                                    'type': 'meterStop',
                                    'value': meter_stop,
                                    'line': line.strip()[:200]
                                })
            
            except Exception as e:
                print(f"  ⚠ Could not parse meter values from {ocpp_file.name}: {e}")
        
        # Analysis: Check if meter values look cumulative or session-based
        # Heuristic: If ALL meterStart values <100,000 Wh (100 kWh), likely not cumulative
        meter_starts = [m['value'] for m in meter_values if m['type'] == 'meterStart']
        
        non_cumulative_count = 0
        non_cumulative_examples = []
        
        if meter_starts:
            # Check if values are suspiciously low (always <100 kWh)
            max_meter_start = max(meter_starts) if meter_starts else 0
            
            if max_meter_start < 100000:  # Less than 100 kWh
                non_cumulative_count = len(meter_starts)
                non_cumulative_examples.append({
                    'issue': f'All meterStart values <100 kWh (max={max_meter_start} Wh)',
                    'detail': 'Likely using session energy instead of cumulative register',
                    'transactions': len(meter_starts)
                })
            
            # Check for monotonic increasing (cumulative should always increase)
            # If meterStart values decrease, definitely not cumulative
            for i in range(1, len(meter_starts)):
                if meter_starts[i] < meter_starts[i-1]:
                    non_cumulative_examples.append({
                        'issue': f'meterStart decreased: {meter_starts[i-1]} Wh → {meter_starts[i]} Wh',
                        'detail': 'Register reset detected - not using cumulative meter',
                        'index': i
                    })
        
        return {
            'transactions_analyzed': transactions_analyzed,
            'non_cumulative_count': non_cumulative_count,
            'meter_values': meter_values[:20],  # First 20 values
            'examples': non_cumulative_examples[:10]
        }
