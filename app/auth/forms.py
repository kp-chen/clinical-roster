"""Authentication forms with enhanced security"""
from flask_wtf import FlaskForm, RecaptchaField
from wtforms import StringField, PasswordField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Email, EqualTo, Length, ValidationError, Regexp
from app.models.user import User
import re


class LoginForm(FlaskForm):
    """Enhanced login form with MFA support"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required')
    ])
    mfa_token = StringField('MFA Code', validators=[
        Length(min=6, max=6, message='MFA code must be 6 digits')
    ])
    remember_me = BooleanField('Remember Me')


class RegistrationForm(FlaskForm):
    """User registration form with strong password requirements"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    password = PasswordField('Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters long')
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
    
    def validate_password(self, password):
        """Enforce strong password policy"""
        pwd = password.data
        
        # Check complexity requirements
        if not re.search(r'[A-Z]', pwd):
            raise ValidationError('Password must contain at least one uppercase letter')
        
        if not re.search(r'[a-z]', pwd):
            raise ValidationError('Password must contain at least one lowercase letter')
        
        if not re.search(r'\d', pwd):
            raise ValidationError('Password must contain at least one number')
        
        if not re.search(r'[!@#$%^&*(),.?":{}|<>]', pwd):
            raise ValidationError('Password must contain at least one special character')
        
        # Check for common passwords
        common_passwords = [
            'password', '12345678', 'qwerty', 'abc123', 'password123',
            'admin', 'letmein', 'welcome', 'monkey', 'dragon'
        ]
        if pwd.lower() in common_passwords:
            raise ValidationError('This password is too common. Please choose a stronger password.')


class MFASetupForm(FlaskForm):
    """MFA setup form"""
    verification_code = StringField('Verification Code', validators=[
        DataRequired(message='Verification code is required'),
        Length(min=6, max=6, message='Code must be 6 digits'),
        Regexp(r'^\d{6}$', message='Code must contain only digits')
    ])


class MFAVerificationForm(FlaskForm):
    """MFA verification form"""
    token = StringField('MFA Code', validators=[
        DataRequired(message='MFA code is required'),
        Length(min=6, max=6, message='Code must be 6 digits'),
        Regexp(r'^\d{6}$', message='Code must contain only digits')
    ])
    backup_code = StringField('Or use backup code', validators=[
        Length(min=8, max=8, message='Backup code must be 8 characters')
    ])
    
    def validate(self):
        """Custom validation - either token or backup code required"""
        if not super().validate():
            return False
        
        if not self.token.data and not self.backup_code.data:
            self.token.errors.append('Please enter either MFA code or backup code')
            return False
        
        return True


class PasswordResetRequestForm(FlaskForm):
    """Request password reset form"""
    email = StringField('Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    # Add CAPTCHA in production
    # recaptcha = RecaptchaField()


class PasswordResetForm(FlaskForm):
    """Reset password form"""
    password = PasswordField('New Password', validators=[
        DataRequired(message='Password is required'),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm Password', validators=[
        DataRequired(message='Please confirm your password'),
        EqualTo('password', message='Passwords must match')
    ])
    
    def validate_password(self, password):
        """Reuse password validation from registration"""
        form = RegistrationForm()
        form.password.data = password.data
        try:
            form.validate_password(password)
        except ValidationError as e:
            raise e


class ChangePasswordForm(FlaskForm):
    """Change password form for logged-in users"""
    current_password = PasswordField('Current Password', validators=[
        DataRequired(message='Current password is required')
    ])
    new_password = PasswordField('New Password', validators=[
        DataRequired(message='New password is required'),
        Length(min=8, message='Password must be at least 8 characters long')
    ])
    confirm_password = PasswordField('Confirm New Password', validators=[
        DataRequired(message='Please confirm your new password'),
        EqualTo('new_password', message='Passwords must match')
    ])
    
    def validate_new_password(self, new_password):
        """Ensure new password is different and meets requirements"""
        if new_password.data == self.current_password.data:
            raise ValidationError('New password must be different from current password')
        
        # Reuse password validation
        form = RegistrationForm()
        form.password.data = new_password.data
        try:
            form.validate_password(form.password)
        except ValidationError as e:
            raise e