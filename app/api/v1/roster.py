"""Roster API endpoints"""
from flask import jsonify, request
from flask_login import login_required, current_user
from datetime import datetime
import logging

from . import api_v1_bp
from app import db
from app.models.roster import GeneratedRoster, RosterProfile, EmergencyUpdate
from app.models.audit import AuditLog
from app.security.audit import audit_log
from app.security.rbac import require_permission, require_resource_access
from app.api.auth import token_required

logger = logging.getLogger(__name__)


@api_v1_bp.route('/rosters', methods=['GET'])
@token_required
@require_permission('roster.view')
def list_rosters():
    """List rosters for current user"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 10, type=int)
        
        # Get rosters for current user
        query = GeneratedRoster.query.filter_by(
            user_id=current_user.id,
            is_active=True
        ).order_by(GeneratedRoster.created_at.desc())
        
        paginated = query.paginate(page=page, per_page=per_page)
        
        rosters = []
        for roster in paginated.items:
            rosters.append({
                'id': roster.id,
                'name': roster.name,
                'start_date': roster.start_date.isoformat(),
                'end_date': roster.end_date.isoformat(),
                'algorithm_used': roster.algorithm_used,
                'created_at': roster.created_at.isoformat(),
                'stats': roster.stats
            })
        
        return jsonify({
            'success': True,
            'rosters': rosters,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': paginated.total,
                'pages': paginated.pages
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing rosters: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1_bp.route('/rosters/<int:id>', methods=['GET'])
@token_required
@require_resource_access('roster', 'view')
@audit_log(AuditLog.ACTION_ROSTER_VIEW, 'roster', lambda kwargs: kwargs.get('id'))
def get_roster(id):
    """Get specific roster details"""
    try:
        roster = GeneratedRoster.query.get_or_404(id)
        
        # Format roster data
        roster_data = {
            'id': roster.id,
            'name': roster.name,
            'start_date': roster.start_date.isoformat(),
            'end_date': roster.end_date.isoformat(),
            'algorithm_used': roster.algorithm_used,
            'constraints_applied': roster.constraints_applied,
            'created_at': roster.created_at.isoformat(),
            'updated_at': roster.updated_at.isoformat(),
            'roster_data': roster.roster_data,
            'stats': roster.stats,
            'emergency_updates': []
        }
        
        # Include emergency updates
        for update in roster.emergency_updates:
            roster_data['emergency_updates'].append({
                'id': update.id,
                'staff_name': update.staff_name,
                'leave_date': update.leave_date.isoformat(),
                'reason': update.reason,
                'replacement_staff': update.replacement_staff,
                'created_at': update.created_at.isoformat(),
                'created_by': update.created_by.email if update.created_by else None
            })
        
        return jsonify({
            'success': True,
            'roster': roster_data
        })
        
    except Exception as e:
        logger.error(f"Error getting roster {id}: {str(e)}")
        return jsonify({'success': False, 'error': 'Internal server error'}), 500


@api_v1_bp.route('/rosters', methods=['POST'])
@token_required
@require_permission('roster.create')
@audit_log(AuditLog.ACTION_ROSTER_CREATE, 'roster')
def create_roster():
    """Create new roster via API"""
    try:
        data = request.get_json()
        
        # Validate required fields
        required = ['name', 'start_date', 'end_date', 'rules', 'staff_data']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Parse dates
        start_date = datetime.strptime(data['start_date'], '%Y-%m-%d').date()
        end_date = datetime.strptime(data['end_date'], '%Y-%m-%d').date()
        
        # Generate roster using provided data
        from app.roster.utils import generate_roster_advanced
        
        # Create temporary data structure
        import tempfile
        import pandas as pd
        
        df = pd.DataFrame(data['staff_data'])
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as tmp:
            df.to_csv(tmp.name, index=False)
            
            # Generate roster
            result = generate_roster_advanced(tmp.name, data['rules'])
        
        # Save roster
        roster = GeneratedRoster(
            user_id=current_user.id,
            name=data['name'],
            start_date=start_date,
            end_date=end_date,
            algorithm_used=data.get('algorithm', 'csp'),
            constraints_applied=data['rules']
        )
        
        roster.roster_data = result['roster']
        roster.stats = result['stats']
        
        db.session.add(roster)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'roster_id': roster.id,
            'message': 'Roster created successfully'
        }), 201
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error creating roster: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_v1_bp.route('/rosters/<int:id>', methods=['PUT'])
@token_required
@require_resource_access('roster', 'edit')
@audit_log(AuditLog.ACTION_ROSTER_EDIT, 'roster', lambda kwargs: kwargs.get('id'))
def update_roster(id):
    """Update roster"""
    try:
        roster = GeneratedRoster.query.get_or_404(id)
        data = request.get_json()
        
        # Update allowed fields
        if 'name' in data:
            roster.name = data['name']
        
        if 'roster_data' in data:
            roster.roster_data = data['roster_data']
            roster.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Roster updated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating roster {id}: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_v1_bp.route('/rosters/<int:id>/emergency-update', methods=['POST'])
@token_required
@require_resource_access('roster', 'edit')
@audit_log('roster_emergency_update', 'roster', lambda kwargs: kwargs.get('id'))
def emergency_update_api(id):
    """Apply emergency update to roster"""
    try:
        roster = GeneratedRoster.query.get_or_404(id)
        data = request.get_json()
        
        # Validate required fields
        required = ['staff_name', 'leave_date']
        for field in required:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400
        
        # Create emergency update
        leave_date = datetime.strptime(data['leave_date'], '%Y-%m-%d').date()
        
        update = EmergencyUpdate(
            roster_id=roster.id,
            staff_name=data['staff_name'],
            leave_date=leave_date,
            reason=data.get('reason', ''),
            replacement_staff=data.get('replacement_staff'),
            created_by_id=current_user.id
        )
        
        # Update roster data
        date_str = leave_date.strftime('%Y-%m-%d')
        if date_str in roster.roster_data:
            day_data = roster.roster_data[date_str]
            
            # Remove staff from duty
            if data['staff_name'] in day_data.get('staff', []):
                day_data['staff'].remove(data['staff_name'])
            
            # Add replacement if specified
            if data.get('replacement_staff'):
                if 'staff' not in day_data:
                    day_data['staff'] = []
                day_data['staff'].append(data['replacement_staff'])
            
            # Update roster
            roster_data = roster.roster_data
            roster_data[date_str] = day_data
            roster.roster_data = roster_data
            roster.updated_at = datetime.utcnow()
            
            # Record adjustment
            update.adjustment_made = {
                'removed': data['staff_name'],
                'added': data.get('replacement_staff'),
                'date': date_str
            }
        
        db.session.add(update)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Emergency update applied successfully',
            'update_id': update.id
        })
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error applying emergency update: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500


@api_v1_bp.route('/profiles', methods=['GET'])
@token_required
@require_permission('profile.view')
def list_profiles():
    """List roster profiles"""
    try:
        profiles = current_user.roster_profiles.filter_by(is_active=True).all()
        
        return jsonify({
            'success': True,
            'profiles': [{
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'rules': p.rules,
                'created_at': p.created_at.isoformat(),
                'updated_at': p.updated_at.isoformat()
            } for p in profiles]
        })
        
    except Exception as e:
        logger.error(f"Error listing profiles: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500