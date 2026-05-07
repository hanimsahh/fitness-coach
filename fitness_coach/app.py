import streamlit as st
import sqlite3, os, asyncio
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="FitCoach AI", page_icon="✦", layout="wide", initial_sidebar_state="expanded")

if "logged_in" not in st.session_state: st.session_state.logged_in = False
if "username"  not in st.session_state: st.session_state.username  = ""
if "messages"  not in st.session_state: st.session_state.messages  = []

DB = os.path.join(os.path.dirname(__file__), "fitness_data.db")

def get_data():
    try:
        c = sqlite3.connect(DB)
        w = pd.read_sql_query("SELECT date,completed FROM workouts WHERE date>=date('now','-7 days') ORDER BY date", c)
        m = pd.read_sql_query("SELECT date,food,calories_min,calories_max FROM meals WHERE date>=date('now','-7 days') ORDER BY date", c)
        c.close(); return w, m
    except: return pd.DataFrame(), pd.DataFrame()

def effort(w):
    if w.empty: return 0
    return int(w["completed"].sum()/len(w)*100)

def nscore(m):
    if m.empty: return 50
    g=["lentils","chicken","tofu","tempeh","salad","oats","quinoa","chickpeas","eggs","salmon","banana","rice"]
    b=["burger","pizza","fries","cake","chips","candy"]
    s=50
    for _,r in m.iterrows():
        f=str(r["food"]).lower()
        if any(x in f for x in g): s+=4
        if any(x in f for x in b): s-=8
    return max(0,min(100,s))

def streak(w):
    if w.empty: return 0
    d=sorted(w[w["completed"]==1]["date"].tolist(),reverse=True)
    if not d: return 0
    s=1
    for i in range(1,len(d)):
        try:
            if (datetime.strptime(d[i-1],"%Y-%m-%d")-datetime.strptime(d[i],"%Y-%m-%d")).days==1: s+=1
            else: break
        except: break
    return s

def get_runner():
    if "runner" not in st.session_state:
        from fitness_coach.agent import root_agent
        from google.adk.runners import Runner
        from google.adk.sessions import InMemorySessionService
        svc=InMemorySessionService()
        r=Runner(agent=root_agent,app_name="fitness_coach",session_service=svc)
        loop=asyncio.new_event_loop()
        sess=loop.run_until_complete(svc.create_session(app_name="fitness_coach",user_id="user1"))
        loop.close()
        st.session_state.runner=r; st.session_state.svc=svc; st.session_state.sess_id=sess.id
    return st.session_state.runner, st.session_state.sess_id

def ask(msg):
    try:
        from google.genai.types import Content, Part
        runner, sid = get_runner()
        loop = asyncio.new_event_loop()
        async def _run():
            out=""
            async for ev in runner.run_async(user_id="user1",session_id=sid,new_message=Content(role="user",parts=[Part(text=msg)])):
                if ev.is_final_response() and ev.content and ev.content.parts:
                    out=ev.content.parts[0].text
            return out
        res=loop.run_until_complete(_run()); loop.close()
        return res or "I'm here — try again?"
    except Exception as e: return f"Error: {str(e)[:80]}"

now = datetime.now().strftime("%H:%M")

# ── GLOBAL CSS ──
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;0,600;1,300;1,400&family=DM+Sans:wght@300;400;500;600&display=swap');
*, *::before, *::after { box-sizing: border-box; }
#MainMenu, footer, header, [data-testid="stToolbar"], [data-testid="stDecoration"] { display: none !important; }
.block-container { padding: 0 !important; max-width: 100% !important; }
[data-testid="stAppViewBlockContainer"] { padding: 0 !important; }

:root {
    --pink: #E8547A;
    --teal: #3BBFB8;
    --bg: #FDF6F0;
    --white: #FFFFFF;
    --text: #2D2D3A;
    --dim: #9090A0;
    --border: rgba(232,84,122,0.12);
}

html, body, .stApp { background: var(--bg) !important; font-family: 'DM Sans', sans-serif; color: var(--text); }

/* Sidebar */
[data-testid="stSidebar"] { background: var(--white) !important; border-right: 1px solid var(--border) !important; }
[data-testid="stSidebar"] > div:first-child { padding: 0 !important; }
[data-testid="stSidebarContent"] { padding: 0 !important; }

