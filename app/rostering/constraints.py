"""Constraint implementations for rostering"""
from typing import Dict, List, Set, Tuple
from datetime import datetime, timedelta
from .csp import Constraint, ConstraintType
import logging

logger = logging.getLogger(__name__)


class MinimumStaffConstraint(Constraint):
    """Ensure minimum staff coverage per day"""
    
    def __init__(self, min_staff: int, dates: List[str], staff: List[str]):
        super().__init__("minimum_staff", ConstraintType.HARD)
        self.min_staff = min_staff
        self.dates = dates
        self.staff = staff
    
    def check(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Check if each day has minimum staff"""
        for date in self.dates:
            staff_count = sum(
                assignment.get((staff, date), 0) 
                for staff in self.staff
            )
            if staff_count < self.min_staff:
                logger.debug(f"Date {date} has only {staff_count} staff (min: {self.min_staff})")
                return False
        return True
    
    def get_violated_assignments(self, assignment: Dict[Tuple[str, str], int]) -> List[str]:
        """Get dates that don't meet minimum staff requirement"""
        violated_dates = []
        for date in self.dates:
            staff_count = sum(
                assignment.get((staff, date), 0) 
                for staff in self.staff
            )
            if staff_count < self.min_staff:
                violated_dates.append(date)
        return violated_dates


class MaxConsecutiveDaysConstraint(Constraint):
    """Limit consecutive working days"""
    
    def __init__(self, max_days: int, dates: List[str], staff: List[str]):
        super().__init__("max_consecutive_days", ConstraintType.HARD)
        self.max_days = max_days
        self.dates = dates
        self.staff = staff
    
    def check(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Check if any staff exceeds max consecutive days"""
        for staff in self.staff:
            consecutive = 0
            for date in self.dates:
                if assignment.get((staff, date), 0) == 1:
                    consecutive += 1
                    if consecutive > self.max_days:
                        logger.debug(f"{staff} works {consecutive} consecutive days (max: {self.max_days})")
                        return False
                else:
                    consecutive = 0
        return True
    
    def get_violated_staff(self, assignment: Dict[Tuple[str, str], int]) -> List[str]:
        """Get staff who violate consecutive days constraint"""
        violated_staff = []
        for staff in self.staff:
            consecutive = 0
            max_consecutive = 0
            for date in self.dates:
                if assignment.get((staff, date), 0) == 1:
                    consecutive += 1
                    max_consecutive = max(max_consecutive, consecutive)
                else:
                    consecutive = 0
            
            if max_consecutive > self.max_days:
                violated_staff.append(staff)
        
        return violated_staff


class MinRestPeriodConstraint(Constraint):
    """Ensure minimum rest between shifts"""
    
    def __init__(self, min_rest_days: int, dates: List[str], staff: List[str]):
        super().__init__("min_rest_period", ConstraintType.HARD)
        self.min_rest_days = min_rest_days
        self.dates = dates
        self.staff = staff
    
    def check(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Check minimum rest period between shifts"""
        for staff in self.staff:
            last_work_idx = None
            
            for i, date in enumerate(self.dates):
                if assignment.get((staff, date), 0) == 1:
                    if last_work_idx is not None:
                        days_between = i - last_work_idx - 1
                        if days_between < self.min_rest_days:
                            logger.debug(f"{staff} has only {days_between} rest days (min: {self.min_rest_days})")
                            return False
                    last_work_idx = i
        
        return True


class SpecialtyCoverageConstraint(Constraint):
    """Ensure each specialty is represented daily"""
    
    def __init__(self, specialties: Dict[str, str], dates: List[str], 
                 min_specialties_per_day: Optional[int] = None):
        super().__init__("specialty_coverage", ConstraintType.HARD)
        self.specialties = specialties  # staff -> specialty
        self.dates = dates
        self.unique_specialties = set(specialties.values())
        self.min_specialties_per_day = min_specialties_per_day or len(self.unique_specialties)
        self.staff_by_specialty = self._group_by_specialty()
    
    def _group_by_specialty(self) -> Dict[str, List[str]]:
        """Group staff by specialty"""
        grouped = {}
        for staff, specialty in self.specialties.items():
            if specialty not in grouped:
                grouped[specialty] = []
            grouped[specialty].append(staff)
        return grouped
    
    def check(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Check if specialties are adequately covered"""
        for date in self.dates:
            covered_specialties = set()
            available_staff = 0
            
            for staff, specialty in self.specialties.items():
                # Check if staff is available (not necessarily assigned)
                if (staff, date) in assignment:
                    if assignment.get((staff, date), 0) == 1:
                        covered_specialties.add(specialty)
                    available_staff += 1
            
            # Adjust requirement based on available staff
            required_specialties = min(
                self.min_specialties_per_day,
                len(self.unique_specialties),
                available_staff
            )
            
            if len(covered_specialties) < required_specialties:
                logger.debug(f"Date {date}: {len(covered_specialties)} specialties covered (need {required_specialties})")
                return False
        
        return True


class FairWorkloadConstraint(Constraint):
    """Distribute workload fairly among staff"""
    
    def __init__(self, staff: List[str], weight: float = 10.0, max_variance: float = 2.0):
        super().__init__("fair_workload", ConstraintType.SOFT, weight)
        self.staff = staff
        self.max_variance = max_variance
    
    def check(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Always returns True for soft constraints"""
        return True
    
    def penalty(self, assignment: Dict[Tuple[str, str], int]) -> float:
        """Calculate penalty based on workload variance"""
        workloads = {}
        for (staff, date), assigned in assignment.items():
            if assigned == 1:
                workloads[staff] = workloads.get(staff, 0) + 1
        
        # Ensure all staff are included
        for staff in self.staff:
            if staff not in workloads:
                workloads[staff] = 0
        
        if not workloads:
            return 0.0
        
        # Calculate mean and variance
        mean_workload = sum(workloads.values()) / len(self.staff)
        variance = sum((w - mean_workload) ** 2 for w in workloads.values()) / len(self.staff)
        
        # Penalty increases with variance
        if variance <= self.max_variance:
            return 0.0
        else:
            return self.weight * (variance - self.max_variance)


class WeekendPreferenceConstraint(Constraint):
    """Minimize weekend assignments based on preferences"""
    
    def __init__(self, preferences: Dict[str, float], dates: List[str], weight: float = 5.0):
        super().__init__("weekend_preference", ConstraintType.SOFT, weight)
        self.preferences = preferences  # staff -> penalty for weekend work
        self.dates = dates
        self.weekend_dates = self._identify_weekend_dates()
    
    def _identify_weekend_dates(self) -> Set[str]:
        """Identify weekend dates"""
        weekend_dates = set()
        for date_str in self.dates:
            date = datetime.strptime(date_str, '%Y-%m-%d')
            if date.weekday() >= 5:  # Saturday or Sunday
                weekend_dates.add(date_str)
        return weekend_dates
    
    def penalty(self, assignment: Dict[Tuple[str, str], int]) -> float:
        """Calculate penalty for weekend assignments"""
        total_penalty = 0.0
        
        for (staff, date), assigned in assignment.items():
            if assigned == 1 and date in self.weekend_dates:
                staff_penalty = self.preferences.get(staff, 5.0)  # Default penalty
                total_penalty += staff_penalty
        
        return self.weight * total_penalty


class HolidayDistributionConstraint(Constraint):
    """Fairly distribute holiday assignments"""
    
    def __init__(self, holidays: Set[str], historical_counts: Dict[str, int], 
                 staff: List[str], weight: float = 8.0):
        super().__init__("holiday_distribution", ConstraintType.SOFT, weight)
        self.holidays = holidays
        self.historical_counts = historical_counts  # staff -> past holiday count
        self.staff = staff
    
    def penalty(self, assignment: Dict[Tuple[str, str], int]) -> float:
        """Penalize uneven holiday distribution"""
        # Count holidays in current assignment
        holiday_assignments = {}
        for staff in self.staff:
            holiday_assignments[staff] = 0
        
        for (staff, date), assigned in assignment.items():
            if assigned == 1 and date in self.holidays:
                holiday_assignments[staff] = holiday_assignments.get(staff, 0) + 1
        
        # Calculate total holidays (historical + current)
        total_holidays = {}
        for staff in self.staff:
            historical = self.historical_counts.get(staff, 0)
            current = holiday_assignments.get(staff, 0)
            total_holidays[staff] = historical + current
        
        # Penalty based on variance in total holiday counts
        if not total_holidays:
            return 0.0
        
        mean_holidays = sum(total_holidays.values()) / len(self.staff)
        variance = sum((count - mean_holidays) ** 2 for count in total_holidays.values())
        
        return self.weight * variance


class TeamPreferenceConstraint(Constraint):
    """Prefer certain staff combinations"""
    
    def __init__(self, team_preferences: Dict[str, List[str]], 
                 dates: List[str], weight: float = 3.0):
        super().__init__("team_preference", ConstraintType.SOFT, weight)
        self.team_preferences = team_preferences  # staff -> [preferred teammates]
        self.dates = dates
    
    def penalty(self, assignment: Dict[Tuple[str, str], int]) -> float:
        """Reward when preferred teammates work together"""
        total_penalty = 0.0
        
        for date in self.dates:
            # Get staff working on this date
            working_staff = [
                staff for staff, d in assignment 
                if d == date and assignment.get((staff, date), 0) == 1
            ]
            
            # Check preferences
            for staff in working_staff:
                if staff in self.team_preferences:
                    preferred = self.team_preferences[staff]
                    # Count how many preferred teammates are working
                    working_preferred = sum(1 for p in preferred if p in working_staff)
                    # Penalty for each missing preferred teammate
                    total_penalty += (len(preferred) - working_preferred)
        
        return self.weight * total_penalty