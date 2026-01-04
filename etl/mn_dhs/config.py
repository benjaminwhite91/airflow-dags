"""Configuration for MN DHS scraper."""
import os
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

# Timezone for snapshot dates
TIMEZONE = ZoneInfo("America/Chicago")

# Paths for standalone CLI usage
# Note: These are relative paths that work when running locally
# In Airflow, use get_airflow_paths() instead
PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"
DEBUG_DIR = PROJECT_ROOT / "debug"
EXPORTS_DIR = PROJECT_ROOT / "exports"
DB_PATH = DATA_DIR / "mn_dhs.duckdb"

# Expected CSV columns (order may vary)
EXPECTED_COLUMNS = {
    "License Number",
    "License Type",
    "Name of Program",
    "AddressLine1",
    "AddressLine2",
    "AddressLine3",
    "City",
    "State",
    "Zip",
    "County",
    "Phone",
    "License Status",
    "License Holder",
    "Capacity",
    "Type Of License",
    "Restrictions",
    "Services",
    "Licensing Authority",
    "Initial Effective Date",
    "Current Effective Date",
    "Expiration Date",
    "License Holder Lives Onsite",
    "EmailAddress",
}

# Date columns to parse
DATE_COLUMNS = [
    "Initial Effective Date",
    "Current Effective Date",
    "Expiration Date",
]

# Columns to monitor for changes
CHANGE_FIELDS = {
    "License Status": "status_change",
    "Capacity": "capacity_change",
    "Current Effective Date": "effective_date_change",
    "Expiration Date": "expiration_date_change",
}

# Signal scoring keywords (case-insensitive)
STATUS_KEYWORDS = {
    "revok": 3,
    "suspend": 2,
    "condition": 1,
}

TEXT_KEYWORDS = [
    "billing",
    "attendance",
    "enrollment",
    "subsidy",
    "CCAP",
    "record falsification",
]

TEXT_FIELDS_TO_SCAN = ["Restrictions", "Services", "Type Of License"]

# License types to download
LICENSE_TYPES = [
    "Child Care Center",
    "Family Child Care",
    "Group Family Child Care",
]


def get_airflow_paths():
    """
    Get paths for Airflow environment.
    
    This should be used instead of the module-level paths when running in Airflow.
    Airflow sets DATA_DIR env var to point to the mounted data directory.
    
    Returns:
        dict: Dictionary with keys 'raw_dir', 'db_path', 'export_dir'
    """
    # Get base data directory from environment (set in docker-compose.yml or Airflow config)
    base_data_dir = os.getenv("DATA_DIR", "/opt/airflow/data")
    mn_dhs_dir = os.path.join(base_data_dir, "mn_dhs")
    
    paths = {
        'raw_dir': os.path.join(mn_dhs_dir, "raw"),
        'db_path': os.path.join(mn_dhs_dir, "mn_dhs.duckdb"),
        'export_dir': os.path.join(mn_dhs_dir, "exports"),
    }
    
    # Ensure directories exist
    for key in ['raw_dir', 'export_dir']:
        os.makedirs(paths[key], exist_ok=True)
    
    return paths


def ensure_local_directories():
    """Create local directories for CLI usage."""
    for dir_path in [DATA_DIR, LOGS_DIR, DEBUG_DIR, EXPORTS_DIR]:
        dir_path.mkdir(parents=True, exist_ok=True)
