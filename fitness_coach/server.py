from flask import Flask, request, jsonify, render_template
import asyncio, os, sys
sys.path.insert(0, '/home/hnmtzl1881/fitness-coach')

app = Flask(__name__, template_folder='templates', static_folder='static')
app.secret_key = 'fitcoach-2026'

_loop = asyncio.new_event_loop()
_runners = {}
_VISION_CACHE = {}

def get_runner(username):
    if username not in _runners:
        from fitness_coach.agent import get_agent_for_user
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        agent = get_agent_for_user(username)
        svc = InMemorySessionService()
        runner = Runner(agent=agent, app_name="fitness_coach", session_service=svc)
        sess = _loop.run_until_complete(svc.create_session(app_name="fitness_coach", user_id=username))
        _runners[username] = {'runner': runner, 'svc': svc, 'sess_id': sess.id}
    return _runners[username]['runner'], _runners[username]['sess_id']

def ask_agent(msg, username):
    try:
        from google.genai.types import Content, Part
        runner, sid = get_runner(username)
        async def _run():
            out = ""
            async for ev in runner.run_async(user_id=username, session_id=sid,
                new_message=Content(role="user", parts=[Part(text=msg)])):
                if ev.is_final_response() and ev.content and ev.content.parts:
                    out = ev.content.parts[0].text
            return out
        return _loop.run_until_complete(_run()) or "I'm here, try again."
    except Exception as e:
        return f"Error: {str(e)[:100]}"

def analyze_food_image(base64_image):
    try:
        import base64
        import vertexai
        from vertexai.generative_models import GenerativeModel, Part
        vertexai.init(project=os.getenv('GOOGLE_CLOUD_PROJECT','fitness-coach-494817'),
                     location=os.getenv('GOOGLE_CLOUD_LOCATION','us-central1'))
        if ',' in base64_image:
            base64_image = base64_image.split(',')[1]
        image_bytes = base64.b64decode(base64_image)
        image_part = Part.from_data(data=image_bytes, mime_type="image/jpeg")
        model = GenerativeModel('gemini-2.5-flash')
        prompt = """You are a nutrition expert. Analyze this food image:
            1. What food you can see
            2. Estimated calorie range
            3. Approximate macros: protein, carbs, fat

            Format:
            🍽️ I can see: [description]
            💪 Protein: ~[X]g | Carbs: ~[X]g | Fat: ~[X]g
            [coaching note]
            """
        response = model.generate_content([prompt, image_part])

        if hasattr(response, "text") and response.text:
            return response.text
        else:
            return "Got it! Let's continue with your fitness plan."

    except Exception as e:
        return f"I couldn't analyze the image. Error: {str(e)[:60]}"

