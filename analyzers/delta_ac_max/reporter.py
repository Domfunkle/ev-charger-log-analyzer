#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Report generation for Delta AC MAX charger log analysis
"""

from collections import defaultdict
import re
from rich.console import Console
from rich.markup import escape
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console(highlight=False)


class Reporter:
    """Handles all terminal output and report generation"""

    @staticmethod
    def _friendly_signal_label(label):
        """Convert internal marker keys into readable display labels."""
        mapping = {
            'suspend_charging': 'Suspend charging',
            'intcomm_get_time': 'IntComm get time',
            'intcomm_write_time': 'IntComm write time',
            'wifi_scan_trigger': 'WiFi scan trigger',
            'wifi_scan_no_ap': 'WiFi no AP found',
            'config_write_success': 'ConfigTable writes',
            'change_configuration': 'ChangeConfig',
            'set_charging_profile': 'SetProfile',
            'rejected_response': 'Rejected',
            'remote_start': 'RemoteStart',
            'boot_notification': 'BootNotif',
            'status_notification': 'StatusNotif',
            'ocpp_timeout': 'Timeout',
            'command_parsing': 'CommandParsing',
            'other': 'Other'
        }

        text = (label or '').strip()
        if not text:
            return text
        if text in mapping:
            return mapping[text]
        if '_' in text:
            return text.replace('_', ' ')
        return text

    @staticmethod
    def _style_timestamps(text):
        """Highlight timestamp-like patterns for faster visual scanning."""
        styled = escape(str(text or ''))
        patterns = [
            r'\b[A-Z][a-z]{2}\s+\d{1,2}\s+\d{4}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\b',
            r'\b[A-Z][a-z]{2}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\b',
            r'\b\d{4}\.\d{2}\.\d{2}\s+\d{2}:\d{2}:\d{2}(?:\.\d+)?\b',
        ]
        for pattern in patterns:
            styled = re.sub(pattern, lambda m: f"[bold cyan]{m.group(0)}[/bold cyan]", styled)
        return styled

    @staticmethod
    def _style_context_line(text):
        """Apply contextual styling to log/message lines."""
        styled = Reporter._style_timestamps(text)
        keyword_patterns = [
            r'Backend connection fail',
            r'SetChargingProfileConf process time out',
            r'StartTransaction\.conf',
            r'transactionId":-1',
            r'ChangeConfiguration',
            r'Rejected',
            r'OCPP16',
            r'EV\d{4}'
        ]
        for pattern in keyword_patterns:
            styled = re.sub(pattern, lambda m: f"[yellow]{m.group(0)}[/yellow]", styled)
        return styled

    @staticmethod
    def _style_value(value):
        """Colorize percentage and timestamp values while keeping text safe."""
        raw = str(value or '').strip()
        if raw.endswith('%'):
            try:
                pct = float(raw[:-1])
                if pct >= 50:
                    color = 'red'
                elif pct >= 10:
                    color = 'yellow'
                else:
                    color = 'green'
                return f"[{color}]{escape(raw)}[/{color}]"
            except ValueError:
                return Reporter._style_timestamps(raw)
        return Reporter._style_timestamps(raw)

    @staticmethod
    def _format_timestamp_message(timestamp, message):
        """Format timestamp-message pairs with contextual colors."""
        ts = Reporter._style_timestamps(timestamp)
        msg = escape(str(message or ''))
        if msg:
            return f"{ts} [dim]-[/dim] [white]{msg}[/white]"
        return ts

    @staticmethod
    def _format_top_block(items):
        """Format top-item list as vertically aligned cell content."""
        if not items:
            return "- None"

        parsed_items = []
        for item in items:
            if ': ' in item:
                label, value = item.split(': ', 1)
                parsed_items.append((label.strip(), value.strip()))
            elif ':' in item:
                label, value = item.split(':', 1)
                parsed_items.append((label.strip(), value.strip()))
            else:
                parsed_items.append((item.strip(), None))

        max_label_len = 0
        for label, value in parsed_items:
            if value is not None:
                max_label_len = max(max_label_len, len(Reporter._friendly_signal_label(label)))

        lines = []
        for label, value in parsed_items:
            display_label = Reporter._friendly_signal_label(label)
            if value is None:
                lines.append(f"- {display_label}")
            else:
                styled_value = Reporter._style_value(value)
                lines.append(f"- {display_label.ljust(max_label_len)} : {styled_value}")

        return '\n'.join(lines)

    @staticmethod
    def _render_leadup_matrix(summary, previous_label='event'):
        """Create a compact aligned table for lead-up signals."""
        rates = summary.get('marker_rates', {})
        marker_display = [
            ('suspend_charging', 'Suspend charging'),
            ('intcomm_get_time', 'IntComm get time'),
            ('intcomm_write_time', 'IntComm write time'),
            ('wifi_scan_trigger', 'WiFi scan trigger'),
            ('wifi_scan_no_ap', 'WiFi no AP found'),
            ('config_write_success', 'ConfigTable writes')
        ]
        marker_label_map = {key: label for key, label in marker_display}
        system_top = Reporter._top_rate_items(rates, marker_label_map, limit=3)

        ocpp_rates = summary.get('ocpp_marker_rates', {})
        ocpp_marker_display = [
            ('change_configuration', 'ChangeConfig'),
            ('set_charging_profile', 'SetProfile'),
            ('rejected_response', 'Rejected'),
            ('remote_start', 'RemoteStart'),
            ('boot_notification', 'BootNotif'),
            ('heartbeat', 'Heartbeat'),
            ('status_notification', 'StatusNotif'),
            ('ocpp_timeout', 'Timeout')
        ]
        ocpp_label_map = {key: label for key, label in ocpp_marker_display}
        ocpp_top = Reporter._top_rate_items(ocpp_rates, ocpp_label_map, limit=3)

        top_ocpp_operations = summary.get('ocpp_top_operations', [])
        ocpp_ops_block = []
        for item in top_ocpp_operations[:3]:
            ocpp_ops_block.append(f"{item.get('name', '')}: {item.get('rate', 0)}%")

        immediate_previous = summary.get('immediate_previous', {})
        previous_items = []
        if immediate_previous:
            dominant = sorted(immediate_previous.items(), key=lambda item: item[1], reverse=True)[:3]
            previous_items = [f"{name}: {count}" for name, count in dominant]

        leadup_table = Table.grid(expand=False)
        leadup_table.add_column(style="cyan", width=24, no_wrap=True)
        leadup_table.add_column(style="white")
        leadup_table.add_row("System lead-up top", Reporter._format_top_block(system_top))
        leadup_table.add_row("OCPP lead-up top", Reporter._format_top_block(ocpp_top))
        leadup_table.add_row("OCPP operations top", Reporter._format_top_block(ocpp_ops_block))
        leadup_table.add_row(f"Previous before {previous_label}", Reporter._format_top_block(previous_items))
        return leadup_table

    @staticmethod
    def _render_detail_matrix(rows, label_width=26):
        """Create a compact aligned table for section details."""
        details_table = Table.grid(expand=False, padding=(0, 2))
        details_table.add_column(style="cyan", width=label_width, no_wrap=True, justify="right")
        details_table.add_column(style="white", justify="left")
        for label, value in rows:
            details_table.add_row(label, value)
        return details_table

    @staticmethod
    def _top_rate_items(rate_dict, label_map=None, limit=3):
        """Return top non-zero rate items for readable multi-line rendering."""
        if not rate_dict:
            return []

        items = [(key, value) for key, value in rate_dict.items() if value > 0]
        if not items:
            return []

        items = sorted(items, key=lambda item: item[1], reverse=True)[:limit]
        parts = []
        for key, value in items:
            label = label_map.get(key, key) if label_map else key
            parts.append(f"{label}: {value}%")
        return parts

    @staticmethod
    def _get_priority_text(charger, ocpp_issues, critical_count, lost_txid, hard_resets):
        """Compute triage priority label for summary table."""
        backend_disconnects = charger.get('backend_disconnects', 0)
        connectivity = charger.get('connectivity_events', {})
        conn_faults = connectivity.get('fault_total', 0)
        conn_recoveries = connectivity.get('recovery_total', 0)

        if hard_resets > 0 or lost_txid > 0 or critical_count >= 20 or backend_disconnects >= 50:
            return "[bold red]High[/bold red]"

        if critical_count > 0 or backend_disconnects > 10 or ocpp_issues >= 80:
            return "[yellow]Med[/yellow]"

        if conn_faults > 0 and conn_faults > conn_recoveries:
            return "[yellow]Med[/yellow]"

        return "[green]Low[/green]"

    @staticmethod
    def _get_connectivity_ratio_text(charger):
        """Return connectivity fault/recovery ratio text."""
        connectivity = charger.get('connectivity_events', {})
        fault_total = connectivity.get('fault_total', 0)
        recovery_total = connectivity.get('recovery_total', 0)

        if fault_total == 0 and recovery_total == 0:
            return '-'

        return f"{fault_total}/{recovery_total}"

    @staticmethod
    def _get_top_volume_signal(charger, ocpp_issues, critical_count):
        """Return highest-volume signal to prioritize investigation."""
        connectivity = charger.get('connectivity_events', {})
        volume_candidates = [
            ("Conn faults", connectivity.get('fault_total', 0)),
            ("Backend fails", charger.get('backend_disconnects', 0)),
            ("OCPP issues", ocpp_issues),
            ("Critical events", critical_count),
            ("Conn events", connectivity.get('total', 0)),
        ]

        label, count = max(volume_candidates, key=lambda item: item[1])
        if count <= 0:
            return "-"
        return f"{label}: {count}"

    @staticmethod
    def _get_top_trigger_text(charger, ocpp_issues, critical_count, lost_txid, hard_resets):
        """Return short top-trigger guidance for scrolling detailed findings."""
        backend_disconnects = charger.get('backend_disconnects', 0)
        connectivity = charger.get('connectivity_events', {})
        conn_faults = connectivity.get('fault_total', 0)
        conn_total = connectivity.get('total', 0)
        change_bursts = charger.get('change_config_bursts', {})

        # Volume-first triage: surface the most frequent issue classes first
        if conn_faults >= 100:
            return "Connectivity fault storm"
        if backend_disconnects >= 30:
            return "Backend disconnect storm"
        if ocpp_issues >= 120:
            return "OCPP issue burst"
        if critical_count >= 20:
            return "Critical hw event cluster"

        # Severe but lower-volume classes
        if hard_resets > 0:
            return "Hard reset data loss"
        if lost_txid >= 3:
            return "Lost TxID billing"
        if change_bursts.get('bursts_with_ocp', 0) > 0:
            return "Config↔OCP correlation"
        if critical_count > 0:
            return "Critical hw events"
        if backend_disconnects >= 10:
            return "Backend disconnects"
        if ocpp_issues >= 60:
            return "OCPP protocol issues"
        if conn_total > 0:
            return "Connectivity churn"
        if lost_txid > 0:
            return "Lost TxID billing"

        return "Review key issues"
    
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

        # Show detailed findings first so final viewport ends on summary
        Reporter._show_detailed_findings(results)
        
        console.print()
        console.rule("[bold cyan]SUMMARY REPORT[/bold cyan]", style="cyan")
        console.print()
        
        # Create summary tables (split to avoid horizontal truncation)
        metrics_table = Table(title="Charger Summary (Core)", show_header=True, header_style="bold magenta")
        metrics_table.add_column("EV #", style="cyan", no_wrap=True)
        metrics_table.add_column("Serial", style="dim", width=14, no_wrap=True)
        metrics_table.add_column("Status", style="white", no_wrap=True)
        metrics_table.add_column("Priority", justify="center", no_wrap=True)
        metrics_table.add_column("Firmware", style="dim", no_wrap=True)
        metrics_table.add_column("FW Upd", justify="right", style="cyan", no_wrap=True)
        metrics_table.add_column("Backend", justify="right", no_wrap=True)
        metrics_table.add_column("Conn", justify="right", style="yellow", no_wrap=True)
        metrics_table.add_column("OCPP", justify="right", no_wrap=True)
        metrics_table.add_column("Critical", justify="right", no_wrap=True)
        metrics_table.add_column("LostTx", justify="right", style="red", no_wrap=True)
        metrics_table.add_column("Resets", justify="right", style="red", no_wrap=True)

        triage_table = Table(title="Charger Summary (Triage)", show_header=True, header_style="bold cyan")
        triage_table.add_column("EV #", style="cyan", no_wrap=True)
        triage_table.add_column("Serial", style="dim", width=14, no_wrap=True)
        triage_table.add_column("Top Volume Signal", style="magenta")
        triage_table.add_column("Top Trigger", style="cyan")
        triage_table.add_column("Key Issues", style="yellow")
        
        # Group by EV number
        grouped = defaultdict(list)
        for result in results:
            grouped[result['ev_number']].append(result)

        ordered_chargers = []
        for ev_num in sorted(grouped.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            chargers = sorted(grouped[ev_num], key=lambda x: x['folder_name'])
            ordered_chargers.extend(chargers)
        
        clean_count = 0
        issue_count = 0

        for index, charger in enumerate(ordered_chargers):
                if index > 0:
                    metrics_table.add_section()
                    triage_table.add_section()

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
                    charger.get('ocpp_timeouts', {}).get('count', 0) +
                    charger.get('change_config_bursts', {}).get('bursts_with_ocp', 0)
                )
                
                # Get critical detector results
                critical_count = len(charger.get('critical_events', [])) if charger.get('critical_events') else 0
                lost_txid = charger.get('lost_transaction_id', {}).get('total_issues', 0)
                hard_resets = charger.get('hard_reset_data_loss', {}).get('incomplete_transactions', 0)
                priority_text = Reporter._get_priority_text(charger, ocpp_issues, critical_count, lost_txid, hard_resets)
                top_volume_signal = Reporter._get_top_volume_signal(charger, ocpp_issues, critical_count)
                top_trigger_text = Reporter._get_top_trigger_text(charger, ocpp_issues, critical_count, lost_txid, hard_resets)
                
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
                
                metrics_table.add_row(
                    escape(str(charger['ev_number'])),
                    escape(str(charger.get('serial', '-'))),
                    status_text,
                    priority_text,
                    escape(str(firmware_display)),
                    f"[cyan]{fw_count}[/cyan]" if fw_count > 0 else '-',
                    str(charger.get('backend_disconnects', 0)),
                    str(charger.get('connectivity_events', {}).get('total', 0)) if charger.get('connectivity_events', {}).get('total', 0) > 0 else '-',
                    str(ocpp_issues) if ocpp_issues > 0 else '-',
                    str(critical_count) if critical_count > 0 else '-',
                    f"[bold red]{lost_txid}[/bold red]" if lost_txid > 0 else '-',
                    f"[bold red]{hard_resets}[/bold red]" if hard_resets > 0 else '-'
                )

                triage_table.add_row(
                    escape(str(charger['ev_number'])),
                    escape(str(charger.get('serial', '-'))),
                    escape(str(top_volume_signal)),
                    escape(str(top_trigger_text)),
                    escape(str(key_issues[:60] + '...' if len(key_issues) > 60 else key_issues))
                )

        console.print(metrics_table)
        console.print()
        console.print(triage_table)
        console.print()
        
        # Statistics summary
        total = clean_count + issue_count
        console.print(f"[bold]Total Chargers:[/bold] {total}")
        console.print(f"[green]Clean:[/green] {clean_count}  [yellow]Issues/Warnings:[/yellow] {issue_count}")
        console.print()
    
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
                    console.print(f"[dim]  First occurrence:[/dim] {Reporter._style_context_line(examples[0].strip())}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {Reporter._style_context_line(examples[-1].strip())}")
                    if result['backend_disconnects'] > len(examples):
                        console.print(f"[dim]  ... and {result['backend_disconnects'] - len(examples)} more occurrences[/dim]")

                leadup = result.get('backend_fail_leadup', {})
                if leadup.get('fail_count', 0) > 0:
                    console.print(f"[dim]  Lead-up signature (within {leadup.get('window_seconds', 60)}s before fail):[/dim]")
                    console.print(Reporter._render_leadup_matrix(leadup, previous_label='fail'))
                console.print()

            event_leadup = result.get('event_leadup', {})
            leadup_categories = [
                ('critical_events', 'Critical Events'),
                ('connectivity_fault_events', 'Connectivity Fault Events'),
                ('lost_transaction_id', 'Lost Transaction ID Events'),
                ('ocpp_rejections', 'OCPP Rejection Events'),
            ]
            for key, label in leadup_categories:
                summary = event_leadup.get(key, {})
                event_count = summary.get('event_count', 0)
                if event_count <= 0:
                    continue

                total_points = summary.get('total_event_points', event_count)
                if total_points > event_count:
                    console.print(f"[yellow]• {label}: {event_count} events analyzed (of {total_points})[/yellow]")
                else:
                    console.print(f"[yellow]• {label}: {event_count} events[/yellow]")
                console.print(Reporter._render_leadup_matrix(summary, previous_label='event'))
            if any(event_leadup.get(key, {}).get('event_count', 0) > 0 for key, _ in leadup_categories):
                console.print()
            
            # MCU errors
            if result.get('mcu_errors', 0) > 0:
                console.print(f"[red]⚠ MCU Communication Errors: {result['mcu_errors']}[/red]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"to MCU False\"[/cyan]")
                examples = result.get('mcu_error_examples', [])
                mcu_rows = []
                if examples:
                    mcu_rows.append(("First occurrence", Reporter._style_context_line(examples[0].strip())))
                    if len(examples) > 1:
                        mcu_rows.append(("Last occurrence", Reporter._style_context_line(examples[-1].strip())))
                    if result['mcu_errors'] > len(examples):
                        mcu_rows.append(("Additional", f"{result['mcu_errors'] - len(examples)} more occurrences"))
                if mcu_rows:
                    console.print(Reporter._render_detail_matrix(mcu_rows))
                console.print()
            
            # OCPP Lost Transaction IDs
            lost_txid = result.get('lost_transaction_id', {})
            if lost_txid.get('total_issues', 0) > 0:
                console.print(f"[bold red]⚠ CRITICAL: Lost Transaction IDs - {lost_txid['total_issues']} billing failures[/bold red]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"transactionId\":-1[/cyan] [dim]or[/dim] [cyan]\"StartTransaction.conf\"[/cyan]")
                console.print(Reporter._render_detail_matrix([
                    ("Pending CALL messages", str(lost_txid.get('pending_call_count', 0))),
                    ("No-response count", str(lost_txid.get('lost_transaction_count', 0))),
                    ("Invalid IDs", str(lost_txid.get('invalid_transaction_ids', 0)))
                ]))
                
                if lost_txid.get('examples'):
                    examples = lost_txid['examples']
                    console.print(f"[dim]  First occurrence:[/dim] {Reporter._format_timestamp_message(examples[0].get('timestamp', ''), examples[0].get('message', ''))}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {Reporter._format_timestamp_message(examples[-1].get('timestamp', ''), examples[-1].get('message', ''))}")
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
                    console.print(f"[dim]  First occurrence:[/dim] {Reporter._format_timestamp_message(examples[0].get('timestamp', ''), examples[0].get('issue', ''))}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {Reporter._format_timestamp_message(examples[-1].get('timestamp', ''), examples[-1].get('issue', ''))}")
                    if abort_count > len(examples):
                        console.print(f"[dim]  ... and {abort_count - len(examples)} more occurrences[/dim]")
                console.print()
            
            # Hard Reset Data Loss
            hard_reset = result.get('hard_reset_data_loss', {})
            if hard_reset.get('incomplete_transactions', 0) > 0:
                console.print(f"[bold red]⚠ CRITICAL: Hard Reset Data Loss - {hard_reset['incomplete_transactions']} lost transactions[/bold red]")
                console.print(Reporter._render_detail_matrix([
                    ("Hard resets", str(hard_reset.get('hard_reset_count', 0))),
                    ("Soft resets", str(hard_reset.get('soft_reset_count', 0)))
                ]))
                
                if hard_reset.get('incomplete_transaction_details'):
                    console.print("[dim]  Lost transactions:[/dim]")
                    for tx in hard_reset['incomplete_transaction_details'][:3]:
                        console.print(f"    ID: {tx.get('transaction_id', 'Unknown')}, Start: {tx.get('start_time', 'Unknown')}")
                console.print()
            
            # Meter Register Issues
            meter = result.get('meter_register_tracking', {})
            if meter.get('non_cumulative_count', 0) > 0:
                console.print(f"[yellow]⚠ WARNING: Meter register appears non-cumulative[/yellow]")
                console.print(Reporter._render_detail_matrix([
                    ("Transactions analyzed", str(meter.get('transactions_analyzed', 0))),
                    ("Non-cumulative count", str(meter.get('non_cumulative_count', 0))),
                    ("Max meterStart", f"{meter.get('max_meter_start', 0)} Wh")
                ]))
                console.print()
            
            # SetChargingProfile timeouts
            profile_timeouts = result.get('charging_profile_timeouts', {})
            if profile_timeouts.get('count', 0) > 100:
                console.print(f"[bold red]⚠ CRITICAL: SetChargingProfile Timeouts: {profile_timeouts['count']}[/bold red]")
                console.print("[dim]   Known firmware bug - backend repeatedly resends profiles[/dim]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"SetChargingProfileConf process time out\"[/cyan]")
                examples = profile_timeouts.get('examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {Reporter._style_context_line(examples[0].strip())}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {Reporter._style_context_line(examples[-1].strip())}")
                    if profile_timeouts['count'] > len(examples):
                        console.print(f"[dim]  ... and {profile_timeouts['count'] - len(examples)} more occurrences[/dim]")
                console.print()
            
            # OCPP Rejections
            rejections = result.get('ocpp_rejections', {})
            if rejections.get('total', 0) > 5:
                console.print(f"[yellow]⚠ OCPP Rejections: {rejections['total']}[/yellow]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"Rejected\"[/cyan] [dim]in OCPP16J_Log.csv[/dim]")
                by_type = rejections.get('by_type', {})
                rejection_rows = [(msg_type, str(count)) for msg_type, count in sorted(by_type.items(), key=lambda x: x[1], reverse=True)]
                if rejection_rows:
                    console.print(Reporter._render_detail_matrix(rejection_rows))
                examples = rejections.get('examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {Reporter._style_context_line(examples[0].strip())}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {Reporter._style_context_line(examples[-1].strip())}")
                    if rejections['total'] > len(examples):
                        console.print(f"[dim]  ... and {rejections['total'] - len(examples)} more occurrences[/dim]")
                console.print()

            # ChangeConfiguration bursts
            change_bursts = result.get('change_config_bursts', {})
            if change_bursts.get('burst_count', 0) > 0:
                console.print(
                    f"[yellow]⚠ ChangeConfiguration Bursts: {change_bursts.get('burst_count', 0)}[/yellow]"
                )
                console.print(
                    f"[dim]  Search term:[/dim] [cyan]" 
                    f"CommandParsing:tReg.tMsgCS.pu8Action=ChangeConfiguration" 
                    f"[/cyan] [dim]in OCPP16J_Log.csv[/dim]"
                )
                console.print(Reporter._render_detail_matrix([
                    ("Total commands", str(change_bursts.get('total_changes', 0))),
                    ("Unique keys", str(change_bursts.get('unique_keys', 0))),
                    ("Largest burst", f"{change_bursts.get('largest_burst_size', 0)} commands"),
                    ("Bursts near OCP", str(change_bursts.get('bursts_with_ocp', 0))),
                    ("Bursts near reconnects", str(change_bursts.get('bursts_with_backend_reconnect', 0)))
                ]))

                examples = change_bursts.get('examples', [])
                if examples:
                    first = examples[0]
                    keys_preview = ', '.join(first.get('keys', [])[:6])
                    if len(first.get('keys', [])) > 6:
                        keys_preview += ', ...'
                    console.print(
                        f"[dim]  First burst:[/dim] {Reporter._style_timestamps(first.get('start', 'Unknown'))} → {Reporter._style_timestamps(first.get('end', 'Unknown'))} "
                        f"({first.get('change_count', 0)} changes, {first.get('duration_seconds', 0)}s)"
                    )
                    console.print(f"[dim]  Keys sample:[/dim] {keys_preview if keys_preview else 'None'}")
                    correlation_items = [
                        f"ConfigTable writes: {first.get('configtable_writes', 0)}",
                        f"Reconnect events: {first.get('backend_reconnect_events', 0)}",
                        f"Nearby OCP: {first.get('ocp_events_nearby', 0)}"
                    ]
                    console.print(
                        Reporter._render_detail_matrix([
                            ("Correlation", Reporter._format_top_block(correlation_items))
                        ], label_width=12)
                    )
                console.print()
            
            # RFID Faults
            rfid = result.get('rfid_faults', {})
            if rfid.get('count', 0) > 100:
                console.print(f"[bold red]⚠ CRITICAL: RFID Module Fault: {rfid['count']} errors[/bold red]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"RFID_Init Fail\"[/cyan]")
                examples = rfid.get('examples', [])
                if examples:
                    console.print(f"[dim]  First occurrence:[/dim] {Reporter._style_context_line(examples[0].strip())}")
                    if len(examples) > 1:
                        console.print(f"[dim]  Last occurrence:[/dim] {Reporter._style_context_line(examples[-1].strip())}")
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
                        console.print(f"       Last log: {Reporter._style_timestamps(last_ts_with_year)}")
                        console.print(f"       Resumed: {Reporter._style_timestamps(first_ts_with_year)}")
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
                console.print(Reporter._render_detail_matrix([
                    ("Modbus comm errors", str(lms.get('load_mgmt_comm_errors', 0))),
                    ("LIMIT_toNoPower events", str(lms.get('limit_to_nopower_count', 0)))
                ]))
                examples = lms.get('examples', [])
                if examples:
                    # Examples are dicts with 'timestamp' and 'line' keys
                    first = examples[0]
                    if isinstance(first, dict):
                        console.print(f"[dim]  First occurrence:[/dim] {Reporter._format_timestamp_message(first.get('timestamp', 'Unknown'), first.get('line', '').strip())}")
                    else:
                        console.print(f"[dim]  First occurrence:[/dim] {Reporter._style_context_line(first.strip())}")
                    
                    if len(examples) > 1:
                        last = examples[-1]
                        if isinstance(last, dict):
                            console.print(f"[dim]  Last occurrence:[/dim] {Reporter._format_timestamp_message(last.get('timestamp', 'Unknown'), last.get('line', '').strip())}")
                        else:
                            console.print(f"[dim]  Last occurrence:[/dim] {Reporter._style_context_line(last.strip())}")
                    
                    total_lms = lms.get('load_mgmt_comm_errors', 0) + lms.get('limit_to_nopower_count', 0)
                    if total_lms > len(examples):
                        console.print(f"[dim]  ... and {total_lms - len(examples)} more occurrences[/dim]")
                console.print()
            
            # Low Current Profiles
            low_current = result.get('low_current_profiles', {})
            if low_current.get('count', 0) > 10:
                console.print(f"[yellow]⚠ Low Current Profiles: {low_current['count']}[/yellow]")
                console.print(f"[dim]  Search term:[/dim] [cyan]\"SetChargingProfile\"[/cyan] [dim]+ check limit values in OCPP16J_Log.csv[/dim]")
                console.print(Reporter._render_detail_matrix([
                    ("Near-zero current", str(low_current.get('zero_current', 0)))
                ], label_width=18))
                examples = low_current.get('examples', [])
                if examples:
                    first = examples[0]
                    first_limit_msg = f"Limit: {first.get('limit', '?')}A"
                    console.print(f"[dim]  First occurrence:[/dim] {Reporter._format_timestamp_message(first.get('timestamp', 'Unknown'), first_limit_msg)}")
                    if len(examples) > 1:
                        last = examples[-1]
                        last_limit_msg = f"Limit: {last.get('limit', '?')}A"
                        console.print(f"[dim]  Last occurrence:[/dim] {Reporter._format_timestamp_message(last.get('timestamp', 'Unknown'), last_limit_msg)}")
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

            # Connectivity Events (EV0117-EV0126 and numeric recoveries)
            connectivity = result.get('connectivity_events', {})
            if connectivity.get('total', 0) > 0:
                console.print(
                    f"[yellow]⚠ Connectivity Events: {connectivity.get('total', 0)}[/yellow]"
                )
                connectivity_rows = [
                    ("Fault events", str(connectivity.get('fault_total', 0))),
                    ("Recovery events", str(connectivity.get('recovery_total', 0)))
                ]

                fault_types = connectivity.get('fault_by_type', {})
                if fault_types:
                    fault_text = ', '.join([f"{name}: {count}" for name, count in list(fault_types.items())[:5]])
                    connectivity_rows.append(("Fault types", fault_text))

                recovery_types = connectivity.get('recovery_by_type', {})
                if recovery_types:
                    recovery_text = ', '.join([f"{name}: {count}" for name, count in list(recovery_types.items())[:5]])
                    connectivity_rows.append(("Recovery types", recovery_text))

                console.print(Reporter._render_detail_matrix(connectivity_rows))

                examples = connectivity.get('examples', [])
                if examples:
                    first = examples[0]
                    console.print(
                        f"[dim]  First occurrence:[/dim] {Reporter._style_timestamps(first.get('timestamp', 'Unknown'))} [dim]-[/dim] "
                        f"{first.get('code', '')} ({first.get('kind', '')})"
                    )
                    if len(examples) > 1:
                        last = examples[-1]
                        console.print(
                            f"[dim]  Last sample:[/dim] {Reporter._style_timestamps(last.get('timestamp', 'Unknown'))} [dim]-[/dim] "
                            f"{last.get('code', '')} ({last.get('kind', '')})"
                        )
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
                sorted_events = sorted(events, key=lambda x: x.get('timestamp') or '', reverse=True)
                for event in sorted_events[:5]:
                    # Parse event dict and format nicely
                    timestamp = event.get('timestamp') or 'Unknown time'
                    code = event.get('code', 'Unknown')
                    desc = event.get('desc', 'Unknown error')
                    cause = event.get('cause', 'Unknown cause')
                    fix = event.get('fix', 'No fix available')
                    is_recovery = event.get('is_recovery', False)
                    
                    status = "[green](Recovered)[/green]" if is_recovery else "[red](Active)[/red]"
                    console.print(f"    [bold cyan]{escape(str(timestamp))}[/bold cyan] [dim]-[/dim] [yellow]{escape(str(code))}[/yellow]: {escape(str(desc))} {status}")

                    event_rows = []
                    fw_at_event = event.get('firmware_at_event')
                    if fw_at_event and fw_at_event != 'Unknown':
                        event_rows.append(("Firmware version", str(fw_at_event)))
                    event_rows.append(("Cause", str(cause)))
                    event_rows.append(("Fix", str(fix)))
                    console.print(Reporter._render_detail_matrix(event_rows, label_width=18))
                    
                    # Show correlated log context if available
                    context = event.get('context', {})
                    system_logs = context.get('system_log', [])
                    ocpp_logs = context.get('ocpp_log', [])
                    
                    if system_logs or ocpp_logs:
                        console.print(f"      [dim]Correlated logs (±5 min):[/dim]")
                        if system_logs:
                            console.print(f"        [dim]SystemLog:[/dim]")
                            for log in system_logs[:3]:  # Show first 3
                                console.print(f"          {Reporter._style_context_line(log)}")
                            if len(system_logs) > 3:
                                console.print(f"          [dim]... and {len(system_logs) - 3} more SystemLog entries[/dim]")
                        if ocpp_logs:
                            console.print(f"        [dim]OCPP Log:[/dim]")
                            for log in ocpp_logs[:3]:  # Show first 3
                                console.print(f"          {Reporter._style_context_line(log)}")
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
                    console.print(f"    {Reporter._format_timestamp_message(update.get('timestamp', ''), update.get('change', ''))}")
                console.print()
            
            console.print()

