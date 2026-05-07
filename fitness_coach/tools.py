import json
import os
import requests
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '.env'))
USDA_API_KEY = os.getenv('USDA_API_KEY')

CACHE_PATH = os.path.join(os.path.dirname(__file__), 'exercise_cache.json')
with open(CACHE_PATH, 'r') as f:
    EXERCISE_CACHE = json.load(f)

def get_exercises(muscle_group: str, equipment: str = "barbell") -> dict:
    """Fetch exercises based on muscle group and equipment.

    Args:
        muscle_group: Target muscle group (e.g., 'chest', 'back', 'legs')
        equipment: Equipment available (e.g., 'barbell', 'dumbbell', 'bodyweight')

    Returns:
        A dictionary containing a list of exercises.
    """
    muscle = muscle_group.lower()
    equip_map = {
        "gym": "barbell", "home equipment": "dumbbell", "home": "dumbbell",
        "none": "bodyweight", "bodyweight": "bodyweight",
        "barbell": "barbell", "dumbbell": "dumbbell",
    }
    equip = equip_map.get(equipment.lower(), "barbell")
    exercises = EXERCISE_CACHE.get(muscle, {}).get(equip, [])
    if not exercises:
        exercises = EXERCISE_CACHE.get(muscle, {}).get("bodyweight", [])
    return {"exercises": [{"name": e} for e in exercises], "muscle_group": muscle_group}


def log_nutrition(food_item: str, portion: str = "1 serving", user_id: str = "user1") -> dict:
    """Get nutritional information for a food item using USDA FoodData Central API.

    Args:
        food_item: The food item to look up (e.g., 'chicken and rice', 'oats')
        portion: Portion size description (small / medium / large)

    Returns:
        A dictionary containing calorie range and macros.
    """
    portion_grams = {
        "small": 150, "medium": 250, "large": 350,
        "big": 350, "huge": 450, "tiny": 100,
        "1 serving": 250, "2 servings": 450,
    }
    grams = 250
    for key, val in portion_grams.items():
        if key in portion.lower():
            grams = val
            break

    # Use fallback directly for simple common foods
    _simple_foods = ['banana','apple','orange','oats','rice','chicken','egg','milk','yogurt','bread']
    if any(sf in food_item.lower() for sf in _simple_foods) and len(food_item.split()) <= 2:
        return _fallback_nutrition(food_item, grams)
    try:
        r = requests.get(
            'https://api.nal.usda.gov/fdc/v1/foods/search',
            params={'query': food_item.split()[0] if len(food_item.split()) > 0 else food_item, 'pageSize': 3, 'api_key': USDA_API_KEY},
            timeout=10
        )

        if r.status_code != 200 or not r.json().get('foods'):
            return _fallback_nutrition(food_item, grams)

        food = r.json()['foods'][0]
        nutrients = {n['nutrientName']: n['value'] for n in food.get('foodNutrients', [])}

        cal100 = nutrients.get('Energy', 150)
        pro100 = nutrients.get('Protein', 10)
        carb100 = nutrients.get('Carbohydrate, by difference', 20)
        fat100 = nutrients.get('Total lipid (fat)', 5)

        # Only apply cooked factor for dry grains/legumes, not for prepared meals
        dry_foods = ['oat', 'lentil', 'rice', 'quinoa', 'pasta', 'bean', 'chickpea', 'barley']
        food_lower = food_item.lower()
        is_dry = any(d in food_lower for d in dry_foods) and not any(x in food_lower for x in ['cooked', 'and ', 'with ', 'soup', 'salad', 'curry'])
        # Cap unrealistic calories - most whole foods are under 300 kcal/100g
        if cal100 > 400 and not any(x in food_lower for x in ['oil', 'butter', 'nut', 'cheese', 'chocolate', 'cake']):
            cal100 = min(cal100, 150)  # likely wrong USDA match
        factor = 0.35 if (cal100 > 300 and is_dry) else 1.0
        scale = grams / 100

        cal = cal100 * scale * factor
        pro = pro100 * scale * factor
        carb = carb100 * scale * factor
        fat = fat100 * scale * factor

        return {
            "food": food_item,
            "calories_range": f"{int(cal * 0.85)}-{int(cal * 1.15)} kcal",
            "protein": f"{round(pro, 1)}g",
            "carbs": f"{round(carb, 1)}g",
            "fat": f"{round(fat, 1)}g",
            "portion": f"~{grams}g",
            "source": "USDA FoodData Central",
            "note": "Estimate per typical portion. Please confirm your portion size."
        }

    except Exception as e:
        return _fallback_nutrition(food_item, grams)


def _fallback_nutrition(food_item: str, grams: int = 250) -> dict:
    # Values per 100g cooked
    foods = {
        "oats": (71, 2.5, 12, 1.4),
        "rice": (130, 2.7, 28, 0.3),
        "lentils": (116, 9, 20, 0.4),
        "chicken": (165, 31, 0, 3.6),
        "tofu": (76, 8, 2, 4.2),
        "tempeh": (195, 19, 9, 11),
        "chickpeas": (164, 8.9, 27, 2.6),
        "banana": (89, 1.1, 23, 0.3),
        "oats": (68, 2.4, 12, 1.4),
        "pasta": (158, 5.8, 31, 0.9),
        "quinoa": (120, 4.4, 21, 1.9),
        "salad": (20, 1.3, 3.6, 0.3),
        "eggs": (155, 13, 1.1, 11),
        "salmon": (208, 20, 0, 13),
        "burger": (250, 15, 20, 12),
        "pizza": (266, 11, 33, 10),
    }
    food_lower = food_item.lower()
    scale = grams / 100
    for key, (cal, p, c, f) in foods.items():
        if key in food_lower:
            cal_base = cal * scale
            return {
                "food": food_item,
                "calories_range": f"{int(cal_base * 0.85)}-{int(cal_base * 1.15)} kcal",
                "protein": f"{round(p * scale, 1)}g",
                "carbs": f"{round(c * scale, 1)}g",
                "fat": f"{round(f * scale, 1)}g",
                "portion": f"~{grams}g",
                "source": "estimate",
                "note": "Estimate based on typical portion. Please confirm your portion size."
            }
    return {
        "food": food_item,
        "calories_range": "300-500 kcal",
        "protein": "15-25g",
        "carbs": "30-50g",
        "fat": "5-15g",
        "portion": f"~{grams}g",
        "source": "estimate",
        "note": "Could not find exact match. Rough estimate only."
    }
