#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility functions for Delta AC MAX charger log analysis
"""

import re
import zipfile
from pathlib import Path


def extract_zips(log_directory, specific_files=None):
    """Extract password-protected ZIP files using SERIAL@delta pattern
    
    Extracts to a folder with the same name as the ZIP (without extension)
    in the same directory as the ZIP file.
    
    Args:
        log_directory: Base directory for log files (Path object)
        specific_files: Optional list of specific zip file paths to extract.
                      If None, extracts all zips in log_directory.
    
    Returns:
        List of Path objects for successfully extracted folders
    """
    print("=" * 80)
    print("EXTRACTING PASSWORD-PROTECTED ZIP FILES")
    print("=" * 80)
    print()
    
    # Determine which zip files to process
    if specific_files:
        # Convert to Path objects and validate they exist
        zip_files = []
        for file_path in specific_files:
            path = Path(file_path)
            if not path.exists():
                print(f"⚠ File not found: {file_path}")
                continue
            if not path.suffix.lower() == '.zip':
                print(f"⚠ Not a ZIP file: {file_path}")
                continue
            zip_files.append(path)
    else:
        # Default behavior: all zips in directory
        zip_files = list(log_directory.glob("*.zip"))
    
    if not zip_files:
        print("No ZIP files found to extract.")
        return []
    
    print(f"Found {len(zip_files)} ZIP file(s) to extract\n")
    
    success_count = 0
    fail_count = 0
    extracted_folders = []
    
    for zip_file in zip_files:
        # Extract serial number - handles three formats:
        # 1. Standard: [2025.11.10-00.37]KKB241600073WE.zip
        # 2. GetDiagnostics: 20250908060735_KKB233100604WE_v01.26.38.00_OCPP16JDiag.zip
        # 3. Serial-first: KKB240500105WE_v01.26.38.00_OCPP16JDiag.zip
        
        # Try standard format first (serial after bracket)
        match = re.search(r'\]([A-Z0-9]{14})', zip_file.name)
        
        # Try GetDiagnostics format (serial between underscores)
        if not match:
            match = re.search(r'_([A-Z0-9]{14})_', zip_file.name)
        
        # Try serial-first format (serial at start of filename)
        if not match:
            match = re.search(r'^([A-Z0-9]{14})_', zip_file.name)
        
        if not match:
            print(f"⚠ Could not extract serial from: {zip_file.name}")
            fail_count += 1
            continue
        
        serial = match.group(1)
        password = f"{serial}@delta"
        
        # Extract to parent directory of zip file (may differ from log_directory)
        extract_base_dir = zip_file.parent
        
        # Destination folder name based on format
        if 'OCPP16JDiag' in zip_file.name or 'Diag' in zip_file.name:
            # GetDiagnostics format: use timestamp_serial format
            # 20250908060735_KKB233100604WE_v01.26.38.00_OCPP16JDiag.zip
            # Extract to: [GetDiag]KKB233100604WE
            dest_folder = extract_base_dir / f"[GetDiag]{serial}"
        else:
            # Standard format: use zip stem
            dest_folder = extract_base_dir / zip_file.stem
        
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
            extracted_folders.append(dest_folder)
            
        except Exception as e:
            print(f"  ✗ Extraction failed: {e}\n")
            fail_count += 1
    
    print()
    print("Extraction Summary:")
    print(f"  Successful: {success_count}")
    print(f"  Failed: {fail_count}")
    print()
    
    return extracted_folders
