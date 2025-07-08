from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import StringField, PasswordField, BooleanField, TextAreaField, IntegerField, DateField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Optional
from models import User
from config import Config

class LoginForm(FlaskForm):
    """User login form"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    remember_me = BooleanField('Remember Me')

class RegistrationForm(FlaskForm):
    """User registration form"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=Config.MIN_PASSWORD_LENGTH, 
               message=f'Password must be at least {Config.MIN_PASSWORD_LENGTH} characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    
    def validate_email(self, email):
        """Check if email already exists"""
        user = User.query.filter_by(email=email.data.lower()).first()
        if user:
            raise ValidationError('Email already registered. Please login or use a different email.')

class ProfileForm(FlaskForm):
    """Roster profile configuration form"""
    name = StringField('Profile Name', validators=[
        DataRequired(message='Profile name is required'),
        Length(max=100)
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=500)
    ])

class ShareProfileForm(FlaskForm):
    """Share roster profile form"""
    email = StringField('Recipient Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    message = TextAreaField('Message (Optional)', validators=[
        Optional(),
        Length(max=500)
    ])

class FileUploadForm(FlaskForm):
    """File upload form with CSRF protection"""
    file = FileField('File', validators=[
        FileRequired(message='Please select a file'),
        FileAllowed(Config.ALLOWED_EXTENSIONS, 
                   message='Invalid file type. Allowed: Excel, CSV, PDF, Images')
    ])

class RosterRulesForm(FlaskForm):
    """Roster generation rules form"""
    min_staff_per_day = IntegerField('Minimum Staff per Day', validators=[
        DataRequired(message='Minimum staff is required'),
    ], default=2)
    roster_start = DateField('Roster Start Date', validators=[
        DataRequired(message='Start date is required')
    ])
    roster_end = DateField('Roster End Date', validators=[
        DataRequired(message='End date is required')
    ])
    staff_column = HiddenField()
    specialty_column = HiddenField()
    date_column = HiddenField()
    end_date_column = HiddenField()
    
    def validate_roster_end(self, field):
        """Ensure end date is after start date"""
        if field.data and self.roster_start.data and field.data < self.roster_start.data:
            raise ValidationError('End date must be after start date')

class EmergencyLeaveForm(FlaskForm):
    """Emergency leave update form"""
    staff_name = StringField('Staff Name', validators=[
        DataRequired(message='Staff name is required')
    ])
    leave_date = DateField('Leave Date', validators=[
        DataRequired(message='Leave date is required')
    ])
    reason = StringField('Reason', validators=[
        Optional(),
        Length(max=200)
    ])
    replacement_staff = StringField('Replacement Staff', validators=[
        Optional(),
        Length(max=100)
    ])

class PasswordResetRequestForm(FlaskForm):
    """Request password reset form"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])

class PasswordResetForm(FlaskForm):
    """Reset password form"""
    password = PasswordField('New Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=Config.MIN_PASSWORD_LENGTH,
               message=f'Password must be at least {Config.MIN_PASSWORD_LENGTH} characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])