@app.route('/')
def index():
    from flask import make_response
    resp = make_response(render_template('index.html'))
    resp.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.json
    msg = data.get('message', '')
    image_data = data.get('image', None)
    username = data.get('username', 'user1')

    if image_data:
        vision_reply = analyze_food_image(image_data)
        # Store vision context for follow-up
        import re as _re2
        _cal = _re2.search(r'(\d{3,4})\s*[-–]\s*(\d{3,4})\s*(?:kcal|calories)', vision_reply, _re2.IGNORECASE) or _re2.search(r'(\d{3,4})\s*[-–]\s*(\d{3,4})', vision_reply)
        _pro = _re2.search(r'Protein[:\s~]*?(\d+)', vision_reply, _re2.IGNORECASE)
        _carb = _re2.search(r'Carbs[:\s~]*?(\d+)', vision_reply, _re2.IGNORECASE)
        _fat = _re2.search(r'Fat[:\s~]*?(\d+)', vision_reply, _re2.IGNORECASE)
        print('Vision cal match:', _cal, 'pro:', _pro)
        _see_m = __import__('re').search(r'I can see: (.+?)(?:\n|$)', vision_reply)
        _full_desc = _see_m.group(1).strip() if _see_m else 'Photo meal'
        import re as _ren
        # Extract clean food name - very aggressive
        _food_vis = _full_desc.strip()
        # Stop at first comma, semicolon
        _food_vis = _food_vis.split(',')[0].strip()
        # Remove leading article phrases
        _food_vis = __import__('re').sub(r'^(A (?:lean and balanced|well-balanced|plate (?:of|featuring|with|containing|showing)|bowl of|serving of|dish of|portion of|meal (?:of|consisting of|featuring))|A|An)\s+', '', _food_vis, flags=__import__('re').IGNORECASE).strip()
        # Remove cooking method words at start
        pass  # skip cooking method removal
        _food_vis = __import__('re').sub(r'^(sliced|diced|chopped|minced|seasoned|grilled|pan-fried|pan-seared|baked|fried|cooked|consisting of|featuring)\s+', '', _food_vis, flags=__import__('re').IGNORECASE).strip()
        # Take first 3 meaningful words
        _words = _food_vis.split()
        _food_vis = ' '.join(_words[:3]).strip('.,').strip()
        if not _food_vis or len(_food_vis) < 3:
            _food_vis = 'Photo meal'
        _pv = int(_pro.group(1)) if _pro else 0
        _cv = int(_carb.group(1)) if _carb else 0
        _fv = int(_fat.group(1)) if _fat else 0
        _cmin = int(_cal.group(1)) if _cal else max(200, int(_pv*4 + _cv*4 + _fv*9) - 50)
        _cmax = int(_cal.group(2)) if _cal else max(250, int(_pv*4 + _cv*4 + _fv*9) + 50)
        _VISION_CACHE[username] = {'food': _food_vis, 'reply': vision_reply, 'cal_min': _cmin, 'cal_max': _cmax, 'protein': (_pro.group(1)+'g') if _pro else '0g', 'carbs': (_carb.group(1)+'g') if _carb else '0g', 'fat': (_fat.group(1)+'g') if _fat else '0g'}
        reply = vision_reply
    else:
        # Inject profile context on first message if profile exists
        import sqlite3 as _sq2
        _db = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
        _conn = _sq2.connect(_db)
        _p = _conn.execute("SELECT goal, equipment, dietary_preference FROM user_profile WHERE user_id=?", (username,)).fetchone()
        _conn.close()
        if _p and _p[0] and username in _runners:
            # Check if this is first message in session
            _sess = _runners[username]
            actual_msg = msg
        elif _p and _p[0] and username not in _runners:
            # Pre-warm with profile context
            get_runner(username)
            context = "SYSTEM: User profile loaded. Goal: " + (_p[0] or '') + ", Equipment: " + (_p[1] or '') + ", Dietary: " + (_p[2] or '') + ". Do NOT ask onboarding questions. Greet warmly and ask how they are today."
            ask_agent(context, username)
            actual_msg = msg
        else:
            actual_msg = msg
        # Check if user refers to a photo meal
        _followup_keywords = ['i had this meal', 'log this', 'that meal', 'this meal', 'i just had this', 'yes that', 'for breakfast', 'for lunch', 'for dinner', 'for snack']
        if any(k in msg.lower() for k in _followup_keywords) and username in _VISION_CACHE:
            _vc = _VISION_CACHE.pop(username)
            try:
                from fitness_coach.memory import save_meal
                _mt = None
                for _mtype in ['breakfast','lunch','dinner','snack']:
                    if _mtype in msg.lower():
                        _mt = _mtype.capitalize()
                        break
                save_meal(user_id=username, food=_vc['food'],
                    calories_min=_vc['cal_min'], calories_max=_vc['cal_max'],
                    protein=_vc['protein'], carbs=_vc['carbs'], fat=_vc['fat'],
                    meal_type=_mt)
                reply = "I've logged your " + _vc['food'] + " — " + str(_vc['cal_min']) + "-" + str(_vc['cal_max']) + " kcal, " + _vc['protein'] + " protein. Great choice!"
            except Exception as _se:
                reply = ask_agent("I had " + _vc['food'] + ". Please confirm it's logged.", username)
        else:
            reply = ask_agent(actual_msg, username)
            # Auto-save workout if user mentions completing it
            _workout_kw = ['completed my workout','finished my workout','did my workout','worked out','i trained','antrenman yaptim','done with workout','completed workout','completed today','completed monday','completed tuesday','completed wednesday','completed thursday','completed friday','completed saturday','completed sunday']
            if any(k in msg.lower() for k in _workout_kw):
                try:
                    from fitness_coach.memory import save_workout
                    import datetime as _dt
                    _days = {'monday':0,'tuesday':1,'wednesday':2,'thursday':3,'friday':4,'saturday':5,'sunday':6}
                    _wdate = _dt.date.today()
                    for _dn, _di in _days.items():
                        if _dn in msg.lower():
                            _today_i = _wdate.weekday()
                            _diff = (_today_i - _di) % 7
                            _wdate = _wdate - _dt.timedelta(days=_diff)
                            break
                    import sqlite3 as _sq
                    _db = __import__('os').path.join(__import__('os').path.dirname(__file__), 'fitness_data.db')
                    _conn = _sq.connect(_db)
                    _conn.execute('INSERT OR REPLACE INTO workouts (user_id, date, completed) VALUES (?,?,?)', (username, str(_wdate), 1))
                    _conn.commit()
                    _conn.close()
                except:
                    pass

    # Auto-parse and save meal from agent reply
    import re as _re
    _meal_match = _re.search(r'(\d+)-(\d+)\s*(?:kcal|calories)', reply, _re.IGNORECASE)
    _food_match = _re.search(r"(?:your|for)\s+([a-z\s&]+?)(?:,|\.|logged)", reply, _re.IGNORECASE)
    _pro_match = _re.search(r'(\d+\.?\d*)g\s*protein', reply, _re.IGNORECASE)
    _carb_match = _re.search(r'(\d+\.?\d*)g\s*carbs', reply, _re.IGNORECASE)
    _fat_match = _re.search(r'(\d+\.?\d*)g\s*fat', reply, _re.IGNORECASE)
    
    _vision_followups = ['i had this meal', 'this meal', 'log this', 'that meal', 'i just had this']
    _is_vision_followup = any(k in msg.lower() for k in _vision_followups)
    if _meal_match and not _is_vision_followup and image_data is None and any(k in msg.lower() for k in ['i had', 'i ate', 'for breakfast', 'for lunch', 'for dinner', 'i just had']):
        try:
            from fitness_coach.memory import save_meal
            _food_name = msg.lower()
            _meal_type_match = _re.search(r'for (breakfast|lunch|dinner|snack)', _food_name, _re.IGNORECASE)
            _meal_type = _meal_type_match.group(1).capitalize() if _meal_type_match else ''
            for prefix in ['hey i had ', 'hey, i had ', 'i just had ', 'i had ', 'i ate ', 'today i had ', 'today, i had ', 'today ']:
                _food_name = _food_name.replace(prefix, '')
            # Remove "A plate featuring..." type descriptions
            import re as _re_name
            _food_name = _re_name.sub(
                r'^(a\s+classic\s+meal\s+featuring|a\s+plate\s+(?:featuring|with|of)|a\s+bowl\s+of|a\s+serving\s+of|a\s+generous|a\s+generous\s+serving\s+of)\s+'
                '',
                _food_name,
                flags=_re_name.IGNORECASE
            )
            _food_name = _food_name.replace('sliced, ', '')
            _food_name = _food_name.replace('grilled or pan-seared ', '')
            _food_name = _food_name.replace('grilled ', '')
            _food_name = _food_name.replace('pan-seared ', '')
            _food_name = _food_name.split(',')[0].split(' and ')[0].split(' served')[0].strip()
            _food_name = _re.sub(r'\s+for\s+(breakfast|lunch|dinner|snack)', '', _food_name, flags=_re.IGNORECASE).strip()
            _food_name = _food_name.strip(' .,!?').capitalize()
            if _meal_type:
                _food_name = _food_name + ' for ' + _meal_type
            save_meal(
                user_id=username,
                food=_food_name[:50],
                calories_min=int(_meal_match.group(1)),
                calories_max=int(_meal_match.group(2)),
                protein=(_pro_match.group(1)+'g') if _pro_match else '0g',
                carbs=(_carb_match.group(1)+'g') if _carb_match else '0g',
                fat=(_fat_match.group(1)+'g') if _fat_match else '0g'
            )
        except Exception as _e:
            print(f"Auto-save meal error: {_e}")

    # AI Meal suggestion
    meal_keywords = ['i had', 'i ate', 'for breakfast', 'for lunch', 'for dinner', 'i just had']
    if any(k in msg.lower() for k in meal_keywords) and not image_data:
        try:
            import sqlite3 as sq
            db = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
            conn = sq.connect(db)
            meals = conn.execute("SELECT protein, carbs FROM meals WHERE user_id=? AND date=date('now') ORDER BY id DESC LIMIT 5", (username,)).fetchall()
            conn.close()
            # Re-fetch meals including just-saved ones
            import sqlite3 as _sq_tip, os as _os_tip, re as _re_tip
            _db_tip = _os_tip.path.join(_os_tip.path.dirname(__file__), 'fitness_data.db')
            _conn_tip = _sq_tip.connect(_db_tip)
            _fresh_meals = _conn_tip.execute("SELECT protein, carbs FROM meals WHERE user_id=? AND date=date('now')", (username,)).fetchall()
            _conn_tip.close()
            total_pro = sum(float(str(m[0] or '0').replace('g','')) for m in _fresh_meals)
            total_carb = sum(float(str(m[1] or '0').replace('g','')) for m in _fresh_meals)
            # Also add macros from current reply in case not saved yet
            _pro_in_reply = _re_tip.search(r'Protein[:\s~]*?([\d.]+)g', reply, _re_tip.IGNORECASE)
            _carb_in_reply = _re_tip.search(r'Carbs?[:\s~]*?([\d.]+)g', reply, _re_tip.IGNORECASE)
            if _pro_in_reply: total_pro += float(_pro_in_reply.group(1))
            if _carb_in_reply: total_carb += float(_carb_in_reply.group(1))
            pro_left = max(0, 120 - total_pro)
            carb_left = max(0, 200 - total_carb)
            tip = ""
            # Get logged foods to avoid suggesting what they already ate
            logged_foods = [str(m[0] or '').lower() for m in meals]
            already_has_oats = any('oat' in f for f in logged_foods)
            already_has_protein = any(p in f for f in logged_foods for p in ['chicken','egg','yogurt','fish','beef','turkey'])
            if pro_left > 30 and not already_has_protein:
                tips_pro = ['Add Greek yogurt or eggs to your next meal.','A chicken breast or tuna can help hit your protein goal.','Try a protein shake or cottage cheese as a snack.']
                import random as _rand
                tip = "\n\nCoach tip: You still need ~" + str(int(pro_left)) + "g of protein today. " + _rand.choice(tips_pro)
            elif carb_left > 50 and not already_has_oats:
                tips_carb = ['A banana or sweet potato would be great.','Brown rice or whole grain bread can boost your carbs.','Try oats or a fruit smoothie.']
                import random as _rand
                tip = "\n\nCoach tip: You need ~" + str(int(carb_left)) + "g more carbs today. " + _rand.choice(tips_carb)
            if tip and not reply.startswith('Error'):
                reply += tip
        except: pass

    # Coach memo for weekly summary
    weekly_keywords = ['how did i do', 'weekly summary', 'how was my week', 'my progress']
    if any(k in msg.lower() for k in weekly_keywords):
        try:
            import sqlite3 as sq
            db = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
            conn = sq.connect(db)
            workouts = conn.execute("SELECT completed FROM workouts WHERE user_id=? AND date>=date('now','-7 days')", (username,)).fetchall()
            profile = conn.execute("SELECT goal FROM user_profile WHERE user_id=?", (username,)).fetchone()
            conn.close()
            completed = sum(1 for w in workouts if w[0])
            total = len(workouts)
            goal = profile[0] if profile else 'your goal'
            goal_phrase = "losing weight" if "weight" in (goal or "").lower() else ("building muscle" if "muscle" in (goal or "").lower() else "getting fit")
            rate = int((completed/total)*100) if total > 0 else 0
            nl = "\n"
            if rate == 100:
                memo = nl + nl + "✦ **A note from your coach:**" + nl + str(completed) + " workouts. Not one skipped. That consistency is exactly what gets results. Every session is a direct investment in " + goal_phrase + ". Keep going."
            elif rate >= 60:
                memo = nl + nl + "✦ **A note from your coach:**" + nl + "You got " + str(completed) + " out of " + str(total) + " workouts done. Real progress. Next week, let's aim for one more."
            else:
                memo = nl + nl + "✦ **A note from your coach:**" + nl + "This week was tough - " + str(completed) + " out of " + str(total) + " workouts. That's okay. You haven't failed - you're just finding your rhythm."
            reply += memo
        except: pass

    return jsonify({'reply': reply})

