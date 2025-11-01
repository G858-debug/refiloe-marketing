"""
Logging utility for Refiloe Marketing
Provides consistent logging across all modules
"""

import logging
import os
from datetime import datetime
import pytz

# Configure logging
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

# Create logger
logger = logging.getLogger('refiloe_marketing')
logger.setLevel(getattr(logging, LOG_LEVEL))

# Create console handler
console_handler = logging.StreamHandler()
console_handler.setLevel(getattr(logging, LOG_LEVEL))
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

# Add handler to logger
logger.addHandler(console_handler)

# Timezone for timestamps
SA_TZ = pytz.timezone('Africa/Johannesburg')


def log_info(message: str):
    """Log info message"""
    logger.info(message)


def log_error(message: str):
    """Log error message"""
    logger.error(message)


def log_warning(message: str):
    """Log warning message"""
    logger.warning(message)


def log_debug(message: str):
    """Log debug message"""
    logger.debug(message)


def get_sa_timestamp():
    """Get current timestamp in South African timezone"""
    return datetime.now(SA_TZ).strftime('%Y-%m-%d %H:%M:%S %Z')
