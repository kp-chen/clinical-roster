# Clinical Roster Builder

A Flask web application for generating medical staff rosters based on leave schedules and specialty requirements. Features advanced PDF parsing with OCR support and Anthropic-inspired design.

## Features
- **Multi-format file support**: Excel, CSV, PDF, and image files
- **Advanced PDF parsing**: Intelligent extraction from tabular roster layouts
- **OCR capabilities**: Automatic text extraction from scanned documents
- **Manual review interface**: Edit and correct extracted data before processing
- **Smart roster generation**: Fair distribution with specialty coverage
- **Export functionality**: Professional Excel output with statistics
- **Real-time validation**: Data cleaning and error detection

## Supported File Formats
- **Excel/CSV**: Direct structured data import
- **PDF**: Tabular roster layouts with "Date Day Staff(ID)" format
- **Images**: PNG, JPG, JPEG with OCR text extraction
- **Multi-page documents**: Up to 5 pages with 200+ staff records

## Usage

1. **Upload**: Drag and drop your roster file (Excel/CSV/PDF/Image)
2. **Review**: For PDFs/images, review and correct extracted data
3. **Configure**: Map columns and set roster rules (dates, minimum staff)
4. **Generate**: Create optimized roster with fair distribution
5. **Export**: Download professional Excel format with statistics

## System Requirements
- Python 3.10+
- Tesseract OCR engine
- Poppler utilities (for PDF processing)

## Installation
```bash
# Install system dependencies (Ubuntu/Debian)
sudo apt-get install tesseract-ocr poppler-utils

# Install Python dependencies
pip install -r requirements.txt

# Run application
python app.py
```

## Development
See CLAUDE.md for development context and conventions.
