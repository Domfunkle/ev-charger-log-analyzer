#!/usr/bin/env python3
"""
EV Charger Log Analysis Tool
Author: Daniel Nathanson
Version: 1.0
Purpose: Automated analysis of EV charger logs for common issues

Analyzes EV charger logs for:
- Backend connection failures
- MCU communication errors
- Logging gaps
- Firmware versions
- High error counts
"""

import argparse
import csv
import re
import zipfile
from pathlib import Path
from collections import defaultdict
from datetime import datetime
import sys


class ChargerAnalyzer:
    """Analyzes EV charger logs for common issues"""
    
    def __init__(self, log_directory=None):
        self.log_directory = Path(log_directory) if log_directory else Path.cwd()
        self.results = []
        
    def extract_zips(self, move_to_archive=True):
        """Extract password-protected ZIP files using SERIAL@delta pattern"""
        print("=" * 80)
        print("EXTRACTING PASSWORD-PROTECTED ZIP FILES")
        print("=" * 80)
        print()
        
        zip_files = list(self.log_directory.glob("*.zip"))
        
        if not zip_files:
            print("No ZIP files found in directory.")
            return
        
        print(f"Found {len(zip_files)} ZIP files\n")
        
        success_count = 0
        fail_count = 0
        
        for zip_file in zip_files:
            # Extract serial number (14 characters after ']')
            match = re.search(r'\]([A-Z0-9]{14})', zip_file.name)
            
            if not match:
                print(f"⚠ Could not extract serial from: {zip_file.name}")
                fail_count += 1
                continue
            
            serial = match.group(1)
            password = f"{serial}@delta"
            dest_folder = self.log_directory / zip_file.stem
            
            print(f"Processing: {zip_file.name}")
            print(f"  Serial: {serial}")
            print(f"  Password: {password}")
            print(f"  Destination: {dest_folder}")
            
            try:
                # Create destination folder
                dest_folder.mkdir(exist_ok=True)
                
                # Extract ZIP with password
                with zipfile.ZipFile(zip_file, 'r') as zip_ref:
                    zip_ref.extractall(dest_folder, pwd=password.encode('utf-8'))
                
                print("  ✓ Extracted successfully\n")
                success_count += 1
                
            except Exception as e:
                print(f"  ✗ Extraction failed: {e}\n")
                fail_count += 1
        
        print(f"\nExtraction Summary:")
        print(f"  Successful: {success_count}")
        print(f"  Failed: {fail_count}\n")
        
        # Move ZIPs to archive folder
        if move_to_archive and success_count > 0:
            archive_dir = self.log_directory / "Original Zips"
            archive_dir.mkdir(exist_ok=True)
            
            print("Moving ZIP files to 'Original Zips' folder...")
            for zip_file in self.log_directory.glob("*.zip"):
                zip_file.rename(archive_dir / zip_file.name)
            print("✓ ZIPs archived\n")
    
    def analyze_charger_log(self, folder):
        """Analyze a single charger log folder"""
        # Extract charger info from folder name
        match = re.search(r'\]([A-Z0-9]{14})(.*)$', folder.name)
        if not match:
            return None
        
        serial = match.group(1)
        suffix = match.group(2).strip()
        
        # Extract EV number
        ev_match = re.search(r'EV(\d+)', suffix)
        ev_num = ev_match.group(1) if ev_match else "Unknown"
        
        is_updated = "-UP" in suffix
        
        system_log = folder / "Storage" / "SystemLog" / "SystemLog"
        
        if not system_log.exists():
            return None
        
        analysis = {
            'ev_number': ev_num,
            'serial': serial,
            'folder_name': folder.name,
            'is_updated': is_updated,
            'firmware_version': None,
            'backend_disconnects': 0,
            'mcu_errors': 0,
            'error_count': 0,
            'logging_gaps': [],
            'issues': [],
            'status': 'Clean'
        }
        
        try:
            with open(system_log, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                lines = content.splitlines()
            
            # Get firmware version
            fw_matches = re.findall(r'Fw2Ver:\s*([\d\.]+)', content)
            if fw_matches:
                analysis['firmware_version'] = fw_matches[-1]
            
            # Count backend disconnects
            backend_fails = re.findall(r'Backend connection fail', content)
            analysis['backend_disconnects'] = len(backend_fails)
            
            # Count MCU errors
            mcu_errors = re.findall(r'Send Command 0x[0-9A-F]+ to MCU False', content)
            analysis['mcu_errors'] = len(mcu_errors)
            
            # Count errors
            errors = re.findall(r'\bERROR\b|\berror\b', content)
            analysis['error_count'] = len(errors)
            
            # Check for logging gaps (January dates only for simplicity)
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
            
            # Determine issues
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
                
                status_color = {
                    'Issue': '\033[91m',      # Red
                    'Warning': '\033[93m',    # Yellow
                    'Clean': '\033[92m'       # Green
                }.get(analysis['status'], '')
                
                reset_color = '\033[0m'
                
                print(f"  EV{analysis['ev_number']}: {status_color}{analysis['status']}{reset_color}")
                
                if analysis['issues']:
                    for issue in analysis['issues']:
                        print(f"    - {issue}")
        
        return self.results
    
    def generate_summary_report(self):
        """Generate and display summary report"""
        if not self.results:
            print("\nNo results to display.")
            return
        
        print("\n" + "=" * 80)
        print("SUMMARY REPORT")
        print("=" * 80)
        print()
        
        # Group by EV number
        grouped = defaultdict(list)
        for result in self.results:
            grouped[result['ev_number']].append(result)
        
        clean_count = 0
        issue_count = 0
        
        for ev_num in sorted(grouped.keys(), key=lambda x: int(x) if x.isdigit() else 999):
            chargers = sorted(grouped[ev_num], key=lambda x: not x['is_updated'])
            
            has_issues = any(c['status'] != 'Clean' for c in chargers)
            
            color = '\033[93m' if has_issues else '\033[92m'  # Yellow or Green
            reset = '\033[0m'
            
            print(f"{color}EV{ev_num.zfill(2)}{reset}")
            
            if has_issues:
                issue_count += 1
            else:
                clean_count += 1
            
            for charger in chargers:
                label = "  [AFTER UPDATE]" if charger['is_updated'] else "  [BEFORE UPDATE]"
                print(label)
                
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
            
            print()
        
        print("=" * 80)
        print("FINAL SUMMARY")
        print("=" * 80)
        print(f"Total Chargers Analyzed: {len(grouped)}")
        print(f"\033[92mClean: {clean_count}\033[0m")
        
        issue_color = '\033[91m' if issue_count > 0 else '\033[92m'
        print(f"{issue_color}With Issues: {issue_count}\033[0m")
        print()
    
    def export_to_csv(self, filename=None):
        """Export results to CSV file"""
        if not self.results:
            return
        
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"ChargerAnalysisResults_{timestamp}.csv"
        
        csv_path = self.log_directory / filename
        
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['ev_number', 'serial', 'folder_name', 'is_updated', 
                         'firmware_version', 'backend_disconnects', 'mcu_errors', 
                         'error_count', 'logging_gaps', 'issues', 'status']
            
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            
            for result in self.results:
                row = result.copy()
                row['logging_gaps'] = '; '.join(row['logging_gaps'])
                row['issues'] = '; '.join(row['issues'])
                writer.writerow(row)
        
        print(f"Detailed results exported to: {csv_path}")


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description='Analyze EV charger logs for common issues',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                              # Extract ZIPs and analyze in current directory
  %(prog)s --skip-extraction            # Analyze already-extracted logs
  %(prog)s --directory /path/to/logs    # Use specific directory
  %(prog)s --no-archive                 # Don't move ZIPs after extraction
        '''
    )
    
    parser.add_argument('-d', '--directory', 
                       help='Directory containing log ZIP files (default: current directory)')
    parser.add_argument('--skip-extraction', action='store_true',
                       help='Skip ZIP extraction, analyze existing folders only')
    parser.add_argument('--no-archive', action='store_true',
                       help='Do not move ZIP files to archive folder after extraction')
    
    args = parser.parse_args()
    
    # Print header
    print("\n")
    print("╔═══════════════════════════════════════════════════════════════╗")
    print("║          EV CHARGER LOG ANALYSIS TOOL v1.0                   ║")
    print("╚═══════════════════════════════════════════════════════════════╝")
    print("\n")
    
    # Initialize analyzer
    analyzer = ChargerAnalyzer(args.directory)
    
    print(f"Working Directory: {analyzer.log_directory}\n")
    
    # Extract ZIPs if not skipped
    if not args.skip_extraction:
        zip_files = list(analyzer.log_directory.glob("*.zip"))
        if zip_files:
            analyzer.extract_zips(move_to_archive=not args.no_archive)
    
    # Analyze all chargers
    analyzer.analyze_all_chargers()
    
    # Generate reports
    analyzer.generate_summary_report()
    analyzer.export_to_csv()
    
    print("\nAnalysis complete!\n")


if __name__ == "__main__":
    main()
