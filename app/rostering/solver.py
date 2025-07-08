"""Solver implementation for roster CSP"""
from typing import Dict, Optional, List, Tuple
import pulp
import logging
from datetime import datetime
from .csp import RosterCSP, ConstraintType
from .constraints import (
    MinimumStaffConstraint, MaxConsecutiveDaysConstraint,
    MinRestPeriodConstraint, SpecialtyCoverageConstraint
)

logger = logging.getLogger(__name__)


class RosterSolver:
    """Solver for roster generation using various algorithms"""
    
    def __init__(self, csp: RosterCSP):
        self.csp = csp
        self.solution = None
        self.solve_time = None
        self.iterations = 0
    
    def solve_with_pulp(self) -> Optional[Dict[Tuple[str, str], int]]:
        """Solve using integer programming with PuLP"""
        logger.info("Starting PuLP solver")
        start_time = datetime.now()
        
        try:
            # Create problem
            prob = pulp.LpProblem("Healthcare_Roster", pulp.LpMinimize)
            
            # Decision variables
            x = {}
            for staff in self.csp.staff:
                for date in self.csp.dates:
                    if 1 in self.csp.domains.get((staff, date), {0}):
                        x[(staff, date)] = pulp.LpVariable(
                            f"assign_{staff}_{date}", 
                            cat='Binary'
                        )
                    else:
                        # Staff not available
                        x[(staff, date)] = 0
            
            # Objective function (minimize soft constraint penalties)
            # For now, simple objective to minimize total assignments (will enhance later)
            soft_penalty_vars = []
            
            # Add workload variance penalty
            workload_vars = {}
            for staff in self.csp.staff:
                workload_vars[staff] = pulp.LpVariable(
                    f"workload_{staff}", 
                    lowBound=0, 
                    cat='Integer'
                )
                # Workload equals sum of assignments
                prob += workload_vars[staff] == pulp.lpSum(
                    x[(staff, date)] for date in self.csp.dates 
                    if (staff, date) in x and isinstance(x[(staff, date)], pulp.LpVariable)
                )
            
            # Add variance penalty (simplified)
            mean_workload = pulp.LpVariable("mean_workload", lowBound=0)
            prob += mean_workload * len(self.csp.staff) == pulp.lpSum(workload_vars.values())
            
            # Minimize variance (simplified - just minimize max difference from mean)
            max_deviation = pulp.LpVariable("max_deviation", lowBound=0)
            for staff in self.csp.staff:
                prob += workload_vars[staff] - mean_workload <= max_deviation
                prob += mean_workload - workload_vars[staff] <= max_deviation
            
            # Objective: minimize maximum deviation
            prob += max_deviation
            
            # Add hard constraints
            for constraint in self.csp.get_hard_constraints():
                self._add_hard_constraint_to_model(prob, x, constraint)
            
            # Solve
            logger.info("Solving integer program...")
            prob.solve(pulp.PULP_CBC_CMD(msg=0))  # Suppress solver output
            
            self.solve_time = (datetime.now() - start_time).total_seconds()
            
            if prob.status == pulp.LpStatusOptimal:
                logger.info(f"Optimal solution found in {self.solve_time:.2f} seconds")
                
                # Extract solution
                solution = {}
                for (staff, date), var in x.items():
                    if isinstance(var, pulp.LpVariable):
                        solution[(staff, date)] = int(var.varValue or 0)
                    else:
                        solution[(staff, date)] = int(var)
                
                self.solution = solution
                return solution
            else:
                logger.warning(f"No optimal solution found. Status: {pulp.LpStatus[prob.status]}")
                return None
                
        except Exception as e:
            logger.error(f"PuLP solver error: {str(e)}")
            return None
    
    def solve_with_backtracking(self) -> Optional[Dict[Tuple[str, str], int]]:
        """Solve using backtracking search"""
        logger.info("Starting backtracking solver")
        start_time = datetime.now()
        
        self.iterations = 0
        assignment = {}
        
        # Initialize with unavailable assignments
        for var, domain in self.csp.domains.items():
            if domain == {0}:
                assignment[var] = 0
        
        result = self._backtrack(assignment)
        
        self.solve_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Backtracking completed in {self.solve_time:.2f} seconds ({self.iterations} iterations)")
        
        if result:
            self.solution = result
        
        return result
    
    def _backtrack(self, assignment: Dict[Tuple[str, str], int]) -> Optional[Dict[Tuple[str, str], int]]:
        """Recursive backtracking search"""
        self.iterations += 1
        
        # Check if assignment is complete
        if self.csp.is_complete(assignment):
            if self.csp.is_consistent(assignment):
                return assignment
            return None
        
        # Select unassigned variable
        var = self.csp.select_unassigned_variable(assignment)
        if not var:
            return None
        
        # Try each value in domain
        for value in self.csp.order_domain_values(var, assignment):
            if value in self.csp.domains[var]:
                # Make assignment
                assignment[var] = value
                
                # Check consistency
                if self.csp.is_consistent(assignment):
                    # Recursive call
                    result = self._backtrack(assignment)
                    if result:
                        return result
                
                # Backtrack
                del assignment[var]
        
        return None
    
    def solve_greedy(self) -> Dict[Tuple[str, str], int]:
        """Greedy algorithm for quick solutions"""
        logger.info("Starting greedy solver")
        start_time = datetime.now()
        
        assignment = {}
        
        # Initialize with unavailable assignments
        for var, domain in self.csp.domains.items():
            if domain == {0}:
                assignment[var] = 0
            else:
                assignment[var] = 0  # Default to not assigned
        
        # Sort dates to process in order
        for date in self.csp.dates:
            # Count current assignments for this date
            current_count = sum(
                1 for staff in self.csp.staff 
                if assignment.get((staff, date), 0) == 1
            )
            
            # Get minimum required (assuming we have MinimumStaffConstraint)
            min_required = 2  # Default
            for constraint in self.csp.constraints:
                if isinstance(constraint, MinimumStaffConstraint):
                    min_required = constraint.min_staff
                    break
            
            # Get available staff sorted by current workload
            staff_workloads = []
            for staff in self.csp.staff:
                if 1 in self.csp.domains.get((staff, date), {0}):
                    workload = sum(
                        1 for d in self.csp.dates 
                        if assignment.get((staff, d), 0) == 1
                    )
                    staff_workloads.append((workload, staff))
            
            # Sort by workload (ascending)
            staff_workloads.sort()
            
            # Assign staff up to minimum required
            assigned = 0
            for _, staff in staff_workloads:
                if current_count + assigned >= min_required:
                    break
                
                # Check if assignment would violate constraints
                assignment[(staff, date)] = 1
                if self._check_staff_constraints(assignment, staff):
                    assigned += 1
                else:
                    assignment[(staff, date)] = 0
        
        self.solve_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Greedy solution found in {self.solve_time:.2f} seconds")
        
        self.solution = assignment
        return assignment
    
    def _check_staff_constraints(self, assignment: Dict[Tuple[str, str], int], staff: str) -> bool:
        """Check if staff assignment violates personal constraints"""
        # Check consecutive days
        consecutive = 0
        max_consecutive = 5  # Default
        
        for constraint in self.csp.constraints:
            if isinstance(constraint, MaxConsecutiveDaysConstraint):
                max_consecutive = constraint.max_days
                break
        
        for date in self.csp.dates:
            if assignment.get((staff, date), 0) == 1:
                consecutive += 1
                if consecutive > max_consecutive:
                    return False
            else:
                consecutive = 0
        
        return True
    
    def _add_hard_constraint_to_model(self, prob, x, constraint):
        """Add hard constraint to PuLP model"""
        if isinstance(constraint, MinimumStaffConstraint):
            # Minimum staff per day
            for date in self.csp.dates:
                staff_vars = [
                    x[(staff, date)] for staff in self.csp.staff
                    if (staff, date) in x and isinstance(x[(staff, date)], pulp.LpVariable)
                ]
                if staff_vars:
                    prob += pulp.lpSum(staff_vars) >= constraint.min_staff, f"MinStaff_{date}"
        
        elif isinstance(constraint, MaxConsecutiveDaysConstraint):
            # Maximum consecutive days
            for staff in self.csp.staff:
                for start_idx in range(len(self.csp.dates) - constraint.max_days):
                    consecutive_vars = []
                    for i in range(constraint.max_days + 1):
                        date = self.csp.dates[start_idx + i]
                        if (staff, date) in x and isinstance(x[(staff, date)], pulp.LpVariable):
                            consecutive_vars.append(x[(staff, date)])
                    
                    if consecutive_vars:
                        prob += pulp.lpSum(consecutive_vars) <= constraint.max_days, \
                                f"MaxConsec_{staff}_{start_idx}"
        
        elif isinstance(constraint, SpecialtyCoverageConstraint):
            # Specialty coverage (simplified - at least one per specialty if possible)
            for date in self.csp.dates:
                for specialty, staff_list in constraint.staff_by_specialty.items():
                    specialty_vars = [
                        x[(staff, date)] for staff in staff_list
                        if (staff, date) in x and isinstance(x[(staff, date)], pulp.LpVariable)
                    ]
                    if specialty_vars:
                        # At least one from each specialty (soft constraint for now)
                        pass  # Can be added as soft constraint with penalty
    
    def get_solution_statistics(self) -> Dict:
        """Get statistics about the solution"""
        if not self.solution:
            return {}
        
        stats = self.csp.get_statistics(self.solution)
        stats['solve_time'] = self.solve_time
        stats['iterations'] = self.iterations
        stats['algorithm'] = 'pulp' if 'Lp' in str(type(self.solution)) else 'backtracking'
        
        return stats
    
    def validate_solution(self) -> Tuple[bool, List[str]]:
        """Validate the solution against all constraints"""
        if not self.solution:
            return False, ["No solution found"]
        
        violations = []
        
        # Check hard constraints
        for constraint in self.csp.get_hard_constraints():
            if not constraint.check(self.solution):
                violations.append(f"Hard constraint violated: {constraint.name}")
        
        # Report soft constraint penalties
        for constraint in self.csp.get_soft_constraints():
            penalty = constraint.penalty(self.solution)
            if penalty > 0:
                violations.append(f"Soft constraint penalty: {constraint.name} = {penalty:.2f}")
        
        is_valid = all(not v.startswith("Hard constraint") for v in violations)
        
        return is_valid, violations