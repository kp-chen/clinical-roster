"""Role-Based Access Control implementation"""
from functools import wraps
from flask import abort, request, jsonify
from flask_login import current_user, login_required
from app.models.user import User, Role


def require_permission(permission):
    """
    Decorator to require specific permission for access
    
    Usage:
        @app.route('/admin/users')
        @require_permission('admin.users.view')
        def admin_users():
            ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_permission(permission):
                # Log unauthorized access attempt
                from app.security.audit import log_security_event
                from app.models.audit import SecurityEvent
                
                log_security_event(
                    SecurityEvent.EVENT_UNAUTHORIZED_ACCESS,
                    severity='warning',
                    description=f'User {current_user.email} attempted to access {request.path} without {permission} permission'
                )
                
                # Return appropriate error based on request type
                if request.is_json:
                    return jsonify({'error': 'Insufficient permissions'}), 403
                else:
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def require_role(role_name):
    """
    Decorator to require specific role for access
    
    Usage:
        @app.route('/admin')
        @require_role('admin')
        def admin_panel():
            ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if not current_user.has_role(role_name):
                from app.security.audit import log_security_event
                from app.models.audit import SecurityEvent
                
                log_security_event(
                    SecurityEvent.EVENT_UNAUTHORIZED_ACCESS,
                    severity='warning',
                    description=f'User {current_user.email} attempted to access {request.path} without {role_name} role'
                )
                
                if request.is_json:
                    return jsonify({'error': 'Insufficient role privileges'}), 403
                else:
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


def check_resource_access(resource_type, resource_id, permission):
    """
    Check if current user has access to a specific resource
    
    Args:
        resource_type: Type of resource (e.g., 'roster', 'profile')
        resource_id: ID of the resource
        permission: Required permission (e.g., 'view', 'edit')
    
    Returns:
        bool: True if user has access, False otherwise
    """
    if not current_user.is_authenticated:
        return False
    
    # Admin has access to everything
    if current_user.has_role(Role.ADMIN):
        return True
    
    # Check general permission
    full_permission = f"{resource_type}.{permission}"
    if not current_user.has_permission(full_permission):
        return False
    
    # Check resource-specific access
    if resource_type == 'roster':
        from app.models.roster import GeneratedRoster
        roster = GeneratedRoster.query.get(resource_id)
        if not roster:
            return False
        
        # Users can access their own rosters
        if roster.user_id == current_user.id:
            return True
        
        # Check if roster is shared with user
        # TODO: Implement roster sharing logic
        
    elif resource_type == 'profile':
        from app.models.roster import RosterProfile
        profile = RosterProfile.query.get(resource_id)
        if not profile:
            return False
        
        # Users can access their own profiles
        if profile.user_id == current_user.id:
            return True
        
        # Check if profile is shared
        for share in profile.shared_profiles:
            if share.shared_with_email == current_user.email and share.is_active:
                return True
    
    return False


def require_resource_access(resource_type, permission, resource_id_param='id'):
    """
    Decorator to check resource-specific access
    
    Usage:
        @app.route('/roster/<int:id>')
        @require_resource_access('roster', 'view')
        def view_roster(id):
            ...
    """
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            resource_id = kwargs.get(resource_id_param)
            if not resource_id:
                abort(400)  # Bad request if resource ID not provided
            
            if not check_resource_access(resource_type, resource_id, permission):
                from app.security.audit import log_security_event
                from app.models.audit import SecurityEvent
                
                log_security_event(
                    SecurityEvent.EVENT_UNAUTHORIZED_ACCESS,
                    severity='warning',
                    description=f'User {current_user.email} denied access to {resource_type} {resource_id}'
                )
                
                if request.is_json:
                    return jsonify({'error': 'Access denied'}), 403
                else:
                    abort(403)
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator


