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
    def detect_precharging_aborts(folder: Path) -> Dict[str, Any]:
        """Detect pre-charging aborts (Authorize → Finishing without StartTransaction)
        
        PATTERN: Charger goes Preparing → Authorize (Accepted) → Finishing with NO StartTransaction.
        This is NOT always a fault - often indicates legitimate safety abort or user error.
        
        Common causes:
        - User error: Connector not fully seated/locked (most common)
        - Vehicle BMS not ready (temperature, initialization)
        - Pilot signal handshake failure
        - Thermal protection triggered
        - Pre-energization safety check failure
        
        Severity classification:
        - INFO: Isolated incidents (<15 sec abort) - likely user error
        - WARNING: Pattern emerging (>3/week) - investigate charger
        - CRITICAL: Frequent (>10% of attempts) - charger fault likely
        
        Args:
            folder: Path to charger log folder
            
        Returns:
            Dict with 'abort_count', 'quick_aborts', 'severity', 'examples'
        """
        from datetime import datetime, timedelta
        
        ocpp_log_dir = folder / "Storage" / "SystemLog"
        if not ocpp_log_dir.exists():
            return {
                'abort_count': 0,
                'quick_aborts': 0,
                'severity': 'INFO',
                'examples': []
            }
        
        # Track state transitions
        preparing_events = []  # List of (timestamp_str, timestamp_dt)
        authorize_events = []  # List of (timestamp_str, timestamp_dt, idTag, status)
        finishing_events = []  # List of (timestamp_str, timestamp_dt)
        start_transaction_events = []  # List of timestamp_str
        
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
                        # Extract timestamp (format: "Feb 17 23:41:46.159")
                        timestamp_match = re.match(r'(\w+ +\d+ \d+:\d+:\d+\.\d+)', line)
                        if not timestamp_match:
                            continue
                        timestamp_str = timestamp_match.group(1)
                        
                        # Parse timestamp to datetime for duration calc
                        # Note: Year inference may be needed, using current year for now
                        try:
                            timestamp_dt = datetime.strptime(timestamp_str, '%b %d %H:%M:%S.%f')
                            # Add current year (approximation - good enough for duration calc)
                            timestamp_dt = timestamp_dt.replace(year=datetime.now().year)
                        except:
                            timestamp_dt = None
                        
                        # Detect StatusNotification: Preparing
                        # Format: [Info][OCPP16J]StatusNotificationReq:pu8SendBuf=[2,"...","StatusNotification",{..."status":"Preparing"...}]
                        if 'StatusNotification' in line and ('"status":"Preparing"' in line or '"status": "Preparing"' in line):
                            preparing_events.append((timestamp_str, timestamp_dt))
                        
                        # Detect Authorize.req
                        # Format: [Info][OCPP16J]AuthorizeReq:pu8SendBuf=[2,"...","Authorize",{"idTag":"..."}]
                        if 'AuthorizeReq' in line or ('"Authorize"' in line and '[2,' in line):
                            # Extract idTag
                            id_match = re.search(r'"idTag"\s*:\s*"([^"]+)"', line)
                            idTag = id_match.group(1) if id_match else "Unknown"
                            # Store as pending authorize (will match with result on next line)
                            authorize_events.append((timestamp_str, timestamp_dt, idTag, None))
                        
                        # Detect Authorize result (conf)
                        # Format: [Info][OCPP16J]ResultParsing:Authorize:status=Accepted,expiryDate=,parentIdTag=...
                        if 'ResultParsing:Authorize' in line:
                            # Extract status
                            status_match = re.search(r'status\s*=\s*([^,\s]+)', line)
                            status = status_match.group(1) if status_match else "Unknown"
                            # Update last authorize event with status
                            if authorize_events and authorize_events[-1][3] is None:
                                last_auth = authorize_events[-1]
                                authorize_events[-1] = (last_auth[0], last_auth[1], last_auth[2], status)
                        
                        # Detect StatusNotification: Finishing
                        # Format: [Info][OCPP16J]StatusNotificationReq:pu8SendBuf=[2,"...","StatusNotification",{..."status":"Finishing"...}]
                        if 'StatusNotification' in line and ('"status":"Finishing"' in line or '"status": "Finishing"' in line):
                            finishing_events.append((timestamp_str, timestamp_dt))
                        
                        # Detect StartTransaction CALL
                        # Format: [Info][OCPP16J]StartTransactionReq:pu8SendBuf=[2,"...","StartTransaction",{...}]
                        if 'StartTransactionReq' in line or ('StartTransaction' in line and '[2,' in line):
                            start_transaction_events.append(timestamp_str)
            
            except Exception as e:
                print(f"  ⚠ Could not parse pre-charging aborts from {ocpp_file.name}: {e}")
        
        # Analyze patterns: Find Authorize (Accepted) followed by Finishing WITHOUT StartTransaction
        aborts = []
        quick_abort_count = 0  # Aborts <15 seconds (likely safety check)
        
        for auth_idx, (auth_ts, auth_dt, idTag, auth_status) in enumerate(authorize_events):
            # Only process Accepted authorizations
            if auth_status != 'Accepted':
                continue
            
            # Look for Finishing event after this Authorize
            finishing_after = [f for f in finishing_events if f[0] > auth_ts]
            if not finishing_after:
                continue  # No Finishing found
            
            next_finishing = finishing_after[0]
            finish_ts, finish_dt = next_finishing
            
            # Check if StartTransaction occurred between Authorize and Finishing
            start_between = any(
                auth_ts < start_ts < finish_ts
                for start_ts in start_transaction_events
            )
            
            if not start_between:
                # This is a pre-charging abort!
                # Calculate duration from Authorize to Finishing
                duration_sec = None
                if auth_dt and finish_dt:
                    try:
                        duration = finish_dt - auth_dt
                        duration_sec = duration.total_seconds()
                        # Handle day wrap-around (negative duration)
                        if duration_sec < 0:
                            duration_sec += 86400  # Add 24 hours
                    except:
                        pass
                
                # Classify as quick abort if <15 seconds
                is_quick = duration_sec is not None and duration_sec < 15
                if is_quick:
                    quick_abort_count += 1
                
                aborts.append({
                    'timestamp': auth_ts,
                    'idTag': idTag,
                    'duration_sec': round(duration_sec, 1) if duration_sec else 'Unknown',
                    'finishing_timestamp': finish_ts,
                    'is_quick_abort': is_quick,
                    'issue': f'Authorize (Accepted) → Finishing in {duration_sec:.1f}s without StartTransaction' if duration_sec else 'Authorize → Finishing without StartTransaction'
                })
        
        # Severity assessment
        abort_count = len(aborts)
        severity = 'INFO'  # Default
        
        if abort_count >= 10:
            severity = 'CRITICAL'  # Frequent pattern
        elif abort_count >= 3:
            severity = 'WARNING'  # Pattern emerging
        else:
            severity = 'INFO'  # Isolated incidents
        
        return {
            'abort_count': abort_count,
            'quick_aborts': quick_abort_count,
            'slow_aborts': abort_count - quick_abort_count,
            'severity': severity,
            'examples': aborts[:10]  # First 10 for display
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
