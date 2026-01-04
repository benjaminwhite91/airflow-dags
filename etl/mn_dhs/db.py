"""Database operations for MN DHS scraper."""
import json
import structlog
from datetime import datetime
from typing import List, Optional, Dict, Any
import duckdb

from . import config
from .models import ProviderSnapshot, ProviderEvent, RunMetadata

logger = structlog.get_logger()


class Database:
    """Database connection and operations using DuckDB."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or str(config.DB_PATH)
        # Change extension to .duckdb
        if self.db_path.endswith('.sqlite'):
            self.db_path = self.db_path.replace('.sqlite', '.duckdb')
        
        self.conn = duckdb.connect(self.db_path)
        self._create_tables()
        logger.info("database_initialized", path=self.db_path)
    
    def _create_tables(self):
        """Create tables if they don't exist."""
        # Provider snapshots table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_snapshots (
                snapshot_date DATE NOT NULL,
                license_number VARCHAR NOT NULL,
                license_type VARCHAR NOT NULL,
                name_of_program VARCHAR,
                address_line1 VARCHAR,
                address_line2 VARCHAR,
                address_line3 VARCHAR,
                city VARCHAR,
                state VARCHAR,
                zip_code VARCHAR,
                county VARCHAR,
                phone VARCHAR,
                license_status VARCHAR NOT NULL,
                license_holder VARCHAR,
                capacity VARCHAR,
                type_of_license VARCHAR,
                restrictions VARCHAR,
                services VARCHAR,
                licensing_authority VARCHAR,
                initial_effective_date DATE,
                current_effective_date DATE,
                expiration_date DATE,
                license_holder_lives_onsite VARCHAR,
                email_address VARCHAR,
                PRIMARY KEY (snapshot_date, license_number)
            )
        """)
        
        # Provider events table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS provider_events (
                event_id VARCHAR PRIMARY KEY,
                license_number VARCHAR NOT NULL,
                event_date DATE NOT NULL,
                event_type VARCHAR NOT NULL,
                field_name VARCHAR,
                old_value VARCHAR,
                new_value VARCHAR,
                signal_score INTEGER DEFAULT 0,
                details_json VARCHAR
            )
        """)
        
        # Create indexes for better query performance
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_license 
            ON provider_events(license_number)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_date 
            ON provider_events(event_date)
        """)
        self.conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_type 
            ON provider_events(event_type)
        """)
        
        # Run metadata table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS run_metadata (
                snapshot_date DATE PRIMARY KEY,
                input_files VARCHAR,
                row_count INTEGER,
                license_types VARCHAR,
                hash_of_inputs VARCHAR,
                created_at TIMESTAMP NOT NULL
            )
        """)
    
    def insert_snapshots(self, snapshots: List[ProviderSnapshot]) -> int:
        """Insert provider snapshots into database."""
        if not snapshots:
            return 0
        
        # Convert snapshots to list of tuples
        rows = []
        for snap in snapshots:
            rows.append((
                snap.snapshot_date,
                snap.license_number,
                snap.license_type,
                snap.name_of_program,
                snap.address_line1,
                snap.address_line2,
                snap.address_line3,
                snap.city,
                snap.state,
                snap.zip_code,
                snap.county,
                snap.phone,
                snap.license_status,
                snap.license_holder,
                snap.capacity,
                snap.type_of_license,
                snap.restrictions,
                snap.services,
                snap.licensing_authority,
                snap.initial_effective_date,
                snap.current_effective_date,
                snap.expiration_date,
                snap.license_holder_lives_onsite,
                snap.email_address,
            ))
        
        # Bulk insert using DuckDB's efficient batch insert
        self.conn.executemany("""
            INSERT OR REPLACE INTO provider_snapshots VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """, rows)
        
        logger.info("snapshots_inserted", count=len(rows))
        return len(rows)
    
    def insert_events(self, events: List[ProviderEvent]) -> int:
        """Insert provider events into database."""
        if not events:
            return 0
        
        rows = []
        for event in events:
            rows.append((
                event.event_id,
                event.license_number,
                event.event_date,
                event.event_type,
                event.field_name,
                event.old_value,
                event.new_value,
                event.signal_score,
                event.details_json,
            ))
        
        self.conn.executemany("""
            INSERT OR REPLACE INTO provider_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)
        
        logger.info("events_inserted", count=len(rows))
        return len(rows)
    
    def insert_run_metadata(self, metadata: RunMetadata) -> None:
        """Insert run metadata."""
        self.conn.execute("""
            INSERT OR REPLACE INTO run_metadata VALUES (?, ?, ?, ?, ?, ?)
        """, [
            metadata.snapshot_date,
            metadata.input_files,
            metadata.row_count,
            metadata.license_types,
            metadata.hash_of_inputs,
            metadata.created_at,
        ])
        
        logger.info("metadata_inserted", snapshot_date=metadata.snapshot_date)
    
    def get_previous_snapshot(self, license_number: str, before_date: str) -> Optional[Dict[str, Any]]:
        """Get the most recent snapshot for a license number before a given date."""
        result = self.conn.execute("""
            SELECT * FROM provider_snapshots
            WHERE license_number = ?
            AND snapshot_date < ?
            ORDER BY snapshot_date DESC
            LIMIT 1
        """, [license_number, before_date]).fetchone()
        
        if result:
            # Get column names
            columns = [desc[0] for desc in self.conn.description]
            return dict(zip(columns, result))
        return None
    
    def get_all_license_numbers(self) -> set:
        """Get all known license numbers from snapshots."""
        results = self.conn.execute("""
            SELECT DISTINCT license_number FROM provider_snapshots
        """).fetchall()
        return {row[0] for row in results}
    
    def export_snapshots_to_csv(self, output_path: str, since_date: Optional[str] = None) -> None:
        """Export snapshots to CSV."""
        if since_date:
            query = """
                SELECT * FROM provider_snapshots
                WHERE snapshot_date >= ?
                ORDER BY snapshot_date, license_number
            """
            self.conn.execute(f"COPY ({query}) TO '{output_path}' (HEADER, DELIMITER ',')", [since_date])
        else:
            query = "SELECT * FROM provider_snapshots ORDER BY snapshot_date, license_number"
            self.conn.execute(f"COPY ({query}) TO '{output_path}' (HEADER, DELIMITER ',')")
        
        # Get row count for logging
        row_count = self.conn.execute(f"SELECT COUNT(*) FROM ({query})").fetchone()[0] if not since_date else \
                    self.conn.execute(f"SELECT COUNT(*) FROM ({query})", [since_date]).fetchone()[0]
        
        logger.info("snapshots_exported", path=output_path, rows=row_count)
    
    def export_events_to_csv(self, output_path: str, since_date: Optional[str] = None) -> None:
        """Export events to CSV."""
        if since_date:
            query = """
                SELECT * FROM provider_events
                WHERE event_date >= ?
                ORDER BY event_date, license_number
            """
            self.conn.execute(f"COPY ({query}) TO '{output_path}' (HEADER, DELIMITER ',')", [since_date])
        else:
            query = "SELECT * FROM provider_events ORDER BY event_date, license_number"
            self.conn.execute(f"COPY ({query}) TO '{output_path}' (HEADER, DELIMITER ',')")
        
        # Get row count for logging
        row_count = self.conn.execute(f"SELECT COUNT(*) FROM ({query})").fetchone()[0] if not since_date else \
                    self.conn.execute(f"SELECT COUNT(*) FROM ({query})", [since_date]).fetchone()[0]
        
        logger.info("events_exported", path=output_path, rows=row_count)
    
    def close(self):
        """Close database connection."""
        self.conn.close()