class PermissionManager:
    """Manage permissions and roles"""
    
    # Permission definitions
    PERMISSIONS = {
        # Admin permissions
        'admin.users.view': 'View all users',
        'admin.users.create': 'Create new users',
        'admin.users.edit': 'Edit user details',
        'admin.users.delete': 'Delete users',
        'admin.roles.manage': 'Manage user roles',
        
        # Roster permissions
        'roster.view': 'View rosters',
        'roster.create': 'Create new rosters',
        'roster.edit': 'Edit existing rosters',
        'roster.delete': 'Delete rosters',
        'roster.export': 'Export rosters',
        'roster.share': 'Share rosters with others',
        'roster.emergency_update': 'Make emergency roster updates',
        
        # Profile permissions
        'profile.view': 'View roster profiles',
        'profile.create': 'Create roster profiles',
        'profile.edit': 'Edit roster profiles',
        'profile.delete': 'Delete roster profiles',
        'profile.share': 'Share roster profiles',
        
        # File permissions
        'file.upload': 'Upload files',
        'file.parse': 'Parse uploaded files',
        'file.delete': 'Delete uploaded files',
        
        # Audit permissions
        'audit.view': 'View audit logs',
        'audit.export': 'Export audit reports',
        
        # Settings permissions
        'settings.view': 'View system settings',
        'settings.edit': 'Modify system settings',
        
        # API permissions
        'api.access': 'Access API endpoints',
        'api.admin': 'Access admin API endpoints',
    }
    
    @classmethod
    def get_user_permissions(cls, user):
        """Get all permissions for a user"""
        permissions = set()
        for role in user.roles:
            permissions.update(role.permissions)
        return list(permissions)
    
    @classmethod
    def grant_role(cls, user, role_name, granted_by=None):
        """Grant a role to a user"""
        from app import db
        from app.models.user import UserRole
        from app.models.audit import AuditLog
        
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            raise ValueError(f"Role {role_name} does not exist")
        
        if user.has_role(role_name):
            return False  # Already has role
        
        # Create user-role association
        user_role = UserRole(
            user_id=user.id,
            role_id=role.id,
            assigned_by_id=granted_by.id if granted_by else None
        )
        db.session.add(user_role)
        
        # Audit log
        AuditLog.log(
            action=AuditLog.ACTION_PERMISSION_CHANGE,
            user_id=granted_by.id if granted_by else None,
            resource_type='user',
            resource_id=user.id,
            details={
                'action': 'grant_role',
                'role': role_name,
                'target_user': user.email
            }
        )
        
        db.session.commit()
        return True
    
    @classmethod
    def revoke_role(cls, user, role_name, revoked_by=None):
        """Revoke a role from a user"""
        from app import db
        from app.models.user import UserRole
        from app.models.audit import AuditLog
        
        role = Role.query.filter_by(name=role_name).first()
        if not role:
            raise ValueError(f"Role {role_name} does not exist")
        
        user_role = UserRole.query.filter_by(
            user_id=user.id,
            role_id=role.id
        ).first()
        
        if not user_role:
            return False  # Doesn't have role
        
        db.session.delete(user_role)
        
        # Audit log
        AuditLog.log(
            action=AuditLog.ACTION_PERMISSION_CHANGE,
            user_id=revoked_by.id if revoked_by else None,
            resource_type='user',
            resource_id=user.id,
            details={
                'action': 'revoke_role',
                'role': role_name,
                'target_user': user.email
            }
        )
        
        db.session.commit()
        return True


# Template helpers
def init_rbac_helpers(app):
    """Initialize template helpers for RBAC"""
    
    @app.template_global()
    def has_permission(permission):
        """Check permission in templates"""
        return current_user.is_authenticated and current_user.has_permission(permission)
    
    @app.template_global()
    def has_role(role_name):
        """Check role in templates"""
        return current_user.is_authenticated and current_user.has_role(role_name)
    
    @app.template_global()
    def can_access_resource(resource_type, resource_id, permission):
        """Check resource access in templates"""
        return check_resource_access(resource_type, resource_id, permission)