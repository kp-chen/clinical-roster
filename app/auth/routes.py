from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, current_user, login_required
from werkzeug.urls import url_parse
from datetime import datetime
import logging

from . import auth_bp
from models import db, User
from forms import LoginForm, RegistrationForm, PasswordResetRequestForm, PasswordResetForm

logger = logging.getLogger(__name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        
        if user and user.check_password(form.password.data):
            if not user.is_active:
                flash('Your account has been deactivated. Please contact support.', 'error')
                return redirect(url_for('auth.login'))
            
            login_user(user, remember=form.remember_me.data)
            logger.info(f'User {user.email} logged in successfully')
            
            # Redirect to next page or home
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('index')
            
            flash('Welcome back!', 'success')
            return redirect(next_page)
        else:
            flash('Invalid email or password', 'error')
            logger.warning(f'Failed login attempt for email: {form.email.data}')
    
    return render_template('auth/login.html', form=form)

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = RegistrationForm()
    if form.validate_on_submit():
        try:
            # Create new user
            user = User(email=form.email.data.lower())
            user.set_password(form.password.data)
            
            db.session.add(user)
            db.session.commit()
            
            logger.info(f'New user registered: {user.email}')
            
            # Auto-login after registration
            login_user(user)
            flash('Registration successful! Welcome to Clinical Roster Builder.', 'success')
            return redirect(url_for('index'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Registration error: {str(e)}')
            flash('An error occurred during registration. Please try again.', 'error')
    
    return render_template('auth/register.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    """User logout"""
    logger.info(f'User {current_user.email} logged out')
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))

@auth_bp.route('/password-reset-request', methods=['GET', 'POST'])
def password_reset_request():
    """Request password reset"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    form = PasswordResetRequestForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user:
            # TODO: Implement email sending with reset token
            flash('Check your email for instructions to reset your password.', 'info')
            logger.info(f'Password reset requested for: {user.email}')
        else:
            # Don't reveal if email exists or not
            flash('Check your email for instructions to reset your password.', 'info')
        
        return redirect(url_for('auth.login'))
    
    return render_template('auth/password_reset_request.html', form=form)

@auth_bp.route('/password-reset/<token>', methods=['GET', 'POST'])
def password_reset(token):
    """Reset password with token"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    
    # TODO: Implement token verification
    user = None  # Get user from token
    
    if not user:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.login'))
    
    form = PasswordResetForm()
    if form.validate_on_submit():
        user.set_password(form.password.data)
        db.session.commit()
        flash('Your password has been reset successfully.', 'success')
        logger.info(f'Password reset completed for: {user.email}')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/password_reset.html', form=form)