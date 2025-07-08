"""Enhanced authentication routes with MFA and security features"""
from flask import render_template, redirect, url_for, flash, request, session, jsonify
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.urls import url_parse
from datetime import datetime, timedelta
import logging
import io
import qrcode
import base64
import secrets

from . import auth_bp
from app import db
from app.models.user import User, Role
from app.models.audit import AuditLog, SecurityEvent
from app.security.audit import audit_log, log_security_event
from app.security.rbac import PermissionManager
from .forms import (
    LoginForm, RegistrationForm, PasswordResetRequestForm, 
    PasswordResetForm, MFASetupForm, MFAVerificationForm,
    ChangePasswordForm
)

logger = logging.getLogger(__name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Enhanced login with MFA support"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        # Check if user exists and password is correct
        if user and user.check_password(form.password.data):
            # Check if account is locked
            if user.is_locked():
                flash('Your account is temporarily locked due to multiple failed login attempts. Please try again later.', 'error')
                log_security_event(
                    SecurityEvent.EVENT_ACCOUNT_LOCKED,
                    severity='warning',
                    description=f'Login attempt on locked account: {user.email}'
                )
                return redirect(url_for('auth.login'))
            
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return redirect(url_for('auth.login'))
            
            # Reset failed login attempts on successful password
            user.reset_failed_login()
            
            # Check if MFA is enabled
            if user.mfa_enabled:
                # Store user ID in session for MFA verification
                session['pending_mfa_user_id'] = user.id
                session['mfa_remember_me'] = form.remember_me.data
                return redirect(url_for('auth.mfa_verify'))
            
            # No MFA, proceed with login
            _complete_login(user, form.remember_me.data)
            
            # Redirect to next page or home
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('index')
            
            return redirect(next_page)
        else:
            # Invalid credentials
            flash('Invalid email or password', 'error')
            
            # Increment failed login attempts
            if user:
                user.increment_failed_login()
                db.session.commit()
                
                if user.is_locked():
                    log_security_event(
                        SecurityEvent.EVENT_ACCOUNT_LOCKED,
                        severity='warning',
                        description=f'Account locked after failed attempts: {user.email}'
                    )
            
            # Log failed attempt
            AuditLog.log(
                action=AuditLog.ACTION_LOGIN_FAILED,
                details={'email': form.email.data},
                request=request
            )
    
    return render_template('auth/login.html', form=form)


@auth_bp.route('/mfa/verify', methods=['GET', 'POST'])
def mfa_verify():
    """Verify MFA token"""
    user_id = session.get('pending_mfa_user_id')
    if not user_id:
        flash('Invalid MFA session. Please login again.', 'error')
        return redirect(url_for('auth.login'))
    
    user = User.query.get(user_id)
    if not user:
        session.pop('pending_mfa_user_id', None)
        flash('Invalid MFA session. Please login again.', 'error')
        return redirect(url_for('auth.login'))
    
    form = MFAVerificationForm()
    if form.validate_on_submit():
        valid = False
        
        # Check MFA token
        if form.token.data:
            valid = user.verify_mfa_token(form.token.data)
            if not valid:
                log_security_event(
                    SecurityEvent.EVENT_INVALID_MFA,
                    severity='warning',
                    description=f'Invalid MFA token for user: {user.email}'
                )
        
        # Check backup code if provided
        elif form.backup_code.data:
            valid = user.verify_backup_code(form.backup_code.data)
            if valid:
                db.session.commit()  # Save the consumed backup code
                flash('Backup code used successfully. Please generate new backup codes.', 'warning')
        
        if valid:
            # Clear MFA session data
            session.pop('pending_mfa_user_id', None)
            remember_me = session.pop('mfa_remember_me', False)
            
            # Complete login
            _complete_login(user, remember_me)
            
            # Log successful MFA
            AuditLog.log(
                action=AuditLog.ACTION_MFA_VERIFIED,
                user_id=user.id,
                request=request
            )
            
            next_page = request.args.get('next', url_for('index'))
            return redirect(next_page)
        else:
            flash('Invalid MFA code or backup code', 'error')
    
    return render_template('auth/mfa_verify.html', form=form)


@auth_bp.route('/mfa/setup', methods=['GET', 'POST'])
@login_required
@audit_log(AuditLog.ACTION_MFA_SETUP)
def mfa_setup():
    """Setup MFA for user account"""
    if current_user.mfa_enabled:
        flash('MFA is already enabled for your account.', 'info')
        return redirect(url_for('index'))
    
    form = MFASetupForm()
    
    # Generate MFA secret if not exists
    if not current_user.mfa_secret:
        current_user.generate_mfa_secret()
        db.session.commit()
    
    if form.validate_on_submit():
        # Verify the token
        if current_user.verify_mfa_token(form.verification_code.data):
            # Enable MFA
            current_user.mfa_enabled = True
            
            # Generate backup codes
            backup_codes = current_user.generate_backup_codes()
            db.session.commit()
            
            flash('MFA has been enabled successfully!', 'success')
            
            # Show backup codes (only shown once)
            return render_template('auth/mfa_backup_codes.html', 
                                 backup_codes=backup_codes)
        else:
            flash('Invalid verification code. Please try again.', 'error')
    
    # Generate QR code
    qr_uri = current_user.get_mfa_uri()
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_uri)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    
    qr_base64 = base64.b64encode(buf.getvalue()).decode()
    
    return render_template('auth/mfa_setup.html', 
                         form=form,
                         qr_code=qr_base64,
                         secret=current_user.mfa_secret)