@app.route('/api/dashboard')
def dashboard():
    username = request.args.get('username', 'user1')
    try:
        import sqlite3 as sq
        from datetime import datetime
        db = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
        conn = sq.connect(db)
        conn.row_factory = sq.Row
        workouts = conn.execute("SELECT date,completed FROM workouts WHERE user_id=? AND date>=date('now','-30 days') ORDER BY date", (username,)).fetchall()
        meals = conn.execute("SELECT date,food,calories_min,calories_max,protein,carbs,fat,meal_type FROM meals WHERE user_id=? ORDER BY date DESC LIMIT 20", (username,)).fetchall()
        profile = conn.execute("SELECT * FROM user_profile WHERE user_id=?", (username,)).fetchone()
        conn.close()

        completed = sum(1 for w in workouts if w['completed'])
        total = len(workouts)

        good = ['lentils','chicken','tofu','tempeh','salad','oats','quinoa','chickpeas','eggs','salmon','banana','rice']
        bad = ['burger','pizza','fries','cake','chips','candy']
        ns = 50 if meals else 0
        for m in meals:
            f = (m['food'] or '').lower()
            if any(g in f for g in good): ns += 10
            if any(b in f for b in bad): ns -= 15
        ns = max(0, min(100, ns))

        dates = sorted([w['date'] for w in workouts if w['completed']], reverse=True)
        streak = 0
        if dates:
            streak = 1
            for i in range(1, len(dates)):
                d1 = datetime.strptime(dates[i-1], '%Y-%m-%d')
                d2 = datetime.strptime(dates[i], '%Y-%m-%d')
                if (d1-d2).days == 1: streak += 1
                else: break

        return jsonify({
            'workouts_completed': completed,
            'workouts_total': total,
            'meals_logged': len(meals),
            'streak': streak,
            'nutrition_score': ns,
            'goal': profile['goal'] if profile else 'Not set',
            'equipment': profile['equipment'] if profile else 'Not set',
            'effort_score': min(100, completed * 15 + (len(meals) * 5)),
            'workout_details': [{'date': w['date'], 'completed': w['completed']} for w in workouts],
            'workout_history': (lambda today, wset: [1 if str(today - __import__('datetime').timedelta(days=(today.weekday()-i)%7)) in wset else 0 for i in range(7)])(__import__('datetime').date.today(), {w['date'] for w in workouts if w['completed']}),
            'total_workouts': completed,
            'completion_rate': int((completed/total)*100) if total > 0 else 0,
            'meal_details': [{'date': m['date'], 'food': m['food'], 'calories_min': m['calories_min'] or 0, 'calories_max': m['calories_max'] or 0, 'protein': m['protein'] or '0', 'carbs': m['carbs'] or '0', 'fat': m['fat'] or '0', 'meal_type': m['meal_type'] if m['meal_type'] else ''} for m in meals],
        })
    except Exception as e:
        return jsonify({'workouts_completed':0,'workouts_total':0,'meals_logged':0,'streak':0,'nutrition_score':0,'error':str(e)})

