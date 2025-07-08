# Clinical Roster Builder - Setup Guide

## Quick Start

1. **Install System Dependencies**
   ```bash
   # Ubuntu/Debian
   sudo apt-get update
   sudo apt-get install -y python3-pip tesseract-ocr poppler-utils ghostscript
   
   # macOS
   brew install tesseract poppler ghostscript
   ```

2. **Create Virtual Environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install Python Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your settings (especially SECRET_KEY)
   ```

5. **Run the Application**
   ```bash
   python run.py
   ```

6. **Access the Application**
   - Open http://localhost:5000 in your browser
   - Create an account to get started

## Features Implemented

### ✅ User Authentication
- Email/password registration and login
- Session management with Flask-Login
- Password hashing with bcrypt

### ✅ File Upload & Processing
- Support for Excel, CSV, PDF, and image files
- OCR extraction from PDFs and images using Tesseract
- Advanced PDF table extraction with Camelot-py
- Manual review interface for extracted data

### ✅ Roster Generation
- Intelligent algorithm with fair workload distribution
- Specialty coverage optimization
- Singapore public holidays integration
- Weekend detection

### ✅ Profile Management
- Save roster configurations as reusable profiles
- Share profiles via email with secure tokens
- Profile listing and management

### ✅ Security Features
- CSRF protection on all forms
- Input validation with Flask-WTF
- Secure file upload handling
- Environment-based configuration

### ✅ Export Functionality
- Export rosters to Excel format
- Include statistics and work distribution
- Professional formatting

## Database Schema

The application uses SQLite by default with the following models:
- **User**: Authentication and user management
- **RosterProfile**: Saved roster configurations
- **SharedProfile**: Profile sharing with tokens
- **GeneratedRoster**: Generated roster instances
- **EmergencyUpdate**: Emergency leave tracking
- **UploadedFile**: File upload audit trail

## Configuration Options

Edit `.env` file to customize:
- `SECRET_KEY`: Application secret (change in production!)
- `DATABASE_URL`: Database connection string
- `MAIL_*`: Email configuration for sharing features
- `SESSION_COOKIE_SECURE`: Set to True for HTTPS

## Troubleshooting

### OCR Not Working
- Ensure Tesseract is installed: `tesseract --version`
- Check Poppler installation: `pdfinfo --version`

### Database Errors
- Delete `clinical_roster.db` and restart to recreate tables
- Check file permissions in the application directory

### Import Errors
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt --force-reinstall`

## Next Steps

### Pending Features
1. **Emergency Leave Handling**: UI for last-minute roster adjustments
2. **Testing Suite**: Comprehensive unit and integration tests
3. **Email Notifications**: Send roster updates to staff
4. **API Documentation**: RESTful API for integrations

### Production Deployment
1. Use PostgreSQL instead of SQLite
2. Set up proper email service (SendGrid, AWS SES)
3. Enable HTTPS and set `SESSION_COOKIE_SECURE=True`
4. Use gunicorn or uwsgi as WSGI server
5. Set up nginx as reverse proxy
6. Implement proper logging and monitoring

## Support

For issues or questions:
- Check CLAUDE.md for development context
- Review error logs in the console
- Ensure all system dependencies are installed