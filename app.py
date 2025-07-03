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

@app.route('/generate-roster', methods=['POST'])
def generate_roster():
    """Generate roster based on rules"""
    filename = request.form.get('filename')
    rules = {
        'min_staff_per_day': int(request.form.get('min_staff', 2)),
        'specialty_column': request.form.get('specialty_column'),
        'date_column': request.form.get('date_column'),
        'staff_column': request.form.get('staff_column')
    }
    
    flash('Roster generation in progress...', 'info')
    return redirect(url_for('view_roster'))

@app.route('/roster')
def view_roster():
    """View generated roster"""
    return render_template('roster.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)