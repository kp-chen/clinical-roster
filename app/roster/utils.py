"""Roster generation utilities"""
from datetime import datetime, timedelta
import pandas as pd
import holidays
import logging
from typing import List, Dict
from app.rostering.csp import RosterCSP
from app.rostering.solver import RosterSolver
from app.rostering.constraints import (
    MinimumStaffConstraint, MaxConsecutiveDaysConstraint,
    SpecialtyCoverageConstraint, FairWorkloadConstraint,
    WeekendPreferenceConstraint, HolidayDistributionConstraint
)
from app.models.roster import StaffPreference

logger = logging.getLogger(__name__)

# Singapore holidays
sg_holidays = holidays.Singapore()


def generate_roster_logic(filepath: str, rules: dict) -> dict:
    """Core roster generation algorithm with Singapore holidays support"""
    try:
        # Load leave data
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Extract rule parameters
        staff_col = rules['staff_column']
        specialty_col = rules['specialty_column']
        start_date_col = rules['date_column']
        end_date_col = rules.get('end_date_column')
        min_staff = rules['min_staff_per_day']
        roster_start = datetime.strptime(rules['roster_start'], '%Y-%m-%d')
        roster_end = datetime.strptime(rules['roster_end'], '%Y-%m-%d')
        
        # Get unique staff and specialties
        all_staff = df[staff_col].unique().tolist()
        all_specialties = df[specialty_col].unique().tolist()
        
        # Create leave tracking
        leave_dates = {}
        for _, row in df.iterrows():
            staff = row[staff_col]
            start_date = pd.to_datetime(row[start_date_col])
            
            if end_date_col and pd.notna(row[end_date_col]):
                end_date = pd.to_datetime(row[end_date_col])
            else:
                end_date = start_date
            
            if staff not in leave_dates:
                leave_dates[staff] = []
            
            # Add all dates in the leave period
            current_date = start_date
            while current_date <= end_date:
                leave_dates[staff].append(current_date.date())
                current_date += timedelta(days=1)
        
        # Generate roster for each day
        roster = {}
        current_date = roster_start
        staff_work_count = {staff: 0 for staff in all_staff}
        
        while current_date <= roster_end:
            date_str = current_date.strftime('%Y-%m-%d')
            
            # Find available staff for this date
            available_staff = []
            for staff in all_staff:
                if staff not in leave_dates or current_date.date() not in leave_dates[staff]:
                    available_staff.append(staff)
            
            # Sort by work count (fair distribution)
            available_staff.sort(key=lambda x: staff_work_count[x])
            
            # Select minimum required staff
            selected_staff = available_staff[:min_staff]
            
            # Enhanced specialty-based selection
            if len(available_staff) >= len(all_specialties):
                # If we have enough staff, try to get at least one from each specialty
                selected_staff = []
                selected_specialties = set()
                
                # Group available staff by specialty
                staff_by_specialty = {}
                for staff in available_staff:
                    specialty = df[df[staff_col] == staff][specialty_col].iloc[0]
                    if specialty not in staff_by_specialty:
                        staff_by_specialty[specialty] = []
                    staff_by_specialty[specialty].append(staff)
                
                # Sort specialties by their staff count (ascending) for fair distribution
                sorted_specialties = sorted(staff_by_specialty.keys(), 
                                          key=lambda x: len(staff_by_specialty[x]))
                
                # Select one staff from each specialty first
                for specialty in sorted_specialties:
                    if len(selected_staff) < min_staff:
                        # Sort staff within specialty by work count
                        specialty_staff = sorted(staff_by_specialty[specialty], 
                                               key=lambda x: staff_work_count[x])
                        selected_staff.append(specialty_staff[0])
                        selected_specialties.add(specialty)
                
                # If we still need more staff, add based on fair distribution
                remaining_staff = [s for s in available_staff if s not in selected_staff]
                remaining_staff.sort(key=lambda x: staff_work_count[x])
                
                while len(selected_staff) < min_staff and remaining_staff:
                    selected_staff.append(remaining_staff.pop(0))
                    
            else:
                # Not enough staff to cover all specialties, just select by fair distribution
                selected_specialties = set()
                for staff in selected_staff:
                    specialty = df[df[staff_col] == staff][specialty_col].iloc[0]
                    selected_specialties.add(specialty)
            
            # Update work counts
            for staff in selected_staff:
                staff_work_count[staff] += 1
            
            # Check if it's a public holiday
            is_holiday = current_date.date() in sg_holidays
            holiday_name = sg_holidays.get(current_date.date(), '')
            
            # Apply Monday in-lieu for Sunday holidays
            is_in_lieu = False
            if current_date.weekday() == 0:  # Monday
                yesterday = current_date - timedelta(days=1)
                if yesterday.date() in sg_holidays:
                    is_holiday = True
                    is_in_lieu = True
                    holiday_name = f"{sg_holidays.get(yesterday.date())} (In Lieu)"
            
            # Store roster for this date
            roster[date_str] = {
                'staff': selected_staff,
                'specialties': list(selected_specialties),
                'available_count': len(available_staff),
                'is_weekend': current_date.weekday() >= 5,
                'is_holiday': is_holiday,
                'holiday_name': holiday_name,
                'is_in_lieu': is_in_lieu
            }
            
            current_date += timedelta(days=1)
        
        # Calculate statistics
        total_days = len(roster)
        days_understaffed = sum(1 for day in roster.values() if len(day['staff']) < min_staff)
        coverage_stats = {
            'total_days': total_days,
            'days_understaffed': days_understaffed,
            'coverage_percentage': ((total_days - days_understaffed) / total_days) * 100,
            'staff_work_distribution': staff_work_count,
            'weekend_days': sum(1 for day in roster.values() if day['is_weekend']),
            'holiday_days': sum(1 for day in roster.values() if day['is_holiday'])
        }
        
        return {
            'roster': roster,
            'stats': coverage_stats,
            'staff_list': all_staff,
            'specialties': all_specialties,
            'rules': rules
        }
        
    except Exception as e:
        raise Exception(f"Error generating roster: {str(e)}")