@app.route('/api/reset', methods=['POST'])
def reset():
    try:
        data = request.json
        username = data.get('username', 'user1')
        import sqlite3 as sq
        db = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
        conn = sq.connect(db)
        conn.execute("DELETE FROM user_profile WHERE user_id=?", (username,))
        conn.execute("DELETE FROM workouts WHERE user_id=?", (username,))
        conn.execute("DELETE FROM meals WHERE user_id=?", (username,))
        conn.commit()
        conn.close()
        if username in _runners:
            del _runners[username]
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)})

@app.route('/api/weight', methods=['GET','POST'])
def weight():
    import sqlite3 as _sq
    db = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    user_id = request.args.get('username') or (request.json or {}).get('username','user1')
    
    if request.method == 'POST':
        data = request.json or {}
        weight = data.get('weight')
        target = data.get('target_weight')
        height = data.get('height')
        conn = _sq.connect(db)
        if weight:
            from datetime import date
            conn.execute("INSERT INTO weight_log (user_id, weight, date) VALUES (?,?,?)",
                (user_id, weight, str(date.today())))
        if target or height:
            conn.execute("INSERT OR REPLACE INTO user_goals (user_id, target_weight, height) VALUES (?,?,?)",
                (user_id, target, height))
        conn.commit()
        conn.close()
        return jsonify({'ok': True})
    else:
        conn = _sq.connect(db)
        logs = conn.execute("SELECT weight, date FROM weight_log WHERE user_id=? ORDER BY date DESC LIMIT 30", (user_id,)).fetchall()
        goals = conn.execute("SELECT target_weight, height FROM user_goals WHERE user_id=?", (user_id,)).fetchone()
        conn.close()
        return jsonify({
            'logs': [{'weight': r[0], 'date': r[1]} for r in logs],
            'target_weight': goals[0] if goals else None,
            'height': goals[1] if goals else None
        })

