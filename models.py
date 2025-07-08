"""
Compatibility layer for old model imports
This file maintains backward compatibility while the codebase is migrated
"""
from app import db
from app.models import *

# Re-export all models for backward compatibility
__all__ = [
    'db',
    'User', 'Role', 'UserRole',
    'RosterProfile', 'SharedProfile', 'GeneratedRoster',
    'EmergencyUpdate', 'UploadedFile', 'StaffPreference',
    'AuditLog', 'DataConsent', 'SecurityEvent'
]