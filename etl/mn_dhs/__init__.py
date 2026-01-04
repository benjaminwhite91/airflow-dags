"""MN DHS Scraper package."""
import structlog
from datetime import datetime
from pathlib import Path
from . import config

# Configure structured logging
def setup_logging():
    """Configure structured logging to stdout and file."""
    # Create log file path
    log_file = config.LOGS_DIR / f"mn_dhs_{datetime.now().strftime('%Y%m%d')}.log"
    
    # Configure structlog
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=open(log_file, 'a')),
        cache_logger_on_first_use=True,
    )
    
    # Also log to stdout
    import logging
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )

__version__ = "0.1.0"
