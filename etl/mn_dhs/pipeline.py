"""Pipeline functions for MN DHS childcare license scraper."""
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Callable

from .ingest import load_multiple_csvs, df_to_snapshots
from .db import Database
from .diff import generate_events
from .models import RunMetadata
from . import config


def find_csv_files(raw_dir: str, snapshot_date: str, csv_paths: Optional[List[str]] = None, logger: Callable = print) -> List[Path]:
    """
    Find CSV files to process.
    
    Args:
        raw_dir: Directory containing raw CSV files
        snapshot_date: Date string (YYYY-MM-DD)
        csv_paths: Optional list of specific CSV paths to use
        logger: Logging function (defaults to print for Airflow compatibility)
        
    Returns:
        List of Path objects to CSV files
        
    Raises:
        FileNotFoundError: If no CSV files found
    """
    csv_files = []
    
    # Use provided paths if available
    if csv_paths:
        for csv_path in csv_paths:
            if csv_path and Path(csv_path).exists():
                csv_files.append(Path(csv_path))
    
    # Fallback: find any CSVs in RAW_DIR from snapshot date
    if not csv_files:
        csv_files = list(Path(raw_dir).glob(f"*{snapshot_date}.csv"))
    
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found for {snapshot_date} in {raw_dir}")
    
    logger(f"Found {len(csv_files)} CSV files: {[f.name for f in csv_files]}")
    return csv_files


def calculate_file_hash(file_paths: List[Path]) -> str:
    """Calculate SHA256 hash of input files."""
    hasher = hashlib.sha256()
    for file_path in sorted(file_paths):
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
    return hasher.hexdigest()


def run_pipeline(snapshot_date: str, db_path: str, raw_dir: str, 
                 csv_paths: Optional[List[str]] = None, logger: Callable = print) -> Dict[str, Any]:
    """
    Run the complete MN DHS scraper pipeline.
    
    Args:
        snapshot_date: Date string (YYYY-MM-DD)
        db_path: Path to DuckDB database
        raw_dir: Directory containing raw CSV files
        csv_paths: Optional list of specific CSV paths to process
        logger: Logging function (defaults to print for Airflow compatibility)
        
    Returns:
        Dictionary with pipeline results (snapshots count, events count, license types)
    """
    logger(f"Starting pipeline for snapshot_date={snapshot_date}")
    
    # Find CSV files
    csv_files = find_csv_files(raw_dir, snapshot_date, csv_paths, logger)
    logger(f"Processing {len(csv_files)} CSV files")
    
    # Load CSVs
    df = load_multiple_csvs(csv_files)
    snapshots = df_to_snapshots(df, snapshot_date)
    logger(f"Loaded {len(snapshots)} provider snapshots")
    
    # Initialize database
    db = Database(db_path)
    
    # Insert snapshots
    inserted_snapshots = db.insert_snapshots(snapshots)
    logger(f"Inserted {inserted_snapshots} snapshots")
    
    # Generate and insert events
    events = generate_events(snapshots, snapshot_date, db)
    inserted_events = db.insert_events(events)
    logger(f"Generated and inserted {inserted_events} events")
    
    # Extract unique license types
    license_types = sorted(list(set(snap.license_type for snap in snapshots)))
    
    # Calculate hash of input files
    input_hash = calculate_file_hash(csv_files)
    
    # Insert run metadata
    metadata = RunMetadata(
        snapshot_date=snapshot_date,
        input_files=json.dumps([str(f) for f in csv_files]),
        row_count=len(snapshots),
        license_types=json.dumps(license_types),
        hash_of_inputs=input_hash,
        created_at=datetime.now().isoformat()
    )
    db.insert_run_metadata(metadata)
    
    logger(f"Pipeline complete: {inserted_snapshots} snapshots, {inserted_events} events")
    logger(f"License types processed: {', '.join(license_types)}")
    
    return {
        'snapshots': inserted_snapshots,
        'events': inserted_events,
        'license_types': license_types,
    }


def export_data(db_path: str, export_dir: str, days_back: int = 7, logger: Callable = print) -> Dict[str, str]:
    """
    Export recent data to CSV files.
    
    Args:
        db_path: Path to DuckDB database
        export_dir: Directory to write export files
        days_back: Number of days of data to export
        logger: Logging function (defaults to print for Airflow compatibility)
        
    Returns:
        Dictionary with paths to exported files
    """
    logger(f"Exporting data from last {days_back} days")
    
    db = Database(db_path)
    
    from datetime import date
    since_date = (date.today() - timedelta(days=days_back)).strftime('%Y-%m-%d')
    
    snapshot_file = Path(export_dir) / f"snapshots_{datetime.now().strftime('%Y%m%d')}.csv"
    events_file = Path(export_dir) / f"events_{datetime.now().strftime('%Y%m%d')}.csv"
    
    db.export_snapshots_to_csv(str(snapshot_file), since_date)
    db.export_events_to_csv(str(events_file), since_date)
    
    logger(f"Exported snapshots to: {snapshot_file}")
    logger(f"Exported events to: {events_file}")
    
    return {
        'snapshot_file': str(snapshot_file),
        'events_file': str(events_file),
    }


def download_csv(license_type: str, snapshot_date: str, output_dir: str, logger: Callable = print) -> str:
    """
    Download CSV from MN DHS for a specific license type.
    
    Note: This is a placeholder for automated download logic.
    Currently returns the expected file path.
    
    Options for implementation:
    1. Selenium/Playwright to automate the web form
    2. Manual download and upload to a location Airflow can access
    3. API if MN DHS provides one (currently they don't)
    
    Args:
        license_type: Type of license to download
        snapshot_date: Date string (YYYY-MM-DD)
        output_dir: Directory to save the CSV
        logger: Logging function (defaults to print for Airflow compatibility)
        
    Returns:
        Path to the downloaded CSV file
    """
    output_file = Path(output_dir) / f"{license_type.replace(' ', '_')}_{snapshot_date}.csv"
    
    # TODO: Implement automated download
    logger(f"CSV should be at: {output_file}")
    logger("WARNING: Automated download not implemented - manually place CSV in output directory")
    
    return str(output_file)


# Airflow task wrappers
def airflow_download_csv(license_type: str, snapshot_date: str, **context):
    """Airflow task wrapper for downloading CSV."""
    paths = config.get_airflow_paths()
    output_file = download_csv(license_type, snapshot_date, paths['raw_dir'])
    context['task_instance'].xcom_push(key=f'csv_path_{license_type}', value=output_file)
    return output_file


def airflow_run_pipeline(snapshot_date: str, **context):
    """Airflow task wrapper for running the pipeline."""
    paths = config.get_airflow_paths()
    
    # Get CSV paths from XCom (optional - will search raw_dir if not provided)
    csv_files = []
    for license_type in config.LICENSE_TYPES:
        csv_path = context.get('task_instance', {}).xcom_pull(
            key=f'csv_path_{license_type}',
            task_ids=f'download_{license_type.replace(" ", "_")}'
        ) if 'task_instance' in context else None
        if csv_path:
            csv_files.append(csv_path)
    
    # Run pipeline (print is captured by Airflow as logs)
    result = run_pipeline(
        snapshot_date=snapshot_date,
        db_path=paths['db_path'],
        raw_dir=paths['raw_dir'],
        csv_paths=csv_files if csv_files else None,
        logger=print
    )
    
    return result


def airflow_export_data(**context):
    """Airflow task wrapper for exporting data."""
    paths = config.get_airflow_paths()
    result = export_data(
        db_path=paths['db_path'],
        export_dir=paths['export_dir'],
        days_back=7,
        logger=print
    )
    return result
