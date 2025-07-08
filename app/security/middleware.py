"""Security middleware for Flask application"""
from flask import request, session, redirect, url_for, flash
from flask_login import current_user, logout_user
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from datetime import datetime, timedelta
import redis
from app.models.audit import SecurityEvent
from app.security.audit import log_security_event


def setup_security_headers(app):
    """Setup security headers for production"""
    
    @app.after_request
    def set_security_headers(response):
        """Set security headers on all responses"""
        # Prevent clickjacking
        response.headers['X-Frame-Options'] = 'DENY'
        
        # Prevent content type sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        
        # Enable XSS protection
        response.headers['X-XSS-Protection'] = '1; mode=block'
        
        # Referrer policy
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        
        # Content Security Policy
        csp = {
            'default-src': "'self'",
            'script-src': "'self' 'unsafe-inline' 'unsafe-eval'",  # Adjust as needed
            'style-src': "'self' 'unsafe-inline'",
            'img-src': "'self' data: https:",
            'font-src': "'self'",
            'connect-src': "'self'",
            'frame-ancestors': "'none'",
            'form-action': "'self'",
            'base-uri': "'self'"
        }
        
        csp_string = '; '.join([f"{key} {value}" for key, value in csp.items()])
        response.headers['Content-Security-Policy'] = csp_string
        
        # Strict Transport Security (HSTS)
        if app.config.get('SESSION_COOKIE_SECURE', False):
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
        # Feature Policy
        response.headers['Feature-Policy'] = "geolocation 'none'; camera 'none'; microphone 'none'"
        
        # Permissions Policy (newer version of Feature Policy)
        response.headers['Permissions-Policy'] = "geolocation=(), camera=(), microphone=()"
        
        return response


def setup_rate_limiting(app):
    """Setup rate limiting for security"""
    # Initialize Redis for rate limit storage
    redis_url = app.config.get('REDIS_URL', 'redis://localhost:6379')
    storage_uri = f"{redis_url}/1"  # Use database 1 for rate limiting
    
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        storage_uri=storage_uri,
        default_limits=["200 per day", "50 per hour"]
    )
    
    # Specific limits for sensitive endpoints
    @limiter.limit("5 per minute")
    @app.route('/auth/login', methods=['POST'])
    def rate_limited_login():
        pass  # Actual login logic in auth blueprint
    
    @limiter.limit("3 per hour")
    @app.route('/auth/password-reset-request', methods=['POST'])
    def rate_limited_password_reset():
        pass  # Actual reset logic in auth blueprint
    
    @limiter.limit("10 per minute")
    @app.route('/api/', methods=['POST', 'PUT', 'DELETE'])
    def rate_limited_api():
        pass  # API endpoints
    
    # Handle rate limit exceeded
    @app.errorhandler(429)
    def rate_limit_handler(e):
        log_security_event(
            SecurityEvent.EVENT_BRUTE_FORCE_ATTEMPT,
            severity='warning',
            description=f"Rate limit exceeded from {request.remote_addr}"
        )
        
        if request.is_json:
            return {'error': 'Rate limit exceeded. Please try again later.'}, 429
        else:
            flash('Too many requests. Please try again later.', 'error')
            return redirect(url_for('index'))
    
    return limiter


def setup_session_security(app):
    """Setup session security middleware"""
    
    @app.before_request
    def check_session_validity():
        """Check session validity before each request"""
        if current_user.is_authenticated:
            # Check session timeout
            last_active = session.get('last_active')
            if last_active:
                last_active_time = datetime.fromisoformat(last_active)
                timeout = app.config.get('PERMANENT_SESSION_LIFETIME', timedelta(hours=24))
                
                if datetime.utcnow() - last_active_time > timeout:
                    logout_user()
                    session.clear()
                    flash('Your session has expired. Please log in again.', 'info')
                    return redirect(url_for('auth.login'))
            
            # Update last active time
            session['last_active'] = datetime.utcnow().isoformat()
            
            # Check for concurrent sessions
            if hasattr(current_user, 'session_token'):
                stored_token = session.get('session_token')
                if stored_token != current_user.session_token:
                    log_security_event(
                        SecurityEvent.EVENT_SESSION_HIJACK_SUSPECTED,
                        severity='critical',
                        description=f"Session token mismatch for user {current_user.email}"
                    )
                    
                    logout_user()
                    session.clear()
                    flash('Session security error. Please log in again.', 'warning')
                    return redirect(url_for('auth.login'))
            
            # Check if account is locked
            if current_user.is_locked():
                logout_user()
                session.clear()
                flash('Your account has been locked. Please contact support.', 'error')
                return redirect(url_for('auth.login'))
    
    @app.before_request
    def enforce_https():
        """Enforce HTTPS in production"""
        if app.config.get('SESSION_COOKIE_SECURE', False):
            if not request.is_secure and request.headers.get('X-Forwarded-Proto') != 'https':
                return redirect(request.url.replace('http://', 'https://'))


