"""API authentication using JWT tokens"""
from functools import wraps
from flask import request, jsonify, current_app
from flask_login import current_user
import jwt
from datetime import datetime, timedelta
import logging

from app.models.user import User
from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


def generate_api_token(user, expires_in=3600):
    """Generate JWT token for API access"""
    try:
        payload = {
            'user_id': user.id,
            'email': user.email,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow()
        }
        
        token = jwt.encode(
            payload,
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
        
        # Log token generation
        AuditLog.log(
            action='api_token_generated',
            user_id=user.id,
            details={'expires_in': expires_in}
        )
        
        return token
        
    except Exception as e:
        logger.error(f"Error generating token: {str(e)}")
        return None


def verify_api_token(token):
    """Verify and decode JWT token"""
    try:
        payload = jwt.decode(
            token,
            current_app.config['SECRET_KEY'],
            algorithms=['HS256']
        )
        
        # Get user
        user = User.query.get(payload['user_id'])
        if not user or not user.is_active:
            return None
        
        return user
        
    except jwt.ExpiredSignatureError:
        logger.warning("Expired token attempted")
        return None
    except jwt.InvalidTokenError as e:
        logger.warning(f"Invalid token: {str(e)}")
        return None


def token_required(f):
    """Decorator to require valid API token"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        
        # Get token from header
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            try:
                # Format: Bearer <token>
                token = auth_header.split(' ')[1]
            except IndexError:
                return jsonify({'success': False, 'error': 'Invalid token format'}), 401
        
        if not token:
            return jsonify({'success': False, 'error': 'Token required'}), 401
        
        # Verify token
        user = verify_api_token(token)
        if not user:
            return jsonify({'success': False, 'error': 'Invalid or expired token'}), 401
        
        # Set current user for the request
        current_user = user
        
        # Log API access
        AuditLog.log(
            action='api_access',
            user_id=user.id,
            resource_type='api',
            details={
                'endpoint': request.endpoint,
                'method': request.method,
                'path': request.path
            },
            request=request
        )
        
        return f(*args, **kwargs)
    
    return decorated_function


def api_key_required(f):
    """Decorator to require API key (alternative to JWT)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = None
        
        # Get API key from header or query param
        if 'X-API-Key' in request.headers:
            api_key = request.headers['X-API-Key']
        elif 'api_key' in request.args:
            api_key = request.args.get('api_key')
        
        if not api_key:
            return jsonify({'success': False, 'error': 'API key required'}), 401
        
        # Verify API key (implement your API key storage/verification)
        # For now, this is a placeholder
        user = verify_api_key(api_key)
        if not user:
            return jsonify({'success': False, 'error': 'Invalid API key'}), 401
        
        current_user = user
        
        return f(*args, **kwargs)
    
    return decorated_function


def verify_api_key(api_key):
    """Verify API key (placeholder - implement based on your needs)"""
    # This would typically check against a database of API keys
    # For now, return None (invalid)
    return None