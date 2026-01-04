"""CLI for MN DHS scraper."""
import json
import hashlib
import structlog
from datetime import datetime, timedelta
from pathlib import Path
from typing import List
import click

from . import setup_logging, config
from .ingest import load_multiple_csvs, df_to_snapshots
from .db import Database
from .diff import generate_events
from .models import RunMetadata

logger = structlog.get_logger()


def parse_since(since_str: str) -> str:
    """Parse 'since' parameter like '30d' to YYYY-MM-DD."""
    if since_str.endswith('d'):
        days = int(since_str[:-1])
        date = datetime.now(config.TIMEZONE) - timedelta(days=days)
        return date.strftime('%Y-%m-%d')
    else:
        # Assume it's already a date string
        return since_str


@click.group()
def cli():
    """MN DHS Licensing Lookup scraper and change tracker."""
    # Ensure directories exist for CLI usage
    config.ensure_local_directories()
    
    # Setup logging with file output for CLI
    log_file = config.LOGS_DIR / f"mn_dhs_{datetime.now().strftime('%Y%m%d')}.log"
    setup_logging(log_to_file=True, log_file_path=str(log_file))


@cli.command()
@click.option(
    '--input',
    'input_paths',
    multiple=True,
    required=True,
    type=click.Path(exists=True),
    help='Input CSV file(s) or glob pattern(s)'
)
@click.option(
    '--snapshot-date',
    type=str,
    help='Snapshot date (YYYY-MM-DD). Defaults to today in America/Chicago.'
)
@click.option(
    '--db-path',
    type=str,
    help='DuckDB database path. Defaults to ./data/mn_dhs.duckdb'
)
def run(input_paths: tuple, snapshot_date: str, db_path: str):
    """Run the scraper pipeline on input CSV files."""
    # Setup
    if snapshot_date is None:
        snapshot_date = datetime.now(config.TIMEZONE).strftime('%Y-%m-%d')
    
    logger.info("starting_run", snapshot_date=snapshot_date, input_files=input_paths)
    
    # Resolve glob patterns
    resolved_files = []
    for pattern in input_paths:
        path = Path(pattern)
        if '*' in pattern:
            # Glob pattern
            parent = path.parent if path.parent.exists() else Path.cwd()
            matches = list(parent.glob(path.name))
            resolved_files.extend(matches)
        else:
            resolved_files.append(path)
    
    if not resolved_files:
        raise click.ClickException(f"No files found matching patterns: {input_paths}")
    
    logger.info("resolved_input_files", files=[str(f) for f in resolved_files])
    
    # Load and merge CSVs
    try:
        df = load_multiple_csvs(resolved_files)
    except Exception as e:
        logger.error("csv_load_failed", error=str(e))
        raise click.ClickException(f"Failed to load CSV files: {e}")
    
    # Convert to snapshots
    snapshots = df_to_snapshots(df, snapshot_date)
    logger.info("snapshots_created", count=len(snapshots))
    
    # Initialize database
    db = Database(db_path)
    
    # Insert snapshots
    inserted_snapshots = db.insert_snapshots(snapshots)
    logger.info("snapshots_persisted", count=inserted_snapshots)
    
    # Generate events
    events = generate_events(snapshots, snapshot_date, db)
    logger.info("events_generated", count=len(events))
    
    # Insert events
    inserted_events = db.insert_events(events)
    logger.info("events_persisted", count=inserted_events)
    
    # Extract unique license types from snapshots
    license_types = sorted(list(set(snap.license_type for snap in snapshots)))
    logger.info("license_types_found", types=license_types, count=len(license_types))
    
    # Calculate hash of input files
    hasher = hashlib.sha256()
    for file_path in sorted(resolved_files):
        with open(file_path, 'rb') as f:
            hasher.update(f.read())
    input_hash = hasher.hexdigest()
    
    # Insert run metadata
    metadata = RunMetadata(
        snapshot_date=snapshot_date,
        input_files=json.dumps([str(f) for f in resolved_files]),
        row_count=len(snapshots),
        license_types=json.dumps(license_types),
        hash_of_inputs=input_hash,
        created_at=datetime.now().isoformat()
    )
    db.insert_run_metadata(metadata)
    
    logger.info(
        "run_complete",
        snapshot_date=snapshot_date,
        snapshots=inserted_snapshots,
        events=inserted_events,
        license_types=license_types
    )
    
    click.echo(f"✓ Run complete for {snapshot_date}")
    click.echo(f"  Snapshots: {inserted_snapshots}")
    click.echo(f"  Events: {inserted_events}")
    click.echo(f"  License Types: {', '.join(license_types)}")


@cli.command()
@click.option(
    '--outdir',
    type=click.Path(),
    default='./exports',
    help='Output directory for CSV exports'
)
@click.option(
    '--since',
    type=str,
    help='Export data since this date (YYYY-MM-DD or "30d" format)'
)
@click.option(
    '--db-path',
    type=str,
    help='DuckDB database path. Defaults to ./data/mn_dhs.duckdb'
)
def export(outdir: str, since: str, db_path: str):
    """Export snapshots and events to CSV files."""
    outdir_path = Path(outdir)
    outdir_path.mkdir(parents=True, exist_ok=True)
    
    # Parse since parameter
    since_date = None
    if since:
        since_date = parse_since(since)
        logger.info("exporting_since", since_date=since_date)
    
    # Initialize database
    db = Database(db_path)
    
    # Export snapshots
    snapshots_file = outdir_path / f"provider_snapshots_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    db.export_snapshots_to_csv(str(snapshots_file), since_date)
    click.echo(f"✓ Snapshots exported to: {snapshots_file}")
    
    # Export events
    events_file = outdir_path / f"provider_events_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    db.export_events_to_csv(str(events_file), since_date)
    click.echo(f"✓ Events exported to: {events_file}")


if __name__ == '__main__':
    cli()
