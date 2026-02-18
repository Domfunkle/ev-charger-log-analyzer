#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report generation for Delta AC MAX charger log analysis
"""

from collections import defaultdict
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()


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
        
        status_style = {
            'Issue': 'bold red',
            'Warning': 'bold yellow',
            'Clean': 'bold green'
        }.get(analysis['status'], 'white')
        
        console.print(f"  {analysis['ev_number']}: [{status_style}]{analysis['status']}[/{status_style}]")
        
        if analysis['issues']:
            for issue in analysis['issues']:
                console.print(f"    - {issue}")
    
    @staticmethod
    def generate_summary_report(results):
        """Generate and display summary report with rich tables
        
        Args:
            results: List of analysis result dictionaries
        """
        if not results:
            console.print("\n[yellow]No results to display.[/yellow]")
            return
        
        console.print()
        console.rule("[bold cyan]SUMMARY REPORT[/bold cyan]", style="cyan")
        console.print()
        
        # Create summary table
        table = Table(title="Charger Analysis Summary", show_header=True, header_style="bold magenta")
        table.add_column("EV #", style="cyan", no_wrap=True)
        table.add_column("Status", style="white")
        table.add_column("Firmware", style="dim")
        table.add_column("FW\nUpdates", justify="right", style="cyan")
        table.add_column("Backend\nDisconnects", justify="right")
        table.add_column("OCPP\nIssues", justify="right")
        table.add_column("Critical\nEvents", justify="right")
        table.add_column("Lost\nTxID", justify="right", style="red")
        table.add_column("Hard\nResets", justify="right", style="red")
        table.add_column("Key Issues", style="yellow")
        
        # Group by EV number
        grouped = defaultdict(list)
        for result in results:
            grouped[result['ev_number']].append(result)
        
        clean_count = 0
        issue_count = 0
        
        for ev_num in sorted(grouped.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            chargers = sorted(grouped[ev_num], key=lambda x: x['folder_name'])
            
            for charger in chargers:
                # Determine status style
                if charger['status'] == 'Clean':
                    status_text = "[green]✓ Clean[/green]"
                    clean_count += 1
                elif charger['status'] == 'Warning':
                    status_text = "[yellow]⚠ Warning[/yellow]"
                    issue_count += 1
                else:
                    status_text = "[red]✗ Issue[/red]"
                    issue_count += 1
                
                # Calculate OCPP issues
                ocpp_issues = (
                    charger.get('charging_profile_timeouts', {}).get('count', 0) +
                    charger.get('ocpp_rejections', {}).get('total', 0) +
                    charger.get('ocpp_timeouts', {}).get('count', 0)
                )
                
                # Get critical detector results
                lost_txid = charger.get('lost_transaction_id', {}).get('total_issues', 0)
                hard_resets = charger.get('hard_reset_data_loss', {}).get('incomplete_transactions', 0)
                
                # Get firmware update info
                fw_updates = charger.get('firmware_updates', {})
                fw_count = fw_updates.get('update_count', 0)
                current_fw = fw_updates.get('current_firmware', charger.get('firmware_version', 'Unknown'))
                previous_fw = fw_updates.get('previous_firmware', '')
                
                # Format firmware display
                if fw_count > 0 and previous_fw:
                    firmware_display = f"{previous_fw} → {current_fw}"
                else:
                    firmware_display = current_fw
                
                # Format key issues (first 2)
                issues_summary = charger.get('issues', [])[:2]
                key_issues = '\n'.join(issues_summary) if issues_summary else '-'
                
                table.add_row(
                    charger['ev_number'],
                    status_text,
                    firmware_display,
                    f"[cyan]{fw_count}[/cyan]" if fw_count > 0 else '-',
                    str(charger.get('backend_disconnects', 0)),
                    str(ocpp_issues) if ocpp_issues > 0 else '-',
                    str(len(charger.get('critical_events', []))) if charger.get('critical_events') else '-',
                    f"[bold red]{lost_txid}[/bold red]" if lost_txid > 0 else '-',
                    f"[bold red]{hard_resets}[/bold red]" if hard_resets > 0 else '-',
                    key_issues[:60] + '...' if len(key_issues) > 60 else key_issues
                )
        
        console.print(table)
        console.print()
        
        # Statistics summary
        total = clean_count + issue_count
        console.print(f"[bold]Total Chargers:[/bold] {total}")
        console.print(f"[green]Clean:[/green] {clean_count}  [yellow]Issues/Warnings:[/yellow] {issue_count}")
        console.print()
        
        # Show detailed findings for chargers with issues
        Reporter._show_detailed_findings(results)
    
    @staticmethod
    def _show_detailed_findings(results):
        """Show detailed findings with log examples for chargers with issues
        
        Args:
            results: List of analysis result dictionaries
        """
        issues_found = [r for r in results if r['status'] != 'Clean']
        
        if not issues_found:
            console.print("[green]✓ No issues found in any chargers![/green]\n")
            return
        
        console.rule("[bold yellow]DETAILED FINDINGS[/bold yellow]", style="yellow")
        console.print()
        
        for result in issues_found:
            console.print(f"[bold cyan]═══ {result['ev_number']} - {result['serial']} ═══[/bold cyan]")
            console.print(f"[dim]Firmware: {result.get('firmware_version', 'Unknown')}[/dim]")
            console.print()
            
            # Backend disconnects
            if result.get('backend_disconnects', 0) > 10:
                console.print(f"[red]⚠ Backend Disconnects: {result['backend_disconnects']}[/red]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"Backend connection fail\"[/cyan]")
                examples = result.get('backend_disconnect_examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {examples[0].strip()}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {examples[-1].strip()}")
                    if result['backend_disconnects'] > len(examples):
                        console.print(f"[dim]  ... and {result['backend_disconnects'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # MCU errors
            if result.get('mcu_errors', 0) > 0:
                console.print(f"[red]⚠ MCU Communication Errors: {result['mcu_errors']}[/red]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"to MCU False\"[/cyan]")
                examples = result.get('mcu_error_examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {examples[0].strip()}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {examples[-1].strip()}")
                    if result['mcu_errors'] > len(examples):
                        console.print(f"[dim]  ... and {result['mcu_errors'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # OCPP Lost Transaction IDs
            lost_txid = result.get('lost_transaction_id', {})
            if lost_txid.get('total_issues', 0) > 0:
                console.print(f"[bold red]⚠ CRITICAL: Lost Transaction IDs - {lost_txid['total_issues']} billing failures[/bold red]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"transactionId\":-1[/cyan] [dim]or[/dim] [cyan]\"StartTransaction.conf\"[/cyan]")
                console.print(f"   • Pending CALL messages: {lost_txid.get('pending_call_count', 0)}")
                console.print(f"   • No-response count: {lost_txid.get('lost_transaction_count', 0)}")
                console.print(f"   • Invalid IDs: {lost_txid.get('invalid_transaction_ids', 0)}")
                
                if lost_txid.get('examples'):
                    examples = lost_txid['examples']
                    console.print(f"[dim]  First occurrence:[/dim] {examples[0].get('timestamp', '')} - {examples[0].get('message', '')}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {examples[-1].get('timestamp', '')} - {examples[-1].get('message', '')}")
                    if lost_txid['total_issues'] > len(examples):
                        console.print(f"[dim]  ... and {lost_txid['total_issues'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # Pre-Charging Aborts
            precharge = result.get('precharging_aborts', {})
            if precharge.get('abort_count', 0) > 0:
                severity = precharge.get('severity', 'INFO')
                abort_count = precharge['abort_count']
                quick_aborts = precharge.get('quick_aborts', 0)
                
                # Color-code based on severity
                if severity == 'CRITICAL':
                    console.print(f"[bold red]⚠ CRITICAL: Pre-Charging Aborts - {abort_count} occurrences[/bold red]")
                    console.print(f"[dim]  Pattern:[/dim] Authorize (Accepted) → Finishing [red]without StartTransaction[/red]")
                    console.print(f"   • Quick aborts (<15 sec): {quick_aborts}")
                    console.print(f"   • Likely cause: [red]Charger hardware fault[/red] (pilot signal, connector lock)")
                    console.print(f"   • Recommendation: [red]Service required - investigate charger[/red]")
                elif severity == 'WARNING':
                    console.print(f"[bold yellow]⚠ WARNING: Pre-Charging Aborts - {abort_count} occurrences[/bold yellow]")
                    console.print(f"[dim]  Pattern:[/dim] Authorize (Accepted) → Finishing [yellow]without StartTransaction[/yellow]")
                    console.print(f"   • Quick aborts (<15 sec): {quick_aborts}")
                    console.print(f"   • Likely cause: [yellow]Pattern emerging[/yellow] - needs investigation")
                    console.print(f"   • Recommendation: [yellow]Monitor for increasing frequency[/yellow]")
                else:  # INFO
                    console.print(f"[bold cyan]ℹ INFO: Pre-Charging Aborts - {abort_count} occurrences[/bold cyan]")
                    console.print(f"[dim]  Pattern:[/dim] Authorize (Accepted) → Finishing [cyan]without StartTransaction[/cyan]")
                    console.print(f"   • Quick aborts (<15 sec): {quick_aborts}")
                    console.print(f"   • Likely cause: [cyan]User error[/cyan] (connector not fully seated/locked)")
                    console.print(f"   • Recommendation: [cyan]No action needed[/cyan] - isolated incidents normal")
                
                # Show examples
                if precharge.get('examples'):
                    examples = precharge['examples']
                    console.print(f"[dim]  First occurrence:[/dim] {examples[0].get('timestamp', '')} - {examples[0].get('issue', '')}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {examples[-1].get('timestamp', '')} - {examples[-1].get('issue', '')}")
                    if abort_count > len(examples):
                        console.print(f"[dim]  ... and {abort_count - len(examples)} more occurrences[/dim]")
                console.print()
            
            # Hard Reset Data Loss
            hard_reset = result.get('hard_reset_data_loss', {})
            if hard_reset.get('incomplete_transactions', 0) > 0:
                console.print(f"[bold red]⚠ CRITICAL: Hard Reset Data Loss - {hard_reset['incomplete_transactions']} lost transactions[/bold red]")
                console.print(f"   • Hard resets: {hard_reset.get('hard_reset_count', 0)}")
                console.print(f"   • Soft resets: {hard_reset.get('soft_reset_count', 0)}")
                
                if hard_reset.get('incomplete_transaction_details'):
                    console.print("[dim]  Lost transactions:[/dim]")
                    for tx in hard_reset['incomplete_transaction_details'][:3]:
                        console.print(f"    ID: {tx.get('transaction_id', 'Unknown')}, Start: {tx.get('start_time', 'Unknown')}")
                console.print()
            
            # Meter Register Issues
            meter = result.get('meter_register_tracking', {})
            if meter.get('non_cumulative_count', 0) > 0:
                console.print(f"[yellow]⚠ WARNING: Meter register appears non-cumulative[/yellow]")
                console.print(f"   • Transactions analyzed: {meter.get('transactions_analyzed', 0)}")
                console.print(f"   • Non-cumulative count: {meter['non_cumulative_count']}")
                console.print(f"   • Max meterStart: {meter.get('max_meter_start', 0)} Wh")
                console.print()
            
            # SetChargingProfile timeouts
            profile_timeouts = result.get('charging_profile_timeouts', {})
            if profile_timeouts.get('count', 0) > 100:
                console.print(f"[bold red]⚠ CRITICAL: SetChargingProfile Timeouts: {profile_timeouts['count']}[/bold red]")
                console.print("[dim]   Known firmware bug - backend repeatedly resends profiles[/dim]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"SetChargingProfileConf process time out\"[/cyan]")
                examples = profile_timeouts.get('examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {examples[0].strip()}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {examples[-1].strip()}")
                    if profile_timeouts['count'] > len(examples):
                        console.print(f"[dim]  ... and {profile_timeouts['count'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # OCPP Rejections
            rejections = result.get('ocpp_rejections', {})
            if rejections.get('total', 0) > 5:
                console.print(f"[yellow]⚠ OCPP Rejections: {rejections['total']}[/yellow]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"Rejected\"[/cyan] [dim]in OCPP16J_Log.csv[/dim]")
                by_type = rejections.get('by_type', {})
                for msg_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True):
                    console.print(f"   • {msg_type}: {count}")
                examples = rejections.get('examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {examples[0].strip()}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {examples[-1].strip()}")
                    if rejections['total'] > len(examples):
                        console.print(f"[dim]  ... and {rejections['total'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # RFID Faults
            rfid = result.get('rfid_faults', {})
            if rfid.get('count', 0) > 100:
                console.print(f"[bold red]⚠ CRITICAL: RFID Module Fault: {rfid['count']} errors[/bold red]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"RFID_Init Fail\"[/cyan]")
                examples = rfid.get('examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {examples[0].strip()}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {examples[-1].strip()}")
                    if rfid['count'] > len(examples):
                        console.print(f"[dim]  ... and {rfid['count'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # Modbus Configuration Issues
            modbus_config = result.get('modbus_config', {})
            if modbus_config.get('is_misconfigured'):
                console.print(f"[bold red]🔴 CRITICAL: Modbus Misconfiguration[/bold red]")
                console.print(f"[dim]  Location:[/dim] Config/evcs file")
                console.print(f"[red]  Issue: {modbus_config.get('issue_description', 'Unknown')}[/red]")
                if modbus_config.get('max_power') is not None:
                    console.print(f"   • ModbusMAXPower: {modbus_config['max_power']} W")
                if modbus_config.get('min_power') is not None:
                    console.print(f"   • ModbusMINPower: {modbus_config['min_power']} W")
                if modbus_config.get('fallback_limit') is not None:
                    console.print(f"   • FallbackLimit: {modbus_config['fallback_limit']} W")
                if modbus_config.get('timeout_enabled') is not None:
                    console.print(f"   • Timeout Enabled: {'Yes' if modbus_config['timeout_enabled'] == 1 else 'No'}")
                console.print("[yellow]  Recommended Fix:[/yellow]")
                console.print("   • Factory reset to remove LMS config, OR")
                console.print("   • Set ModbusMAXPower = 4294967295 (0xFFFFFFFF = MAX)")
                console.print("   • Set FallbackLimit ≥ 1380W (6A minimum per IEC 61851-1)")
                console.print()
            
            # System Reboots and Power Loss
            reboots = result.get('system_reboots', {})
            reboot_count = reboots.get('reboot_count', 0)
            power_loss_count = reboots.get('power_loss_count', 0)
            firmware_update_count = reboots.get('firmware_update_count', 0)
            max_gap_days = reboots.get('max_gap_days', 0)
            
            if reboot_count > 0:
                # Determine severity
                if power_loss_count > 5:
                    severity = "red"
                    icon = "⚠️"
                elif power_loss_count > 2:
                    severity = "yellow"
                    icon = "⚠"
                else:
                    severity = "cyan"
                    icon = "ℹ"
                
                console.print(f"[{severity}]{icon} System Reboots Detected: {reboot_count} events[/{severity}]")
                console.print(f"[dim]  Analysis:[/dim] SystemLog gap detection")
                console.print(f"   • Power loss events: {power_loss_count}")
                console.print(f"   • Firmware updates: {firmware_update_count}")
                console.print(f"   • Max logging gap: {max_gap_days:.1f} days")
                
                # Show up to 3 most recent events
                events = reboots.get('events', [])
                if events:
                    console.print(f"[dim]  Recent events:[/dim]")
                    # Sort chronologically by first_timestamp (resume time - most recent first)
                    # Since logs lack year, infer based on assumption:
                    # - Higher month numbers (Jul-Dec) likely from previous year
                    # - Lower month numbers (Jan-Jun) likely from current year
                    # This creates effective chronological order for ~1 year of logs
                    
                    def parse_and_infer_year(ts_str):
                        try:
                            from datetime import datetime
                            # Parse 'Feb  9 03:58:50' format
                            parts = ts_str.split()
                            if len(parts) >= 3:
                                month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                           'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
                                month = month_map.get(parts[0], 1)
                                day = int(parts[1])
                                time_parts = parts[2].split(':')
                                hour = int(time_parts[0]) if len(time_parts) > 0 else 0
                                minute = int(time_parts[1]) if len(time_parts) > 1 else 0
                                second = int(time_parts[2]) if len(time_parts) > 2 else 0
                                
                                # Infer year: months 1-6 (Jan-Jun) = current year (higher sort value)
                                # months 7-12 (Jul-Dec) = previous year (lower sort value)
                                # This assumes logs span ~1 year and we're closer to Jan-Jun
                                inferred_year = 2026 if month <= 6 else 2025
                                
                                # Return tuple for sorting (year, month, day, hour, minute, second)
                                return (inferred_year, month, day, hour, minute, second)
                        except:
                            pass
                        return (0, 0, 0, 0, 0, 0)
                    
                    # Sort by inferred timestamp - newest first
                    sorted_events = sorted(events, key=lambda x: parse_and_infer_year(x.get('first_timestamp', '')), reverse=True)
                    
                    # Helper to add year to timestamp for display
                    def add_year_to_timestamp(ts_str):
                        """Add inferred year to timestamp string for display"""
                        try:
                            parts = ts_str.split()
                            if len(parts) >= 3:
                                month_map = {'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                                           'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12}
                                month = month_map.get(parts[0], 0)
                                if month:
                                    # Same year inference logic as sorting
                                    year = 2026 if month <= 6 else 2025
                                    # Format: "Feb  9 2026 03:58:50"
                                    return f"{parts[0]} {parts[1]:>2} {year} {parts[2]}"
                        except:
                            pass
                        return ts_str
                    
                    for i, event in enumerate(sorted_events[:3], 1):
                        event_type = event.get('type', 'unknown')
                        gap_days = event.get('gap_days', 0)
                        gap_hours = event.get('gap_hours', 0)
                        last_ts = event.get('last_timestamp', 'Unknown')
                        first_ts = event.get('first_timestamp', 'Unknown')
                        evidence = event.get('evidence', [])
                        
                        # Add inferred year to timestamps
                        last_ts_with_year = add_year_to_timestamp(last_ts)
                        first_ts_with_year = add_year_to_timestamp(first_ts)
                        
                        # Set icon and label based on event type
                        if event_type == "power_loss":
                            type_icon = "🔌"
                            type_label = "Power Loss"
                        elif event_type == "firmware_update":
                            type_icon = "🔄"
                            type_label = "Firmware Update"
                        elif event_type == "systemlog_failure":
                            type_icon = "⚠️"
                            type_label = "SystemLog Failure"
                        else:
                            type_icon = "❓"
                            type_label = "Unknown Event"
                        
                        if gap_days > 1:
                            gap_str = f"{gap_days:.1f} days"
                        else:
                            gap_str = f"{gap_hours:.1f} hours"
                        
                        console.print(f"    {type_icon} {type_label}: Gap {gap_str}")
                        console.print(f"       Last log: {last_ts_with_year}")
                        console.print(f"       Resumed: {first_ts_with_year}")
                        if evidence:
                            console.print(f"       Evidence: {', '.join(evidence)}")
                    
                    if len(events) > 3:
                        console.print(f"[dim]     ... and {len(events) - 3} more events[/dim]")
                
                # Recommendations for power loss
                if power_loss_count > 2:
                    console.print("[yellow]  Recommended Actions:[/yellow]")
                    console.print("   • Investigate site power quality (voltage sags, outages)")
                    console.print("   • Check RTC battery if dates reset to Jul 20 2025")
                    console.print("   • Review facility electrical system for instability")
                
                # Recommendations for SystemLog failures
                systemlog_failure_count = reboots.get('systemlog_failure_count', 0)
                if systemlog_failure_count > 0:
                    console.print("[yellow]  SystemLog Issue Detected:[/yellow]")
                    console.print("   • SystemLog stopped but charger remained operational (OCPP active)")
                    console.print("   • Likely firmware bug or storage issue, not power loss")
                    console.print("   • Consider firmware update if available")
                    console.print("   • Report to Delta if recurring on multiple chargers")
                
                console.print()
            
            # LMS Issues
            lms = result.get('lms_issues', {})
            if lms.get('load_mgmt_comm_errors', 0) > 5 or lms.get('limit_to_nopower_count', 0) > 0:
                console.print(f"[yellow]⚠ Load Management System Issues[/yellow]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"Load_Mgmt_Comm_Error\"[/cyan] [dim]or[/dim] [cyan]\"LIMIT_toNoPower\"[/cyan]")
                console.print(f"   • Modbus comm errors: {lms.get('load_mgmt_comm_errors', 0)}")
                console.print(f"   • LIMIT_toNoPower events: {lms.get('limit_to_nopower_count', 0)}")
                examples = lms.get('examples', [])
                if examples:
                    # Examples are dicts with 'timestamp' and 'line' keys
                    first = examples[0]
                    if isinstance(first, dict):
                        console.print(f"[dim]  First occurrence:[/dim] {first.get('timestamp', 'Unknown')} - {first.get('line', '').strip()}")
                    else:
                        console.print(f"[dim]  First occurrence:[/dim] {first.strip()}")
                    
                    if len(examples) > 1:
                        last = examples[-1]
                        if isinstance(last, dict):
                            console.print(f"[dim]  Last occurrence:[/dim] {last.get('timestamp', 'Unknown')} - {last.get('line', '').strip()}")
                        else:
                            console.print(f"[dim]  Last occurrence:[/dim] {last.strip()}")
                    
                    total_lms = lms.get('load_mgmt_comm_errors', 0) + lms.get('limit_to_nopower_count', 0)
                    if total_lms > len(examples):
                        console.print(f"[dim]  ... and {total_lms - len(examples)} more occurrences[/dim]")
                console.print()
            
            # Low Current Profiles
            low_current = result.get('low_current_profiles', {})
            if low_current.get('count', 0) > 10:
                console.print(f"[yellow]⚠ Low Current Profiles: {low_current['count']}[/yellow]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"SetChargingProfile\"[/cyan] [dim]+ check limit values in OCPP16J_Log.csv[/dim]")
                console.print(f"   • Near-zero current: {low_current.get('zero_current', 0)}")
                examples = low_current.get('examples', [])
                if examples:
                    first = examples[0]
                    console.print(f"[dim]  First occurrence:[/dim] {first.get('timestamp', 'Unknown')} - Limit: {first.get('limit', '?')}A")
                    if len(examples) > 1:
                        last = examples[-1]
                        console.print(f"[dim]  Last occurrence:[/dim] {last.get('timestamp', 'Unknown')} - Limit: {last.get('limit', '?')}A")
                    if low_current['count'] > len(examples):
                        console.print(f"[dim]  ... and {low_current['count'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # State Transitions
            states = result.get('state_transitions', {})
            if states.get('invalid'):
                console.print(f"[red]⚠ Invalid State Transitions: {len(states['invalid'])}[/red]")
                for trans in states['invalid'][:3]:
                    console.print(f"    {trans}")
                console.print()
            
            if len(states.get('suspicious', [])) > 5:
                console.print(f"[yellow]⚠ Suspicious State Transitions: {len(states['suspicious'])}[/yellow]")
                for trans in states['suspicious'][:3]:
                    console.print(f"    {trans}")
                console.print()
            
            # Critical Events
            events = result.get('critical_events', [])
            if events:
                console.print(f"[red]⚠ Critical Hardware Events: {len(events)}[/red]")
                
                # Extract unique error codes for search term
                error_codes = set(event.get('code', '') for event in events if event.get('code'))
                if error_codes:
                    search_codes = '" or "'.join(sorted(error_codes))
                    console.print(f"[dim]  Search term:[/dim] [cyan]\"{search_codes}\"[/cyan] [dim]in Events.csv files[/dim]")
                
                console.print(f"[dim]  Showing {min(5, len(events))} of {len(events)} events (most recent first):[/dim]")
                # Sort events by timestamp (newest first)
                sorted_events = sorted(events, key=lambda x: x.get('timestamp', ''), reverse=True)
                for event in sorted_events[:5]:
                    # Parse event dict and format nicely
                    timestamp = event.get('timestamp', 'Unknown time')
                    code = event.get('code', 'Unknown')
                    desc = event.get('desc', 'Unknown error')
                    cause = event.get('cause', 'Unknown cause')
                    fix = event.get('fix', 'No fix available')
                    is_recovery = event.get('is_recovery', False)
                    
                    status = "[green](Recovered)[/green]" if is_recovery else "[red](Active)[/red]"
                    console.print(f"    [bold]{timestamp}[/bold] - {code}: {desc} {status}")
                    
                    # Show firmware version when event occurred
                    fw_at_event = event.get('firmware_at_event')
                    if fw_at_event and fw_at_event != 'Unknown':
                        console.print(f"      [dim]Firmware version:[/dim] {fw_at_event}")
                    
                    console.print(f"      [dim]Cause:[/dim] {cause}")
                    console.print(f"      [dim]Fix:[/dim] {fix}")
                    
                    # Show correlated log context if available
                    context = event.get('context', {})
                    system_logs = context.get('system_log', [])
                    ocpp_logs = context.get('ocpp_log', [])
                    
                    if system_logs or ocpp_logs:
                        console.print(f"      [dim]Correlated logs (±5 min):[/dim]")
                        if system_logs:
                            console.print(f"        [dim]SystemLog:[/dim]")
                            for log in system_logs[:3]:  # Show first 3
                                console.print(f"          {log}")
                            if len(system_logs) > 3:
                                console.print(f"          [dim]... and {len(system_logs) - 3} more SystemLog entries[/dim]")
                        if ocpp_logs:
                            console.print(f"        [dim]OCPP Log:[/dim]")
                            for log in ocpp_logs[:3]:  # Show first 3
                                console.print(f"          {log}")
                            if len(ocpp_logs) > 3:
                                console.print(f"          [dim]... and {len(ocpp_logs) - 3} more OCPP entries[/dim]")
                console.print()
            
            # Logging Gaps
            gaps = result.get('logging_gaps', [])
            if gaps:
                console.print(f"[yellow]⚠ Logging Gaps: {', '.join(gaps)}[/yellow]")
                console.print()
            
            # Firmware Updates
            fw_updates = result.get('firmware_updates', {})
            if fw_updates.get('update_count', 0) > 0:
                console.print(f"[cyan]ℹ Firmware Updates: {fw_updates['update_count']}[/cyan]")
                history = fw_updates.get('firmware_history', [])
                # Show most recent updates first
                for update in reversed(history):
                    console.print(f"    {update.get('timestamp', '')} - {update.get('change', '')}")
                console.print()
            
            console.print()

