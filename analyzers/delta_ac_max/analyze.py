#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
EV Charger Log Analysis Tool
Author: Daniel Nathanson
Version: 0.0.1 (Development)
Purpose: Automated analysis of EV charger logs for common issues

Analyzes EV charger logs for:
- Backend connection failures
- MCU communication errors
- Logging gaps
- Firmware versions
- High error counts
"""

import argparse
import re
import sys
from pathlib import Path

# Fix Windows encoding issues with Unicode characters
if sys.platform == 'win32':
    try:
        # Set UTF-8 encoding for stdout
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        # Python < 3.7
        import codecs
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')

# Import modular components
from .detectors import EventDetector, OcppDetector, HardwareDetector, LmsDetector, StateMachineDetector
from .reporter import Reporter
from .utils import extract_zips


class ChargerAnalyzer:
    """Analyzes EV charger logs for common issues"""
    
    def __init__(self, log_directory=None):
        self.log_directory = Path(log_directory) if log_directory else Path.cwd()
        self.results = []
        self.event_detector = EventDetector()
        self.ocpp_detector = OcppDetector()
        self.hardware_detector = HardwareDetector()
        self.lms_detector = LmsDetector()
        self.state_detector = StateMachineDetector()
        
    def extract_zips_wrapper(self, specific_files=None):
        """Wrapper for extract_zips utility function"""
        extract_zips(self.log_directory, specific_files)
    
    def analyze_charger_log(self, folder):
        """Analyze a single charger log folder"""
        # Extract charger info from folder name
        match = re.search(r'\]([A-Z0-9]{14})(.*)$', folder.name)
        
        if not match:
            return None
        
        serial = match.group(1)
        suffix = match.group(2).strip()
        
        # Try to get ChargBox ID from Config/evcs file
        chargebox_id = self.event_detector.get_chargebox_id(folder)
        
        # Determine display ID
        if chargebox_id:
            ev_num = chargebox_id
        elif '[GetDiag]' in folder.name:
            ev_num = serial
        else:
            ev_match = re.search(r'EV(\d+)', suffix)
            ev_num = ev_match.group(1) if ev_match else serial
        
        system_log = folder / "Storage" / "SystemLog" / "SystemLog"
        
        if not system_log.exists():
            return None
        
        # Initialize analysis result structure
        analysis = {
            'ev_number': ev_num,
            'serial': serial,
            'folder_name': folder.name,
            'folder_path': str(folder),
            'firmware_version': None,
            'backend_disconnects': 0,
            'backend_disconnect_examples': [],
            'mcu_errors': 0,
            'mcu_error_examples': [],
            'error_count': 0,
            'logging_gaps': [],
            'issues': [],
            'status': 'Clean',
            'log_file': str(system_log),
            'events': [],
            'critical_events': [],
            'charging_profile_timeouts': {'count': 0, 'examples': []},
            'ocpp_rejections': {'total': 0, 'by_type': {}, 'examples': []},
            'ng_flags': {'count': 0, 'examples': []},
            'ocpp_timeouts': {'count': 0, 'examples': []},
            'rfid_faults': {'count': 0, 'examples': []},
            'state_transitions': {'transitions': [], 'invalid': [], 'suspicious': [], 'final_states': {}}
        }
        
        # Run all detectors
        events = self.event_detector.parse_events(folder)
        analysis['events'] = events
        
        analysis['charging_profile_timeouts'] = self.ocpp_detector.detect_charging_profile_timeouts(folder)
        analysis['ocpp_rejections'] = self.ocpp_detector.detect_ocpp_rejections(folder)
        analysis['ng_flags'] = self.ocpp_detector.detect_ng_flags(folder)
        analysis['ocpp_timeouts'] = self.ocpp_detector.detect_ocpp_timeouts(folder)
        analysis['rfid_faults'] = self.hardware_detector.detect_rfid_faults(folder)
        analysis['low_current_profiles'] = self.ocpp_detector.detect_low_current_profiles(folder)
        analysis['lms_issues'] = self.lms_detector.detect_lms_issues(folder, self.event_detector.parse_events)
        analysis['state_transitions'] = self.state_detector.parse_ocpp_state_transitions(folder)
        
        # Identify critical events
        critical_codes = ['EV0081', 'EV0082', 'EV0083', 'EV0084', 'EV0085', 'EV0086', 'EV0087',
                         'EV0088', 'EV0089', 'EV0090', 'EV0091', 'EV0092', 'EV0093', 'EV0094',
                         'EV0095', 'EV0096', 'EV0097', 'EV0098', 'EV0099', 'EV0100', 'EV0101',
                         'EV0110', 'EV0114', 'EV0115', 'EV0116']
        critical_events = [e for e in events if e['code'] in critical_codes]
        
        # Add log context for each critical event
        for event in critical_events:
            context = self.event_detector.get_log_context(folder, event['timestamp'], window_minutes=5)
            event['context'] = context
        
        analysis['critical_events'] = critical_events
        
        # Parse system log for baseline metrics
        try:
            with open(system_log, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.splitlines()
            
            # Get firmware version
            fw_matches = re.findall(r'Fw2Ver:\s*([\d\.]+)', content)
            if fw_matches:
                analysis['firmware_version'] = fw_matches[-1]
            
            # Count backend disconnects and get examples
            backend_fail_lines = [line for line in lines if 'Backend connection fail' in line]
            analysis['backend_disconnects'] = len(backend_fail_lines)
            analysis['backend_disconnect_examples'] = backend_fail_lines[:3]
            
            # Count MCU errors and get examples
            mcu_error_lines = [line for line in lines if re.search(r'Send Command 0x[0-9A-Fa-f]+ to MCU False', line)]
            analysis['mcu_errors'] = len(mcu_error_lines)
            analysis['mcu_error_examples'] = mcu_error_lines[:3]
            
            # Count errors
            errors = re.findall(r'\bERROR\b|\berror\b', content)
            analysis['error_count'] = len(errors)
            
            # Check for logging gaps
            jan_dates = []
            for line in lines:
                match = re.match(r'^Jan (\d+)', line)
                if match:
                    jan_dates.append(int(match.group(1)))
            
            jan_dates = sorted(set(jan_dates))
            
            if len(jan_dates) > 1:
                for i in range(len(jan_dates) - 1):
                    diff = jan_dates[i + 1] - jan_dates[i]
                    if diff > 2:
                        gap = f"Jan {jan_dates[i]} to Jan {jan_dates[i + 1]} ({diff} days)"
                        analysis['logging_gaps'].append(gap)
            
            # Determine issues and status
            if analysis['backend_disconnects'] > 10:
                analysis['issues'].append(f"High backend disconnects: {analysis['backend_disconnects']}")
                analysis['status'] = 'Issue'
            
            if analysis['mcu_errors'] > 0:
                analysis['issues'].append(f"MCU communication errors: {analysis['mcu_errors']}")
                analysis['status'] = 'Issue'
            
            if analysis['logging_gaps']:
                analysis['issues'].append(f"Logging gaps: {', '.join(analysis['logging_gaps'])}")
                analysis['status'] = 'Issue'
            
            if analysis['error_count'] > 100:
                analysis['issues'].append(f"High error count: {analysis['error_count']}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['critical_events']:
                analysis['issues'].append(f"Critical hardware events: {len(analysis['critical_events'])}")
                analysis['status'] = 'Issue'
            
            if analysis['charging_profile_timeouts']['count'] > 100:
                analysis['issues'].append(f"⚠️ CRITICAL: SetChargingProfile timeouts: {analysis['charging_profile_timeouts']['count']}")
                analysis['status'] = 'Issue'
            
            if analysis['ocpp_rejections']['total'] > 5:
                rejection_summary = ', '.join([f"{k}:{v}" for k, v in analysis['ocpp_rejections']['by_type'].items()])
                analysis['issues'].append(f"OCPP rejections: {analysis['ocpp_rejections']['total']} ({rejection_summary})")
                if analysis['ocpp_rejections']['total'] > 50:
                    analysis['status'] = 'Issue'
                elif analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['ng_flags']['count'] > 10:
                analysis['issues'].append(f"NG flags (processing errors): {analysis['ng_flags']['count']}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['ocpp_timeouts']['count'] > 20:
                analysis['issues'].append(f"OCPP timeouts: {analysis['ocpp_timeouts']['count']}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['rfid_faults']['count'] > 100:
                analysis['issues'].append(f"⚠️ CRITICAL: RFID module fault: {analysis['rfid_faults']['count']} errors")
                analysis['status'] = 'Issue'
            
            if analysis['low_current_profiles']['count'] > 10:
                analysis['issues'].append(f"⚠️ Backend issue: {analysis['low_current_profiles']['count']} low-current profiles (<6A), {analysis['low_current_profiles']['zero_current']} near-zero")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['lms_issues']['load_mgmt_comm_errors'] > 5 or analysis['lms_issues']['limit_to_nopower_count'] > 0:
                analysis['issues'].append(f"⚠️ LMS issue: {analysis['lms_issues']['load_mgmt_comm_errors']} comm errors, {analysis['lms_issues']['limit_to_nopower_count']} LIMIT_toNoPower events")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if analysis['state_transitions']['invalid']:
                analysis['issues'].append(f"OCPP protocol violations: {len(analysis['state_transitions']['invalid'])}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
            
            if len(analysis['state_transitions']['suspicious']) > 5:
                analysis['issues'].append(f"Suspicious state transitions: {len(analysis['state_transitions']['suspicious'])}")
                if analysis['status'] == 'Clean':
                    analysis['status'] = 'Warning'
        
        except Exception as e:
            print(f"Error analyzing {folder.name}: {e}")
            return None
        
        return analysis
    
    def analyze_all_chargers(self):
        """Analyze all charger log folders"""
        print("=" * 80)
        print("ANALYZING CHARGER LOGS")
        print("=" * 80)
        print()
        
        folders = [f for f in self.log_directory.iterdir() 
                   if f.is_dir() and f.name != "Original Zips"]
        
        if not folders:
            print("No log folders found.")
            return []
        
        print(f"Found {len(folders)} log folders to analyze\n")
        
        for folder in folders:
            print(f"Analyzing: {folder.name}")
            analysis = self.analyze_charger_log(folder)
            
            if analysis:
                self.results.append(analysis)
                Reporter.generate_per_charger_summary(analysis)
            
            print()
        
        return self.results
    
    def generate_summary_report(self):
        """Generate and display summary report using Reporter"""
        Reporter.generate_summary_report(self.results)


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Analyze EV charger logs for common issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                                    # Extract all ZIPs and analyze in current directory
  %(prog)s -z EV01_before.zip                 # Extract and analyze a specific ZIP file
  %(prog)s -z EV01.zip EV02.zip               # Extract and analyze multiple specific ZIPs
  %(prog)s --skip-extraction                  # Analyze already-extracted logs only
  %(prog)s --directory /path/to/logs          # Use specific directory
  %(prog)s -d /path/to/logs -z EV01.zip       # Analyze specific ZIP in specific directory
        '''
    )
    
    parser.add_argument('-d', '--directory', 
                       help='Directory containing log ZIP files (default: current directory)')
    parser.add_argument('-z', '--zip', nargs='*', metavar='FILE',
                       help='Specific ZIP file(s) to extract and analyze. Can be relative or absolute paths.')
    parser.add_argument('--skip-extraction', action='store_true',
                       help='Skip ZIP extraction, analyze existing folders only')
    
    args = parser.parse_args()
    
    # Print header
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║      EV CHARGER LOG ANALYSIS TOOL v0.0.1 (Development)        ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print("\n")
    
    # Initialize analyzer
    analyzer = ChargerAnalyzer(args.directory)
    
    print(f"Working Directory: {analyzer.log_directory}\n")
    
    # Extract ZIPs if not skipped
    if not args.skip_extraction:
        if args.zip is not None:
            # User specified specific zip file(s)
            if len(args.zip) == 0:
                print("Error: --zip requires at least one file argument")
                print("Usage: --zip FILE1.zip [FILE2.zip ...]")
                sys.exit(1)
            analyzer.extract_zips_wrapper(specific_files=args.zip)
        else:
            # Default behavior: extract all zips in directory
            zip_files = list(analyzer.log_directory.glob("*.zip"))
            if zip_files:
                analyzer.extract_zips_wrapper()
    
    # Analyze all chargers
    analyzer.analyze_all_chargers()
    
    # Generate reports
    analyzer.generate_summary_report()
    
    print("\nAnalysis complete!\n")


if __name__ == "__main__":
    main()
