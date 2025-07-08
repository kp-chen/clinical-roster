"""Production configuration"""
import os
from .base import Config


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    ENV = 'production'
    
    # Use PostgreSQL in production
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    if SQLALCHEMY_DATABASE_URI and SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
        # Fix for SQLAlchemy
        SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1)
    
    # Security settings
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_NAME = '__Host-session'  # More secure cookie name
    SESSION_COOKIE_SAMESITE = 'Strict'
    PERMANENT_SESSION_LIFETIME = {'hours': 2}  # Shorter sessions in production
    
    # Force HTTPS
    PREFERRED_URL_SCHEME = 'https'
    
    # Stricter file upload limits
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB in production
    
    # Performance
    SEND_FILE_MAX_AGE_DEFAULT = 31536000  # 1 year caching for static files
    
    # Email settings (must be configured via environment)
    MAIL_SUPPRESS_SEND = False
    
    # Enhanced security
    WTF_CSRF_ENABLED = True
    WTF_CSRF_SSL_STRICT = True
    
    # Require all encryption keys to be set
    if not os.environ.get('FIELD_ENCRYPTION_KEY'):
        raise ValueError("FIELD_ENCRYPTION_KEY must be set in production")
    
    if not os.environ.get('SECRET_KEY'):
        raise ValueError("SECRET_KEY must be set in production")
    
    # Database connection pool
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
        'pool_size': 10,
        'max_overflow': 20,
    }
    
    # Logging
    LOG_LEVEL = 'WARNING'
    
    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_HEADERS_ENABLED = True
    
    # Content Security Policy
    CONTENT_SECURITY_POLICY = {
        'default-src': "'self'",
        'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",
        'style-src': "'self' 'unsafe-inline'",
        'img-src': "'self' data: https:",
        'font-src': "'self'",
        'connect-src': "'self'",
        'frame-ancestors': "'none'",
        'form-action': "'self'",
        'base-uri': "'self'"
    }
    
    # CORS settings (if API is exposed)
    CORS_ORIGINS = os.environ.get('CORS_ORIGINS', '').split(',')
    
    # Monitoring
    PROMETHEUS_ENABLED = True