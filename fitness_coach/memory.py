import sqlite3
import os
from datetime import datetime
from fitness_coach.sheets import log_workout_to_sheets, log_meal_to_sheets, save_profile_to_sheets

DB_PATH = os.path.join(os.path.dirname(__file__), 'fitness_data.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS workouts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, date TEXT, completed BOOLEAN, notes TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS meals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id TEXT, date TEXT, food TEXT,
        calories_min INTEGER, calories_max INTEGER,
        protein TEXT, carbs TEXT, fat TEXT
    )''')
    c.execute('''CREATE TABLE IF NOT EXISTS user_profile (
        user_id TEXT PRIMARY KEY,
        goal TEXT, equipment TEXT, dietary_preference TEXT, created_at TEXT
    )''')
    conn.commit()
    conn.close()

def save_workout(user_id: str, completed: bool, notes: str = "") -> dict:
    """Log a workout session.
    
    Args:
        user_id: The user identifier
        completed: Whether the workout was completed
        notes: Any additional notes
    
    Returns:
        Confirmation message
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO workouts (user_id, date, completed, notes) VALUES (?,?,?,?)',
        (user_id, datetime.now().strftime('%Y-%m-%d'), completed, notes)
    )
    conn.commit()
    conn.close()
    
    # Also log to Google Sheets
    log_workout_to_sheets(completed, notes)
    
    return {"status": "saved", "completed": completed, "date": datetime.now().strftime('%Y-%m-%d')}

def save_meal(user_id: str, food: str, calories_min: int, calories_max: int, protein: str, carbs: str, fat: str, meal_type: str = None) -> dict:
    """Log a meal.
    
    Args:
        user_id: The user identifier
        food: Food item description
        calories_min: Minimum calorie estimate
        calories_max: Maximum calorie estimate
        protein: Protein content
        carbs: Carbohydrate content
        fat: Fat content
    
    Returns:
        Confirmation message
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT INTO meals (user_id, date, food, calories_min, calories_max, protein, carbs, fat, meal_type) VALUES (?,?,?,?,?,?,?,?,?)',
        (user_id, datetime.now().strftime('%Y-%m-%d'), food, calories_min, calories_max, protein, carbs, fat, meal_type)
    )
    conn.commit()
    conn.close()
    
    # Also log to Google Sheets
    log_meal_to_sheets(food, calories_min, calories_max, protein, carbs, fat)
    
    return {"status": "saved", "food": food, "date": datetime.now().strftime('%Y-%m-%d')}

def save_profile(user_id: str, goal: str, equipment: str, dietary: str) -> dict:
    """Save user profile.
    
    Args:
        user_id: The user identifier
        goal: Fitness goal
        equipment: Available equipment
        dietary: Dietary preferences
    
    Returns:
        Confirmation message
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        'INSERT OR REPLACE INTO user_profile (user_id, goal, equipment, dietary_preference, created_at) VALUES (?,?,?,?,?)',
        (user_id, goal, equipment, dietary, datetime.now().strftime('%Y-%m-%d %H:%M'))
    )
    conn.commit()
    conn.close()
    
    # Also save to Google Sheets
    save_profile_to_sheets(goal, equipment, dietary)
    
    return {"status": "saved", "goal": goal}

def get_weekly_summary(user_id: str) -> dict:
    """Get weekly workout and nutrition summary for analytics.
    
    Args:
        user_id: The user identifier
    
    Returns:
        Weekly summary with patterns
    """
    init_db()
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    c.execute('''SELECT date, completed, notes FROM workouts 
                 WHERE user_id=? AND date >= date('now', '-7 days')
                 ORDER BY date''', (user_id,))
    workouts = c.fetchall()
    
    c.execute('''SELECT date, food, calories_min, calories_max, protein FROM meals 
                 WHERE user_id=? AND date >= date('now', '-7 days')
                 ORDER BY date''', (user_id,))
    meals = c.fetchall()
    
    conn.close()
    
    total = len(workouts)
    completed = sum(1 for w in workouts if w[1])
    skipped = total - completed
    
    return {
        "workouts_total": total,
        "workouts_completed": completed,
        "workouts_skipped": skipped,
        "completion_rate": f"{int((completed/total)*100)}%" if total > 0 else "0%",
        "meals_logged": len(meals),
        "workout_details": [{"date": w[0], "completed": w[1], "notes": w[2]} for w in workouts],
        "meal_details": [{"date": m[0], "food": m[1]} for m in meals],
    }
