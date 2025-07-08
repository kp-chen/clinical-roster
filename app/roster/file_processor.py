"""Enhanced file processing with progress tracking and better error handling"""
import os
import re
import logging
import hashlib
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Callable
import pandas as pd
from PIL import Image
import pytesseract
import PyPDF2
from pdf2image import convert_from_path
import tempfile

logger = logging.getLogger(__name__)

# Try importing camelot
try:
    import camelot
    CAMELOT_AVAILABLE = True
    logger.info("Camelot-py is available for enhanced PDF table extraction")
except ImportError:
    CAMELOT_AVAILABLE = False
    logger.warning("Camelot-py not available. Install with: pip install camelot-py[cv]")


class FileProcessor:
    """Enhanced file processor with progress callbacks"""
    
    def __init__(self, progress_callback: Optional[Callable] = None):
        self.progress_callback = progress_callback
        self.extraction_stats = {
            'total_records': 0,
            'successful_extractions': 0,
            'failed_extractions': 0,
            'confidence_scores': []
        }
    
    def _update_progress(self, message: str, percentage: int):
        """Update progress if callback provided"""
        if self.progress_callback:
            self.progress_callback(message, percentage)
        logger.info(f"Progress: {percentage}% - {message}")
    
    def process_file(self, filepath: str, file_type: str) -> Dict:
        """Process file based on type"""
        self._update_progress("Starting file processing", 0)
        
        # Calculate file hash for deduplication
        file_hash = self._calculate_file_hash(filepath)
        
        try:
            if file_type in ['xlsx', 'xls']:
                result = self._process_excel(filepath)
            elif file_type == 'csv':
                result = self._process_csv(filepath)
            elif file_type == 'pdf':
                result = self._process_pdf(filepath)
            elif file_type in ['png', 'jpg', 'jpeg']:
                result = self._process_image(filepath)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
            
            result['file_hash'] = file_hash
            result['extraction_stats'] = self.extraction_stats
            
            self._update_progress("Processing complete", 100)
            return result
            
        except Exception as e:
            logger.error(f"File processing error: {str(e)}")
            raise
    
    def _calculate_file_hash(self, filepath: str) -> str:
        """Calculate SHA-256 hash of file"""
        sha256_hash = hashlib.sha256()
        with open(filepath, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def _process_excel(self, filepath: str) -> Dict:
        """Process Excel file"""
        self._update_progress("Reading Excel file", 10)
        
        df = pd.read_excel(filepath)
        self._update_progress("Excel file loaded", 50)
        
        # Detect columns automatically
        columns_detected = self._detect_columns(df)
        
        self._update_progress("Processing data", 80)
        
        return {
            'type': 'structured',
            'data': df.to_dict('records'),
            'columns': df.columns.tolist(),
            'columns_detected': columns_detected,
            'row_count': len(df)
        }
    
    def _process_csv(self, filepath: str) -> Dict:
        """Process CSV file"""
        self._update_progress("Reading CSV file", 10)
        
        # Try different encodings
        encodings = ['utf-8', 'latin-1', 'cp1252']
        df = None
        
        for encoding in encodings:
            try:
                df = pd.read_csv(filepath, encoding=encoding)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            raise ValueError("Unable to read CSV file with any encoding")
        
        self._update_progress("CSV file loaded", 50)
        
        columns_detected = self._detect_columns(df)
        
        self._update_progress("Processing data", 80)
        
        return {
            'type': 'structured',
            'data': df.to_dict('records'),
            'columns': df.columns.tolist(),
            'columns_detected': columns_detected,
            'row_count': len(df)
        }
    
    def _process_pdf(self, filepath: str) -> Dict:
        """Process PDF with enhanced extraction"""
        self._update_progress("Starting PDF processing", 5)
        
        if CAMELOT_AVAILABLE:
            try:
                # Try Camelot first for better table extraction
                result = self._extract_tables_camelot(filepath)
                if result['data']:
                    return result
            except Exception as e:
                logger.warning(f"Camelot extraction failed: {str(e)}")
        
        # Fallback to text extraction
        self._update_progress("Extracting text from PDF", 30)
        text = self._extract_text_from_pdf(filepath)
        
        self._update_progress("Parsing extracted text", 60)
        parsed_data = self._parse_roster_text(text)
        
        return {
            'type': 'unstructured',
            'raw_text': text,
            'parsed_data': parsed_data,
            'data': parsed_data,
            'extraction_method': 'text_parsing'
        }
    
    def _process_image(self, filepath: str) -> Dict:
        """Process image with OCR"""
        self._update_progress("Preprocessing image", 10)
        
        # Preprocess image for better OCR
        image = Image.open(filepath)
        processed_image = self._preprocess_image(image)
        
        self._update_progress("Running OCR", 40)
        
        # Configure Tesseract for better results
        custom_config = r'--oem 3 --psm 6'
        text = pytesseract.image_to_string(processed_image, config=custom_config)
        
        self._update_progress("Parsing OCR results", 70)
        parsed_data = self._parse_roster_text(text)
        
        return {
            'type': 'unstructured',
            'raw_text': text,
            'parsed_data': parsed_data,
            'data': parsed_data,
            'extraction_method': 'ocr'
        }
    
    def _preprocess_image(self, image: Image) -> Image:
        """Preprocess image for better OCR"""
        # Convert to grayscale
        if image.mode != 'L':
            image = image.convert('L')
        
        # Resize if too small
        width, height = image.size
        if width < 1000:
            scale = 1000 / width
            new_size = (int(width * scale), int(height * scale))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
        
        return image
    
    def _extract_tables_camelot(self, filepath: str) -> Dict:
        """Extract tables using Camelot"""
        self._update_progress("Detecting tables in PDF", 10)
        
        roster_data = []
        
        # Try lattice method first (for bordered tables)
        tables = camelot.read_pdf(filepath, pages='all', flavor='lattice')
        
        if len(tables) == 0:
            self._update_progress("Trying stream method", 20)
            tables = camelot.read_pdf(filepath, pages='all', flavor='stream')
        
        self._update_progress(f"Found {len(tables)} tables", 30)
        
        for i, table in enumerate(tables):
            progress = 30 + (i / len(tables)) * 40
            self._update_progress(f"Processing table {i+1}/{len(tables)}", int(progress))
            
            df = table.df
            
            # Process table data
            table_data = self._process_table_data(df)
            roster_data.extend(table_data)
        
        self.extraction_stats['total_records'] = len(roster_data)
        self.extraction_stats['successful_extractions'] = len(roster_data)
        
        return {
            'type': 'structured',
            'data': roster_data,
            'extraction_method': 'camelot_tables',
            'table_count': len(tables)
        }
    
    def _process_table_data(self, df: pd.DataFrame) -> List[Dict]:
        """Process table data from DataFrame"""
        roster_data = []
        current_date = None
        current_day = None
        
        for idx, row in df.iterrows():
            # Look for date/day pattern
            first_col = str(row[0]).strip()
            date_match = re.match(r'^(\d+)\s*(Mon|Tue|Wed|Thu|Fri|Sat|Sun)', first_col, re.IGNORECASE)
            
            if date_match:
                current_date = date_match.group(1)
                current_day = date_match.group(2).title()
            
            # Extract staff information
            for col_idx, cell in enumerate(row):
                cell_text = str(cell).strip()
                
                # Skip empty cells
                if not cell_text or cell_text == 'nan':
                    continue
                
                # Look for staff pattern
                staff_match = re.search(r'([A-Za-z][A-Za-z\s/\-\.]+?)\s*\(([A-Z0-9]+)\)', cell_text)
                
                if staff_match and current_date:
                    staff_name = staff_match.group(1).strip()
                    staff_id = staff_match.group(2).strip()
                    
                    roster_data.append({
                        'Date': current_date,
                        'Day': current_day,
                        'Staff_Name': staff_name,
                        'Staff_ID': staff_id,
                        'Specialty': '',
                        'Leave_Type': '',
                        'confidence': 0.9
                    })
        
        return roster_data
    
    def _extract_text_from_pdf(self, filepath: str) -> str:
        """Extract text from PDF with fallback to OCR"""
        text = ""
        
        try:
            # Try PyPDF2 first
            with open(filepath, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                for page_num, page in enumerate(pdf_reader.pages):
                    progress = 30 + (page_num / total_pages) * 20
                    self._update_progress(f"Extracting page {page_num + 1}/{total_pages}", int(progress))
                    
                    page_text = page.extract_text()
                    if page_text.strip():
                        text += page_text + "\n"
            
            if text.strip():
                return text
                
        except Exception as e:
            logger.error(f"PyPDF2 extraction failed: {str(e)}")
        
        # Fallback to OCR
        self._update_progress("Using OCR extraction", 50)
        
        try:
            images = convert_from_path(filepath, dpi=300)
            total_images = len(images)
            
            for i, image in enumerate(images):
                progress = 50 + (i / total_images) * 30
                self._update_progress(f"OCR page {i + 1}/{total_images}", int(progress))
                
                page_text = pytesseract.image_to_string(image)
                text += page_text + "\n"
                
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            raise
        
        return text
    
    def _parse_roster_text(self, text: str) -> List[Dict]:
        """Parse roster information from text"""
        lines = [line.strip() for line in text.strip().split('\n') if line.strip()]
        roster_data = []
        
        patterns = {
            'date_day': re.compile(r'^(\d+)\s+(Mon|Tue|Wed|Thu|Fri|Sat|Sun)([A-Za-z].*)', re.IGNORECASE),
            'staff_with_id': re.compile(r'([A-Za-z][A-Za-z\s/]+?)\s*\(([A-Z0-9]+)\)', re.IGNORECASE),
            'date_range': re.compile(r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\s*[-–to]\s*(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', re.IGNORECASE),
        }
        
        current_date = None
        current_day = None
        
        for line_num, line in enumerate(lines):
            # Check for date + day pattern
            date_day_match = patterns['date_day'].match(line)
            if date_day_match:
                current_date = date_day_match.group(1)
                current_day = date_day_match.group(2)
                remainder_text = date_day_match.group(3)
                
                # Extract staff from remainder
                staff_matches = patterns['staff_with_id'].findall(remainder_text)
                
                for staff_name, staff_id in staff_matches:
                    roster_data.append({
                        'Staff_Name': staff_name.strip(),
                        'Staff_ID': staff_id,
                        'Date': current_date,
                        'Day': current_day,
                        'Specialty': '',
                        'Leave_Type': 'Work',
                        'confidence': 0.8
                    })
            
            # Check for standalone staff names
            else:
                staff_matches = patterns['staff_with_id'].findall(line)
                for staff_name, staff_id in staff_matches:
                    roster_data.append({
                        'Staff_Name': staff_name.strip(),
                        'Staff_ID': staff_id,
                        'Date': current_date or '',
                        'Day': current_day or '',
                        'Specialty': '',
                        'Leave_Type': 'Work',
                        'confidence': 0.6
                    })
        
        self.extraction_stats['total_records'] = len(roster_data)
        self.extraction_stats['successful_extractions'] = len(roster_data)
        
        return roster_data
    
    def _detect_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """Auto-detect column types"""
        detected = {}
        
        for col in df.columns:
            col_lower = str(col).lower()
            
            # Staff name detection
            if any(keyword in col_lower for keyword in ['staff', 'name', 'employee', 'doctor']):
                detected['staff_column'] = col
            
            # Specialty detection
            elif any(keyword in col_lower for keyword in ['specialty', 'speciality', 'department', 'dept']):
                detected['specialty_column'] = col
            
            # Date detection
            elif any(keyword in col_lower for keyword in ['date', 'start', 'from']):
                if 'end' not in col_lower:
                    detected['date_column'] = col
            
            # End date detection
            elif any(keyword in col_lower for keyword in ['end', 'to', 'until']):
                detected['end_date_column'] = col
        
        return detected