def setup_request_validation(app):
    """Setup request validation middleware"""
    
    @app.before_request
    def validate_request():
        """Validate incoming requests"""
        # Check for suspicious patterns
        suspicious_patterns = [
            '../',  # Directory traversal
            '..\\',  # Windows directory traversal
            '<script',  # XSS attempt
            'javascript:',  # XSS attempt
            'SELECT * FROM',  # SQL injection
            'DROP TABLE',  # SQL injection
            'UNION SELECT',  # SQL injection
            '; --',  # SQL injection
        ]
        
        # Check URL
        for pattern in suspicious_patterns:
            if pattern.lower() in request.url.lower():
                log_security_event(
                    SecurityEvent.EVENT_SUSPICIOUS_LOGIN,
                    severity='warning',
                    description=f"Suspicious pattern in URL: {pattern}",
                    details={'url': request.url, 'ip': request.remote_addr}
                )
                return 'Bad Request', 400
        
        # Check form data
        if request.form:
            for key, value in request.form.items():
                if isinstance(value, str):
                    for pattern in suspicious_patterns:
                        if pattern.lower() in value.lower():
                            log_security_event(
                                SecurityEvent.EVENT_SUSPICIOUS_LOGIN,
                                severity='warning',
                                description=f"Suspicious pattern in form data: {pattern}",
                                details={'field': key, 'ip': request.remote_addr}
                            )
                            return 'Bad Request', 400
        
        # Validate Content-Type for API endpoints
        if request.path.startswith('/api/') and request.method in ['POST', 'PUT', 'PATCH']:
            content_type = request.headers.get('Content-Type', '')
            if 'application/json' not in content_type:
                return {'error': 'Content-Type must be application/json'}, 400


class IPBlocker:
    """IP blocking functionality for security"""
    
    def __init__(self, redis_client, block_duration=3600):
        self.redis = redis_client
        self.block_duration = block_duration  # seconds
        self.prefix = 'blocked_ip:'
    
    def is_blocked(self, ip_address):
        """Check if IP is blocked"""
        key = f"{self.prefix}{ip_address}"
        return self.redis.exists(key)
    
    def block_ip(self, ip_address, reason=None, duration=None):
        """Block an IP address"""
        key = f"{self.prefix}{ip_address}"
        duration = duration or self.block_duration
        
        block_data = {
            'blocked_at': datetime.utcnow().isoformat(),
            'reason': reason or 'Security violation',
            'duration': duration
        }
        
        self.redis.setex(key, duration, str(block_data))
        
        log_security_event(
            'ip_blocked',
            severity='warning',
            description=f"IP {ip_address} blocked for {duration} seconds",
            details={'reason': reason}
        )
    
    def unblock_ip(self, ip_address):
        """Manually unblock an IP address"""
        key = f"{self.prefix}{ip_address}"
        self.redis.delete(key)


def init_security_middleware(app):
    """Initialize all security middleware"""
    setup_security_headers(app)
    setup_rate_limiting(app)
    setup_session_security(app)
    setup_request_validation(app)
    
    # Initialize IP blocker if Redis is available
    if app.config.get('REDIS_URL'):
        redis_client = redis.from_url(app.config['REDIS_URL'])
        app.ip_blocker = IPBlocker(redis_client)
        
        @app.before_request
        def check_ip_block():
            """Check if IP is blocked"""
            if hasattr(app, 'ip_blocker') and app.ip_blocker.is_blocked(request.remote_addr):
                return 'Access Denied', 403