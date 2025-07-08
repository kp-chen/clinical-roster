"""Roster management routes"""
from flask import render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import login_required, current_user
from datetime import datetime, timedelta
import pandas as pd
import os
import json
import logging

from . import roster_bp
from app import db
from app.models.roster import GeneratedRoster, RosterProfile, EmergencyUpdate
from app.models.audit import AuditLog
from app.security.audit import audit_log
from app.security.rbac import require_permission, require_resource_access
from .utils import generate_roster_logic, generate_roster_advanced
from .forms import RosterRulesForm, EmergencyLeaveForm, ProfileForm

logger = logging.getLogger(__name__)


@roster_bp.route('/')
def index():
    """Home page with Anthropic-style design"""
    return render_template('index.html', user=current_user)


@roster_bp.route('/configure-rules/<filename>')
@login_required
@require_permission('roster.create')
def configure_rules(filename):
    """Configure rostering rules with Anthropic-style UI"""
    from app import current_app
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        columns = df.columns.tolist()
        preview_data = df.head(5).to_dict('records')
        
        return render_template('configure_rules.html', 
                             filename=filename,
                             columns=columns,
                             preview_data=preview_data)
    except Exception as e:
        flash(f'Error loading file: {str(e)}', 'error')
        return redirect(url_for('roster.index'))


@roster_bp.route('/generate-roster', methods=['POST'])
@login_required
@require_permission('roster.create')
@audit_log(AuditLog.ACTION_ROSTER_CREATE, 'roster')
def generate_roster():
    """Generate roster based on rules"""
    from app import current_app
    filename = request.form.get('filename')
    filepath = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
    
    rules = {
        'min_staff_per_day': int(request.form.get('min_staff', 2)),
        'specialty_column': request.form.get('specialty_column'),
        'date_column': request.form.get('date_column'),
        'staff_column': request.form.get('staff_column'),
        'end_date_column': request.form.get('end_date_column'),
        'roster_start': request.form.get('roster_start'),
        'roster_end': request.form.get('roster_end'),
        'max_consecutive_days': int(request.form.get('max_consecutive_days', 5)),
        'use_advanced_algorithm': request.form.get('use_advanced', 'off') == 'on'
    }
    
    try:
        # Generate roster using selected algorithm
        if rules['use_advanced_algorithm']:
            roster_result = generate_roster_advanced(filepath, rules)
        else:
            roster_result = generate_roster_logic(filepath, rules)
        
        # Save to database
        generated_roster = GeneratedRoster(
            user_id=current_user.id,
            name=f"Roster {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            start_date=datetime.strptime(rules['roster_start'], '%Y-%m-%d').date(),
            end_date=datetime.strptime(rules['roster_end'], '%Y-%m-%d').date(),
            algorithm_used='csp' if rules['use_advanced_algorithm'] else 'greedy',
            constraints_applied=rules
        )
        
        generated_roster.roster_data = roster_result['roster']
        generated_roster.stats = roster_result['stats']
        
        db.session.add(generated_roster)
        db.session.commit()
        
        flash('Roster generated successfully!', 'success')
        return redirect(url_for('roster.view_roster', id=generated_roster.id))
        
    except Exception as e:
        flash(f'Error generating roster: {str(e)}', 'error')
        logger.error(f'Roster generation error: {str(e)}')
        return redirect(url_for('roster.configure_rules', filename=filename))


@roster_bp.route('/roster/<int:id>')
@login_required
@require_resource_access('roster', 'view')
@audit_log(AuditLog.ACTION_ROSTER_VIEW, 'roster', lambda kwargs: kwargs.get('id'))
def view_roster(id):
    """View generated roster"""
    roster = GeneratedRoster.query.get_or_404(id)
    
    # Sort dates for display
    sorted_dates = sorted(roster.roster_data.keys())
    
    return render_template('roster.html', 
                         roster_obj=roster,
                         roster=roster.roster_data,
                         stats=roster.stats,
                         sorted_dates=sorted_dates)


