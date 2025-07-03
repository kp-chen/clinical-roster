#!/usr/bin/env python3
"""
Test script for roster generation algorithm
"""
import os
import sys
import pandas as pd
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import generate_roster_logic

def test_roster_generation():
    """Test the roster generation with sample data"""
    print("Testing roster generation algorithm...")
    
    # Test data file
    test_file = 'test_leave_data.csv'
    
    # Test rules
    rules = {
        'staff_column': 'Staff_Name',
        'specialty_column': 'Specialty',
        'date_column': 'Leave_Start',
        'end_date_column': 'Leave_End',
        'min_staff_per_day': 2,
        'roster_start': '2025-07-01',
        'roster_end': '2025-07-31'
    }
    
    try:
        # Generate roster
        result = generate_roster_logic(test_file, rules)
        
        print(f"✅ Roster generated successfully!")
        print(f"📊 Statistics:")
        print(f"   - Total days: {result['stats']['total_days']}")
        print(f"   - Coverage rate: {result['stats']['coverage_percentage']:.1f}%")
        print(f"   - Days understaffed: {result['stats']['days_understaffed']}")
        print(f"   - Total staff: {len(result['staff_list'])}")
        print(f"   - Total specialties: {len(result['specialties'])}")
        
        print(f"\n👥 Staff work distribution:")
        for staff, days in result['stats']['staff_work_distribution'].items():
            print(f"   - {staff}: {days} days")
        
        print(f"\n🏥 Available specialties: {', '.join(result['specialties'])}")
        
        # Show a few sample days
        print(f"\n📅 Sample roster days:")
        sample_dates = list(result['roster'].keys())[:5]
        for date in sample_dates:
            day_data = result['roster'][date]
            staff_names = ', '.join(day_data['staff'])
            specialties = ', '.join(day_data['specialties'])
            weekend = "🌅" if day_data['is_weekend'] else ""
            print(f"   {date} {weekend}: {staff_names} ({specialties})")
        
        return True
        
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_roster_generation()
    sys.exit(0 if success else 1)