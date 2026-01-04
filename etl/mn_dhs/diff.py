"""Change detection and event generation."""
import json
import structlog
from typing import List, Dict, Any, Optional
from datetime import datetime

from . import config
from .models import ProviderSnapshot, ProviderEvent
from .db import Database

logger = structlog.get_logger()


def calculate_signal_score(
    license_status: str,
    restrictions: str,
    services: str,
    type_of_license: str
) -> int:
    """Calculate signal score based on keywords."""
    score = 0
    
    # Check license status
    status_lower = license_status.lower()
    for keyword, points in config.STATUS_KEYWORDS.items():
        if keyword in status_lower:
            score += points
            logger.debug("status_keyword_match", keyword=keyword, points=points)
    
    # Check text fields for red flag keywords
    text_fields = [restrictions, services, type_of_license]
    combined_text = " ".join(text_fields).lower()
    
    for keyword in config.TEXT_KEYWORDS:
        if keyword.lower() in combined_text:
            score += 2
            logger.debug("text_keyword_match", keyword=keyword, points=2)
    
    return score


def detect_changes(
    current: ProviderSnapshot,
    previous: Optional[Dict[str, Any]],
    snapshot_date: str
) -> List[ProviderEvent]:
    """Detect changes between current and previous snapshot."""
    events = []
    
    # New provider
    if previous is None:
        signal_score = calculate_signal_score(
            current.license_status,
            current.restrictions,
            current.services,
            current.type_of_license
        )
        
        event = ProviderEvent(
            license_number=current.license_number,
            event_date=snapshot_date,
            event_type="new_provider",
            new_value=current.license_status,
            signal_score=signal_score,
        )
        events.append(event)
        logger.info(
            "new_provider_detected",
            license_number=current.license_number,
            signal_score=signal_score
        )
        return events
    
    # Track all changed fields
    changed_fields = []
    
    # Check monitored fields for changes
    for field, event_type in config.CHANGE_FIELDS.items():
        # Map field name to snapshot attribute
        attr_map = {
            "License Status": "license_status",
            "Capacity": "capacity",
            "Current Effective Date": "current_effective_date",
            "Expiration Date": "expiration_date",
        }
        
        attr_name = attr_map[field]
        current_value = getattr(current, attr_name)
        previous_value = previous.get(attr_name)
        
        # Normalize None/"" for comparison
        current_normalized = str(current_value) if current_value else ""
        previous_normalized = str(previous_value) if previous_value else ""
        
        if current_normalized != previous_normalized:
            signal_score = 0
            
            # Calculate signal score for status changes
            if event_type == "status_change":
                signal_score = calculate_signal_score(
                    current.license_status,
                    current.restrictions,
                    current.services,
                    current.type_of_license
                )
            
            event = ProviderEvent(
                license_number=current.license_number,
                event_date=snapshot_date,
                event_type=event_type,
                field_name=field,
                old_value=previous_normalized,
                new_value=current_normalized,
                signal_score=signal_score,
            )
            events.append(event)
            changed_fields.append(field)
            
            logger.info(
                "change_detected",
                license_number=current.license_number,
                field=field,
                event_type=event_type,
                old_value=previous_normalized[:50],
                new_value=current_normalized[:50],
                signal_score=signal_score
            )
    
    # Check other fields for generic field_change events
    other_fields = [
        ("name_of_program", "Name of Program"),
        ("address_line1", "AddressLine1"),
        ("city", "City"),
        ("county", "County"),
        ("phone", "Phone"),
        ("license_holder", "License Holder"),
        ("type_of_license", "Type Of License"),
        ("restrictions", "Restrictions"),
        ("services", "Services"),
        ("email_address", "EmailAddress"),
    ]
    
    for attr_name, display_name in other_fields:
        current_value = getattr(current, attr_name, "")
        previous_value = previous.get(attr_name, "")
        
        # Normalize
        current_normalized = str(current_value) if current_value else ""
        previous_normalized = str(previous_value) if previous_value else ""
        
        if current_normalized != previous_normalized:
            # Calculate signal score if restrictions/services changed
            signal_score = 0
            if attr_name in ["restrictions", "services", "type_of_license"]:
                signal_score = calculate_signal_score(
                    current.license_status,
                    current.restrictions,
                    current.services,
                    current.type_of_license
                )
            
            changed_fields.append(display_name)
            
            event = ProviderEvent(
                license_number=current.license_number,
                event_date=snapshot_date,
                event_type="field_change",
                field_name=display_name,
                old_value=previous_normalized,
                new_value=current_normalized,
                signal_score=signal_score,
                details_json=json.dumps({"field": display_name})
            )
            events.append(event)
            
            logger.debug(
                "field_change_detected",
                license_number=current.license_number,
                field=display_name,
                old_value=previous_normalized[:50],
                new_value=current_normalized[:50]
            )
    
    # Add summary details to all events if multiple fields changed
    if len(changed_fields) > 1:
        for event in events:
            if not event.details_json:
                event.details_json = json.dumps({"changed_fields": changed_fields})
    
    return events


def generate_events(
    snapshots: List[ProviderSnapshot],
    snapshot_date: str,
    db: Database
) -> List[ProviderEvent]:
    """Generate events for all snapshots by comparing to previous state."""
    all_events = []
    
    logger.info("generating_events", num_snapshots=len(snapshots), snapshot_date=snapshot_date)
    
    for snapshot in snapshots:
        # Get previous snapshot
        previous = db.get_previous_snapshot(snapshot.license_number, snapshot_date)
        
        # Detect changes
        events = detect_changes(snapshot, previous, snapshot_date)
        all_events.extend(events)
    
    logger.info("events_generated", total_events=len(all_events), snapshot_date=snapshot_date)
    
    return all_events
