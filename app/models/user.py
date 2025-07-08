"""User model with enhanced security features"""
from datetime import datetime, timedelta
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import json
import pyotp
from app import db


class User(UserMixin, db.Model):
    """User model with MFA and enhanced security"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    
    # MFA fields
    mfa_secret = db.Column(db.String(32))
    mfa_enabled = db.Column(db.Boolean, default=False)
    backup_codes = db.Column(db.Text)  # JSON array of encrypted backup codes
    
    # Account security
    failed_login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)
    last_login_at = db.Column(db.DateTime)
    last_login_ip = db.Column(db.String(45))
    
    # Session management
    session_token = db.Column(db.String(64))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    roster_profiles = db.relationship('RosterProfile', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    generated_rosters = db.relationship('GeneratedRoster', backref='creator', lazy='dynamic', cascade='all, delete-orphan')
    roles = db.relationship('Role', secondary='user_roles', backref='users')
    audit_logs = db.relationship('AuditLog', backref='user', lazy='dynamic')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def generate_mfa_secret(self):
        """Generate a new MFA secret"""
        self.mfa_secret = pyotp.random_base32()
        return self.mfa_secret
    
    def get_mfa_uri(self, issuer_name="Clinical Roster System"):
        """Get MFA URI for QR code generation"""
        if not self.mfa_secret:
            self.generate_mfa_secret()
        return pyotp.totp.TOTP(self.mfa_secret).provisioning_uri(
            name=self.email,
            issuer_name=issuer_name
        )
    
    def verify_mfa_token(self, token):
        """Verify MFA token"""
        if not self.mfa_secret:
            return False
        totp = pyotp.TOTP(self.mfa_secret)
        return totp.verify(token, valid_window=1)
    
    def generate_backup_codes(self, count=8):
        """Generate backup codes for MFA"""
        codes = []
        for _ in range(count):
            code = ''.join(secrets.token_hex(4).upper()[i:i+4] for i in range(0, 8, 4))
            codes.append(code)
        
        # Store hashed versions
        hashed_codes = [generate_password_hash(code) for code in codes]
        self.backup_codes = json.dumps(hashed_codes)
        
        return codes  # Return plain codes to show to user once
    
    def verify_backup_code(self, code):
        """Verify and consume a backup code"""
        if not self.backup_codes:
            return False
        
        hashed_codes = json.loads(self.backup_codes)
        for i, hashed_code in enumerate(hashed_codes):
            if check_password_hash(hashed_code, code):
                # Remove used code
                hashed_codes.pop(i)
                self.backup_codes = json.dumps(hashed_codes)
                return True
        return False
    
    def is_locked(self):
        """Check if account is locked due to failed login attempts"""
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False
    
    def increment_failed_login(self, lockout_duration_minutes=15, max_attempts=5):
        """Increment failed login counter and lock if necessary"""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.utcnow() + timedelta(minutes=lockout_duration_minutes)
    
    def reset_failed_login(self):
        """Reset failed login counter on successful login"""
        self.failed_login_attempts = 0
        self.locked_until = None
    
    def generate_session_token(self):
        """Generate a new session token"""
        self.session_token = secrets.token_urlsafe(32)
        return self.session_token
    
    def has_permission(self, permission):
        """Check if user has a specific permission"""
        for role in self.roles:
            if permission in role.permissions:
                return True
        return False
    
    def has_role(self, role_name):
        """Check if user has a specific role"""
        return any(role.name == role_name for role in self.roles)
    
    def __repr__(self):
        return f'<User {self.email}>'


class Role(db.Model):
    """Role model for RBAC"""
    __tablename__ = 'roles'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255))
    permissions = db.Column(db.JSON, default=list)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Common roles
    ADMIN = 'admin'
    SCHEDULER = 'scheduler'
    STAFF = 'staff'
    VIEWER = 'viewer'
    
    @staticmethod
    def create_default_roles():
        """Create default roles with permissions"""
        default_roles = [
            {
                'name': Role.ADMIN,
                'description': 'System administrator with full access',
                'permissions': [
                    'admin.users.view', 'admin.users.create', 'admin.users.edit', 'admin.users.delete',
                    'roster.view', 'roster.create', 'roster.edit', 'roster.delete', 'roster.export',
                    'profile.view', 'profile.create', 'profile.edit', 'profile.delete', 'profile.share',
                    'audit.view', 'settings.edit'
                ]
            },
            {
                'name': Role.SCHEDULER,
                'description': 'Roster scheduler with create/edit permissions',
                'permissions': [
                    'roster.view', 'roster.create', 'roster.edit', 'roster.export',
                    'profile.view', 'profile.create', 'profile.edit', 'profile.share'
                ]
            },
            {
                'name': Role.STAFF,
                'description': 'Medical staff with view permissions',
                'permissions': [
                    'roster.view', 'profile.view'
                ]
            },
            {
                'name': Role.VIEWER,
                'description': 'Read-only access to rosters',
                'permissions': [
                    'roster.view'
                ]
            }
        ]
        
        for role_data in default_roles:
            role = Role.query.filter_by(name=role_data['name']).first()
            if not role:
                role = Role(**role_data)
                db.session.add(role)
        
        db.session.commit()
    
    def __repr__(self):
        return f'<Role {self.name}>'


class UserRole(db.Model):
    """Association table for user-role many-to-many relationship"""
    __tablename__ = 'user_roles'
    
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), primary_key=True)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.id'), primary_key=True)
    assigned_at = db.Column(db.DateTime, default=datetime.utcnow)
    assigned_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    assigned_by = db.relationship('User', foreign_keys=[assigned_by_id])