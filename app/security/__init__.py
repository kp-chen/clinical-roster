"""Security module for Clinical Roster System"""
from app.security.audit import audit_log, log_security_event, setup_audit_logging
from app.security.encryption import FieldEncryption, EncryptedField, SecureDataHandler
from app.security.rbac import (
    require_permission, require_role, check_resource_access, 
    require_resource_access, PermissionManager
)
from app.security.middleware import init_security_middleware

__all__ = [
    'audit_log', 'log_security_event', 'setup_audit_logging',
    'FieldEncryption', 'EncryptedField', 'SecureDataHandler',
    'require_permission', 'require_role', 'check_resource_access',
    'require_resource_access', 'PermissionManager',
    'init_security_middleware'
]