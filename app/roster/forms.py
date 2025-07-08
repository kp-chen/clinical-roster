"""Roster-related forms"""
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileRequired, FileAllowed
from wtforms import (
    StringField, IntegerField, DateField, SelectField, 
    TextAreaField, BooleanField, HiddenField
)
from wtforms.validators import DataRequired, Length, Optional, ValidationError
from datetime import datetime


class FileUploadForm(FlaskForm):
    """File upload form with CSRF protection"""
    file = FileField('File', validators=[
        FileRequired(message='Please select a file'),
        FileAllowed(['xlsx', 'xls', 'csv', 'pdf', 'png', 'jpg', 'jpeg'], 
                   message='Invalid file type. Allowed: Excel, CSV, PDF, Images')
    ])


class RosterRulesForm(FlaskForm):
    """Roster generation rules form"""
    min_staff_per_day = IntegerField('Minimum Staff per Day', validators=[
        DataRequired(message='Minimum staff is required'),
    ], default=2)
    max_consecutive_days = IntegerField('Maximum Consecutive Days', validators=[
        DataRequired(message='Maximum consecutive days is required'),
    ], default=5)
    roster_start = DateField('Roster Start Date', validators=[
        DataRequired(message='Start date is required')
    ])
    roster_end = DateField('Roster End Date', validators=[
        DataRequired(message='End date is required')
    ])
    staff_column = HiddenField()
    specialty_column = HiddenField()
    date_column = HiddenField()
    end_date_column = HiddenField()
    use_advanced_algorithm = BooleanField('Use Advanced Algorithm (CSP)')
    
    def validate_roster_end(self, field):
        """Ensure end date is after start date"""
        if field.data and self.roster_start.data and field.data < self.roster_start.data:
            raise ValidationError('End date must be after start date')
    
    def validate_max_consecutive_days(self, field):
        """Validate max consecutive days"""
        if field.data < 1:
            raise ValidationError('Maximum consecutive days must be at least 1')
        if field.data > 14:
            raise ValidationError('Maximum consecutive days cannot exceed 14')


class EmergencyLeaveForm(FlaskForm):
    """Emergency leave update form"""
    staff_name = StringField('Staff Name', validators=[
        DataRequired(message='Staff name is required')
    ])
    leave_date = DateField('Leave Date', validators=[
        DataRequired(message='Leave date is required')
    ])
    reason = StringField('Reason', validators=[
        Optional(),
        Length(max=200)
    ])
    replacement_staff = StringField('Replacement Staff', validators=[
        Optional(),
        Length(max=100)
    ])
    
    def validate_leave_date(self, field):
        """Ensure leave date is not in the past"""
        if field.data < datetime.now().date():
            raise ValidationError('Cannot update roster for past dates')


class ProfileForm(FlaskForm):
    """Roster profile configuration form"""
    name = StringField('Profile Name', validators=[
        DataRequired(message='Profile name is required'),
        Length(max=100)
    ])
    description = TextAreaField('Description', validators=[
        Optional(),
        Length(max=500)
    ])


class ShareProfileForm(FlaskForm):
    """Share roster profile form"""
    email = StringField('Recipient Email', validators=[
        DataRequired(message='Email is required'),
        Email(message='Invalid email address')
    ])
    message = TextAreaField('Message (Optional)', validators=[
        Optional(),
        Length(max=500)
    ])


class StaffPreferenceForm(FlaskForm):
    """Staff preference form"""
    staff_name = StringField('Staff Name', validators=[
        DataRequired(message='Staff name is required'),
        Length(max=100)
    ])
    staff_email = StringField('Email', validators=[
        Optional(),
        Email(message='Invalid email address')
    ])
    specialty = StringField('Specialty', validators=[
        Optional(),
        Length(max=50)
    ])
    max_consecutive_days = IntegerField('Max Consecutive Days', 
                                      validators=[Optional()], 
                                      default=5)
    min_rest_days = IntegerField('Min Rest Days Between Shifts', 
                                validators=[Optional()], 
                                default=2)
    weekend_preference_score = IntegerField('Weekend Preference (0-10)', 
                                          validators=[Optional()], 
                                          default=5)
    holiday_preference_score = IntegerField('Holiday Preference (0-10)', 
                                          validators=[Optional()], 
                                          default=5)
    
    def validate_weekend_preference_score(self, field):
        """Validate preference score range"""
        if field.data is not None and (field.data < 0 or field.data > 10):
            raise ValidationError('Score must be between 0 and 10')
    
    def validate_holiday_preference_score(self, field):
        """Validate preference score range"""
        if field.data is not None and (field.data < 0 or field.data > 10):
            raise ValidationError('Score must be between 0 and 10')