def generate_roster_advanced(filepath: str, rules: dict) -> dict:
    """Generate roster using CSP approach"""
    try:
        # Load data (reuse existing logic)
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Extract parameters
        staff_col = rules['staff_column']
        specialty_col = rules['specialty_column']
        staff_list = df[staff_col].unique().tolist()
        specialties = dict(zip(
            df[staff_col], 
            df[specialty_col]
        ))
        
        # Date range
        start_date = datetime.strptime(rules['roster_start'], '%Y-%m-%d')
        end_date = datetime.strptime(rules['roster_end'], '%Y-%m-%d')
        dates = []
        current = start_date
        while current <= end_date:
            dates.append(current.strftime('%Y-%m-%d'))
            current += timedelta(days=1)
        
        # Create CSP
        csp = RosterCSP(staff_list, dates, specialties)
        
        # Add hard constraints
        csp.add_constraint(MinimumStaffConstraint(rules['min_staff_per_day']))
        csp.add_constraint(MaxConsecutiveDaysConstraint(rules.get('max_consecutive_days', 5)))
        csp.add_constraint(SpecialtyCoverageConstraint(specialties))
        
        # Add soft constraints
        csp.add_constraint(FairWorkloadConstraint())
        
        # Get preferences from database
        weekend_prefs = {}
        holiday_history = {}
        
        for staff in staff_list:
            pref = StaffPreference.query.filter_by(staff_name=staff).first()
            if pref:
                weekend_prefs[staff] = 10 - pref.weekend_preference_score  # Invert for penalty
                holiday_history[staff] = pref.total_holidays_worked
            else:
                weekend_prefs[staff] = 5.0
                holiday_history[staff] = 0
        
        csp.add_constraint(WeekendPreferenceConstraint(weekend_prefs))
        
        # Holiday constraint
        holidays_set = set()
        for date_str in dates:
            date = datetime.strptime(date_str, '%Y-%m-%d').date()
            if date in sg_holidays:
                holidays_set.add(date_str)
        
        if holidays_set:
            csp.add_constraint(HolidayDistributionConstraint(holidays_set, holiday_history))
        
        # Initialize domains with leave schedule
        leave_schedule = extract_leave_schedule(df, rules)
        csp.initialize_domains(leave_schedule)
        
        # Solve
        solver = RosterSolver(csp)
        solution = solver.solve_with_pulp()
        
        if solution:
            # Convert solution to roster format
            return format_solution_as_roster(solution, dates, staff_list, specialties)
        else:
            # Fallback to greedy algorithm
            logger.warning("CSP solver failed, falling back to greedy algorithm")
            return generate_roster_logic(filepath, rules)
            
    except Exception as e:
        logger.error(f"Advanced roster generation failed: {str(e)}")
        # Fallback to greedy algorithm
        return generate_roster_logic(filepath, rules)


