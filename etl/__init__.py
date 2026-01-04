"""MN DHS Scraper package."""
import structlog
import logging
from datetime import datetime
from pathlib import Path

__version__ = "0.1.0"


def setup_logging(log_to_file: bool = False, log_file_path: str = None):
    """
    Configure structured logging.
    
    Args:
        log_to_file: Whether to log to a file (for CLI usage)
        log_file_path: Path to log file (only used if log_to_file=True)
    
    Note:
        In Airflow, set log_to_file=False to let Airflow capture stdout.
        For CLI usage, set log_to_file=True with a log file path.
    """
    processors = [
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.format_exc_info,
        structlog.processors.JSONRenderer()
    ]
    
    if log_to_file and log_file_path:
        # For CLI usage - log to file
        try:
            log_file = open(log_file_path, 'a')
            structlog.configure(
                processors=processors,
                wrapper_class=structlog.BoundLogger,
                context_class=dict,
                logger_factory=structlog.PrintLoggerFactory(file=log_file),
                cache_logger_on_first_use=True,
            )
        except (IOError, OSError) as e:
            # Fallback to stdout if file can't be opened
            print(f"Warning: Could not open log file {log_file_path}: {e}")
            structlog.configure(
                processors=processors,
                wrapper_class=structlog.BoundLogger,
                context_class=dict,
                logger_factory=structlog.PrintLoggerFactory(),
                cache_logger_on_first_use=True,
            )
    else:
        # For Airflow - log to stdout (Airflow will capture it)
        structlog.configure(
            processors=processors,
            wrapper_class=structlog.BoundLogger,
            context_class=dict,
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )
    
    # Also configure standard logging (some libraries use this)
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )
