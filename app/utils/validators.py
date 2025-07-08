"""Validation utilities"""
import re
from datetime import datetime, date
from typing import Optional, List, Dict


def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))


def validate_password_strength(password: str) -> Dict[str, bool]:
    """
    Validate password strength and return detailed results
    
    Returns dict with:
    - valid: Overall validity
    - length: At least 8 characters
    - uppercase: Contains uppercase letter
    - lowercase: Contains lowercase letter
    - digit: Contains number
    - special: Contains special character
    """
    results = {
        'valid': True,
        'length': len(password) >= 8,
        'uppercase': bool(re.search(r'[A-Z]', password)),
        'lowercase': bool(re.search(r'[a-z]', password)),
        'digit': bool(re.search(r'\d', password)),
        'special': bool(re.search(r'[!@#$%^&*(),.?":{}|<>]', password))
    }
    
    # Overall validity requires all checks to pass
    results['valid'] = all([
        results['length'],
        results['uppercase'],
        results['lowercase'],
        results['digit'],
        results['special']
    ])
    
    return results


def validate_date_range(start_date: date, end_date: date, 
                       max_days: Optional[int] = None) -> bool:
    """Validate date range"""
    if start_date > end_date:
        return False
    
    if max_days:
        delta = (end_date - start_date).days
        if delta > max_days:
            return False
    
    return True


def validate_phone_number(phone: str, country_code: str = 'SG') -> bool:
    """Validate phone number format"""
    # Remove spaces, dashes, and parentheses
    phone = re.sub(r'[\s\-\(\)]', '', phone)
    
    if country_code == 'SG':
        # Singapore phone numbers: +65 8XXX XXXX or 9XXX XXXX
        pattern = r'^(\+65)?[89]\d{7}$'
        return bool(re.match(pattern, phone))
    
    # Generic international format
    pattern = r'^\+?\d{10,15}$'
    return bool(re.match(pattern, phone))


def validate_nric(nric: str) -> bool:
    """Validate Singapore NRIC/FIN format"""
    # Format: S1234567A
    pattern = r'^[STFG]\d{7}[A-Z]$'
    if not re.match(pattern, nric.upper()):
        return False
    
    # Could add checksum validation here
    return True


def validate_staff_id(staff_id: str) -> bool:
    """Validate staff ID format"""
    # Alphanumeric, 4-10 characters
    pattern = r'^[A-Z0-9]{4,10}$'
    return bool(re.match(pattern, staff_id.upper()))


def validate_file_type(filename: str, allowed_extensions: List[str]) -> bool:
    """Validate file extension"""
    if '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in allowed_extensions


def validate_roster_rules(rules: Dict) -> List[str]:
    """
    Validate roster generation rules
    Returns list of validation errors (empty if valid)
    """
    errors = []
    
    # Required fields
    required = ['min_staff_per_day', 'roster_start', 'roster_end', 
                'staff_column', 'specialty_column', 'date_column']
    
    for field in required:
        if field not in rules:
            errors.append(f"Missing required field: {field}")
    
    # Validate minimum staff
    if 'min_staff_per_day' in rules:
        try:
            min_staff = int(rules['min_staff_per_day'])
            if min_staff < 1:
                errors.append("Minimum staff must be at least 1")
            if min_staff > 100:
                errors.append("Minimum staff seems unreasonably high")
        except (ValueError, TypeError):
            errors.append("Minimum staff must be a number")
    
    # Validate dates
    try:
        if 'roster_start' in rules and 'roster_end' in rules:
            start = datetime.strptime(rules['roster_start'], '%Y-%m-%d').date()
            end = datetime.strptime(rules['roster_end'], '%Y-%m-%d').date()
            
            if start > end:
                errors.append("Start date must be before end date")
            
            # Maximum roster period (e.g., 3 months)
            if (end - start).days > 90:
                errors.append("Roster period cannot exceed 90 days")
    except ValueError:
        errors.append("Invalid date format (use YYYY-MM-DD)")
    
    # Validate max consecutive days
    if 'max_consecutive_days' in rules:
        try:
            max_days = int(rules.get('max_consecutive_days', 5))
            if max_days < 1 or max_days > 14:
                errors.append("Max consecutive days must be between 1 and 14")
        except (ValueError, TypeError):
            errors.append("Max consecutive days must be a number")
    
    return errors


def sanitize_input(text: str, max_length: Optional[int] = None, 
                  allow_html: bool = False) -> str:
    """Sanitize user input"""
    if not text:
        return ''
    
    # Remove null bytes
    text = text.replace('\x00', '')
    
    # Strip whitespace
    text = text.strip()
    
    # Remove HTML if not allowed
    if not allow_html:
        # Basic HTML stripping
        text = re.sub(r'<[^>]+>', '', text)
    
    # Limit length
    if max_length and len(text) > max_length:
        text = text[:max_length]
    
    return text


def validate_json_structure(data: Dict, schema: Dict) -> List[str]:
    """
    Validate JSON data against a simple schema
    
    Schema format:
    {
        'field_name': {'type': str, 'required': True},
        'other_field': {'type': int, 'required': False, 'min': 0, 'max': 100}
    }
    """
    errors = []
    
    for field, rules in schema.items():
        # Check required fields
        if rules.get('required', False) and field not in data:
            errors.append(f"Missing required field: {field}")
            continue
        
        if field not in data:
            continue
        
        value = data[field]
        
        # Type validation
        expected_type = rules.get('type')
        if expected_type and not isinstance(value, expected_type):
            errors.append(f"Field '{field}' must be of type {expected_type.__name__}")
            continue
        
        # Numeric range validation
        if isinstance(value, (int, float)):
            if 'min' in rules and value < rules['min']:
                errors.append(f"Field '{field}' must be at least {rules['min']}")
            if 'max' in rules and value > rules['max']:
                errors.append(f"Field '{field}' must be at most {rules['max']}")
        
        # String length validation
        if isinstance(value, str):
            if 'min_length' in rules and len(value) < rules['min_length']:
                errors.append(f"Field '{field}' must be at least {rules['min_length']} characters")
            if 'max_length' in rules and len(value) > rules['max_length']:
                errors.append(f"Field '{field}' must be at most {rules['max_length']} characters")
    
    return errors