/* Metrics */
[data-testid="stMetric"] { background: var(--white) !important; border-radius: 12px !important; border: 1px solid var(--border) !important; padding: 12px 14px !important; }
[data-testid="stMetricValue"] { font-family: 'Cormorant Garamond', serif !important; font-size: 1.6rem !important; color: var(--text) !important; font-weight: 600 !important; line-height: 1.1 !important; }
[data-testid="stMetricLabel"] p { font-size: 0.6rem !important; letter-spacing: 1.5px !important; text-transform: uppercase !important; color: var(--dim) !important; font-family: 'DM Sans', sans-serif !important; }
[data-testid="stMetricDelta"] { display: none !important; }
[data-testid="stVerticalBlock"] { gap: 0.5rem !important; }

/* Chat input */
.stChatInput > div { border-radius: 14px !important; border: 2px solid var(--border) !important; background: var(--white) !important; }
.stChatInput > div:focus-within { border-color: var(--pink) !important; box-shadow: 0 0 0 4px rgba(232,84,122,0.08) !important; }

/* Form */
[data-testid="stForm"] { border: none !important; padding: 0 !important; background: transparent !important; }
.stTextInput > label { display: none !important; }
.stTextInput > div > div > input {
    border-radius: 12px !important; border: 2px solid var(--border) !important;
    background: var(--white) !important; color: var(--text) !important;
    font-size: 0.9rem !important; padding: 12px 16px !important;
    font-family: 'DM Sans', sans-serif !important;
}
.stTextInput > div > div > input:focus { border-color: var(--pink) !important; box-shadow: 0 0 0 4px rgba(232,84,122,0.08) !important; }
.stTextInput > div > div > input::placeholder { color: rgba(45,45,58,0.3) !important; }
.stButton > button {
    background: linear-gradient(135deg, var(--pink), #C0365A) !important;
    color: white !important; border: none !important; border-radius: 12px !important;
    font-size: 0.9rem !important; font-weight: 600 !important; padding: 13px 24px !important;
    width: 100% !important; font-family: 'DM Sans', sans-serif !important;
    box-shadow: 0 6px 20px rgba(232,84,122,0.25) !important;
}

::-webkit-scrollbar { width: 3px; }
::-webkit-scrollbar-thumb { background: rgba(232,84,122,0.2); border-radius: 100px; }
</style>
""", unsafe_allow_html=True)

# ══════════════════════════════════
#  LOGIN
# ══════════════════════════════════
if not st.session_state.logged_in:
    # hide sidebar on login
    st.markdown("<style>[data-testid='stSidebar']{display:none!important}[data-testid='collapsedControl']{display:none!important}</style>", unsafe_allow_html=True)

    _, center, _ = st.columns([1, 1.4, 1])
    with center:
        # Decorative blobs
        st.markdown("""
        <div style="position:fixed;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:0;overflow:hidden;">
            <svg style="position:absolute;top:-100px;left:-80px;width:420px;opacity:0.13;" viewBox="0 0 400 400">
                <path d="M300,50 C380,80 420,180 380,270 C340,360 220,400 130,370 C40,340 -20,240 10,150 C40,60 140,20 220,10Z" fill="#3BBFB8"/>
            </svg>
            <svg style="position:absolute;bottom:-80px;right:-60px;width:360px;opacity:0.1;" viewBox="0 0 400 400">
                <path d="M250,30 C350,60 410,160 390,260 C370,360 260,420 160,400 C60,380 -10,280 5,180 C20,80 110,20 190,10Z" fill="#E8547A"/>
            </svg>
            <svg style="position:absolute;top:60px;right:120px;width:100px;opacity:0.18;transform:rotate(-10deg);" viewBox="0 0 120 200">
                <line x1="60" y1="200" x2="60" y2="0" stroke="#3BBFB8" stroke-width="1.5"/>
                <path d="M60,40 C40,20 15,15 10,30 C5,45 30,55 60,40Z" fill="none" stroke="#3BBFB8" stroke-width="1.5"/>
                <path d="M60,75 C80,55 105,50 110,65 C115,80 90,90 60,75Z" fill="none" stroke="#3BBFB8" stroke-width="1.5"/>
                <path d="M60,110 C40,90 15,85 10,100 C5,115 30,125 60,110Z" fill="none" stroke="#E8547A" stroke-width="1.5"/>
                <path d="M60,145 C80,125 105,120 110,135 C115,150 90,160 60,145Z" fill="none" stroke="#E8547A" stroke-width="1.5"/>
            </svg>
            <svg style="position:absolute;bottom:80px;left:80px;width:80px;opacity:0.15;transform:rotate(15deg);" viewBox="0 0 120 200">
                <line x1="60" y1="200" x2="60" y2="0" stroke="#E8547A" stroke-width="1.5"/>
                <path d="M60,50 C40,30 15,25 10,40 C5,55 30,65 60,50Z" fill="none" stroke="#E8547A" stroke-width="1.5"/>
                <path d="M60,90 C80,70 105,65 110,80 C115,95 90,105 60,90Z" fill="none" stroke="#3BBFB8" stroke-width="1.5"/>
                <path d="M60,130 C40,110 15,105 10,120 C5,135 30,145 60,130Z" fill="none" stroke="#3BBFB8" stroke-width="1.5"/>
            </svg>
            <svg style="position:absolute;top:200px;left:200px;width:160px;opacity:0.1;" viewBox="0 0 200 150">
                <circle cx="20" cy="30" r="3.5" fill="#E8547A"/>
                <circle cx="60" cy="10" r="2.5" fill="#E8547A"/>
                <circle cx="100" cy="40" r="4" fill="#E8547A"/>
                <circle cx="140" cy="15" r="2" fill="#3BBFB8"/>
                <circle cx="180" cy="50" r="3" fill="#3BBFB8"/>
                <circle cx="40" cy="80" r="2.5" fill="#3BBFB8"/>
                <circle cx="120" cy="90" r="3.5" fill="#E8547A"/>
                <circle cx="160" cy="70" r="2" fill="#E8547A"/>
            </svg>
            <div style="position:absolute;top:100px;right:200px;font-size:14px;color:#E8547A;opacity:0.2;">✦</div>
            <div style="position:absolute;top:300px;left:160px;font-size:10px;color:#3BBFB8;opacity:0.22;">✦</div>
            <div style="position:absolute;bottom:160px;right:180px;font-size:12px;color:#E8547A;opacity:0.18;">✦</div>
            <div style="position:absolute;bottom:240px;left:300px;font-size:8px;color:#3BBFB8;opacity:0.2;">✦</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="position:relative;z-index:1;padding:48px 0 24px;">
            <div style="text-align:center;margin-bottom:40px;">
                <div style="display:inline-flex;align-items:center;justify-content:center;
                     width:56px;height:56px;border-radius:18px;
                     background:linear-gradient(135deg,#E8547A,#3BBFB8);
                     margin-bottom:16px;box-shadow:0 8px 28px rgba(232,84,122,0.28);">
                    <span style="color:white;font-size:1.5rem;">✦</span>
                </div>
                <div style="font-family:'Cormorant Garamond',serif;font-size:3rem;font-weight:300;
                     color:#2D2D3A;letter-spacing:1px;line-height:1;">FitCoach</div>
                <div style="font-size:0.62rem;color:#9090A0;letter-spacing:5px;
                     text-transform:uppercase;margin-top:8px;">AI Fitness Coach</div>
            </div>
        """, unsafe_allow_html=True)

        st.markdown("""
        <div style="background:white;border-radius:24px;padding:36px;
             box-shadow:0 20px 60px rgba(232,84,122,0.1),0 4px 16px rgba(0,0,0,0.04);
             border:1px solid rgba(232,84,122,0.08);position:relative;z-index:1;">
            <div style="font-family:'Cormorant Garamond',serif;font-size:1.8rem;
                 font-weight:400;color:#2D2D3A;margin-bottom:6px;">Welcome back ✦</div>
            <div style="font-size:0.83rem;color:#9090A0;margin-bottom:24px;line-height:1.6;">
                Sign in to continue your fitness journey.</div>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            name = st.text_input("n", placeholder="Enter your name to continue", label_visibility="collapsed")
            sub = st.form_submit_button("Get started →", use_container_width=True)
            if sub and name.strip():
                st.session_state.logged_in = True
                st.session_state.username = name.strip()
                st.rerun()
            elif sub:
                st.error("Please enter your name.")

        st.markdown("""
        <div style="position:relative;z-index:1;">
            <div style="margin-top:20px;padding:20px 24px;background:rgba(59,191,184,0.04);
                 border-radius:14px;border:1px solid rgba(59,191,184,0.12);">
                <div style="display:flex;align-items:center;gap:10px;font-size:0.78rem;
                     color:#9090A0;margin-bottom:8px;">
                    <span style="width:5px;height:5px;border-radius:50%;background:#3BBFB8;
                          flex-shrink:0;display:inline-block;"></span>
                    Personalised AI workout plans</div>
                <div style="display:flex;align-items:center;gap:10px;font-size:0.78rem;
                     color:#9090A0;margin-bottom:8px;">
                    <span style="width:5px;height:5px;border-radius:50%;background:#3BBFB8;
                          flex-shrink:0;display:inline-block;"></span>
                    Smart nutrition tracking with USDA data</div>
                <div style="display:flex;align-items:center;gap:10px;font-size:0.78rem;
                     color:#9090A0;">
                    <span style="width:5px;height:5px;border-radius:50%;background:#3BBFB8;
                          flex-shrink:0;display:inline-block;"></span>
                    Weekly behavioral insights</div>
            </div>
            <div style="text-align:center;font-size:0.66rem;color:#9090A0;margin-top:16px;opacity:0.7;">
                No account needed · Free forever</div>
        </div>
        </div>
        """, unsafe_allow_html=True)

    st.stop()

# ══════════════════════════════════
#  SIDEBAR
# ══════════════════════════════════
with st.sidebar:
    st.markdown(f"""
    <div style="padding:24px 16px 20px;">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
            <div style="width:30px;height:30px;border-radius:9px;
                 background:linear-gradient(135deg,#E8547A,#3BBFB8);
                 display:flex;align-items:center;justify-content:center;
                 color:white;font-size:12px;flex-shrink:0;">✦</div>
            <div style="font-family:'Cormorant Garamond',serif;font-size:1.3rem;
                 color:#2D2D3A;letter-spacing:0.5px;">FitCoach</div>
        </div>
        <div style="font-size:0.58rem;color:#9090A0;letter-spacing:3.5px;
             text-transform:uppercase;padding-bottom:18px;margin-bottom:18px;
             border-bottom:1px solid rgba(232,84,122,0.1);">AI Fitness Coach</div>

        <div style="display:flex;align-items:center;gap:9px;padding:9px 12px;
             border-radius:10px;font-size:0.81rem;margin-bottom:2px;
             background:rgba(232,84,122,0.08);color:#E8547A;
             border:1px solid rgba(232,84,122,0.12);">💬 &nbsp;Coach Chat</div>
        <div style="display:flex;align-items:center;gap:9px;padding:9px 12px;
             border-radius:10px;font-size:0.81rem;color:#9090A0;margin-bottom:2px;">
             📊 &nbsp;Progress</div>
        <div style="display:flex;align-items:center;gap:9px;padding:9px 12px;
             border-radius:10px;font-size:0.81rem;color:#9090A0;margin-bottom:2px;">
             🥗 &nbsp;Nutrition</div>
        <div style="display:flex;align-items:center;gap:9px;padding:9px 12px;
             border-radius:10px;font-size:0.81rem;color:#9090A0;margin-bottom:2px;">
             🏋️ &nbsp;Workouts</div>
        <div style="height:1px;background:rgba(232,84,122,0.1);margin:12px 0;"></div>
        <div style="display:flex;align-items:center;gap:9px;padding:9px 12px;
             border-radius:10px;font-size:0.81rem;color:#9090A0;">
             ⚙️ &nbsp;Settings</div>
    </div>

    <div style="position:absolute;bottom:24px;left:16px;right:16px;">
        <div style="background:rgba(232,84,122,0.05);border-radius:12px;
             padding:12px 14px;border:1px solid rgba(232,84,122,0.1);">
            <div style="font-size:0.83rem;font-weight:600;color:#2D2D3A;">{st.session_state.username}</div>
            <div style="font-size:0.66rem;color:#9090A0;margin-top:3px;
                 display:flex;align-items:center;gap:5px;">
                <span style="width:6px;height:6px;border-radius:50%;background:#22C55E;
                      display:inline-block;"></span>Active now</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ══════════════════════════════════
#  MAIN
# ══════════════════════════════════
workouts, meals = get_data()
e = effort(workouts)
h = nscore(meals)
s = streak(workouts)
mc = len(meals)

chat_col, dash_col = st.columns([3, 1.6])

# ── CHAT ──
with chat_col:
    st.markdown("""
    <div style="background:white;border-bottom:1px solid rgba(232,84,122,0.1);
         padding:16px 28px;display:flex;align-items:center;justify-content:space-between;">
        <div>
            <div style="font-family:'Cormorant Garamond',serif;font-size:1.15rem;color:#2D2D3A;">
                ✦ Your AI <span style="color:#E8547A;">Coach</span></div>
            <div style="font-size:0.67rem;color:#9090A0;">Always here · Always listening</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;background:rgba(34,197,94,0.08);
             border:1px solid rgba(34,197,94,0.2);border-radius:100px;padding:4px 12px;
             font-size:0.65rem;color:#16A34A;">
            <span style="width:5px;height:5px;border-radius:50%;background:#22C55E;
                  display:inline-block;"></span>Online</div>
    </div>
    """, unsafe_allow_html=True)

    if not st.session_state.messages:
        st.markdown(f"""
        <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;
             min-height:340px;text-align:center;padding:40px;
             background:linear-gradient(135deg,rgba(232,84,122,0.02),rgba(59,191,184,0.02));">
            <div style="width:60px;height:60px;border-radius:50%;
                 background:linear-gradient(135deg,rgba(232,84,122,0.1),rgba(59,191,184,0.1));
                 border:1px solid rgba(232,84,122,0.2);display:flex;align-items:center;
                 justify-content:center;font-size:1.3rem;margin-bottom:18px;">✦</div>
            <div style="font-family:'Cormorant Garamond',serif;font-size:1.5rem;
                 color:#2D2D3A;margin-bottom:8px;">
                Hello, <span style="color:#E8547A;">{st.session_state.username}</span></div>
            <div style="font-size:0.83rem;color:#9090A0;line-height:1.75;max-width:260px;
                 margin-bottom:20px;">
                Tell me your goal and I'll build a personalised plan just for you.</div>
            <div style="display:flex;flex-wrap:wrap;gap:8px;justify-content:center;">
                <div style="background:white;border:1px solid rgba(232,84,122,0.15);
                     border-radius:100px;padding:7px 16px;font-size:0.74rem;color:#9090A0;
                     box-shadow:0 2px 8px rgba(0,0,0,0.04);">I want to lose weight</div>
                <div style="background:white;border:1px solid rgba(232,84,122,0.15);
                     border-radius:100px;padding:7px 16px;font-size:0.74rem;color:#9090A0;
                     box-shadow:0 2px 8px rgba(0,0,0,0.04);">Help me build muscle</div>
                <div style="background:white;border:1px solid rgba(232,84,122,0.15);
                     border-radius:100px;padding:7px 16px;font-size:0.74rem;color:#9090A0;
                     box-shadow:0 2px 8px rgba(0,0,0,0.04);">I want to get fit</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        html = '<div style="padding:22px 28px;">'
        for msg in st.session_state.messages:
            txt = msg["content"].replace("<","&lt;").replace(">","&gt;")
            if msg["role"] == "user":
                html += f"""
                <div style="display:flex;justify-content:flex-end;margin-bottom:14px;">
                    <div>
                        <div style="background:linear-gradient(135deg,#E8547A,#C0365A);
                             color:white;padding:10px 16px;border-radius:18px 18px 4px 18px;
                             font-size:0.86rem;line-height:1.6;max-width:420px;
                             word-break:break-word;box-shadow:0 4px 14px rgba(232,84,122,0.22);">
                             {txt}</div>
                        <div style="font-size:0.6rem;color:#9090A0;margin-top:3px;text-align:right;">{now}</div>
                    </div>
                </div>"""
            else:
                txt2 = txt.replace("\n","<br>")
                html += f"""
                <div style="display:flex;align-items:flex-end;gap:9px;margin-bottom:14px;">
                    <div style="width:28px;height:28px;border-radius:50%;
                         background:linear-gradient(135deg,rgba(232,84,122,0.1),rgba(59,191,184,0.1));
                         border:1px solid rgba(232,84,122,0.2);display:flex;align-items:center;
                         justify-content:center;font-size:11px;color:#E8547A;flex-shrink:0;">✦</div>
                    <div>
                        <div style="background:white;color:#2D2D3A;padding:12px 16px;
                             border-radius:18px 18px 18px 4px;font-size:0.86rem;line-height:1.75;
                             max-width:480px;border:1px solid rgba(232,84,122,0.1);
                             word-break:break-word;box-shadow:0 2px 10px rgba(0,0,0,0.04);">
                             {txt2}</div>
                        <div style="font-size:0.6rem;color:#9090A0;margin-top:3px;">Coach · {now}</div>
                    </div>
                </div>"""
        html += "</div>"
        st.markdown(html, unsafe_allow_html=True)

    if prompt := st.chat_input("Message your coach..."):
        st.session_state.messages.append({"role":"user","content":prompt})
        with st.spinner(""):
            reply = ask(prompt)
        st.session_state.messages.append({"role":"assistant","content":reply})
        st.rerun()

# ── DASHBOARD ──
with dash_col:
    st.markdown("""
    <div style="background:white;border-left:1px solid rgba(232,84,122,0.1);
         min-height:100vh;padding:20px 16px;">
        <div style="font-family:'Cormorant Garamond',serif;font-size:1.2rem;color:#2D2D3A;">
            This <span style="color:#3BBFB8;">Week</span></div>
        <div style="font-size:0.58rem;color:#9090A0;letter-spacing:2px;text-transform:uppercase;
             margin-top:3px;padding-bottom:14px;border-bottom:1px solid rgba(232,84,122,0.08);
             margin-bottom:16px;">Your progress snapshot</div>
    </div>
    """, unsafe_allow_html=True)

    c1, c2 = st.columns(2)
    with c1: st.metric("💪 Effort", f"{e}/100")
    with c2: st.metric("🥗 Nutrition", f"{h}/100")
    c3, c4 = st.columns(2)
    with c3: st.metric("🔥 Streak", f"{s}d")
    with c4: st.metric("🍽️ Meals", mc)

    if not workouts.empty:
        st.markdown('<p style="font-size:0.58rem;letter-spacing:2px;text-transform:uppercase;color:#9090A0;margin:14px 0 6px;">Workout History</p>', unsafe_allow_html=True)
        workouts["day"] = pd.to_datetime(workouts["date"]).dt.strftime("%a")
        fig = go.Figure(go.Bar(
            x=workouts["day"], y=[1]*len(workouts),
            marker_color=workouts["completed"].map({1:"#E8547A",0:"rgba(232,84,122,0.1)"}).tolist(),
            marker_line_width=0
        ))
        fig.update_layout(height=100, margin=dict(l=0,r=0,t=0,b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#9090A0", tickfont=dict(size=9, family="DM Sans")),
            yaxis=dict(showgrid=False, visible=False), showlegend=False)
        st.plotly_chart(fig, use_container_width=True, config={"displayModeBar":False})

    if not meals.empty and len(meals) > 1:
        st.markdown('<p style="font-size:0.58rem;letter-spacing:2px;text-transform:uppercase;color:#9090A0;margin:14px 0 6px;">Calorie Trend</p>', unsafe_allow_html=True)
        meals["avg"] = (meals["calories_min"] + meals["calories_max"]) / 2
        meals["day"] = pd.to_datetime(meals["date"]).dt.strftime("%a")
        fig2 = go.Figure()
        fig2.add_trace(go.Scatter(
            x=meals["day"], y=meals["avg"], mode="lines+markers",
            line=dict(color="#3BBFB8", width=2),
            marker=dict(color="white", size=5, line=dict(color="#3BBFB8", width=2)),
            fill="tozeroy", fillcolor="rgba(59,191,184,0.07)"
        ))
        fig2.update_layout(height=90, margin=dict(l=0,r=0,t=0,b=0),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            xaxis=dict(showgrid=False, color="#9090A0", tickfont=dict(size=9)),
            yaxis=dict(showgrid=False, visible=False))
        st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar":False})

    if not meals.empty:
        st.markdown('<p style="font-size:0.58rem;letter-spacing:2px;text-transform:uppercase;color:#9090A0;margin:14px 0 6px;">Recent Meals</p>', unsafe_allow_html=True)
        for _, row in meals.tail(4).iterrows():
            st.markdown(f"""
            <div style="background:rgba(232,84,122,0.03);border-radius:8px;padding:8px 10px;
                 margin-bottom:5px;border:1px solid rgba(232,84,122,0.08);
                 display:flex;justify-content:space-between;align-items:center;">
                <span style="font-size:0.76rem;color:#2D2D3A;overflow:hidden;
                      text-overflow:ellipsis;white-space:nowrap;max-width:65%;">{str(row["food"])[:20]}</span>
                <span style="font-size:0.7rem;color:#E8547A;font-weight:600;flex-shrink:0;
                      margin-left:8px;">{row["calories_min"]}-{row["calories_max"]}</span>
            </div>""", unsafe_allow_html=True)
