"""Audit logging functionality for security compliance"""
from functools import wraps
from datetime import datetime
import json
from flask import request, g, current_app
from flask_login import current_user
from app import db
from app.models.audit import AuditLog, SecurityEvent


def audit_log(action, resource_type=None, get_resource_id=None):
    """
    Decorator for automatic audit logging
    
    Args:
        action: The action being performed (e.g., 'roster_view')
        resource_type: Type of resource being accessed (e.g., 'roster')
        get_resource_id: Function to extract resource ID from kwargs
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Record start time
            start_time = datetime.utcnow()
            
            # Initialize audit details
            details = {
                'function': f.__name__,
                'args': {}
            }
            
            # Extract resource ID if function provided
            resource_id = None
            if get_resource_id:
                resource_id = get_resource_id(kwargs)
            elif 'id' in kwargs:
                resource_id = kwargs['id']
            elif 'roster_id' in kwargs:
                resource_id = kwargs['roster_id']
            
            # Add relevant kwargs to details (excluding sensitive data)
            safe_kwargs = ['filename', 'profile_id', 'date', 'staff_name']
            for key in safe_kwargs:
                if key in kwargs:
                    details['args'][key] = kwargs[key]
            
            # Execute the function
            error_occurred = False
            error_message = None
            try:
                result = f(*args, **kwargs)
                return result
            except Exception as e:
                error_occurred = True
                error_message = str(e)
                raise
            finally:
                # Calculate duration
                duration_ms = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                
                # Create audit log entry
                try:
                    entry = AuditLog(
                        action=action,
                        user_id=current_user.id if current_user.is_authenticated else None,
                        resource_type=resource_type,
                        resource_id=resource_id,
                        ip_address=request.remote_addr,
                        user_agent=request.headers.get('User-Agent', '')[:255],
                        request_method=request.method,
                        request_path=request.path,
                        timestamp=start_time,
                        duration_ms=duration_ms,
                        details=details
                    )
                    
                    if error_occurred:
                        entry.error_message = error_message
                        entry.response_status = 500
                    elif hasattr(g, 'audit_response_status'):
                        entry.response_status = g.audit_response_status
                    
                    db.session.add(entry)
                    db.session.commit()
                except Exception as audit_error:
                    # Log audit failure but don't break the application
                    current_app.logger.error(f"Audit logging failed: {audit_error}")
        
        return decorated_function
    return decorator


def log_security_event(event_type, severity='warning', description=None, details=None):
    """Log a security-related event"""
    try:
        event = SecurityEvent(
            event_type=event_type,
            severity=severity,
            user_id=current_user.id if current_user.is_authenticated else None,
            ip_address=request.remote_addr if request else None,
            user_agent=request.headers.get('User-Agent', '')[:255] if request else None,
            description=description,
            details=details
        )
        db.session.add(event)
        db.session.commit()
        
        # Alert if critical
        if severity == 'critical':
            alert_security_team(event)
            
    except Exception as e:
        current_app.logger.error(f"Security event logging failed: {e}")


def alert_security_team(event):
    """Send alerts for critical security events"""
    # TODO: Implement email/SMS alerting
    current_app.logger.critical(f"SECURITY ALERT: {event.event_type} - {event.description}")


def setup_audit_logging(app):
    """Setup application-wide audit logging"""
    
    @app.before_request
    def before_request_audit():
        """Log all requests for audit trail"""
        g.request_start_time = datetime.utcnow()
        
        # Log authentication attempts
        if request.endpoint == 'auth.login' and request.method == 'POST':
            email = request.form.get('email', 'unknown')
            AuditLog.log(
                action=AuditLog.ACTION_LOGIN_FAILED,  # Will update on success
                details={'email': email},
                request=request
            )
    
    @app.after_request
    def after_request_audit(response):
        """Complete audit logging after request"""
        # Store response status for audit decorator
        g.audit_response_status = response.status_code
        
        # Log static file access for PHI-containing files
        if request.path.startswith('/static/') and any(
            ext in request.path for ext in ['.pdf', '.xlsx', '.csv']
        ):
            AuditLog.log(
                action='static_file_access',
                resource_type='file',
                details={'file_path': request.path},
                request=request,
                response=response
            )
        
        return response
    
    @app.errorhandler(403)
    def forbidden_audit(error):
        """Log forbidden access attempts"""
        log_security_event(
            SecurityEvent.EVENT_UNAUTHORIZED_ACCESS,
            severity='warning',
            description=f"403 Forbidden: {request.path}",
            details={
                'endpoint': request.endpoint,
                'method': request.method,
                'user_id': current_user.id if current_user.is_authenticated else None
            }
        )
        return error


class AuditReportGenerator:
    """Generate audit reports for compliance"""
    
    @staticmethod
    def generate_user_activity_report(user_id, start_date, end_date):
        """Generate activity report for a specific user"""
        logs = AuditLog.query.filter(
            AuditLog.user_id == user_id,
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).order_by(AuditLog.timestamp.desc()).all()
        
        return {
            'user_id': user_id,
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_actions': len(logs),
            'actions_by_type': AuditReportGenerator._group_by_action(logs),
            'logs': [AuditReportGenerator._serialize_log(log) for log in logs]
        }
    
    @staticmethod
    def generate_phi_access_report(start_date, end_date):
        """Generate report of all PHI access"""
        phi_actions = [
            AuditLog.ACTION_ROSTER_VIEW,
            AuditLog.ACTION_ROSTER_EXPORT,
            AuditLog.ACTION_FILE_PARSE,
            'static_file_access'
        ]
        
        logs = AuditLog.query.filter(
            AuditLog.action.in_(phi_actions),
            AuditLog.timestamp >= start_date,
            AuditLog.timestamp <= end_date
        ).order_by(AuditLog.timestamp.desc()).all()
        
        return {
            'period': {
                'start': start_date.isoformat(),
                'end': end_date.isoformat()
            },
            'total_accesses': len(logs),
            'unique_users': len(set(log.user_id for log in logs if log.user_id)),
            'accesses_by_user': AuditReportGenerator._group_by_user(logs),
            'logs': [AuditReportGenerator._serialize_log(log) for log in logs]
        }
    
    @staticmethod
    def _group_by_action(logs):
        """Group logs by action type"""
        grouped = {}
        for log in logs:
            if log.action not in grouped:
                grouped[log.action] = 0
            grouped[log.action] += 1
        return grouped
    
    @staticmethod
    def _group_by_user(logs):
        """Group logs by user"""
        grouped = {}
        for log in logs:
            user_id = log.user_id or 'anonymous'
            if user_id not in grouped:
                grouped[user_id] = 0
            grouped[user_id] += 1
        return grouped
    
    @staticmethod
    def _serialize_log(log):
        """Serialize audit log for report"""
        return {
            'id': log.id,
            'timestamp': log.timestamp.isoformat(),
            'action': log.action,
            'user_id': log.user_id,
            'resource_type': log.resource_type,
            'resource_id': log.resource_id,
            'ip_address': log.ip_address,
            'duration_ms': log.duration_ms,
            'details': log.details
        }