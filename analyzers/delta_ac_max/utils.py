#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Utility functions for Delta AC MAX charger log analysis
"""

import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from rich.console import Console
from rich.live import Live
from rich.table import Table


console = Console(highlight=False)


def _prepare_zip_task(zip_file):
    """Prepare extraction metadata for a zip file."""
    match = re.search(r'\]([A-Z0-9]{14})', zip_file.name)

    if not match:
        match = re.search(r'_([A-Z0-9]{14})_', zip_file.name)

    if not match:
        match = re.search(r'^([A-Z0-9]{14})_', zip_file.name)

    if not match:
        return None

    serial = match.group(1)
    password = f"{serial}@delta"

    extract_base_dir = zip_file.parent
    if 'OCPP16JDiag' in zip_file.name or 'Diag' in zip_file.name:
        dest_folder = extract_base_dir / f"[GetDiag]{serial}"
    else:
        dest_folder = extract_base_dir / zip_file.stem

    return {
        'zip_file': zip_file,
        'serial': serial,
        'password': password,
        'dest_folder': dest_folder,
    }


def _extract_single_zip(task, extraction_status=None, status_lock=None):
    """Extract one password-protected zip and return structured result."""
    zip_file = task['zip_file']
    dest_folder = task['dest_folder']
    password = task['password']

    if extraction_status is not None:
        if status_lock:
            with status_lock:
                extraction_status[zip_file.name]['status'] = 'Extracting'
        else:
            extraction_status[zip_file.name]['status'] = 'Extracting'

    try:
        dest_folder.mkdir(exist_ok=True)
        with zipfile.ZipFile(zip_file, 'r') as zip_ref:
            zip_ref.extractall(dest_folder, pwd=password.encode('utf-8'))

        if extraction_status is not None:
            if status_lock:
                with status_lock:
                    extraction_status[zip_file.name]['status'] = 'Complete'
            else:
                extraction_status[zip_file.name]['status'] = 'Complete'

        return {
            'ok': True,
            'zip_file': zip_file,
            'serial': task['serial'],
            'password': password,
            'dest_folder': dest_folder,
            'error': None,
        }
    except Exception as error:
        if extraction_status is not None:
            if status_lock:
                with status_lock:
                    extraction_status[zip_file.name]['status'] = 'Failed'
                    extraction_status[zip_file.name]['error'] = str(error)
            else:
                extraction_status[zip_file.name]['status'] = 'Failed'
                extraction_status[zip_file.name]['error'] = str(error)

        return {
            'ok': False,
            'zip_file': zip_file,
            'serial': task['serial'],
            'password': password,
            'dest_folder': dest_folder,
            'error': str(error),
        }


def _create_extraction_progress_table(extraction_status, zip_order, spinner_frame=0):
    """Create a live progress table for ZIP extraction."""
    spinner_frames = ['⠋', '⠙', '⠹', '⠸', '⠼', '⠴', '⠦', '⠧', '⠇', '⠏']
    spinner = spinner_frames[spinner_frame % len(spinner_frames)]

    table = Table(title="Extraction Progress", show_header=True, header_style="bold cyan")
    table.add_column("ZIP File", style="cyan", width=44)
    table.add_column("Serial", width=16)
    table.add_column("Status", width=12)
    table.add_column("Destination", style="dim")

    for zip_name in zip_order:
        info = extraction_status.get(zip_name, {})
        status = info.get('status', 'Queued')
        if status == 'Complete':
            status_text = "[green]✓ Complete[/green]"
        elif status == 'Failed':
            status_text = "[red]✗ Failed[/red]"
        elif status == 'Extracting':
            status_text = f"[yellow]{spinner} Extracting[/yellow]"
        else:
            status_text = "[dim]⏳ Queued[/dim]"

        destination = info.get('destination', '-')
        if len(destination) > 50:
            destination = '...' + destination[-47:]

        table.add_row(
            zip_name if len(zip_name) <= 42 else zip_name[:39] + '...',
            info.get('serial', ''),
            status_text,
            destination
        )

    return table


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
    console.print("=" * 80)
    console.print("EXTRACTING PASSWORD-PROTECTED ZIP FILES")
    console.print("=" * 80)
    console.print()
    
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
        console.print("No ZIP files found to extract.")
        return []
    
    console.print(f"Found {len(zip_files)} ZIP file(s) to extract\n")
    
    prepared_tasks = []
    fail_count = 0
    for zip_file in zip_files:
        task = _prepare_zip_task(zip_file)
        if not task:
            console.print(f"⚠ Could not extract serial from: {zip_file.name}")
            fail_count += 1
            continue
        prepared_tasks.append(task)

    success_count = 0
    extracted_folders = []

    if prepared_tasks:
        worker_count = min(4, len(prepared_tasks))
        console.print(f"Using {worker_count} parallel extraction worker(s)\n")

        extraction_status = {}
        zip_order = []
        for task in prepared_tasks:
            zip_name = task['zip_file'].name
            zip_order.append(zip_name)
            extraction_status[zip_name] = {
                'serial': task['serial'],
                'status': 'Queued',
                'destination': str(task['dest_folder']),
                'error': ''
            }

        status_lock = threading.Lock()

        results = []
        spinner_frame = 0
        with Live(_create_extraction_progress_table(extraction_status, zip_order, spinner_frame=spinner_frame), refresh_per_second=8, console=console) as live:
            with ThreadPoolExecutor(max_workers=worker_count) as executor:
                futures = [
                    executor.submit(_extract_single_zip, task, extraction_status, status_lock)
                    for task in prepared_tasks
                ]

                while True:
                    spinner_frame += 1
                    live.update(_create_extraction_progress_table(extraction_status, zip_order, spinner_frame=spinner_frame))
                    if all(future.done() for future in futures):
                        break
                    time.sleep(0.1)

                for future in as_completed(futures):
                    results.append(future.result())

                live.update(_create_extraction_progress_table(extraction_status, zip_order, spinner_frame=spinner_frame))

        console.print()
        for result in results:
            if result['ok']:
                success_count += 1
                extracted_folders.append(result['dest_folder'])
            else:
                fail_count += 1

        failed_results = [result for result in results if not result['ok']]
        if failed_results:
            console.print("[yellow]Extraction failures:[/yellow]")
            for result in failed_results:
                console.print(f"  {result['zip_file'].name}: {result['error']}")
            console.print()
    
    console.print()
    console.print("Extraction Summary:")
    console.print(f"  Successful: {success_count}")
    console.print(f"  Failed: {fail_count}")
    console.print()
    
    return extracted_folders