def extract_leave_schedule(df: pd.DataFrame, rules: dict) -> Dict[str, List[str]]:
    """Extract leave schedule from dataframe"""
    leave_schedule = {}
    
    staff_col = rules['staff_column']
    start_date_col = rules['date_column']
    end_date_col = rules.get('end_date_column')
    
    for _, row in df.iterrows():
        staff = row[staff_col]
        start_date = pd.to_datetime(row[start_date_col])
        
        if end_date_col and pd.notna(row[end_date_col]):
            end_date = pd.to_datetime(row[end_date_col])
        else:
            end_date = start_date
        
        # Add all dates in the leave period
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            if date_str not in leave_schedule:
                leave_schedule[date_str] = []
            leave_schedule[date_str].append(staff)
            current_date += timedelta(days=1)
    
    return leave_schedule


def format_solution_as_roster(solution: Dict, dates: List[str], 
                             staff_list: List[str], specialties: Dict[str, str]) -> Dict:
    """Convert CSP solution to roster format"""
    roster = {}
    
    for date in dates:
        assigned_staff = []
        assigned_specialties = set()
        
        for staff in staff_list:
            if solution.get((staff, date), 0) == 1:
                assigned_staff.append(staff)
                assigned_specialties.add(specialties[staff])
        
        # Check date properties
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        is_holiday = date_obj.date() in sg_holidays
        holiday_name = sg_holidays.get(date_obj.date(), '')
        
        # Monday in-lieu check
        is_in_lieu = False
        if date_obj.weekday() == 0:  # Monday
            yesterday = date_obj - timedelta(days=1)
            if yesterday.date() in sg_holidays:
                is_holiday = True
                is_in_lieu = True
                holiday_name = f"{sg_holidays.get(yesterday.date())} (In Lieu)"
        
        roster[date] = {
            'staff': assigned_staff,
            'specialties': list(assigned_specialties),
            'available_count': len([s for s in staff_list if solution.get((s, date), 0) >= 0]),
            'is_weekend': date_obj.weekday() >= 5,
            'is_holiday': is_holiday,
            'holiday_name': holiday_name,
            'is_in_lieu': is_in_lieu
        }
    
    # Calculate statistics
    staff_work_count = {}
    for (staff, date), assigned in solution.items():
        if assigned == 1:
            staff_work_count[staff] = staff_work_count.get(staff, 0) + 1
    
    total_days = len(dates)
    days_understaffed = sum(1 for day in roster.values() if len(day['staff']) < 2)  # Assuming min 2
    
    stats = {
        'total_days': total_days,
        'days_understaffed': days_understaffed,
        'coverage_percentage': ((total_days - days_understaffed) / total_days) * 100,
        'staff_work_distribution': staff_work_count,
        'weekend_days': sum(1 for day in roster.values() if day['is_weekend']),
        'holiday_days': sum(1 for day in roster.values() if day['is_holiday'])
    }
    
    return {
        'roster': roster,
        'stats': stats,
        'staff_list': staff_list,
        'specialties': list(set(specialties.values()))
    }