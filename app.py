from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify, session
from flask_login import LoginManager, login_required, current_user
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect
import pandas as pd
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import json
from PIL import Image
import pytesseract
import PyPDF2
from pdf2image import convert_from_path
import io
import tempfile
import re
import logging
from typing import List, Dict
import holidays

# Import models and configuration
from config import config
from models import db, User, RosterProfile, GeneratedRoster, UploadedFile
from forms import FileUploadForm, RosterRulesForm, ProfileForm, ShareProfileForm

# Configure logging first
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Then try importing camelot
try:
    import camelot
    CAMELOT_AVAILABLE = True
    logger.info("Camelot-py is available for enhanced PDF table extraction")
except ImportError:
    CAMELOT_AVAILABLE = False
    logger.warning("Camelot-py not available. Install with: pip install camelot-py[cv]")

# Initialize Flask app with configuration
app = Flask(__name__)
config_name = os.environ.get('FLASK_ENV', 'development')
app.config.from_object(config[config_name])

# Initialize extensions
db.init_app(app)
migrate = Migrate(app, db)
csrf = CSRFProtect(app)
login_manager = LoginManager(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'

# Import and register blueprints
from auth import auth_bp
app.register_blueprint(auth_bp, url_prefix='/auth')

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# Custom Jinja2 filters
@app.template_filter('datetime')
def datetime_filter(date_string):
    """Convert date string to datetime object for formatting"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except:
        return datetime.now()

# Create necessary directories
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/css', exist_ok=True)

# Singapore holidays
sg_holidays = holidays.Singapore()

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def extract_text_from_pdf(filepath: str) -> str:
    """Extract text from PDF file using multiple methods"""
    logger.info(f"Starting PDF text extraction from: {filepath}")
    
    # Method 1: PyPDF2 text extraction
    try:
        text = ""
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            logger.info(f"PDF has {len(pdf_reader.pages)} pages")
            
            for page_num, page in enumerate(pdf_reader.pages):
                page_text = page.extract_text()
                if page_text.strip():
                    text += page_text + "\n"
                    logger.info(f"Page {page_num + 1}: Extracted {len(page_text)} characters")
                else:
                    logger.warning(f"Page {page_num + 1}: No text found")
        
        if text.strip():
            logger.info(f"PyPDF2 extracted {len(text)} characters total")
            return text
        else:
            logger.warning("PyPDF2 extraction returned empty text")
            
    except Exception as e:
        logger.error(f"PyPDF2 extraction failed: {str(e)}")
    
    # Method 2: OCR fallback
    try:
        logger.info("Attempting OCR extraction...")
        images = convert_from_path(filepath, dpi=300)  # Higher DPI for better OCR
        text = ""
        
        for i, image in enumerate(images):
            # Configure Tesseract for better table recognition
            custom_config = r'--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz()\- '
            page_text = pytesseract.image_to_string(image, config=custom_config)
            
            if page_text.strip():
                text += page_text + "\n"
                logger.info(f"OCR Page {i + 1}: Extracted {len(page_text)} characters")
            else:
                logger.warning(f"OCR Page {i + 1}: No text found")
        
        if text.strip():
            logger.info(f"OCR extracted {len(text)} characters total")
            return text
        else:
            logger.error("OCR extraction returned empty text")
            
    except Exception as e:
        logger.error(f"OCR extraction failed: {str(e)}")
    
    raise Exception("All PDF text extraction methods failed")

def extract_text_from_image(filepath):
    """Extract text from image using OCR"""
    try:
        image = Image.open(filepath)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")

def extract_tables_from_pdf_camelot(filepath: str) -> List[Dict]:
    """Extract tables from PDF using Camelot for better handling of merged cells"""
    logger.info(f"Starting Camelot table extraction from: {filepath}")
    
    if not CAMELOT_AVAILABLE:
        logger.error("Camelot-py is not installed")
        raise Exception("Camelot-py is required for table extraction. Install with: pip install camelot-py[cv]")
    
    roster_data = []
    
    try:
        # Read PDF tables using Camelot
        # Use 'lattice' method for tables with lines/borders
        # Use 'stream' method for tables without borders
        tables = camelot.read_pdf(filepath, pages='all', flavor='lattice')
        
        if len(tables) == 0:
            # Try stream method if lattice didn't find tables
            logger.info("No tables found with lattice method, trying stream method")
            tables = camelot.read_pdf(filepath, pages='all', flavor='stream')
        
        logger.info(f"Found {len(tables)} tables in PDF")
        
        current_date = None
        current_day = None
        
        for table_num, table in enumerate(tables):
            df = table.df
            logger.info(f"Processing table {table_num + 1} with shape {df.shape}")
            
            # Process each row
            for idx, row in df.iterrows():
                # Look for date/day pattern in first column
                first_col = str(row[0]).strip()
                
                # Check if this row contains a date/day header
                date_match = re.match(r'^(\d+)\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)', first_col, re.IGNORECASE)
                if date_match:
                    current_date = date_match.group(1)
                    current_day = date_match.group(2).title()
                    logger.info(f"Found date header: {current_date} {current_day}")
                
                # Process all columns for staff names
                for col_idx, cell in enumerate(row):
                    cell_text = str(cell).strip()
                    
                    # Skip empty cells or cells that are just dates
                    if not cell_text or re.match(r'^\d+\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)?$', cell_text, re.IGNORECASE):
                        continue
                    
                    # Look for staff name pattern with ID
                    staff_match = re.search(r'([A-Za-z][A-Za-z\s/\-\.]+?)\s*\(([A-Z0-9]+)\)', cell_text)
                    
                    if staff_match and current_date and current_day:
                        staff_name = staff_match.group(1).strip()
                        staff_id = staff_match.group(2).strip()
                        
                        roster_data.append({
                            'Date': current_date,
                            'Day': current_day,
                            'Staff_Name': staff_name,
                            'Staff_ID': staff_id,
                            'Specialty': '',
                            'Leave_Type': '',
                            'extracted': True,
                            'source': f'Table {table_num + 1}, Row {idx + 1}, Col {col_idx + 1}'
                        })
                        logger.info(f"Extracted: {staff_name} ({staff_id}) on {current_date} {current_day}")
                    
                    elif current_date and current_day and re.search(r'[A-Za-z]{2,}', cell_text):
                        # Try to extract just names without IDs
                        # Clean up the text
                        clean_text = re.sub(r'[^\w\s/\-\.]', ' ', cell_text)
                        clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                        
                        if len(clean_text) > 2 and not clean_text.isdigit():
                            roster_data.append({
                                'Date': current_date,
                                'Day': current_day,
                                'Staff_Name': clean_text,
                                'Staff_ID': '',
                                'Specialty': '',
                                'Leave_Type': '',
                                'extracted': True,
                                'source': f'Table {table_num + 1}, Row {idx + 1}, Col {col_idx + 1}'
                            })
                            logger.info(f"Extracted name without ID: {clean_text} on {current_date} {current_day}")
        
        # If no roster data found, try to extract leave schedule format
        if not roster_data:
            logger.info("No roster format found, trying leave schedule format")
            roster_data = _extract_leave_schedule_from_tables(tables)
        
        logger.info(f"Camelot extraction complete. Found {len(roster_data)} records")
        return roster_data
        
    except Exception as e:
        logger.error(f"Camelot extraction failed: {str(e)}")
        raise

def _extract_leave_schedule_from_tables(tables) -> List[Dict]:
    """Extract leave schedule format from Camelot tables"""
    roster_data = []
    
    for table_num, table in enumerate(tables):
        df = table.df
        
        # Try to identify header row
        header_row = None
        for idx in range(min(3, len(df))):  # Check first 3 rows
            row = df.iloc[idx]
            row_text = ' '.join(str(cell).lower() for cell in row)
            if any(keyword in row_text for keyword in ['name', 'staff', 'leave', 'start', 'end', 'from', 'to']):
                header_row = idx
                break
        
        if header_row is not None:
            # Use identified row as headers
            df.columns = df.iloc[header_row]
            df = df[header_row + 1:].reset_index(drop=True)
        
        # Try to map columns
        name_col = None
        start_col = None
        end_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if 'name' in col_lower or 'staff' in col_lower:
                name_col = col
            elif 'start' in col_lower or 'from' in col_lower:
                start_col = col
            elif 'end' in col_lower or 'to' in col_lower:
                end_col = col
        
        if name_col:
            for idx, row in df.iterrows():
                staff_name = str(row[name_col]).strip() if name_col else ''
                leave_start = str(row[start_col]).strip() if start_col else ''
                leave_end = str(row[end_col]).strip() if end_col else ''
                
                if staff_name and len(staff_name) > 2:
                    roster_data.append({
                        'Staff_Name': staff_name,
                        'Staff_ID': '',
                        'Leave_Start': leave_start,
                        'Leave_End': leave_end,
                        'Specialty': '',
                        'Leave_Type': 'Leave',
                        'extracted': True,
                        'source': f'Table {table_num + 1}, Row {idx + 1}'
                    })
    
    return roster_data

def _parse_extracted_text(text: str) -> List[Dict]:
    """Parse roster information from extracted text using intelligent pattern matching"""
    logger.info("Starting intelligent roster text parsing")
    
    lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
    roster_data = []
    
    # Enhanced regex patterns for different roster formats
    patterns = {
        # Pattern 1: "1 Thu" or "1Thu" at start of line, followed by staff name
        'date_day': re.compile(r'^(\d+)\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun)([A-Za-z].*)', re.IGNORECASE),
        
        # Pattern 2: "Name (ID)" format - more precise
        'staff_with_id': re.compile(r'([A-Za-z][A-Za-z\s/]+?)\s*\(([A-Z0-9]+)\)', re.IGNORECASE),
        
        # Pattern 3: Date range patterns
        'date_range': re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*[-–to]\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.IGNORECASE),
        
        # Pattern 4: Single date patterns
        'single_date': re.compile(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b'),
        
        # Pattern 5: Leave/Holiday keywords
        'leave_keywords': re.compile(r'\b(leave|holiday|vacation|absent|off|sick)\b', re.IGNORECASE)
    }
    
    current_date = None
    current_day = None
    
    for line_num, line in enumerate(lines):
        logger.debug(f"Processing line {line_num + 1}: {line}")
        
        # Skip lines that are just headers
        if line.lower() in ['leave', 'roster', 'schedule']:
            continue
        
        # Check for date + day pattern at start of line
        date_day_match = patterns['date_day'].match(line)
        if date_day_match:
            current_date = date_day_match.group(1)
            current_day = date_day_match.group(2)
            remainder_text = date_day_match.group(3)  # Everything after day name
            
            logger.info(f"Found date/day pattern: Date={current_date}, Day={current_day}")
            
            # Extract staff names from the remainder text
            staff_matches = patterns['staff_with_id'].findall(remainder_text)
            
            for staff_name, staff_id in staff_matches:
                staff_name = staff_name.strip()
                # Clean up any remaining day name artifacts
                staff_name = re.sub(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*', '', staff_name, flags=re.IGNORECASE)
                
                if staff_name and len(staff_name) > 1:  # Only add if name is meaningful
                    roster_data.append({
                        'Staff_Name': staff_name,
                        'Staff_ID': staff_id,
                        'Date': current_date,
                        'Day': current_day,
                        'Specialty': '',  # To be filled by user
                        'Leave_Type': 'Work',
                        'parsed_from': f'Line {line_num + 1}',
                        'confidence': 'high'
                    })
                    logger.info(f"Extracted staff: {staff_name} ({staff_id})")
            
            continue
        
        # Check for standalone staff names (only if no date/day pattern found)
        staff_matches = patterns['staff_with_id'].findall(line)
        if staff_matches:
            for staff_name, staff_id in staff_matches:
                staff_name = staff_name.strip()
                # Clean up any day name artifacts at the beginning
                staff_name = re.sub(r'^(Mon|Tue|Wed|Thu|Fri|Sat|Sun)\s*', '', staff_name, flags=re.IGNORECASE)
                
                if staff_name and len(staff_name) > 1:  # Only add if name is meaningful
                    roster_data.append({
                        'Staff_Name': staff_name,
                        'Staff_ID': staff_id,
                        'Date': current_date or '',
                        'Day': current_day or '',
                        'Specialty': '',
                        'Leave_Type': 'Work',
                        'parsed_from': f'Line {line_num + 1}',
                        'confidence': 'medium'
                    })
                    logger.info(f"Extracted standalone staff: {staff_name} ({staff_id})")
        
        # Check for date ranges (leave schedules)
        date_range_match = patterns['date_range'].search(line)
        if date_range_match:
            start_date = date_range_match.group(1)
            end_date = date_range_match.group(2)
            
            # Look for staff names in the same line
            staff_matches = patterns['staff_with_id'].findall(line)
            for staff_name, staff_id in staff_matches:
                staff_name = staff_name.strip()
                roster_data.append({
                    'Staff_Name': staff_name,
                    'Staff_ID': staff_id,
                    'Leave_Start': start_date,
                    'Leave_End': end_date,
                    'Specialty': '',
                    'Leave_Type': 'Leave',
                    'parsed_from': f'Line {line_num + 1}',
                    'confidence': 'high'
                })
                logger.info(f"Extracted leave schedule: {staff_name} ({start_date} to {end_date})")
    
    logger.info(f"Parsing complete. Extracted {len(roster_data)} records")
    return roster_data

def parse_roster_text(text: str) -> List[Dict]:
    """Main entry point for roster text parsing with validation"""
    try:
        if not text or not text.strip():
            logger.warning("Empty text provided for parsing")
            return []
        
        # Clean up text
        text = re.sub(r'\s+', ' ', text)  # Normalize whitespace
        text = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', text)  # Remove control characters
        
        logger.info(f"Parsing text of length {len(text)}")
        
        parsed_data = _parse_extracted_text(text)
        
        # Validate parsed data
        validated_data = validate_parsed_data(parsed_data)
        
        return validated_data
        
    except Exception as e:
        logger.error(f"Error parsing roster text: {str(e)}")
        return [{
            'text_line': text[:200] + '...' if len(text) > 200 else text,
            'error': str(e),
            'extracted': False
        }]

def validate_parsed_data(data: List[Dict]) -> List[Dict]:
    """Validate and clean parsed roster data"""
    logger.info(f"Validating {len(data)} parsed records")
    
    validated = []
    seen_staff = set()
    
    for record in data:
        # Basic validation
        if not record.get('Staff_Name', '').strip():
            logger.warning(f"Skipping record with empty staff name: {record}")
            continue
        
        # Clean staff name
        staff_name = record['Staff_Name'].strip()
        staff_name = re.sub(r'\s+', ' ', staff_name)  # Normalize whitespace
        
        # Skip if name is too short or invalid
        if len(staff_name) < 2:
            logger.warning(f"Skipping invalid staff name: {staff_name}")
            continue
        
        # Validate staff name (should contain at least one letter)
        if not re.search(r'[A-Za-z]', staff_name):
            logger.warning(f"Skipping invalid staff name: {staff_name}")
            continue
        
        record['Staff_Name'] = staff_name
        
        # Create unique key for deduplication
        unique_key = f"{staff_name}_{record.get('Staff_ID', '')}_{record.get('Date', '')}_{record.get('Day', '')}"
        
        if unique_key in seen_staff:
            logger.debug(f"Skipping duplicate record: {unique_key}")
            continue
        
        seen_staff.add(unique_key)
        
        # Validate dates if present
        for date_field in ['Date', 'Leave_Start', 'Leave_End']:
            if date_field in record and record[date_field]:
                try:
                    # Try to parse and normalize date
                    date_str = record[date_field]
                    if re.match(r'^\d+$', date_str):  # Day number only
                        # Keep as-is for now
                        pass
                    elif '/' in date_str or '-' in date_str:
                        # Try to parse full date
                        parsed_date = pd.to_datetime(date_str, errors='coerce')
                        if pd.isna(parsed_date):
                            logger.warning(f"Invalid date format: {date_str}")
                            record[date_field] = ''
                        else:
                            record[date_field] = parsed_date.strftime('%Y-%m-%d')
                except Exception as e:
                    logger.warning(f"Date parsing error for {date_field}={record[date_field]}: {e}")
                    record[date_field] = ''
        
        validated.append(record)
    
    logger.info(f"Validation complete. {len(validated)} valid records")
    return validated

@app.route('/')
def index():
    """Home page with Anthropic-style design"""
    return render_template('index.html', user=current_user)

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload_leave():
    """Handle file upload with support for multiple formats"""
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            try:
                file_ext = filename.rsplit('.', 1)[1].lower()
                
                # Handle different file types
                if file_ext in ['xlsx', 'xls']:
                    df = pd.read_excel(filepath)
                    session_data = {
                        'type': 'structured',
                        'filename': filename,
                        'data': df.to_dict('records')
                    }
                    
                elif file_ext == 'csv':
                    df = pd.read_csv(filepath)
                    session_data = {
                        'type': 'structured',
                        'filename': filename,
                        'data': df.to_dict('records')
                    }
                    
                elif file_ext == 'pdf':
                    # Try Camelot table extraction first for better merged cell handling
                    if CAMELOT_AVAILABLE:
                        try:
                            roster_data = extract_tables_from_pdf_camelot(filepath)
                            if roster_data:
                                logger.info(f"Successfully extracted {len(roster_data)} records using Camelot")
                                session_data = {
                                    'type': 'unstructured',
                                    'filename': filename,
                                    'raw_text': f"Extracted {len(roster_data)} records from PDF tables",
                                    'parsed_data': roster_data
                                }
                            else:
                                raise Exception("No data extracted from tables")
                        except Exception as e:
                            logger.warning(f"Camelot extraction failed, falling back to text extraction: {str(e)}")
                            # Fall back to text extraction
                            text = extract_text_from_pdf(filepath)
                            roster_data = parse_roster_text(text)
                            session_data = {
                                'type': 'unstructured',
                                'filename': filename,
                                'raw_text': text,
                                'parsed_data': roster_data
                            }
                    else:
                        # Use existing text extraction if Camelot not available
                        text = extract_text_from_pdf(filepath)
                        roster_data = parse_roster_text(text)
                        session_data = {
                            'type': 'unstructured',
                            'filename': filename,
                            'raw_text': text,
                            'parsed_data': roster_data
                        }
                    
                elif file_ext in ['png', 'jpg', 'jpeg']:
                    text = extract_text_from_image(filepath)
                    roster_data = parse_roster_text(text)
                    session_data = {
                        'type': 'unstructured',
                        'filename': filename,
                        'raw_text': text,
                        'parsed_data': roster_data
                    }
                
                # Store in a temporary JSON file (in production, use proper session management)
                session_file = os.path.join(app.config['UPLOAD_FOLDER'], f'session_{filename}.json')
                with open(session_file, 'w') as f:
                    json.dump(session_data, f)
                
                flash(f'Successfully uploaded {filename}', 'success')
                
                if session_data['type'] == 'structured':
                    return redirect(url_for('configure_rules', filename=filename))
                else:
                    return redirect(url_for('review_extraction', filename=filename))
                    
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/review-extraction/<filename>')
@login_required
def review_extraction(filename):
    """Review and edit extracted data from PDF/images"""
    session_file = os.path.join(app.config['UPLOAD_FOLDER'], f'session_{filename}.json')
    
    try:
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        return render_template('review_extraction.html', 
                             filename=filename,
                             raw_text=session_data.get('raw_text', ''),
                             parsed_data=session_data.get('parsed_data', []))
    except Exception as e:
        flash(f'Error loading extracted data: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/process-extraction', methods=['POST'])
@login_required
def process_extraction():
    """Process manually corrected extraction data"""
    try:
        filename = request.form.get('filename')
        
        # Extract form data
        staff_names = request.form.getlist('staff_name[]')
        specialties = request.form.getlist('specialty[]')
        leave_starts = request.form.getlist('leave_start[]')
        leave_ends = request.form.getlist('leave_end[]')
        
        # Create structured data from form inputs
        structured_data = []
        for i in range(len(staff_names)):
            if staff_names[i].strip():  # Only include non-empty rows
                structured_data.append({
                    'Staff_Name': staff_names[i].strip(),
                    'Specialty': specialties[i].strip() if i < len(specialties) else '',
                    'Leave_Start': leave_starts[i] if i < len(leave_starts) else '',
                    'Leave_End': leave_ends[i] if i < len(leave_ends) else ''
                })
        
        # Convert to DataFrame and save as CSV for processing
        df = pd.DataFrame(structured_data)
        processed_file = os.path.join(app.config['UPLOAD_FOLDER'], f'processed_{filename}.csv')
        df.to_csv(processed_file, index=False)
        
        # Update session data
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f'session_{filename}.json')
        with open(session_file, 'r') as f:
            session_data = json.load(f)
        
        session_data['type'] = 'structured'
        session_data['data'] = structured_data
        
        with open(session_file, 'w') as f:
            json.dump(session_data, f)
        
        flash('Extraction data processed successfully!', 'success')
        return redirect(url_for('configure_rules', filename=f'processed_{filename}.csv'))
        
    except Exception as e:
        flash(f'Error processing extraction: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/configure-rules/<filename>')
@login_required
def configure_rules(filename):
    """Configure rostering rules with Anthropic-style UI"""
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        columns = df.columns.tolist()
        preview_data = df.head(5).to_dict('records')
        
        return render_template('configure_rules.html', 
                             filename=filename,
                             columns=columns,
                             preview_data=preview_data)
    except Exception as e:
        flash(f'Error loading file: {str(e)}', 'error')
        return redirect(url_for('index'))

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
            
            # Store roster for this date
            roster[date_str] = {
                'staff': selected_staff,
                'specialties': list(selected_specialties),
                'available_count': len(available_staff),
                'is_weekend': current_date.weekday() >= 5,
                'is_holiday': is_holiday,
                'holiday_name': holiday_name
            }
            
            current_date += timedelta(days=1)
        
        # Calculate statistics
        total_days = len(roster)
        days_understaffed = sum(1 for day in roster.values() if len(day['staff']) < min_staff)
        coverage_stats = {
            'total_days': total_days,
            'days_understaffed': days_understaffed,
            'coverage_percentage': ((total_days - days_understaffed) / total_days) * 100,
            'staff_work_distribution': staff_work_count
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

@app.route('/generate-roster', methods=['POST'])
@login_required
def generate_roster():
    """Generate roster based on rules"""
    filename = request.form.get('filename')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    rules = {
        'min_staff_per_day': int(request.form.get('min_staff', 2)),
        'specialty_column': request.form.get('specialty_column'),
        'date_column': request.form.get('date_column'),
        'staff_column': request.form.get('staff_column'),
        'end_date_column': request.form.get('end_date_column'),
        'roster_start': request.form.get('roster_start'),
        'roster_end': request.form.get('roster_end')
    }
    
    try:
        # Generate roster
        roster_result = generate_roster_logic(filepath, rules)
        
        # Store results in session file
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f'roster_{filename}.json')
        with open(session_file, 'w') as f:
            # Convert datetime objects to strings for JSON serialization
            roster_json = {}
            for date, data in roster_result['roster'].items():
                roster_json[date] = {
                    'staff': data['staff'],
                    'specialties': data['specialties'],
                    'available_count': data['available_count'],
                    'is_weekend': data['is_weekend']
                }
            
            json.dump({
                'roster': roster_json,
                'stats': roster_result['stats'],
                'staff_list': roster_result['staff_list'],
                'specialties': roster_result['specialties'],
                'rules': rules
            }, f, indent=2)
        
        flash('Roster generated successfully!', 'success')
        return redirect(url_for('view_roster', filename=filename))
        
    except Exception as e:
        flash(f'Error generating roster: {str(e)}', 'error')
        return redirect(url_for('configure_rules', filename=filename))

@app.route('/roster')
@login_required
def view_roster():
    """View generated roster"""
    filename = request.args.get('filename')
    
    if not filename:
        flash('No roster data found', 'error')
        return redirect(url_for('index'))
    
    try:
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f'roster_{filename}.json')
        with open(session_file, 'r') as f:
            roster_data = json.load(f)
        
        # Sort dates for display
        sorted_dates = sorted(roster_data['roster'].keys())
        
        return render_template('roster.html', 
                             roster=roster_data['roster'],
                             stats=roster_data['stats'],
                             staff_list=roster_data['staff_list'],
                             specialties=roster_data['specialties'],
                             rules=roster_data['rules'],
                             sorted_dates=sorted_dates,
                             filename=filename)
    except Exception as e:
        flash(f'Error loading roster: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/export-roster')
@login_required
def export_roster():
    """Export roster to Excel format"""
    filename = request.args.get('filename')
    
    if not filename:
        flash('No roster data found', 'error')
        return redirect(url_for('index'))
    
    try:
        session_file = os.path.join(app.config['UPLOAD_FOLDER'], f'roster_{filename}.json')
        with open(session_file, 'r') as f:
            roster_data = json.load(f)
        
        # Create DataFrame for export
        export_data = []
        for date, day_data in roster_data['roster'].items():
            date_obj = datetime.strptime(date, '%Y-%m-%d')
            day_name = date_obj.strftime('%A')
            
            if day_data['staff']:
                for staff in day_data['staff']:
                    export_data.append({
                        'Date': date,
                        'Day': day_name,
                        'Staff': staff,
                        'Specialties_Covered': ', '.join(day_data['specialties']),
                        'Available_Staff_Count': day_data['available_count'],
                        'Is_Weekend': 'Yes' if day_data['is_weekend'] else 'No'
                    })
            else:
                export_data.append({
                    'Date': date,
                    'Day': day_name,
                    'Staff': 'NO STAFF ASSIGNED',
                    'Specialties_Covered': '',
                    'Available_Staff_Count': day_data['available_count'],
                    'Is_Weekend': 'Yes' if day_data['is_weekend'] else 'No'
                })
        
        # Create Excel file
        df = pd.DataFrame(export_data)
        
        # Create a temporary file for download
        temp_file = os.path.join(app.config['UPLOAD_FOLDER'], f'roster_export_{filename}.xlsx')
        
        # Write to Excel with formatting
        with pd.ExcelWriter(temp_file, engine='openpyxl') as writer:
            df.to_excel(writer, sheet_name='Roster', index=False)
            
            # Add statistics sheet
            stats_data = [
                ['Total Days', roster_data['stats']['total_days']],
                ['Coverage Percentage', f"{roster_data['stats']['coverage_percentage']:.1f}%"],
                ['Days Understaffed', roster_data['stats']['days_understaffed']],
                ['Total Staff', len(roster_data['staff_list'])],
                ['Total Specialties', len(roster_data['specialties'])],
                ['', ''],
                ['Staff Work Distribution', '']
            ]
            
            for staff, days in roster_data['stats']['staff_work_distribution'].items():
                stats_data.append([staff, f"{days} days"])
            
            stats_df = pd.DataFrame(stats_data, columns=['Metric', 'Value'])
            stats_df.to_excel(writer, sheet_name='Statistics', index=False)
        
        return send_file(temp_file, as_attachment=True, 
                        download_name=f'clinical_roster_{filename}.xlsx')
        
    except Exception as e:
        flash(f'Error exporting roster: {str(e)}', 'error')
        return redirect(url_for('view_roster', filename=filename))

# Create tables will be handled in run.py or during app initialization

@app.context_processor
def inject_user():
    """Make current_user available in all templates"""
    return dict(current_user=current_user)

@app.route('/profiles')
@login_required
def list_profiles():
    """List user's saved roster profiles"""
    profiles = current_user.roster_profiles.filter_by(is_active=True).order_by(
        RosterProfile.updated_at.desc()
    ).all()
    return render_template('profiles/list.html', profiles=profiles)

@app.route('/profiles/save', methods=['POST'])
@login_required
def save_profile():
    """Save current roster configuration as a profile"""
    form = ProfileForm()
    if form.validate_on_submit():
        try:
            # Get rules from form or session
            rules = request.get_json() or session.get('current_rules', {})
            
            profile = RosterProfile(
                user_id=current_user.id,
                name=form.name.data,
                description=form.description.data,
                rules=rules
            )
            
            db.session.add(profile)
            db.session.commit()
            
            flash('Profile saved successfully!', 'success')
            return jsonify({'success': True, 'profile_id': profile.id})
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error saving profile: {str(e)}')
            return jsonify({'success': False, 'error': str(e)}), 500
    
    return jsonify({'success': False, 'errors': form.errors}), 400

@app.route('/profiles/<int:profile_id>/share', methods=['POST'])
@login_required
def share_profile(profile_id):
    """Share a roster profile via email"""
    profile = RosterProfile.query.filter_by(
        id=profile_id, 
        user_id=current_user.id,
        is_active=True
    ).first_or_404()
    
    form = ShareProfileForm()
    if form.validate_on_submit():
        try:
            # Create share record
            from models import SharedProfile
            share = SharedProfile(
                profile_id=profile.id,
                shared_with_email=form.email.data.lower()
            )
            db.session.add(share)
            db.session.commit()
            
            # TODO: Send email with share link
            share_url = url_for('view_shared_profile', token=share.token, _external=True)
            
            flash(f'Profile shared with {form.email.data}', 'success')
            return redirect(url_for('list_profiles'))
            
        except Exception as e:
            db.session.rollback()
            logger.error(f'Error sharing profile: {str(e)}')
            flash('Error sharing profile. Please try again.', 'error')
    
    return render_template('profiles/share.html', profile=profile, form=form)

@app.route('/shared/<token>')
def view_shared_profile(token):
    """View a shared profile"""
    from models import SharedProfile
    
    share = SharedProfile.query.filter_by(token=token, is_active=True).first_or_404()
    
    if share.is_expired:
        flash('This share link has expired.', 'error')
        return redirect(url_for('index'))
    
    # Update access time
    share.accessed_at = datetime.utcnow()
    db.session.commit()
    
    return render_template('profiles/shared_view.html', 
                         profile=share.profile,
                         share=share)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()  # Create tables if they don't exist
    app.run(debug=True, port=5000)