import hashlib

def hash_pw(pw):
    return hashlib.sha256(pw.encode()).hexdigest()

@app.route('/api/register', methods=['POST'])
def register():
    data = request.json
    un = data.get('username','').strip()
    pw = data.get('password','').strip()
    if not un or not pw:
        return jsonify({'ok':False,'error':'Username and password required'})
    import sqlite3 as _sq3
    _db3 = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    conn = _sq3.connect(_db3)
    existing = conn.execute("SELECT user_id FROM user_profile WHERE user_id=?", (un,)).fetchone()
    if existing:
        conn.close()
        return jsonify({'ok':False,'error':'Username already taken'})
    conn.execute("INSERT OR IGNORE INTO user_profile (user_id) VALUES (?)", (un,))
    conn.execute("UPDATE user_profile SET password=? WHERE user_id=?", (hash_pw(pw), un))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/login', methods=['POST'])
def login():
    data = request.json
    un = data.get('username','').strip()
    pw = data.get('password','').strip()
    import sqlite3 as _sq3
    _db3 = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    conn = _sq3.connect(_db3)
    row = conn.execute("SELECT password FROM user_profile WHERE user_id=?", (un,)).fetchone()
    conn.close()
    if not row:
        return jsonify({'ok':False,'error':'User not found'})
    if row[0] and row[0] != hash_pw(pw):
        return jsonify({'ok':False,'error':'Wrong password'})
    return jsonify({'ok':True})

