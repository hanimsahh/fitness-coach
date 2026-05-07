import gspread
import os
from google.oauth2.service_account import Credentials
from datetime import datetime

SHEET_ID = "1mQpV4YqGBV4GXxp-W6FMNPl2_p9qzTEX9NLdo0xgZG0"
CREDS_PATH = os.path.join(os.path.dirname(__file__), 'service_account.json')

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive'
]

def get_sheet():
    creds = Credentials.from_service_account_file(CREDS_PATH, scopes=SCOPES)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)

def init_sheets():
    """Create required sheets if they don't exist."""
    spreadsheet = get_sheet()
    existing = [ws.title for ws in spreadsheet.worksheets()]
    
    if 'Workouts' not in existing:
        ws = spreadsheet.add_worksheet(title='Workouts', rows=1000, cols=10)
        ws.append_row(['Date', 'Completed', 'Notes'])
    
    if 'Meals' not in existing:
        ws = spreadsheet.add_worksheet(title='Meals', rows=1000, cols=10)
        ws.append_row(['Date', 'Food', 'Calories Min', 'Calories Max', 'Protein', 'Carbs', 'Fat'])
    
    if 'Profile' not in existing:
        ws = spreadsheet.add_worksheet(title='Profile', rows=10, cols=5)
        ws.append_row(['Key', 'Value'])
    
    print('Sheets initialized!')

def log_workout_to_sheets(completed: bool, notes: str = ""):
    """Log workout to Google Sheets."""
    try:
        ws = get_sheet().worksheet('Workouts')
        ws.append_row([
            datetime.now().strftime('%Y-%m-%d'),
            'Yes' if completed else 'No',
            notes
        ])
        return True
    except Exception as e:
        print(f"Sheets error: {e}")
        return False

def log_meal_to_sheets(food: str, calories_min: int, calories_max: int, protein: str, carbs: str, fat: str):
    """Log meal to Google Sheets."""
    try:
        ws = get_sheet().worksheet('Meals')
        ws.append_row([
            datetime.now().strftime('%Y-%m-%d'),
            food,
            calories_min,
            calories_max,
            protein,
            carbs,
            fat
        ])
        return True
    except Exception as e:
        print(f"Sheets error: {e}")
        return False

def save_profile_to_sheets(goal: str, equipment: str, dietary: str):
    """Save user profile to Google Sheets."""
    try:
        ws = get_sheet().worksheet('Profile')
        ws.clear()
        ws.append_row(['Key', 'Value'])
        ws.append_row(['Goal', goal])
        ws.append_row(['Equipment', equipment])
        ws.append_row(['Dietary', dietary])
        ws.append_row(['Updated', datetime.now().strftime('%Y-%m-%d %H:%M')])
        return True
    except Exception as e:
        print(f"Sheets error: {e}")
        return False
