"""Utility decorators for the application"""
from functools import wraps
from flask import request, jsonify, current_app
from flask_login import current_user
import time
import logging

logger = logging.getLogger(__name__)


def json_required(f):
    """Decorator to ensure request has JSON content"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not request.is_json:
            return jsonify({'error': 'Content-Type must be application/json'}), 400
        return f(*args, **kwargs)
    return decorated_function


def validate_json(*expected_args):
    """Decorator to validate required JSON fields"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not request.is_json:
                return jsonify({'error': 'Content-Type must be application/json'}), 400
            
            data = request.get_json()
            missing = []
            
            for arg in expected_args:
                if arg not in data:
                    missing.append(arg)
            
            if missing:
                return jsonify({
                    'error': 'Missing required fields',
                    'missing_fields': missing
                }), 400
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def rate_limit(calls=10, period=60):
    """Simple rate limiting decorator"""
    def decorator(f):
        calls_made = {}
        
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get identifier (user ID or IP)
            if current_user.is_authenticated:
                identifier = f"user_{current_user.id}"
            else:
                identifier = f"ip_{request.remote_addr}"
            
            now = time.time()
            
            # Clean old entries
            calls_made[identifier] = [
                timestamp for timestamp in calls_made.get(identifier, [])
                if now - timestamp < period
            ]
            
            # Check rate limit
            if len(calls_made.get(identifier, [])) >= calls:
                return jsonify({
                    'error': 'Rate limit exceeded',
                    'retry_after': period
                }), 429
            
            # Record this call
            if identifier not in calls_made:
                calls_made[identifier] = []
            calls_made[identifier].append(now)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def async_task(f):
    """Decorator to run function asynchronously (requires Celery setup)"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # This is a placeholder - implement with Celery or similar
        # For now, just run synchronously
        return f(*args, **kwargs)
    return decorated_function


def cache_result(timeout=300):
    """Cache function result (requires Redis or similar)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # This is a placeholder - implement with Redis
            # For now, just execute the function
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def measure_performance(f):
    """Measure and log function performance"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = f(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # ms
            
            if execution_time > 1000:  # Log slow operations
                logger.warning(
                    f"Slow operation: {f.__name__} took {execution_time:.2f}ms"
                )
            
            return result
            
        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(
                f"Error in {f.__name__} after {execution_time:.2f}ms: {str(e)}"
            )
            raise
    
    return decorated_function


def admin_required(f):
    """Require admin role"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            if request.is_json:
                return jsonify({'error': 'Authentication required'}), 401
            return current_app.login_manager.unauthorized()
        
        if not current_user.has_role('admin'):
            if request.is_json:
                return jsonify({'error': 'Admin access required'}), 403
            abort(403)
        
        return f(*args, **kwargs)
    return decorated_function


def log_activity(action, resource_type=None):
    """Log user activity (simplified version of audit_log)"""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Log before execution
            logger.info(
                f"User {current_user.email if current_user.is_authenticated else 'anonymous'} "
                f"performing {action} on {resource_type or 'system'}"
            )
            
            result = f(*args, **kwargs)
            
            # Log after execution
            logger.info(f"Action {action} completed successfully")
            
            return result
        return decorated_function
    return decorator