from flask import Flask, render_template, request, redirect, url_for, flash, send_file, jsonify
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

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Custom Jinja2 filters
@app.template_filter('datetime')
def datetime_filter(date_string):
    """Convert date string to datetime object for formatting"""
    try:
        return datetime.strptime(date_string, '%Y-%m-%d')
    except:
        return datetime.now()

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv', 'pdf', 'png', 'jpg', 'jpeg'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs('static/css', exist_ok=True)

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_from_pdf(filepath):
    """Extract text from PDF file"""
    text = ""
    try:
        # Try PyPDF2 first
        with open(filepath, 'rb') as file:
            pdf_reader = PyPDF2.PdfReader(file)
            for page in pdf_reader.pages:
                text += page.extract_text()
        
        # If no text found, try OCR
        if not text.strip():
            images = convert_from_path(filepath)
            for image in images:
                text += pytesseract.image_to_string(image)
                
    except Exception as e:
        raise Exception(f"Error processing PDF: {str(e)}")
    
    return text

def extract_text_from_image(filepath):
    """Extract text from image using OCR"""
    try:
        image = Image.open(filepath)
        text = pytesseract.image_to_string(image)
        return text
    except Exception as e:
        raise Exception(f"Error processing image: {str(e)}")

def parse_roster_text(text):
    """Parse roster information from extracted text"""
    # This is a simple parser - you'll need to customize based on your roster format
    lines = text.strip().split('\n')
    roster_data = []
    
    # Simple parsing logic - customize this based on your actual roster format
    for line in lines:
        if line.strip():
            # Example: Try to extract name, date, and other info
            # This will need to be adapted to your specific format
            parts = line.split()
            if len(parts) >= 2:
                roster_data.append({
                    'text_line': line.strip(),
                    'extracted': True
                })
    
    return roster_data

@app.route('/')
def index():
    """Home page with Anthropic-style design"""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
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

@app.route('/configure-rules/<filename>')
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
    """Core roster generation algorithm"""
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
            
            # Store roster for this date
            roster[date_str] = {
                'staff': selected_staff,
                'specialties': list(selected_specialties),
                'available_count': len(available_staff),
                'is_weekend': current_date.weekday() >= 5
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

if __name__ == '__main__':
    app.run(debug=True, port=5000)