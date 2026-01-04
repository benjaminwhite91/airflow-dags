"""CSV ingestion and normalization."""
import re
import structlog
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
import pandas as pd

from . import config
from .models import ProviderSnapshot

logger = structlog.get_logger()


def normalize_zip(zip_str: str) -> str:
    """Normalize zip code to 5 or 5+4 format."""
    if pd.isna(zip_str):
        return ""
    
    # Strip all whitespace
    cleaned = str(zip_str).replace(" ", "").strip()
    
    # Return as-is if valid format
    if re.match(r'^\d{5}(-\d{4})?$', cleaned):
        return cleaned
    
    # Try to extract first 5 or 9 digits
    digits = re.sub(r'\D', '', cleaned)
    if len(digits) >= 5:
        if len(digits) >= 9:
            return f"{digits[:5]}-{digits[5:9]}"
        return digits[:5]
    
    return cleaned


def normalize_phone(phone_str: str) -> str:
    """Normalize phone number by stripping spaces."""
    if pd.isna(phone_str):
        return ""
    return str(phone_str).strip().replace(" ", "")


def parse_date(date_str: str) -> str | None:
    """Parse MM/DD/YYYY to YYYY-MM-DD."""
    if pd.isna(date_str) or str(date_str).strip() == "":
        return None
    
    try:
        # Handle MM/DD/YYYY format
        dt = pd.to_datetime(date_str, format='%m/%d/%Y')
        return dt.strftime('%Y-%m-%d')
    except:
        logger.warning("date_parse_failed", date_str=date_str)
        return None


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize a raw CSV dataframe."""
    # Drop unnamed columns
    unnamed_cols = [col for col in df.columns if re.match(r'^Unnamed:', str(col))]
    if unnamed_cols:
        # Only drop if entirely null
        for col in unnamed_cols:
            if df[col].isna().all():
                df = df.drop(columns=[col])
                logger.info("dropped_unnamed_column", column=col)
    
    # Strip whitespace from all string columns
    for col in df.columns:
        if df[col].dtype == 'object':
            df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else "")
    
    # Normalize specific fields
    if 'Zip' in df.columns:
        df['Zip'] = df['Zip'].apply(normalize_zip)
    
    if 'Phone' in df.columns:
        df['Phone'] = df['Phone'].apply(normalize_phone)
    
    # Parse dates
    for date_col in config.DATE_COLUMNS:
        if date_col in df.columns:
            df[date_col] = df[date_col].apply(parse_date)
    
    # Ensure License Number is string
    if 'License Number' in df.columns:
        df['License Number'] = df['License Number'].astype(str)
    
    return df


def validate_columns(df: pd.DataFrame) -> None:
    """Validate that all expected columns are present."""
    actual_cols = set(df.columns)
    # Ignore any Unnamed columns
    actual_cols = {col for col in actual_cols if not re.match(r'^Unnamed:', str(col))}
    
    missing = config.EXPECTED_COLUMNS - actual_cols
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    
    extra = actual_cols - config.EXPECTED_COLUMNS
    if extra:
        logger.warning("extra_columns_found", columns=sorted(extra))


def load_csv(file_path: Path) -> pd.DataFrame:
    """Load and validate a single CSV file."""
    logger.info("loading_csv", file=str(file_path))
    
    try:
        # Read CSV with flexible encoding
        df = pd.read_csv(file_path, dtype=str, encoding='utf-8')
    except UnicodeDecodeError:
        # Fallback to latin1 if utf-8 fails
        df = pd.read_csv(file_path, dtype=str, encoding='latin1')
    
    logger.info("csv_loaded", rows=len(df), file=str(file_path))
    
    # Validate structure
    validate_columns(df)
    
    # Clean and normalize
    df = clean_dataframe(df)
    
    return df


def load_multiple_csvs(file_paths: List[Path]) -> pd.DataFrame:
    """Load multiple CSV files and deduplicate."""
    dfs = []
    
    for file_path in file_paths:
        try:
            df = load_csv(file_path)
            dfs.append(df)
        except Exception as e:
            logger.error("csv_load_failed", file=str(file_path), error=str(e))
            # Save problematic CSV to debug
            debug_path = config.DEBUG_DIR / f"failed_{file_path.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
            import shutil
            shutil.copy(file_path, debug_path)
            raise
    
    if not dfs:
        raise ValueError("No valid CSV files loaded")
    
    # Concatenate all dataframes
    combined = pd.concat(dfs, ignore_index=True)
    logger.info("combined_csvs", total_rows=len(combined), num_files=len(dfs))
    
    # Deduplicate by license number
    # Prefer rows with non-null capacity, then non-null dates
    combined['_has_capacity'] = combined['Capacity'].notna() & (combined['Capacity'] != "")
    combined['_has_dates'] = (
        combined['Current Effective Date'].notna() | 
        combined['Expiration Date'].notna()
    )
    
    # Sort to put best rows first
    combined = combined.sort_values(
        by=['License Number', '_has_capacity', '_has_dates'],
        ascending=[True, False, False]
    )
    
    # Track duplicates
    duplicates = combined.duplicated(subset=['License Number'], keep='first')
    if duplicates.any():
        logger.warning(
            "deduplicating_license_numbers",
            num_duplicates=duplicates.sum(),
            duplicate_licenses=combined[duplicates]['License Number'].tolist()
        )
    
    # Keep first occurrence of each license number
    combined = combined.drop_duplicates(subset=['License Number'], keep='first')
    
    # Drop helper columns
    combined = combined.drop(columns=['_has_capacity', '_has_dates'])
    
    return combined


def df_to_snapshots(df: pd.DataFrame, snapshot_date: str) -> List[ProviderSnapshot]:
    """Convert dataframe to list of ProviderSnapshot objects."""
    snapshots = []
    
    for _, row in df.iterrows():
        snapshot = ProviderSnapshot(
            snapshot_date=snapshot_date,
            license_number=row['License Number'],
            license_type=row['License Type'],
            name_of_program=row['Name of Program'],
            address_line1=row['AddressLine1'],
            address_line2=row['AddressLine2'],
            address_line3=row['AddressLine3'],
            city=row['City'],
            state=row['State'],
            zip_code=row['Zip'],
            county=row['County'],
            phone=row['Phone'],
            license_status=row['License Status'],
            license_holder=row['License Holder'],
            capacity=row['Capacity'] if row['Capacity'] else None,
            type_of_license=row['Type Of License'],
            restrictions=row['Restrictions'],
            services=row['Services'],
            licensing_authority=row['Licensing Authority'],
            initial_effective_date=row['Initial Effective Date'],
            current_effective_date=row['Current Effective Date'],
            expiration_date=row['Expiration Date'],
            license_holder_lives_onsite=row['License Holder Lives Onsite'],
            email_address=row['EmailAddress'],
        )
        snapshots.append(snapshot)
    
    return snapshots
