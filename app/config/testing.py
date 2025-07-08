"""Testing configuration"""
from .base import Config


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    DEBUG = True
    ENV = 'testing'
    
    # Use in-memory SQLite for tests
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable CSRF for testing
    WTF_CSRF_ENABLED = False
    
    # Use simple secret key for testing
    SECRET_KEY = 'test-secret-key'
    
    # Disable rate limiting in tests
    RATELIMIT_ENABLED = False
    
    # Don't send emails during tests
    MAIL_SUPPRESS_SEND = True
    
    # Disable login requirement for tests
    LOGIN_DISABLED = False
    
    # Speed up password hashing for tests
    BCRYPT_LOG_ROUNDS = 4
    
    # Test-specific settings
    PRESERVE_CONTEXT_ON_EXCEPTION = False
    
    # Disable audit logging in tests by default
    ENABLE_AUDIT_LOGGING = False
    
    # Use test encryption key
    FIELD_ENCRYPTION_KEY = 'test-encryption-key-do-not-use-in-production='
    
    # Shorter token expiry for tests
    API_TOKEN_EXPIRY = 300  # 5 minutes
    
    # Test upload folder
    UPLOAD_FOLDER = '/tmp/test_uploads'
    
    # Logging
    LOG_LEVEL = 'ERROR'  # Only log errors during tests