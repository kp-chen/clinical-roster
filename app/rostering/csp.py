"""Constraint Satisfaction Problem framework for rostering"""
from typing import List, Dict, Set, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ConstraintType(Enum):
    """Types of constraints"""
    HARD = "hard"  # Must be satisfied
    SOFT = "soft"  # Should be satisfied if possible


@dataclass
class Constraint:
    """Base constraint class"""
    name: str
    type: ConstraintType
    weight: float = 1.0  # For soft constraints
    
    def check(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Check if constraint is satisfied"""
        raise NotImplementedError
    
    def penalty(self, assignment: Dict[Tuple[str, str], int]) -> float:
        """Calculate penalty for soft constraints"""
        return 0.0 if self.check(assignment) else self.weight
    
    def get_violated_assignments(self, assignment: Dict[Tuple[str, str], int]) -> List[Tuple[str, str]]:
        """Get list of assignments that violate this constraint"""
        return []


class RosterCSP:
    """Constraint Satisfaction Problem for roster generation"""
    
    def __init__(self, staff: List[str], dates: List[str], specialties: Dict[str, str]):
        self.staff = staff
        self.dates = dates
        self.specialties = specialties
        self.constraints: List[Constraint] = []
        self.domains: Dict[Tuple[str, str], Set[int]] = {}  # (staff, date) -> {0, 1}
        
        # Initialize all domains to {0, 1} (not assigned, assigned)
        for s in staff:
            for d in dates:
                self.domains[(s, d)] = {0, 1}
        
        logger.info(f"Initialized CSP with {len(staff)} staff and {len(dates)} dates")
    
    def add_constraint(self, constraint: Constraint):
        """Add a constraint to the problem"""
        self.constraints.append(constraint)
        logger.info(f"Added constraint: {constraint.name} ({constraint.type.value})")
    
    def initialize_domains(self, leave_schedule: Dict[str, List[str]]):
        """Initialize domains based on availability"""
        # leave_schedule: date -> [staff on leave]
        for date, staff_on_leave in leave_schedule.items():
            for staff in staff_on_leave:
                if (staff, date) in self.domains:
                    # Staff on leave - domain is {0} only
                    self.domains[(staff, date)] = {0}
                    logger.debug(f"{staff} marked unavailable on {date}")
        
        # Count available slots
        available_count = sum(1 for domain in self.domains.values() if 1 in domain)
        total_slots = len(self.staff) * len(self.dates)
        logger.info(f"Available slots: {available_count}/{total_slots} ({available_count/total_slots*100:.1f}%)")
    
    def get_hard_constraints(self) -> List[Constraint]:
        """Get all hard constraints"""
        return [c for c in self.constraints if c.type == ConstraintType.HARD]
    
    def get_soft_constraints(self) -> List[Constraint]:
        """Get all soft constraints"""
        return [c for c in self.constraints if c.type == ConstraintType.SOFT]
    
    def is_consistent(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Check if assignment satisfies all hard constraints"""
        for constraint in self.get_hard_constraints():
            if not constraint.check(assignment):
                logger.debug(f"Hard constraint violated: {constraint.name}")
                return False
        return True
    
    def calculate_penalty(self, assignment: Dict[Tuple[str, str], int]) -> float:
        """Calculate total penalty for soft constraints"""
        total_penalty = 0.0
        for constraint in self.get_soft_constraints():
            penalty = constraint.penalty(assignment)
            if penalty > 0:
                logger.debug(f"Soft constraint {constraint.name} penalty: {penalty}")
            total_penalty += penalty
        return total_penalty
    
    def get_unassigned_variables(self, assignment: Dict[Tuple[str, str], int]) -> List[Tuple[str, str]]:
        """Get variables that haven't been assigned yet"""
        unassigned = []
        for staff in self.staff:
            for date in self.dates:
                if (staff, date) not in assignment:
                    unassigned.append((staff, date))
        return unassigned
    
    def is_complete(self, assignment: Dict[Tuple[str, str], int]) -> bool:
        """Check if assignment is complete"""
        return len(assignment) == len(self.staff) * len(self.dates)
    
    def get_consistent_values(self, var: Tuple[str, str], 
                            assignment: Dict[Tuple[str, str], int]) -> List[int]:
        """Get values that maintain consistency when assigned to var"""
        staff, date = var
        consistent_values = []
        
        for value in self.domains[var]:
            # Try assigning this value
            test_assignment = assignment.copy()
            test_assignment[var] = value
            
            # Check if it maintains consistency
            if self.is_consistent(test_assignment):
                consistent_values.append(value)
        
        return consistent_values
    
    def inference(self, var: Tuple[str, str], value: int, 
                  assignment: Dict[Tuple[str, str], int]) -> Optional[Dict[Tuple[str, str], Set[int]]]:
        """
        Perform constraint propagation inference
        Returns updated domains or None if inconsistency detected
        """
        # Simple forward checking
        new_domains = {k: v.copy() for k, v in self.domains.items()}
        
        # For now, just return the domains without modification
        # More sophisticated inference can be added later
        return new_domains
    
    def select_unassigned_variable(self, assignment: Dict[Tuple[str, str], int]) -> Optional[Tuple[str, str]]:
        """
        Select next variable to assign using MRV heuristic
        (Minimum Remaining Values - choose variable with fewest legal values)
        """
        unassigned = self.get_unassigned_variables(assignment)
        if not unassigned:
            return None
        
        # Calculate legal values for each unassigned variable
        min_values = float('inf')
        best_var = None
        
        for var in unassigned:
            legal_values = self.get_consistent_values(var, assignment)
            if len(legal_values) < min_values:
                min_values = len(legal_values)
                best_var = var
        
        return best_var
    
    def order_domain_values(self, var: Tuple[str, str], 
                           assignment: Dict[Tuple[str, str], int]) -> List[int]:
        """
        Order domain values using least constraining value heuristic
        Choose value that rules out the fewest choices for other variables
        """
        values = list(self.domains[var])
        
        # For now, prefer assigning (1) over not assigning (0)
        # More sophisticated ordering can be added
        return sorted(values, reverse=True)
    
    def get_statistics(self, assignment: Dict[Tuple[str, str], int]) -> Dict:
        """Get statistics about the current assignment"""
        stats = {
            'total_slots': len(self.staff) * len(self.dates),
            'assigned_slots': sum(1 for v in assignment.values() if v == 1),
            'coverage_by_date': {},
            'workload_by_staff': {},
            'hard_constraints_satisfied': self.is_consistent(assignment),
            'soft_constraint_penalty': self.calculate_penalty(assignment)
        }
        
        # Calculate coverage by date
        for date in self.dates:
            assigned = sum(1 for s in self.staff if assignment.get((s, date), 0) == 1)
            stats['coverage_by_date'][date] = assigned
        
        # Calculate workload by staff
        for staff in self.staff:
            workdays = sum(1 for d in self.dates if assignment.get((staff, d), 0) == 1)
            stats['workload_by_staff'][staff] = workdays
        
        return stats