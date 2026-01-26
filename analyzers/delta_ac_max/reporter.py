#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report generation for Delta AC MAX charger log analysis
"""

from collections import defaultdict


class Reporter:
    """Handles all terminal output and report generation"""
    
    @staticmethod
    def generate_per_charger_summary(analysis):
        """Generate inline summary for a single charger during analysis
        
        Args:
            analysis: Analysis result dictionary for one charger
        """
        if not analysis:
            return
        
        status_color = {
            'Issue': '\033[91m',
            'Warning': '\033[93m',
            'Clean': '\033[92m'
        }.get(analysis['status'], '')
        
        reset_color = '\033[0m'
        
        print(f"  {analysis['ev_number']}: {status_color}{analysis['status']}{reset_color}")
        
        if analysis['issues']:
            for issue in analysis['issues']:
                print(f"    - {issue}")
        
        if analysis['backend_disconnects'] > 10 and analysis['backend_disconnect_examples']:
            print(f"    Examples (first 3):")
            for example in analysis['backend_disconnect_examples']:
                print(f"      {example}")
        
        if analysis['mcu_errors'] > 0 and analysis['mcu_error_examples']:
            print(f"    MCU Error Examples (first 3):")
            for example in analysis['mcu_error_examples']:
                print(f"      {example}")
        
        if analysis['critical_events']:
            print(f"    Critical Hardware Events ({len(analysis['critical_events'])}):")
            for event in analysis['critical_events'][:3]:
                desc = event.get('desc', event['code'])
                cause = event.get('cause', 'Unknown cause')
                fix = event.get('fix', 'Power cycle recommended')
                print(f"      [{event['timestamp']}] {event['code']}: {desc}")
                print(f"        Cause: {cause}")
                print(f"        Fix: {fix}")
                
                context = event.get('context', {})
                if context.get('system_log'):
                    print(f"        SystemLog context (±5min):")
                    for log_line in context['system_log'][:3]:
                        print(f"          {log_line}")
                if context.get('ocpp_log'):
                    print(f"        OCPP Log context:")
                    for log_line in context['ocpp_log'][:2]:
                        print(f"          {log_line}")
    
    @staticmethod
    def generate_summary_report(results):
        """Generate and display summary report
        
        Args:
            results: List of analysis result dictionaries
        """
        if not results:
            print("\nNo results to display.")
            return
        
        print("\n" + "=" * 80)
        print("SUMMARY REPORT")
        print("=" * 80)
        print()
        
        # Group by EV number
        grouped = defaultdict(list)
        for result in results:
            grouped[result['ev_number']].append(result)
        
        clean_count = 0
        issue_count = 0
        
        for ev_num in sorted(grouped.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            chargers = sorted(grouped[ev_num], key=lambda x: x['folder_name'])
            
            has_issues = any(c['status'] != 'Clean' for c in chargers)
            
            color = '\033[93m' if has_issues else '\033[92m'  # Yellow or Green
            reset = '\033[0m'
            
            # Display charger ID (don't add EV prefix if it's a ChargBox ID)
            # Only add EV prefix if it's a numeric ID from folder name
            if ev_num.isdigit():
                display_id = f"EV{ev_num.zfill(2)}"
            else:
                display_id = ev_num
            
            print(f"{color}{display_id}{reset}")
            
            if has_issues:
                issue_count += 1
            else:
                clean_count += 1
            
            for charger in chargers:
                print(f"  Log Folder: {charger['folder_name']}")
                print(f"    Log File: {charger['log_file']}")
                print(f"    Folder: {charger['folder_path']}")
                
                if charger['firmware_version']:
                    print(f"    Firmware: {charger['firmware_version']}")
                
                print(f"    Backend Disconnects: {charger['backend_disconnects']}")
                print(f"    MCU Errors: {charger['mcu_errors']}")
                
                if charger['logging_gaps']:
                    print(f"    Logging Gaps: {', '.join(charger['logging_gaps'])}")
                
                if charger['issues']:
                    print("    Issues:")
                    for issue in charger['issues']:
                        print(f"      - {issue}")
                
                # Show timestamp examples for issues
                if charger['backend_disconnects'] > 10 and charger['backend_disconnect_examples']:
                    print("    Backend Disconnect Examples:")
                    for example in charger['backend_disconnect_examples']:
                        print(f"      {example}")
                
                if charger['mcu_errors'] > 0 and charger['mcu_error_examples']:
                    print("    MCU Error Examples:")
                    for example in charger['mcu_error_examples']:
                        print(f"      {example}")
                
                # Show critical hardware events with details
                if charger['critical_events']:
                    print(f"    Critical Hardware Events ({len(charger['critical_events'])}):")
                    for event in charger['critical_events'][:3]:  # Show first 3 in detail
                        desc = event.get('desc', event['code'])
                        cause = event.get('cause', 'Unknown cause')
                        fix = event.get('fix', 'Power cycle recommended')
                        print(f"      [{event['timestamp']}] {event['code']}: {desc}")
                        print(f"        Cause: {cause}")
                        print(f"        Fix: {fix}")
                        print(f"        Event File: {event['file']}")
                        
                        # Show log context
                        context = event.get('context', {})
                        if context.get('system_log'):
                            print(f"        SystemLog context (±5min):")
                            for log_line in context['system_log'][:5]:  # Show more in summary
                                print(f"          {log_line}")
                        if context.get('ocpp_log'):
                            print(f"        OCPP Log context:")
                            for log_line in context['ocpp_log'][:3]:
                                print(f"          {log_line}")
                        print()  # Blank line between events
                
                # Show SetChargingProfile timeout bug (CRITICAL firmware issue)
                if charger['charging_profile_timeouts']['count'] > 100:
                    timeouts = charger['charging_profile_timeouts']
                    print(f"    \033[91m⚠️  CRITICAL FIRMWARE BUG: SetChargingProfile Timeouts ({timeouts['count']})\033[0m")
                    print(f"        Root Cause: Charger advertises support for 20 periods in ChargingScheduleMaxPeriods")
                    print(f"                    but firmware only supports 10 periods max")
                    print(f"        Impact: Backend disconnects, failed load management, intermittent charging")
                    print(f"        Workaround: Contact backend provider (e.g., GreenFlux) to limit profiles to 10 periods")
                    print(f"        Permanent Fix: Report to Delta as firmware bug requiring fix")
                    print(f"        Files: Storage/SystemLog/OCPP16J_Log.csv (and rotations)")
                    if timeouts['examples']:
                        print(f"        Examples:")
                        for example in timeouts['examples']:
                            print(f"          {example}")
                    print()
                
                # Show OCPP rejections (especially RemoteStartTransaction)
                if charger['ocpp_rejections']['total'] > 5:
                    rejections = charger['ocpp_rejections']
                    print(f"    OCPP Rejections ({rejections['total']}):")
                    for msg_type, count in sorted(rejections['by_type'].items(), key=lambda x: x[1], reverse=True):
                        print(f"      {msg_type}: {count}")
                    
                    # Special note for RemoteStartTransaction rejections
                    if 'RemoteStartTransaction' in rejections['by_type']:
                        print(f"      ⓘ RemoteStartTransaction Rejected often means:")
                        print(f"         - Vehicle not connected when user tries app unlock")
                        print(f"         - Recommend: Plug in first, then use app")
                    
                    print(f"      Files: Storage/SystemLog/OCPP16J_Log.csv (and rotations)")
                    if rejections['examples']:
                        print(f"      Examples:")
                        for example in rejections['examples'][:3]:
                            print(f"        {example}")
                    print()
                
                # Show NG flags (message processing errors)
                if charger['ng_flags']['count'] > 10:
                    ng = charger['ng_flags']
                    print(f"    NG Flags (Processing Errors): {ng['count']}")
                    print(f"      ⓘ NG flags indicate message processing failures or invalid data")
                    if ng['examples']:
                        print(f"      Examples:")
                        for example in ng['examples']:
                            print(f"        {example}")
                    print()
                
                # Show other OCPP timeouts
                if charger['ocpp_timeouts']['count'] > 20:
                    timeouts = charger['ocpp_timeouts']
                    print(f"    OCPP Timeouts (Other): {timeouts['count']}")
                    print(f"      Files: Storage/SystemLog/OCPP16J_Log.csv (and rotations)")
                    if timeouts['examples']:
                        print(f"      Examples:")
                        for example in timeouts['examples'][:3]:
                            print(f"        {example}")
                    print()
                
                # Show RFID faults (CRITICAL - hardware replacement)
                if charger['rfid_faults']['count'] > 100:
                    rfid = charger['rfid_faults']
                    print(f"    \033[91m⚠️  CRITICAL HARDWARE FAULT: RFID Module (RYRR20I) - {rfid['count']} errors\033[0m")
                    print(f"        Impact: RFID cards not recognized, users cannot start charging")
                    print(f"        Root Cause: Faulty RFID reader module (RYRR20I)")
                    print(f"        Resolution: CHARGER REPLACEMENT REQUIRED (not a serviceable part)")
                    print(f"        Files: Storage/SystemLog/SystemLog (and rotations)")
                    if rfid['examples']:
                        print(f"        Examples:")
                        for example in rfid['examples']:
                            print(f"          {example}")
                    print()
                
                # Show low-current charging profiles (backend issue)
                if charger['low_current_profiles']['count'] > 10:
                    profiles = charger['low_current_profiles']
                    print(f"    \033[93m⚠️  Backend Issue: Low-Current Charging Profiles (<6A)\033[0m")
                    print(f"        Total: {profiles['count']} profiles, {profiles['zero_current']} near-zero (0-1A)")
                    print(f"        Impact: Charger suspends charging per IEC 61851-1 standard")
                    print(f"        Behavior: State changes to 'Preparing' while vehicle still connected")
                    print(f"        Root Cause: Backend (GreenFlux/etc.) sending 0A or <6A current limits")
                    print(f"        Resolution: Contact backend provider - likely unintentional load management")
                    print(f"        ⓘ This is EXPECTED charger behavior, NOT a charger fault")
                    
                    if profiles['examples']:
                        print(f"        Examples of low-current profiles:")
                        for example in profiles['examples'][:5]:
                            print(f"          [{example['timestamp']}] Connector {example['connector']}: {example['limit']:.1f}A")
                    print()
                
                # Show Load Management System issues
                if charger['lms_issues']['load_mgmt_comm_errors'] > 5 or charger['lms_issues']['limit_to_nopower_count'] > 0:
                    lms = charger['lms_issues']
                    print(f"    \033[93m⚠️  Load Management System (LMS) Issues\033[0m")
                    print(f"        Load_Mgmt_Comm errors: {lms['load_mgmt_comm_errors']}")
                    print(f"        LIMIT_toNoPower events (EV0103): {lms['limit_to_nopower_count']}")
                    print(f"        Impact: Charger stuck in current-limited state (0A/low power)")
                    print(f"        Root Causes:")
                    print(f"          1. Local LMS communication failure (Modbus device/cable)")
                    print(f"          2. Modbus register misconfiguration (fallback power = 0W)")
                    print(f"          3. Registers not reset after LMS testing/configuration")
                    print(f"        Common Scenario: Multi-charger site with load balancing")
                    print(f"        ")
                    print(f"        \033[1mDiagnostic Questions:\033[0m")
                    print(f"          • Did you configure Modbus registers at any stage?")
                    print(f"          • Can you read Modbus registers 40202-40204 and 41601?")
                    print(f"          • Expected values: 40202=0x0000, 40204=0xFFFF, 41601=0xFFFF")
                    print(f"          • If 40204=0x0000 → ROOT CAUSE (0W fallback power)")
                    print(f"        ")
                    print(f"        Resolution:")
                    print(f"          1. Physically disconnect LMS (Modbus cable)")
                    print(f"          2. Factory reset charger to clear stuck state")
                    print(f"          3. Test standalone charging (without LMS)")
                    print(f"          4. If works standalone → LMS configuration issue")
                    print(f"          5. OR: Modbus write correct values to registers")
                    print(f"        ⓘ This is LOCAL load management (Modbus), NOT OCPP backend")
                    
                    if lms['limit_to_nopower_count'] > 0:
                        print(f"        LIMIT_toNoPower Events:")
                        for event in lms['limit_to_nopower_events'][:5]:
                            print(f"          [{event['timestamp']}] {event['code']}: {event.get('description', 'LIMIT_toNoPower')}")
                    
                    if lms['examples']:
                        print(f"        Load_Mgmt_Comm Error Examples:")
                        for example in lms['examples'][:3]:
                            print(f"          [{example['timestamp']}] {example['line'][:120]}...")
                    print()
                
                # Show OCPP state transition issues
                state_trans = charger['state_transitions']
                if state_trans['invalid'] or len(state_trans['suspicious']) > 5:
                    print(f"    OCPP State Transition Issues:")
                    
                    if state_trans['invalid']:
                        print(f"      Protocol Violations ({len(state_trans['invalid'])}):")
                        for violation in state_trans['invalid'][:3]:
                            print(f"        [{violation['timestamp']}] Connector {violation['connector']}: {violation['reason']}")
                    
                    if state_trans['suspicious']:
                        print(f"      Suspicious Patterns ({len(state_trans['suspicious'])}):")
                        for pattern in state_trans['suspicious'][:5]:
                            print(f"        [{pattern['timestamp']}] Connector {pattern['connector']}: {pattern['pattern']}")
                            print(f"          Concern: {pattern['concern']}")
                        
                        # If we detected low-current profiles, add correlation note
                        if charger['low_current_profiles']['count'] > 10:
                            print(f"          \033[93mⓘ NOTE: {charger['low_current_profiles']['count']} low-current profiles detected - likely correlated!\033[0m")
                            print(f"          Check low-current profiles section above for details")
                    
                    if state_trans['final_states']:
                        print(f"      Final States:")
                        for conn_id, state in sorted(state_trans['final_states'].items()):
                            print(f"        Connector {conn_id}: {state}")
                    
                    print()
            
            print()
        
        print("=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        print(f"Total Chargers Analyzed: {len(grouped)}")
        print(f"\033[92mClean: {clean_count}\033[0m")
        
        issue_color = '\033[91m' if issue_count > 0 else '\033[92m'
        print(f"{issue_color}With Issues: {issue_count}\033[0m")
        print()
