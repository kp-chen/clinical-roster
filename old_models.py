from datetime import datetime, timedelta
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
import secrets
import json

db = SQLAlchemy()

class User(UserMixin, db.Model):
    """User model for authentication"""
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    roster_profiles = db.relationship('RosterProfile', backref='owner', lazy='dynamic', cascade='all, delete-orphan')
    generated_rosters = db.relationship('GeneratedRoster', backref='creator', lazy='dynamic', cascade='all, delete-orphan')
    
    def set_password(self, password):
        """Set password hash"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check password against hash"""
        return check_password_hash(self.password_hash, password)
    
    def __repr__(self):
        return f'<User {self.email}>'

class RosterProfile(db.Model):
    """Saved roster configuration profiles"""
    __tablename__ = 'roster_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    rules_json = db.Column(db.Text, nullable=False)  # JSON string of rules configuration
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    shared_profiles = db.relationship('SharedProfile', backref='profile', lazy='dynamic', cascade='all, delete-orphan')
    generated_rosters = db.relationship('GeneratedRoster', backref='profile', lazy='dynamic')
    
    @property
    def rules(self):
        """Get rules as dictionary"""
        return json.loads(self.rules_json) if self.rules_json else {}
    
    @rules.setter
    def rules(self, value):
        """Set rules from dictionary"""
        self.rules_json = json.dumps(value)
    
    def __repr__(self):
        return f'<RosterProfile {self.name}>'

class SharedProfile(db.Model):
    """Shared roster profiles with access tokens"""
    __tablename__ = 'shared_profiles'
    
    id = db.Column(db.Integer, primary_key=True)
    profile_id = db.Column(db.Integer, db.ForeignKey('roster_profiles.id'), nullable=False)
    shared_with_email = db.Column(db.String(120), nullable=False)
    token = db.Column(db.String(64), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime, nullable=False)
    accessed_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    
    def __init__(self, **kwargs):
        super(SharedProfile, self).__init__(**kwargs)
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            self.expires_at = datetime.utcnow() + timedelta(days=7)
    
    @property
    def is_expired(self):
        """Check if share link has expired"""
        return datetime.utcnow() > self.expires_at
    
    def __repr__(self):
        return f'<SharedProfile {self.token[:8]}...>'

class GeneratedRoster(db.Model):
    """Generated roster instances"""
    __tablename__ = 'generated_rosters'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    profile_id = db.Column(db.Integer, db.ForeignKey('roster_profiles.id'))
    name = db.Column(db.String(100), nullable=False)
    roster_data_json = db.Column(db.Text, nullable=False)  # JSON string of roster data
    stats_json = db.Column(db.Text)  # JSON string of statistics
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relationships
    emergency_updates = db.relationship('EmergencyUpdate', backref='roster', lazy='dynamic', cascade='all, delete-orphan')
    
    @property
    def roster_data(self):
        """Get roster data as dictionary"""
        return json.loads(self.roster_data_json) if self.roster_data_json else {}
    
    @roster_data.setter
    def roster_data(self, value):
        """Set roster data from dictionary"""
        self.roster_data_json = json.dumps(value)
    
    @property
    def stats(self):
        """Get statistics as dictionary"""
        return json.loads(self.stats_json) if self.stats_json else {}
    
    @stats.setter
    def stats(self, value):
        """Set statistics from dictionary"""
        self.stats_json = json.dumps(value)
    
    def __repr__(self):
        return f'<GeneratedRoster {self.name}>'

class EmergencyUpdate(db.Model):
    """Emergency leave updates for rosters"""
    __tablename__ = 'emergency_updates'
    
    id = db.Column(db.Integer, primary_key=True)
    roster_id = db.Column(db.Integer, db.ForeignKey('generated_rosters.id'), nullable=False)
    staff_name = db.Column(db.String(100), nullable=False)
    leave_date = db.Column(db.Date, nullable=False)
    reason = db.Column(db.String(200))
    replacement_staff = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    
    # Relationships
    created_by = db.relationship('User', backref='emergency_updates')
    
    def __repr__(self):
        return f'<EmergencyUpdate {self.staff_name} on {self.leave_date}>'

class UploadedFile(db.Model):
    """Track uploaded files for audit and cleanup"""
    __tablename__ = 'uploaded_files'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_type = db.Column(db.String(10), nullable=False)
    file_size = db.Column(db.Integer)
    upload_date = db.Column(db.DateTime, default=datetime.utcnow)
    processed = db.Column(db.Boolean, default=False)
    
    # Relationships
    user = db.relationship('User', backref='uploaded_files')
    
    def __repr__(self):
        return f'<UploadedFile {self.original_filename}>'