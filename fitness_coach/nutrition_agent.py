from google.adk.agents.llm_agent import Agent
from fitness_coach.tools import log_nutrition
from fitness_coach.memory import save_meal

nutrition_agent = Agent(
    model='gemini-2.5-flash',
    name='nutrition_agent',
    description='Handles meal logging and nutrition tracking.',
    tools=[log_nutrition, save_meal],
    instruction="""You are a nutrition specialist and meal tracker.

When a user logs a meal:
1. Call log_nutrition to get calorie range and macros
2. Call save_meal to store it with user_id="user1"
3. Always present calories as a RANGE (e.g. 400-500 kcal), never exact
4. Ask user to confirm portion size
5. Give a brief nutritional comment relevant to their goal

Never give exact calorie numbers. Always ranges.
Be non-judgmental about food choices.
""",
)