@app.route('/api/init', methods=['POST'])
def init():
    data = request.json
    username = data.get('username', 'user1')
    try:
        get_runner(username)
    except:
        pass
    return jsonify({'ok': True})


@app.route('/api/change_password', methods=['POST'])
def change_password():
    data = request.json
    un = data.get('username','').strip()
    pw = data.get('password','').strip()
    if not un or not pw:
        return jsonify({'ok':False,'error':'Missing fields'})
    import sqlite3 as _sq3
    _db3 = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    conn = _sq3.connect(_db3)
    conn.execute("UPDATE user_profile SET password=? WHERE user_id=?", (hash_pw(pw), un))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})

@app.route('/api/update_profile', methods=['POST'])
def update_profile():
    data = request.json
    un = data.get('username','').strip()
    goal = data.get('goal','')
    equip = data.get('equipment','')
    import sqlite3 as _sq3
    _db3 = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    conn = _sq3.connect(_db3)
    conn.execute("UPDATE user_profile SET goal=?, equipment=? WHERE user_id=?", (goal, equip, un))
    conn.commit()
    conn.close()
    return jsonify({'ok':True})


@app.route('/api/save_email', methods=['POST'])
def save_email():
    data = request.json
    un = data.get('username','').strip()
    email = data.get('email','').strip()
    enabled = data.get('enabled', False)
    import sqlite3 as _sq3
    _db3 = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    conn = _sq3.connect(_db3)
    try:
        conn.execute("ALTER TABLE user_profile ADD COLUMN email TEXT")
    except: pass
    try:
        conn.execute("ALTER TABLE user_profile ADD COLUMN email_enabled INTEGER DEFAULT 0")
    except: pass
    conn.execute("UPDATE user_profile SET email=?, email_enabled=? WHERE user_id=?", (email, 1 if enabled else 0, un))
    conn.commit()
    conn.close()
    # Send confirmation email
    if email and enabled:
        try:
            import resend
            from dotenv import load_dotenv
            load_dotenv('/home/hnmtzl1881/fitness-coach/.env')
            resend.api_key = os.environ.get('RESEND_API_KEY','')
            resend.Emails.send({
                "from": "FitCoach <onboarding@resend.dev>",
                "to": "hanimmmm828@gmail.com",
                "subject": "✅ FitCoach Daily Emails Activated!",
                "html": f"""
<!DOCTYPE html>
<html>
<body style="margin:0;padding:0;background:#FFF5F7;font-family:'Helvetica Neue',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#FFF5F7;padding:40px 0;">
    <tr><td align="center">
      <table width="520" cellpadding="0" cellspacing="0" style="background:white;border-radius:20px;overflow:hidden;box-shadow:0 4px 24px rgba(201,24,74,0.10);">
        <tr><td style="background:linear-gradient(135deg,#E8547A,#C9184A);padding:36px 40px;text-align:center;">
          <div style="display:inline-block;background:rgba(255,255,255,0.2);border-radius:14px;padding:10px 16px;margin-bottom:12px;">
            <span style="font-size:28px;">✦</span>
          </div>
          <h1 style="margin:0;color:white;font-size:26px;font-weight:700;letter-spacing:-0.5px;">FitCoach</h1>
          <p style="margin:4px 0 0;color:rgba(255,255,255,0.8);font-size:13px;letter-spacing:2px;text-transform:uppercase;">AI Fitness Coach</p>
        </td></tr>
        <tr><td style="padding:40px;">
          <h2 style="margin:0 0 8px;color:#2A1520;font-size:22px;">Welcome, {un}! 🎉</h2>
          <p style="color:#A07080;font-size:15px;line-height:1.6;margin:0 0 24px;">Your daily motivation emails have been activated. Every morning at <strong style="color:#C9184A;">8:00 AM</strong>, you'll receive a personalized summary of your fitness journey.</p>
          <div style="background:#FFF5F7;border-radius:14px;padding:20px;margin-bottom:24px;">
            <p style="margin:0 0 12px;color:#2A1520;font-weight:600;font-size:14px;">📬 What to expect each morning:</p>
              <p style="margin:0 0 10px;color:#A07080;font-size:13px;">💪 &nbsp; Your workout completion status</p>
              <p style="margin:0 0 10px;color:#A07080;font-size:13px;">🍽 &nbsp; Yesterday's nutrition summary</p>
              <p style="margin:0 0 10px;color:#A07080;font-size:13px;">🔥 &nbsp; Your current streak</p>
              <p style="margin:0;color:#A07080;font-size:13px;">⚡ &nbsp; A personalized motivational message</p>
          </div>
          <div style="text-align:center;margin-bottom:24px;">
            <a href="#" style="display:inline-block;background:linear-gradient(135deg,#E8547A,#C9184A);color:white;text-decoration:none;padding:14px 32px;border-radius:12px;font-weight:600;font-size:15px;">Open FitCoach ✦</a>
          </div>
          <p style="color:#C0A0A8;font-size:12px;text-align:center;margin:0;">You're on your way to a healthier you. Stay consistent! 🌟</p>
        </td></tr>
        <tr><td style="background:#FFF5F7;padding:20px;text-align:center;border-top:1px solid #FFE4EC;">
          <p style="margin:0;color:#C0A0A8;font-size:12px;">FitCoach AI &middot; Your Personal Fitness Coach</p>
          <p style="margin:4px 0 0;color:#C0A0A8;font-size:11px;">✦ Always here &middot; Always listening</p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>
"""
            })
        except Exception as e:
            print(f"Confirmation email error: {e}")
    return jsonify({'ok':True})


