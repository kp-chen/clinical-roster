"""Audit logging models for compliance"""
from datetime import datetime
from app import db


class AuditLog(db.Model):
    """Comprehensive audit trail for HIPAA/PDPA compliance"""
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    action = db.Column(db.String(50), nullable=False)  # login, logout, view_roster, etc.
    resource_type = db.Column(db.String(50))  # roster, profile, user, etc.
    resource_id = db.Column(db.Integer)
    
    # Request details
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    request_method = db.Column(db.String(10))
    request_path = db.Column(db.String(255))
    
    # Response details
    response_status = db.Column(db.Integer)
    error_message = db.Column(db.Text)
    
    # Timing
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    duration_ms = db.Column(db.Integer)  # Request duration in milliseconds
    
    # Additional context
    details = db.Column(db.JSON)  # Additional contextual information
    
    # Indexes for performance
    __table_args__ = (
        db.Index('idx_audit_user_timestamp', 'user_id', 'timestamp'),
        db.Index('idx_audit_action_timestamp', 'action', 'timestamp'),
        db.Index('idx_audit_resource', 'resource_type', 'resource_id'),
    )
    
    # Action constants
    ACTION_LOGIN = 'login'
    ACTION_LOGOUT = 'logout'
    ACTION_LOGIN_FAILED = 'login_failed'
    ACTION_MFA_SETUP = 'mfa_setup'
    ACTION_MFA_VERIFIED = 'mfa_verified'
    ACTION_PASSWORD_RESET = 'password_reset'
    
    ACTION_ROSTER_VIEW = 'roster_view'
    ACTION_ROSTER_CREATE = 'roster_create'
    ACTION_ROSTER_EDIT = 'roster_edit'
    ACTION_ROSTER_DELETE = 'roster_delete'
    ACTION_ROSTER_EXPORT = 'roster_export'
    ACTION_ROSTER_SHARE = 'roster_share'
    
    ACTION_FILE_UPLOAD = 'file_upload'
    ACTION_FILE_PARSE = 'file_parse'
    ACTION_FILE_DELETE = 'file_delete'
    
    ACTION_USER_CREATE = 'user_create'
    ACTION_USER_EDIT = 'user_edit'
    ACTION_USER_DELETE = 'user_delete'
    ACTION_PERMISSION_CHANGE = 'permission_change'
    
    ACTION_DATA_EXPORT = 'data_export'
    ACTION_SETTINGS_CHANGE = 'settings_change'
    
    @classmethod
    def log(cls, action, user_id=None, resource_type=None, resource_id=None, 
            details=None, request=None, response=None, duration_ms=None):
        """Create an audit log entry"""
        entry = cls(
            action=action,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            duration_ms=duration_ms
        )
        
        if request:
            entry.ip_address = request.remote_addr
            entry.user_agent = request.headers.get('User-Agent', '')[:255]
            entry.request_method = request.method
            entry.request_path = request.path
        
        if response:
            entry.response_status = response.status_code
        
        db.session.add(entry)
        db.session.commit()
        
        return entry
    
    def __repr__(self):
        return f'<AuditLog {self.action} by user {self.user_id} at {self.timestamp}>'


class DataConsent(db.Model):
    """Track data processing consent for PDPA compliance"""
    __tablename__ = 'data_consents'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    consent_type = db.Column(db.String(50), nullable=False)  # 'roster_sharing', 'email_notifications', etc.
    purpose = db.Column(db.Text)  # Purpose of data processing
    granted = db.Column(db.Boolean, default=False)
    granted_at = db.Column(db.DateTime)
    revoked_at = db.Column(db.DateTime)
    ip_address = db.Column(db.String(45))
    consent_text_version = db.Column(db.String(20))  # Version of consent text shown
    
    # Indexes
    __table_args__ = (
        db.Index('idx_consent_user_type', 'user_id', 'consent_type'),
    )
    
    # Consent types
    TYPE_ROSTER_SHARING = 'roster_sharing'
    TYPE_EMAIL_NOTIFICATIONS = 'email_notifications'
    TYPE_DATA_ANALYTICS = 'data_analytics'
    TYPE_THIRD_PARTY_INTEGRATION = 'third_party_integration'
    
    @property
    def is_active(self):
        """Check if consent is currently active"""
        return self.granted and not self.revoked_at
    
    def grant(self, ip_address=None):
        """Grant consent"""
        self.granted = True
        self.granted_at = datetime.utcnow()
        self.ip_address = ip_address
        self.revoked_at = None
    
    def revoke(self):
        """Revoke consent"""
        self.revoked_at = datetime.utcnow()
    
    def __repr__(self):
        return f'<DataConsent {self.consent_type} for user {self.user_id}>'


class SecurityEvent(db.Model):
    """Track security-related events for monitoring"""
    __tablename__ = 'security_events'
    
    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(50), nullable=False)
    severity = db.Column(db.String(20), nullable=False)  # 'info', 'warning', 'critical'
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(255))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    description = db.Column(db.Text)
    details = db.Column(db.JSON)
    resolved = db.Column(db.Boolean, default=False)
    resolved_at = db.Column(db.DateTime)
    resolved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Event types
    EVENT_SUSPICIOUS_LOGIN = 'suspicious_login'
    EVENT_BRUTE_FORCE_ATTEMPT = 'brute_force_attempt'
    EVENT_ACCOUNT_LOCKED = 'account_locked'
    EVENT_UNAUTHORIZED_ACCESS = 'unauthorized_access'
    EVENT_DATA_BREACH_SUSPECTED = 'data_breach_suspected'
    EVENT_INVALID_MFA = 'invalid_mfa'
    EVENT_SESSION_HIJACK_SUSPECTED = 'session_hijack_suspected'
    
    # Relationships
    resolved_by = db.relationship('User', foreign_keys=[resolved_by_id])
    
    def __repr__(self):
        return f'<SecurityEvent {self.event_type} at {self.timestamp}>'