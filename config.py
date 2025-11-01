"""
Configuration file for Refiloe Marketing Application
Loads settings from environment variables
"""

import os
from datetime import timedelta

class Config:
    """Base configuration"""
    
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'
    
    # Supabase settings
    SUPABASE_URL = os.getenv('SUPABASE_URL')
    SUPABASE_SERVICE_KEY = os.getenv('SUPABASE_SERVICE_KEY')
    SUPABASE_ANON_KEY = os.getenv('SUPABASE_ANON_KEY')
    
    # AI Services
    ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')
    REPLICATE_API_TOKEN = os.getenv('REPLICATE_API_TOKEN')
    
    # Social Media
    FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv('FACEBOOK_PAGE_ACCESS_TOKEN')
    FACEBOOK_PAGE_ID = os.getenv('FACEBOOK_PAGE_ID')
    
    # Feature flags
    ENABLE_SOCIAL_MEDIA = os.getenv('ENABLE_SOCIAL_MEDIA', 'true').lower() == 'true'
    
    # Scheduler settings
    SCHEDULER_API_ENABLED = True
    SCHEDULER_TIMEZONE = 'Africa/Johannesburg'
    
    # Logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    @staticmethod
    def validate():
        """Validate required environment variables"""
        required_vars = [
            'SUPABASE_URL',
            'ANTHROPIC_API_KEY'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        return True


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': ProductionConfig
}