@app.route('/api/insights')
def insights():
    username = request.args.get('username','')
    import sqlite3 as _sq3
    from datetime import datetime
    _db3 = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    conn = _sq3.connect(_db3)
    conn.row_factory = _sq3.Row
    workouts = conn.execute("SELECT * FROM workouts WHERE user_id=? AND date>=date('now','-7 days') AND completed=1", (username,)).fetchall()
    meals = conn.execute("SELECT * FROM meals WHERE user_id=? AND date>=date('now','-7 days') ORDER BY date", (username,)).fetchall()
    all_w = conn.execute("SELECT date FROM workouts WHERE user_id=? AND completed=1 ORDER BY date DESC", (username,)).fetchall()
    streak = 0
    if all_w:
        streak = 1
        for i in range(1, len(all_w)):
            d1 = datetime.strptime(all_w[i-1]['date'], '%Y-%m-%d')
            d2 = datetime.strptime(all_w[i]['date'], '%Y-%m-%d')
            if (d1-d2).days == 1: streak += 1
            else: break
    food_count = {}
    for m in meals:
        food_count[m['food']] = food_count.get(m['food'], 0) + 1
    top_foods = sorted([{'food':k,'count':v} for k,v in food_count.items()], key=lambda x: -x['count'])[:5]
    cal_by_day = {}
    for m in meals:
        cal = ((m['calories_min'] or 0) + (m['calories_max'] or 0)) / 2
        cal_by_day[m['date']] = cal_by_day.get(m['date'], 0) + cal
    calorie_trend = [{'date':k,'calories':int(v)} for k,v in sorted(cal_by_day.items())]
    avg_cal = int(sum(cal_by_day.values()) / len(cal_by_day)) if cal_by_day else 0
    conn.close()
    return jsonify({'total_workouts':len(workouts),'total_meals':len(meals),'avg_calories':avg_cal,'streak':streak,'top_foods':top_foods,'calorie_trend':calorie_trend})

