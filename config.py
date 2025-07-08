"""
Configuration module - imports from app.config
This file maintains backward compatibility during migration
"""
from app.config import config, DevelopmentConfig, ProductionConfig, TestingConfig

# Re-export for backward compatibility
__all__ = ['config', 'DevelopmentConfig', 'ProductionConfig', 'TestingConfig']