@roster_bp.route('/roster/<int:id>/export')
@login_required
@require_resource_access('roster', 'export')
@audit_log(AuditLog.ACTION_ROSTER_EXPORT, 'roster', lambda kwargs: kwargs.get('id'))
def export_roster(id):
    """Export roster to Excel format"""
    from app import current_app
    roster = GeneratedRoster.query.get_or_404(id)
    
    try:
        # Create DataFrame for export
        export_data = []
        for date, day_data in roster.roster_data.items():
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_name = date_obj.strftime('%A')
            
            if day_data.get('staff'):
                for staff in day_data['staff']:
                    export_data.append({
                        'Date': date,
                        'Day': day_name,
                        'Staff': staff,
                        'Specialties_Covered': ', '.join(day_data.get('specialties', [])),
                        'Is_Weekend': 'Yes' if day_data.get('is_weekend') else 'No',
                        'Is_Holiday': 'Yes' if day_data.get('is_holiday') else 'No',
                        'Holiday_Name': day_data.get('holiday_name', '')
                    })
            else:
                export_data.append({
                    'Date': date,
                    'Day': day_name,
                    'Staff': 'NO STAFF ASSIGNED',
                    'Specialties_Covered': '',
                    'Is_Weekend': 'Yes' if day_data.get('is_weekend') else 'No',
                    'Is_Holiday': 'Yes' if day_data.get('is_holiday') else 'No',
                    'Holiday_Name': day_data.get('holiday_name', '')
                })
        
        # Create Excel file
        df = pd.DataFrame(export_data)
        
        # Create a temporary file for download
        temp_file = os.path.join(current_app.config['UPLOAD_FOLDER'], 
                                f'roster_export_{id}_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')
        
        # Write to Excel with formatting
        with pd.ExcelWriter(temp_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Roster', index=False)
            
            # Add statistics sheet
            stats_data = []
            if roster.stats:
                stats_data.append(['Total Days', roster.stats.get('total_days', 0)])
                stats_data.append(['Coverage Percentage', f"{roster.stats.get('coverage_percentage', 0):.1f}%"])
                stats_data.append(['Days Understaffed', roster.stats.get('days_understaffed', 0)])
                stats_data.append(['', ''])
                stats_data.append(['Staff Work Distribution', ''])
                
                for staff, days in roster.stats.get('staff_work_distribution', {}).items():
                    stats_data.append([staff, f"{days} days"])
            
            if stats_data:
                stats_df = pd.DataFrame(stats_data, columns=['Metric', 'Value'])
                stats_df.to_excel(writer, sheet_name='Statistics', index=False)
        
        return send_file(temp_file, as_attachment=True, 
                        download_name=f'clinical_roster_{roster.name}.xlsx')
        
    except Exception as e:
        flash(f'Error exporting roster: {str(e)}', 'error')
        return redirect(url_for('roster.view_roster', id=id))


@roster_bp.route('/roster/<int:id>/emergency-update', methods=['GET', 'POST'])
@login_required
@require_resource_access('roster', 'edit')
@audit_log('roster_emergency_update', 'roster', lambda kwargs: kwargs.get('id'))
def emergency_update(id):
    """Handle emergency leave updates"""
    roster = GeneratedRoster.query.get_or_404(id)
    form = EmergencyLeaveForm()
    
    if form.validate_on_submit():
        try:
            # Create emergency update record
            update = EmergencyUpdate(
                roster_id=roster.id,
                staff_name=form.staff_name.data,
                leave_date=form.leave_date.data,
                reason=form.reason.data,
                replacement_staff=form.replacement_staff.data,
                created_by_id=current_user.id
            )
            
            # Update roster data
            date_str = form.leave_date.data.strftime('%Y-%m-%d')
            if date_str in roster.roster_data:
                day_data = roster.roster_data[date_str]
                
                # Remove staff from duty
                if form.staff_name.data in day_data.get('staff', []):
                    day_data['staff'].remove(form.staff_name.data)
                
                # Add replacement if specified
                if form.replacement_staff.data:
                    if 'staff' not in day_data:
                        day_data['staff'] = []
                    day_data['staff'].append(form.replacement_staff.data)
                
                # Update roster
                roster_data = roster.roster_data
                roster_data[date_str] = day_data
                roster.roster_data = roster_data
                
                # Record adjustment details
                update.adjustment_made = {
                    'removed': form.staff_name.data,
                    'added': form.replacement_staff.data,
                    'date': date_str
                }
            
            db.session.add(update)
            db.session.commit()
            
            flash('Emergency update applied successfully', 'success')
            return redirect(url_for('roster.view_roster', id=roster.id))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error applying emergency update: {str(e)}', 'error')
    
    return render_template('roster/emergency_update.html', form=form, roster=roster)


@roster_bp.route('/profiles')
@login_required
@require_permission('profile.view')
def list_profiles():
    """List user's saved roster profiles"""
    profiles = current_user.roster_profiles.filter_by(is_active=True).order_by(
        RosterProfile.updated_at.desc()
    ).all()
    return render_template('profiles/list.html', profiles=profiles)


@roster_bp.route('/profiles/save', methods=['POST'])
@login_required
@require_permission('profile.create')
@audit_log(AuditLog.ACTION_ROSTER_CREATE, 'profile')
def save_profile():
    """Save current roster configuration as a profile"""
    form = ProfileForm()
    if form.validate_on_submit():
        try:
            # Get rules from form or session
            rules = request.get_json() or session.get('current_rules', {})
            
            profile = RosterProfile(
                user_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                rules=rules
            )
            
            db.session.add(profile)
            db.session.commit()
            
            flash('Profile saved successfully!', 'success')
            return jsonify({'success': True, 'profile_id': profile.id})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error saving profile: {str(e)}')
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({'success': False, 'errors': form.errors}), 400