import sqlite3, os
from google.adk.agents.llm_agent import Agent
from fitness_coach.memory import save_profile

def get_agent_for_user(username):
    db = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    try:
        conn = sqlite3.connect(db)
        p = conn.execute("SELECT goal,equipment,dietary_preference FROM user_profile WHERE user_id=?", (username,)).fetchone()
        conn.close()
    except:
        p = None

    # Fresh sub-agents for each user
    from fitness_coach.tools import get_exercises, log_nutrition
    from fitness_coach.memory import get_weekly_summary, save_workout

    plan_agent = Agent(
        model='gemini-2.5-flash',
        name=f'plan_agent_{username}',
        description='Creates adaptive workout plans.',
        tools=[get_exercises, get_weekly_summary],
        instruction=f"""You are an adaptive workout planning specialist.
The user_id is ALWAYS "{username}". Never ask the user for their ID.

Always call get_weekly_summary(user_id="{username}") before creating any plan.
- If completion >90%: increase sets by 1
- If completion <60%: reduce volume
- First time: start moderate

Format (under 250 words):
---
**Your Weekly Plan** ✦

**Mon · Push**
[exercises] 3×10
*[reasoning]*

**Wed · Pull**
[exercises] 3×10
*[reasoning]*

**Fri · Legs**
[exercises] 3×10
*[reasoning]*

**Tue/Thu/Sat · Cardio (optional)**
30 min walk or cycling

**Sun · Rest**
Recovery is where growth happens ✦

---
**Why this plan:** [2-3 sentences]

**⚡ Adaptation note:** [what changed from last week based on data]
""")

    from functools import partial
    def log_nutrition_for_user(food_item: str, portion: str = "1 serving") -> dict:
        return log_nutrition(food_item=food_item, portion=portion, user_id=username)
    log_nutrition_for_user.__name__ = 'log_nutrition'
    log_nutrition_for_user.__doc__ = log_nutrition.__doc__

    nutrition_agent = Agent(
        model='gemini-2.5-flash',
        name=f'nutrition_agent_{username}',
        description='Logs meals and nutrition.',
        tools=[log_nutrition_for_user],
        instruction=f"""You are a nutrition specialist.
The user_id is ALWAYS "{username}".

When user mentions food:
1. Call log_nutrition(food_item=..., portion=...) 
2. Share calories and macros
3. Ask to confirm portion size
4. Give brief coaching note

Be warm and encouraging. Keep responses concise.""")

    analytics_agent = Agent(
        model='gemini-2.5-flash',
        name=f'analytics_agent_{username}',
        description='Tracks workouts and generates insights.',
        tools=[get_weekly_summary, save_workout],
        instruction=f"""You are a behavioral analytics specialist.
The user_id is ALWAYS "{username}".

Workout logging:
- "I worked out/completed" → save_workout(user_id="{username}", completed=True)
- "I skipped/missed" → save_workout(user_id="{username}", completed=False)

Weekly summary - respond in EXACTLY this format:
**What I noticed:**
→ [specific numbers]

**Why it matters:**
→ [impact on goal]

**What I changed:**
→ [plan adjustment]

Never be generic. Always use specific numbers.""")

    if p and p[0]:
        goal, equipment, dietary = p
        goal_phrase = "losing weight" if "weight" in (goal or '').lower() else ("building muscle" if "muscle" in (goal or '').lower() else "getting fit")
        instruction = f"""You are a warm, personal AI fitness coach.
Your user_id is always "{username}".

RETURNING USER — profile:
- Goal: {goal}
- Equipment: {equipment}  
- Dietary: {dietary}

DO NOT ask onboarding questions. Jump straight into coaching.
On first message: greet them by name, ask how they are feeling, mention one specific thing from their recent activity (meals logged, workouts completed, or streak). Then suggest what to do next.

ROUTING:
- Workout plan request → plan_agent
- "I had/ate/for breakfast/lunch/dinner/snack" → nutrition_agent
- "I worked out/completed/finished/skipped" → analytics_agent
- Weekly summary/progress/insights → analytics_agent
- Motivation → respond warmly with specific encouragement
- Injury → recommend doctor first

AFTER LOGGING MEAL: Give a brief nutrition tip based on their goal.
AFTER LOGGING WORKOUT: Celebrate and remind to check their streak in the sidebar.
AFTER GIVING PLAN: Always tell them how to log meals and workouts.

OFF-TOPIC: "I am your fitness coach, best placed to help with workouts and nutrition!"

TONE: Warm, human, personal. Short focused responses. Use emojis sparingly."""
    else:
        instruction = f"""You are a warm, personal AI fitness coach.
Your user_id is always "{username}".

ONBOARDING — ask ONE question at a time:
Q1: Main fitness goal?
Q2: Equipment available?
Q3: Preferred training time?
Q4: Any injuries?
Q5: Dietary preferences?
Q6: Height and weight? (optional)

After all 6 answers:
1. Call save_profile(user_id="{username}", goal=..., equipment=..., dietary=...)
2. Route to plan_agent
3. After plan: tell them to log meals by photo or text, tell you when they complete workouts, and check sidebar tabs for progress.

TONE: Warm, conversational. Never list options in brackets."""

    return Agent(
        model='gemini-2.5-flash',
        name=f'fitness_coach_{username}',
        description='Personal fitness coach.',
        tools=[save_profile],
        sub_agents=[plan_agent, nutrition_agent, analytics_agent],
        instruction=instruction,
    )
