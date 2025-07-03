from flask import Flask, render_template, request, redirect, url_for, flash, send_file
import pandas as pd
import os
from datetime import datetime, timedelta
from werkzeug.utils import secure_filename
import json

# Initialize Flask app
app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'  # Needed for flash messages

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'xlsx', 'xls', 'csv'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Create uploads directory if it doesn't exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    """Check if uploaded file has allowed extension"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/')
def index():
    """Home page showing upload form and existing rosters"""
    return render_template('index.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload_leave():
    """Handle leave roster upload"""
    if request.method == 'POST':
        # Check if file was uploaded
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
        
        if file and allowed_file(file.filename):
            # Save file securely
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            # Process the file
            try:
                if filename.endswith('.csv'):
                    df = pd.read_csv(filepath)
                else:
                    df = pd.read_excel(filepath)
                
                # Store basic info about the upload
                flash(f'Successfully uploaded {filename} with {len(df)} records', 'success')
                return redirect(url_for('configure_rules', filename=filename))
                
            except Exception as e:
                flash(f'Error processing file: {str(e)}', 'error')
                return redirect(request.url)
    
    return render_template('upload.html')

@app.route('/configure-rules/<filename>')
def configure_rules(filename):
    """Configure rostering rules"""
    # Load the uploaded file to show preview
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(filepath)
        else:
            df = pd.read_excel(filepath)
        
        # Get column names and preview data
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
    # Get form data
    filename = request.form.get('filename')
    rules = {
        'min_staff_per_day': int(request.form.get('min_staff', 2)),
        'specialty_column': request.form.get('specialty_column'),
        'date_column': request.form.get('date_column'),
        'staff_column': request.form.get('staff_column')
    }
    
    # This is where you'll implement the roster logic
    # For now, we'll create a simple example
    flash('Roster generation in progress...', 'info')
    return redirect(url_for('view_roster'))

@app.route('/roster')
def view_roster():
    """View generated roster"""
    return render_template('roster.html')

if __name__ == '__main__':
    app.run(debug=True, port=5000)