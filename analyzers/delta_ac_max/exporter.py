#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV export functionality for Delta AC MAX charger log analysis
"""

import pandas as pd
from datetime import datetime
from pathlib import Path


class CsvExporter:
    """Handles CSV export of analysis results"""
    
    @staticmethod
    def export_to_csv(results, output_dir=None):
        """Export analysis results to CSV using pandas
        
        Args:
            results: List of analysis result dictionaries
            output_dir: Optional output directory (default: current directory)
            
        Returns:
            Path to exported CSV file
        """
        if not results:
            return None
        
        # Flatten results into rows
        rows = []
        for result in results:
            row = {
                'EV_Number': result['ev_number'],
                'Serial': result['serial'],
                'Status': result['status'],
                'Firmware': result.get('firmware_version', 'Unknown'),
                
                # Firmware update tracking (INFO)
                'Firmware_Updates_Count': result.get('firmware_updates', {}).get('update_count', 0),
                'Current_Firmware': result.get('firmware_updates', {}).get('current_firmware', ''),
                'Previous_Firmware': result.get('firmware_updates', {}).get('previous_firmware', ''),
                'MCU_Firmware': result.get('firmware_updates', {}).get('mcu_firmware', ''),
                
                # Basic metrics
                'Backend_Disconnects': result.get('backend_disconnects', 0),
                'MCU_Errors': result.get('mcu_errors', 0),
                'Error_Count': result.get('error_count', 0),
                'Logging_Gaps': ', '.join(result.get('logging_gaps', [])),
                
                # OCPP issues
                'SetChargingProfile_Timeouts': result.get('charging_profile_timeouts', {}).get('count', 0),
                'OCPP_Rejections_Total': result.get('ocpp_rejections', {}).get('total', 0),
                'RemoteStartTransaction_Rejected': result.get('ocpp_rejections', {}).get('by_type', {}).get('RemoteStartTransaction', 0),
                'NG_Flags': result.get('ng_flags', {}).get('count', 0),
                'OCPP_Timeouts': result.get('ocpp_timeouts', {}).get('count', 0),
                'Low_Current_Profiles': result.get('low_current_profiles', {}).get('count', 0),
                'Zero_Current_Profiles': result.get('low_current_profiles', {}).get('zero_current', 0),
                
                # Hardware issues
                'RFID_Faults': result.get('rfid_faults', {}).get('count', 0),
                'Critical_Events': len(result.get('critical_events', [])),
                
                # System reboots and power loss
                'Reboot_Count': result.get('system_reboots', {}).get('reboot_count', 0),
                'Power_Loss_Count': result.get('system_reboots', {}).get('power_loss_count', 0),
                'Firmware_Update_Reboots': result.get('system_reboots', {}).get('firmware_update_count', 0),
                'SystemLog_Failure_Count': result.get('system_reboots', {}).get('systemlog_failure_count', 0),
                'Max_Logging_Gap_Days': result.get('system_reboots', {}).get('max_gap_days', 0),
                
                # LMS issues
                'LMS_Comm_Errors': result.get('lms_issues', {}).get('load_mgmt_comm_errors', 0),
                'LMS_LIMIT_toNoPower': result.get('lms_issues', {}).get('limit_to_nopower_count', 0),
                
                # Modbus configuration
                'Modbus_Configured': result.get('modbus_config', {}).get('has_modbus_config', False),
                'Modbus_Misconfigured': result.get('modbus_config', {}).get('is_misconfigured', False),
                'Modbus_MAX_Power': result.get('modbus_config', {}).get('max_power', ''),
                'Modbus_MIN_Power': result.get('modbus_config', {}).get('min_power', ''),
                'Modbus_Issue': result.get('modbus_config', {}).get('issue_description', ''),
                
                # State transitions
                'State_Invalid_Transitions': len(result.get('state_transitions', {}).get('invalid', [])),
                'State_Suspicious_Transitions': len(result.get('state_transitions', {}).get('suspicious', [])),
                
                # Phase 1: Critical OCPP detectors
                'Lost_TransactionID_Count': result.get('lost_transaction_id', {}).get('total_issues', 0),
                'Lost_TransactionID_NoResponse': result.get('lost_transaction_id', {}).get('lost_transaction_count', 0),
                'Lost_TransactionID_Invalid': result.get('lost_transaction_id', {}).get('invalid_transaction_ids', 0),
                
                'Hard_Reset_Count': result.get('hard_reset_data_loss', {}).get('hard_reset_count', 0),
                'Soft_Reset_Count': result.get('hard_reset_data_loss', {}).get('soft_reset_count', 0),
                'Hard_Reset_Incomplete_Transactions': result.get('hard_reset_data_loss', {}).get('incomplete_transactions', 0),
                
                'Meter_Register_Transactions_Analyzed': result.get('meter_register_tracking', {}).get('transactions_analyzed', 0),
                'Meter_Register_Non_Cumulative': result.get('meter_register_tracking', {}).get('non_cumulative_count', 0),
                
                # Summary
                'Issues_Summary': ' | '.join(result.get('issues', [])),
                'Folder_Path': result.get('folder_path', ''),
            }
            rows.append(row)
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        
        # Sort by EV number (numeric if possible)
        def sort_key(ev_num):
            try:
                return (0, int(ev_num))
            except ValueError:
                return (1, ev_num)
        
        df['_sort_key'] = df['EV_Number'].apply(sort_key)
        df = df.sort_values('_sort_key').drop('_sort_key', axis=1)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ChargerAnalysisResults_{timestamp}.csv"
        
        if output_dir:
            output_path = Path(output_dir) / filename
        else:
            output_path = Path.cwd() / filename
        
        # Export to CSV
        df.to_csv(output_path, index=False)
        
        return output_path
    
    @staticmethod
    def export_events_to_csv(results, output_dir=None):
        """Export critical events to separate CSV file
        
        Args:
            results: List of analysis result dictionaries
            output_dir: Optional output directory
            
        Returns:
            Path to exported CSV file
        """
        if not results:
            return None
        
        # Flatten critical events
        rows = []
        for result in results:
            ev_num = result['ev_number']
            serial = result['serial']
            
            for event in result.get('critical_events', []):
                row = {
                    'EV_Number': ev_num,
                    'Serial': serial,
                    'Timestamp': event.get('timestamp', 'Unknown'),
                    'Event_Code': event.get('code', 'Unknown'),
                    'Description': event.get('desc', event.get('code', 'Unknown')),
                    'Root_Cause': event.get('cause', 'Unknown'),
                    'Resolution': event.get('fix', 'Unknown'),
                    'Event_File': event.get('file', 'Unknown'),
                }
                rows.append(row)
        
        if not rows:
            return None
        
        # Create DataFrame
        df = pd.DataFrame(rows)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"ChargerCriticalEvents_{timestamp}.csv"
        
        if output_dir:
            output_path = Path(output_dir) / filename
        else:
            output_path = Path.cwd() / filename
        
        # Export to CSV
        df.to_csv(output_path, index=False)
        
        return output_path
