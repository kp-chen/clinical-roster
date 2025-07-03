# Clinical Roster Builder - Project Context

## Overview
Flask web app for creating medical staff rosters based on leave schedules and clinical specialties. Features Anthropic-inspired design and supports multiple file formats including PDF/image OCR.

## Tech Stack
- Backend: Flask 3.0.0
- Data Processing: pandas, PyPDF2, pytesseract (OCR)
- File Handling: openpyxl (Excel), pdf2image, Pillow (images)
- Frontend: Jinja2 templates, custom CSS (Anthropic design system)
- Python: 3.10+
- Development: Ubuntu WSL, VS Code
- System Dependencies: poppler-utils, tesseract-ocr

## Project Structure
- app.py: Main Flask application with multi-format file processing
- templates/: Jinja2 HTML templates
  - base.html: Base template with Anthropic-inspired header
  - index.html: Home page with clean card design
  - upload.html: Drag-and-drop file upload with format support
  - configure_rules.html: Rules configuration
  - review_extraction.html: OCR data review and editing
  - roster.html: Display generated roster
- static/css/style.css: Anthropic-inspired design system
- uploads/: Temporary file storage (gitignored)
- requirements.txt: Python dependencies
- CLAUDE.md: This file
- README.md: User documentation

## Current Features
1. Multi-format file upload (Excel/CSV/PDF/Images) with drag-and-drop
2. OCR extraction from PDF and image files
3. Manual review and correction of extracted data
4. Basic rule configuration interface
5. Column mapping for flexible file formats
6. Anthropic-inspired UI with orange accent (#D97757)
7. Progress step indicators
8. Responsive design with loading states

## Design System
- Primary Color: #D97757 (Anthropic orange)
- Font: System font stack (-apple-system, BlinkMacSystemFont, etc.)
- Card-based layout with consistent spacing
- Clean typography with proper hierarchy
- Smooth transitions and hover states
- Accessibility-friendly color contrast

## TODO Priority List
1. Improve OCR parsing accuracy for roster formats
2. Implement roster generation algorithm
3. Add database (SQLite) for storing rosters and templates
4. Specialty-based minimum coverage rules
5. Export roster as Excel/PDF with formatting
6. Advanced constraints (max consecutive days, fair distribution)
7. Save and reuse extraction templates for PDFs
8. Batch processing for multiple files
9. User authentication and multi-tenant support
10. Real-time roster conflict detection

## Key Business Rules
- Each day must have minimum staff coverage
- Respect all leave requests (non-negotiable)
- Ensure specialty coverage when possible
- Distribute weekend/holiday shifts fairly
- Account for part-time staff availability
- Support various input formats (structured and unstructured)

## Code Conventions
- Type hints for function parameters
- Docstrings for all functions
- Handle errors gracefully with user-friendly messages
- Validate all user inputs
- Use datetime for all date operations
- Comment complex logic, especially OCR parsing
- Follow Anthropic's clean design principles

## File Processing Flow
1. User uploads file (Excel/CSV/PDF/Image)
2. System detects file type:
   - Structured (Excel/CSV): Direct to column mapping
   - Unstructured (PDF/Image): OCR extraction → Manual review → Column mapping
3. Configure roster rules
4. Generate roster based on availability
5. Export final roster

## OCR Processing Details
- PDF: Try PyPDF2 text extraction first, fall back to OCR if needed
- Images: Direct OCR using Tesseract
- Extracted text is parsed for roster patterns
- User can review and correct extraction errors
- Support for tabular and free-text roster formats

## API Endpoints
- GET /: Home page
- GET/POST /upload: File upload handler
- GET /review-extraction/<filename>: Review OCR results
- GET /configure-rules/<filename>: Set roster rules
- POST /generate-roster: Create roster from rules
- GET /roster: View generated roster

## Development Workflow
- Activate environment: source venv/bin/activate
- Run application: python app.py
- Install new packages: pip install package_name && pip freeze > requirements.txt
- Test file uploads: Use sample files in various formats
- Git workflow: Feature branches → Main

## Expected Data Format
Leave schedule should contain:
- Staff_Name: Doctor's name
- Specialty: Clinical specialty
- Leave_Start: Start date (YYYY-MM-DD)
- Leave_End: End date (YYYY-MM-DD)
- Leave_Type: Optional leave category

For PDF/Images, the system attempts to extract these fields automatically.

## Current Implementation Status
- DONE: Basic Flask setup with templates
- DONE: Multi-format file upload with drag-and-drop
- DONE: Anthropic-inspired UI design
- DONE: PDF and image OCR extraction
- DONE: Manual data correction interface
- DONE: Preview uploaded data
- DONE: Column mapping interface
- IN PROGRESS: Roster generation logic
- IN PROGRESS: OCR parsing improvements
- TODO: Database storage
- TODO: Export functionality
- TODO: Advanced rules engine
- TODO: Extraction templates

## Architecture Decisions
- Flask for simplicity and quick development
- Pandas for data manipulation (medical staff familiar with Excel)
- OCR support for legacy paper-based rosters
- SQLite for local storage (can migrate to PostgreSQL)
- Server-side rendering with Jinja2
- Custom CSS instead of framework for precise Anthropic-style design
- Modular file processing based on format detection

## Recent Changes
- Added support for PDF and image file uploads
- Implemented OCR extraction using Tesseract
- Created Anthropic-inspired design system
- Added drag-and-drop file upload interface
- Built manual review interface for extracted data
- Improved UX with progress indicators and loading states

## Performance Considerations
- Large PDF files may take time to process
- OCR accuracy depends on image/scan quality
- Consider background job queue for large files
- Cache extracted data to avoid reprocessing

## Security Notes
- File upload size limited to 16MB
- Validate file types on server side
- Sanitize OCR-extracted text
- Use secure_filename for all uploads
- Consider virus scanning for production

## Future Enhancements
- Machine learning for better roster pattern recognition
- API endpoints for integration with hospital systems
- Real-time collaboration features
- Mobile-responsive roster viewing
- Automated shift swapping suggestions
- Integration with staff preference systems