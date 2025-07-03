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
clinical-roster/
├── app.py              # Main Flask application
├── templates/          # Jinja2 HTML templates
│   ├── base.html      # Base template with common styling
│   ├── index.html     # Home page
│   ├── upload.html    # Leave schedule upload
│   ├── configure_rules.html  # Rules configuration
│   └── roster.html    # Display generated roster
├── uploads/           # Temporary file storage (gitignored)
├── static/            # CSS/JS files (to be created)
├── requirements.txt   # Python dependencies
├── CLAUDE.md         # This file
└── README.md         # User documentation

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