@auth_bp.route('/mfa/disable', methods=['POST'])
@login_required
@audit_log('mfa_disable')
def mfa_disable():
    """Disable MFA (requires current password)"""
    password = request.form.get('password')
    
    if not password or not current_user.check_password(password):
        flash('Invalid password', 'error')
        return redirect(url_for('index'))
    
    current_user.mfa_enabled = False
    current_user.mfa_secret = None
    current_user.backup_codes = None
    db.session.commit()
    
    flash('MFA has been disabled', 'success')
    return redirect(url_for('index'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Enhanced user registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Create new user
            user = User(email=form.email.data.lower())
            user.set_password(form.password.data)
            
            # Generate session token
            user.generate_session_token()
            
            db.session.add(user)
            db.session.commit()
            
            # Assign default role (staff)
            PermissionManager.grant_role(user, Role.STAFF)
            
            # Log registration
            AuditLog.log(
                action=AuditLog.ACTION_USER_CREATE,
                user_id=user.id,
                resource_type='user',
                resource_id=user.id,
                request=request
            )
            
            # Auto-login after registration
            login_user(user)
            session['session_token'] = user.session_token
            
            flash('Registration successful! Welcome to Clinical Roster Builder. Consider enabling MFA for enhanced security.', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Registration error: {str(e)}')
            flash('An error occurred during registration. Please try again.', 'error')
    
    return render_template('auth/register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    """Enhanced logout with audit logging"""
    # Log logout
    AuditLog.log(
        action=AuditLog.ACTION_LOGOUT,
        user_id=current_user.id,
        request=request
    )
    
    # Clear session
    session.clear()
    
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/password/change', methods=['GET', 'POST'])
@login_required
@audit_log('password_change')
def change_password():
    """Change password for logged-in user"""
    form = ChangePasswordForm()
    
    if form.validate_on_submit():
        if not current_user.check_password(form.current_password.data):
            flash('Current password is incorrect', 'error')
        else:
            current_user.set_password(form.new_password.data)
            db.session.commit()
            
            flash('Your password has been changed successfully', 'success')
            return redirect(url_for('index'))
    
    return render_template('auth/change_password.html', form=form)


def _complete_login(user, remember_me):
    """Complete the login process"""
    # Update login tracking
    user.last_login_at = datetime.utcnow()
    user.last_login_ip = request.remote_addr
    
    # Generate new session token
    user.generate_session_token()
    db.session.commit()
    
    # Login user
    login_user(user, remember=remember_me)
    
    # Store session token
    session['session_token'] = user.session_token
    session['last_active'] = datetime.utcnow().isoformat()
    
    # Log successful login
    AuditLog.log(
        action=AuditLog.ACTION_LOGIN,
        user_id=user.id,
        request=request
    )
    
    flash('Welcome back!', 'success')
    logger.info(f'User {user.email} logged in successfully from {request.remote_addr}')