@app.route('/api/ai_insights')
def ai_insights():
    username = request.args.get('username','')
    import sqlite3 as _sq3
    _db3 = os.path.join(os.path.dirname(__file__), 'fitness_data.db')
    conn = _sq3.connect(_db3)
    conn.row_factory = _sq3.Row
    meals = conn.execute("SELECT food FROM meals WHERE user_id=? AND date>=date('now','-7 days')", (username,)).fetchall()
    workouts = conn.execute("SELECT completed FROM workouts WHERE user_id=? AND date>=date('now','-7 days')", (username,)).fetchall()
    profile = conn.execute("SELECT goal FROM user_profile WHERE user_id=?", (username,)).fetchone()
    conn.close()
    meal_summary = ', '.join([m['food'] for m in meals[:8]]) or 'none logged'
    workout_count = sum(1 for w in workouts if w['completed'])
    goal = profile['goal'] if profile else 'general fitness'
    prompt = f"You are a fitness coach. Analyze this week briefly in 3-4 sentences. Goal: {goal}. Workouts: {workout_count}. Meals: {meal_summary}. Be encouraging, specific, use emojis."
    try:
        analysis = ask_agent(prompt, username+'_insights')
        return jsonify({'analysis': analysis})
    except:
        return jsonify({'analysis': 'Keep up the great work! Consistency is key. 💪'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=False)
