# Clinical Roster Builder - Project Context

## Overview
Flask web app for creating medical staff rosters based on leave schedules and clinical specialties.

## Tech Stack
- Backend: Flask 3.0.0
- Data Processing: pandas
- File Handling: openpyxl (Excel files)  
- Frontend: Jinja2 templates, vanilla CSS
- Python: 3.10+
- Development: Ubuntu WSL, VS Code

## Project Structure
- app.py: Main Flask application
- templates/: Jinja2 HTML templates
  - base.html: Base template with common styling
  - index.html: Home page
  - upload.html: Leave schedule upload
  - configure_rules.html: Rules configuration
  - roster.html: Display generated roster
- uploads/: Temporary file storage (gitignored)
- static/: CSS/JS files (to be created)
- requirements.txt: Python dependencies
- CLAUDE.md: This file
- README.md: User documentation

## Current Features
1. File upload (Excel/CSV) for leave schedules
2. Basic rule configuration interface
3. Column mapping for flexible file formats

## TODO Priority List
1. Implement roster generation algorithm
2. Add database (SQLite) for storing rosters
3. Specialty-based minimum coverage rules  
4. Export roster as Excel/PDF
5. Advanced constraints (max consecutive days, fair distribution)
6. User authentication
7. Real-time roster validation

## Key Business Rules
- Each day must have minimum staff coverage
- Respect all leave requests (non-negotiable)
- Ensure specialty coverage when possible
- Distribute weekend/holiday shifts fairly
- Account for part-time staff availability

## Code Conventions
- Type hints for function parameters
- Docstrings for all functions
- Handle errors gracefully with user-friendly messages
- Validate all user inputs
- Use datetime for all date operations
- Comment complex logic

## Development Workflow
- Activate environment: source venv/bin/activate
- Run application: python app.py
- Install new packages: pip install package_name && pip freeze > requirements.txt
- Git workflow: add, commit with descriptive message, push to origin main

## Expected Data Format
Leave schedule should contain:
- Staff_Name: Doctor's name
- Specialty: Clinical specialty  
- Leave_Start: Start date (YYYY-MM-DD)
- Leave_End: End date (YYYY-MM-DD)
- Leave_Type: Optional leave category

## Current Implementation Status
- DONE: Basic Flask setup with templates
- DONE: File upload functionality
- DONE: Preview uploaded data
- DONE: Column mapping interface
- IN PROGRESS: Roster generation logic
- TODO: Database storage
- TODO: Export functionality
- TODO: Advanced rules engine

## Architecture Decisions
- Using Flask for simplicity and quick development
- Pandas for data manipulation (medical staff familiar with Excel-like operations)
- SQLite for local storage (can migrate to PostgreSQL for production)
- Server-side rendering with Jinja2 (no frontend framework needed initially)

## Notes for Future Development
- Consider adding API endpoints for integration with hospital systems
- May need to handle multiple departments/wards separately
- Consider shift patterns (day/night/on-call)
- Holiday and weekend weighting for fairness
- Integration with existing HR systems via CSV/API