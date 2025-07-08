"""Development configuration"""
from .base import Config


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    ENV = 'development'
    
    # Use SQLite for development
    SQLALCHEMY_DATABASE_URI = 'sqlite:///dev_clinical_roster.db'
    
    # Less secure settings for development
    SESSION_COOKIE_SECURE = False
    WTF_CSRF_ENABLED = True
    
    # Email - use console backend for development
    MAIL_SUPPRESS_SEND = True
    
    # Enable all debug features
    SQLALCHEMY_ECHO = False  # Set to True to see SQL queries
    TEMPLATES_AUTO_RELOAD = True
    
    # Simplified rate limiting for development
    RATELIMIT_ENABLED = False
    
    # Development-specific features
    SEND_FILE_MAX_AGE_DEFAULT = 0  # Disable caching
    EXPLAIN_TEMPLATE_LOADING = False
    
    # Allow longer sessions in development
    PERMANENT_SESSION_LIFETIME = {'days': 7}
    
    # Logging
    LOG_LEVEL = 'DEBUG'