"""Authentication API endpoints"""
from flask import jsonify, request
from datetime import datetime
import logging

from . import api_v1_bp
from app import db
from app.models.user import User
from app.models.audit import AuditLog
from app.api.auth import generate_api_token

logger = logging.getLogger(__name__)


@api_v1_bp.route('/auth/login', methods=['POST'])
def api_login():
    """API login endpoint to get JWT token"""
    try:
        data = request.get_json()
        
        if not data or 'email' not in data or 'password' not in data:
            return jsonify({
                'success': False,
                'error': 'Email and password required'
            }), 400
        
        # Find user
        user = User.query.filter_by(email=data['email'].lower()).first()
        
        if not user or not user.check_password(data['password']):
            # Log failed attempt
            AuditLog.log(
                action=AuditLog.ACTION_LOGIN_FAILED,
                details={'email': data['email'], 'api': True},
                request=request
            )
            
            return jsonify({
                'success': False,
                'error': 'Invalid credentials'
            }), 401
        
        # Check if account is locked
        if user.is_locked():
            return jsonify({
                'success': False,
                'error': 'Account locked due to multiple failed attempts'
            }), 403
        
        if not user.is_active:
            return jsonify({
                'success': False,
                'error': 'Account deactivated'
            }), 403
        
        # Check MFA if enabled
        if user.mfa_enabled and 'mfa_token' in data:
            if not user.verify_mfa_token(data['mfa_token']):
                return jsonify({
                    'success': False,
                    'error': 'Invalid MFA token'
                }), 401
        elif user.mfa_enabled:
            return jsonify({
                'success': False,
                'error': 'MFA token required',
                'mfa_required': True
            }), 401
        
        # Generate token
        expires_in = data.get('expires_in', 3600)  # Default 1 hour
        token = generate_api_token(user, expires_in)
        
        if not token:
            return jsonify({
                'success': False,
                'error': 'Failed to generate token'
            }), 500
        
        # Update login info
        user.last_login_at = datetime.utcnow()
        user.last_login_ip = request.remote_addr
        user.reset_failed_login()
        db.session.commit()
        
        # Log successful login
        AuditLog.log(
            action=AuditLog.ACTION_LOGIN,
            user_id=user.id,
            details={'api': True},
            request=request
        )
        
        return jsonify({
            'success': True,
            'token': token,
            'expires_in': expires_in,
            'user': {
                'id': user.id,
                'email': user.email,
                'roles': [role.name for role in user.roles]
            }
        })
        
    except Exception as e:
        logger.error(f"API login error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1_bp.route('/auth/refresh', methods=['POST'])
def api_refresh_token():
    """Refresh API token"""
    try:
        data = request.get_json()
        
        if not data or 'token' not in data:
            return jsonify({
                'success': False,
                'error': 'Current token required'
            }), 400
        
        # Verify current token
        from app.api.auth import verify_api_token
        user = verify_api_token(data['token'])
        
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid or expired token'
            }), 401
        
        # Generate new token
        expires_in = data.get('expires_in', 3600)
        new_token = generate_api_token(user, expires_in)
        
        if not new_token:
            return jsonify({
                'success': False,
                'error': 'Failed to generate token'
            }), 500
        
        return jsonify({
            'success': True,
            'token': new_token,
            'expires_in': expires_in
        })
        
    except Exception as e:
        logger.error(f"Token refresh error: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Internal server error'
        }), 500


@api_v1_bp.route('/auth/logout', methods=['POST'])
def api_logout():
    """API logout (invalidate token)"""
    # In a stateless JWT system, logout is typically handled client-side
    # by removing the token. For enhanced security, you could:
    # 1. Maintain a token blacklist in Redis
    # 2. Use short-lived tokens with refresh tokens
    
    return jsonify({
        'success': True,
        'message': 'Logged out successfully'
    })