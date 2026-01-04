"""Data models for MN DHS scraper."""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
import uuid


@dataclass
class ProviderSnapshot:
    """Single snapshot of a provider on a given date."""
    snapshot_date: str  # YYYY-MM-DD
    license_number: str
    license_type: str
    name_of_program: str
    address_line1: str
    address_line2: str
    address_line3: str
    city: str
    state: str
    zip_code: str
    county: str
    phone: str
    license_status: str
    license_holder: str
    capacity: Optional[str]
    type_of_license: str
    restrictions: str
    services: str
    licensing_authority: str
    initial_effective_date: Optional[str]  # YYYY-MM-DD
    current_effective_date: Optional[str]  # YYYY-MM-DD
    expiration_date: Optional[str]  # YYYY-MM-DD
    license_holder_lives_onsite: str
    email_address: str


@dataclass
class ProviderEvent:
    """Change event for a provider."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    license_number: str = ""
    event_date: str = ""  # YYYY-MM-DD
    event_type: str = ""  # new_provider, status_change, capacity_change, etc.
    field_name: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    signal_score: int = 0
    details_json: Optional[str] = None


@dataclass
class RunMetadata:
    """Metadata for a scraper run."""
    snapshot_date: str  # YYYY-MM-DD
    input_files: str  # JSON list
    row_count: int
    license_types: str  # JSON list of unique license types in this run
    hash_of_inputs: Optional[str]
    created_at: str  # ISO datetime
