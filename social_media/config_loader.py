"""
Configuration loader utility for social media automation system.
Provides centralized config loading with caching.
"""

import yaml
from typing import Dict, Any
from utils.logger import log_info, log_warning

_CONFIG_CACHE = None

def load_config(config_path: str = 'social_media/config.yaml') -> Dict[str, Any]:
    """
    Load configuration from YAML file.

    Args:
        config_path: Path to config file

    Returns:
        Dict containing configuration
    """
    global _CONFIG_CACHE

    if _CONFIG_CACHE is not None:
        return _CONFIG_CACHE

    try:
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)
            _CONFIG_CACHE = config
            log_info(f"Configuration loaded from {config_path}")
            return config
    except Exception as e:
        log_warning(f"Failed to load config from {config_path}: {e}")
        return {}

def clear_config_cache():
    """Clear cached configuration (useful for testing)."""
    global _CONFIG_CACHE
    _CONFIG_CACHE = None
