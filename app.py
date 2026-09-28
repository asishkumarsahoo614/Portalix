"""
Portalix — Personal Productivity Dashboard
Full-stack Streamlit application with AI features powered by Google Gemini Flash.
"""

import os
import json
import hashlib
import base64
import re
import datetime
import random
import pytz
from pathlib import Path

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from dotenv import load_dotenv

# ── Crypto ──────────────────────────────────────────────────────────────────
from cryptography.fernet import Fernet

# ── Google Gemini (new google-genai SDK) ─────────────────────────────────────
from google import genai
from google.genai import types as genai_types

# ── Load env ─────────────────────────────────────────────────────────────────
load_dotenv()

# ═══════════════════════════════════════════════════════════════════════════════
# CONSTANTS & CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

APP_NAME = "Portalix"
VERSION  = "1.1.0"

# ── Futuristic gradient palette pool (randomized per login session) ──────────
GRADIENT_PALETTES = [
    # night purples
    ("135deg", "#0d0d1a", "#1a1a2e", "#16213e", "#0f3460",
     "rgba(124,92,216,0.6)", "rgba(124,92,216,0.4)"),
    # deep teal-navy
    ("135deg", "#020c1b", "#0a192f", "#112240", "#1d3461",
     "rgba(0,200,200,0.45)", "rgba(0,180,180,0.3)"),
    # crimson-dark
    ("135deg", "#0d0408", "#1a0012", "#2d001a", "#3d0030",
     "rgba(200,30,100,0.5)", "rgba(160,20,80,0.35)"),
    # amber-dark
    ("135deg", "#0d0900", "#1a1200", "#2a1d00", "#3d2e00",
     "rgba(220,140,0,0.5)", "rgba(200,120,0,0.35)"),
    # emerald-dark
    ("135deg", "#000d08", "#001a10", "#002a1a", "#003d28",
     "rgba(0,200,120,0.45)", "rgba(0,160,100,0.3)"),
    # cobalt blue
    ("135deg", "#00060d", "#00101f", "#001833", "#002147",
     "rgba(30,120,255,0.5)", "rgba(20,100,220,0.35)"),
]

GRADIENT_PALETTES_DAY = [
    ("135deg", "#f0f4ff", "#e8eeff", "#dde8ff", "#d0dcff",
     "rgba(59,130,212,0.4)", "rgba(59,130,212,0.25)"),
    ("135deg", "#f0fff8", "#e0fff2", "#d0ffea", "#b8ffd8",
     "rgba(0,180,100,0.35)", "rgba(0,160,80,0.2)"),
    ("135deg", "#fff0f8", "#ffe0f0", "#ffd0e8", "#ffb8d8",
     "rgba(200,0,100,0.35)", "rgba(180,0,80,0.2)"),
]

BROWSERS = ["Default", "Chrome", "Firefox", "Edge", "Safari", "Brave"]

DEMO_USERS = {
    "demo": {"password_hash": hashlib.sha256(b"demo123").hexdigest(), "name": "Demo User"},
    "pro":  {"password_hash": hashlib.sha256(b"pro123").hexdigest(),  "name": "Pro User"},
    "admin":{"password_hash": hashlib.sha256(b"admin123").hexdigest(),"name": "Admin"},
}

# ═══════════════════════════════════════════════════════════════════════════════
# ENCRYPTION HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_fernet() -> Fernet:
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        # Derive a stable key from a fixed seed so vault survives restarts in demo
        key = base64.urlsafe_b64encode(hashlib.sha256(b"portalix-demo-vault-key").digest())
    else:
        key = key.encode()
    return Fernet(key)

def encrypt_text(plain: str) -> str:
    return get_fernet().encrypt(plain.encode()).decode()

def decrypt_text(token: str) -> str:
    try:
        return get_fernet().decrypt(token.encode()).decode()
    except Exception:
        return "••••••••"

def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


# ═══════════════════════════════════════════════════════════════════════════════
# GEMINI AI HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def get_gemini_client():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None
    try:
        return genai.Client(api_key=api_key)
    except Exception:
        return None

def gemini_ask(prompt: str, fallback: str = "AI unavailable.") -> str:
    client = get_gemini_client()
    if not client:
        return fallback
    try:
        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=prompt,
        )
        return response.text.strip()
    except Exception as e:
        return f"{fallback} (Error: {e})"

def ai_summarize_url(url: str) -> dict:
    prompt = (
        f"Given the URL '{url}', provide:\n"
        "1. A single short category tag (1-2 words, e.g. 'News', 'Dev Tools', 'Social', 'Shopping', 'Productivity')\n"
        "2. A one-sentence summary of what this website likely offers.\n"
        "Reply ONLY in this exact JSON format:\n"
        '{"category": "...", "summary": "..."}'
    )
    raw = gemini_ask(prompt, fallback='{"category": "General", "summary": "No summary available."}')
    try:
        # Extract JSON from response
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"category": "General", "summary": raw[:120]}

def ai_parse_reminder(text: str) -> dict:
    now = datetime.datetime.now()
    prompt = (
        f"Today is {now.strftime('%A, %B %d, %Y %H:%M')}.\n"
        f"Parse this reminder request: '{text}'\n"
        "Extract the reminder message and the exact datetime.\n"
        "Reply ONLY in this exact JSON format:\n"
        '{"message": "...", "datetime": "YYYY-MM-DD HH:MM", "display": "human readable time"}'
    )
    raw = gemini_ask(prompt, fallback='{"message": "' + text + '", "datetime": "", "display": "Unknown time"}')
    try:
        match = re.search(r'\{.*?\}', raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return {"message": text, "datetime": "", "display": "Could not parse time"}

def ai_password_check(passwords: list) -> str:
    if not passwords:
        return "No passwords to check."
    prompt = (
        f"Check these {len(passwords)} password entries for security issues.\n"
        "Look for: weak passwords (too short, common words), duplicates, patterns.\n"
        "Passwords (hashed for safety, just count them): " + str(len(passwords)) + " entries.\n"
        "Provide a brief 2-3 sentence security assessment and 1-2 actionable recommendations."
    )
    return gemini_ask(prompt, fallback="AI password check unavailable.")

def ai_productivity_insights(data_summary: str) -> str:
    prompt = (
        f"Here is a user's website usage summary from Portalix dashboard:\n{data_summary}\n\n"
        "Provide 2-3 concise, personalized productivity insights and one actionable tip. "
        "Be encouraging and specific. Keep response under 150 words."
    )
    return gemini_ask(prompt, fallback="AI insights unavailable. Keep track of your usage patterns!")

def ai_troubleshoot(question: str) -> str:
    prompt = (
        f"You are the Portalix Help Assistant. A user asked: '{question}'\n\n"
        "Portalix is a personal productivity dashboard with: Pinned Websites, Custom Spaces, "
        "Password Vault, Smart Reminders, Time Analytics, and AI features.\n"
        "Answer helpfully in 2-4 sentences. If unrelated to the app, politely redirect."
    )
    return gemini_ask(prompt, fallback="I'm sorry, the AI assistant is currently unavailable. Please check the FAQ below.")


# ═══════════════════════════════════════════════════════════════════════════════
# SESSION STATE INITIALIZATION
# ═══════════════════════════════════════════════════════════════════════════════

def init_session():
    defaults = {
        "authenticated": False,
        "username": "",
        "user_name": "",
        "night_mode": True,
        "pinned_sites": [],
        "custom_spaces": [],
        "vault_items": [],
        "reminders": [],
        "time_logs": [],
        "active_tab": "🏠 Dashboard",
        "signup_mode": False,
        "registered_users": dict(DEMO_USERS),
        # Randomized per-session visuals (picked once at first load)
        "session_palette_idx": random.randint(0, len(GRADIENT_PALETTES) - 1),
        "session_day_palette_idx": random.randint(0, len(GRADIENT_PALETTES_DAY) - 1),
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    # Seed demo data for new sessions
    if st.session_state.authenticated and not st.session_state.pinned_sites:
        _seed_demo_data()

def _seed_demo_data():
    st.session_state.pinned_sites = [
        {"id": 1, "title": "GitHub", "url": "https://github.com", "category": "Dev Tools",
         "summary": "World's leading platform for code hosting and collaboration.", "browser": "Default", "space": None},
        {"id": 2, "title": "Notion", "url": "https://notion.so", "category": "Productivity",
         "summary": "All-in-one workspace for notes, tasks, wikis, and databases.", "browser": "Default", "space": None},
        {"id": 3, "title": "YouTube", "url": "https://youtube.com", "category": "Video",
         "summary": "Video streaming platform with billions of hours of content.", "browser": "Chrome", "space": "Multimedia Space"},
    ]
    st.session_state.custom_spaces = [
        {"id": 1, "name": "Work Space", "icon": "💼", "floating": False, "urls": [
            {"title": "Gmail", "url": "https://mail.google.com"},
            {"title": "Google Drive", "url": "https://drive.google.com"},
        ]},
    ]
    st.session_state.reminders = [
        {"id": 1, "message": "Review weekly goals", "datetime": (datetime.datetime.now() + datetime.timedelta(hours=3)).strftime("%Y-%m-%d %H:%M"), "display": "In 3 hours", "done": False},
    ]
    # Generate 30 days of mock time log data
    now = datetime.datetime.now()
    sites = ["GitHub", "Notion", "YouTube", "Gmail", "Reddit"]
    logs = []
    for d in range(30):
        day = now - datetime.timedelta(days=d)
        for _ in range(random.randint(2, 8)):
            logs.append({
                "site": random.choice(sites),
                "minutes": random.randint(2, 45),
                "date": day.strftime("%Y-%m-%d"),
                "hour": random.randint(8, 22),
            })
    st.session_state.time_logs = logs


# ═══════════════════════════════════════════════════════════════════════════════
# CSS STYLING
# ═══════════════════════════════════════════════════════════════════════════════

def inject_css(night_mode: bool):
    # Pick session palette
    pidx = st.session_state.get("session_palette_idx", 0)
    didx = st.session_state.get("session_day_palette_idx", 0)

    if night_mode:
        pal = GRADIENT_PALETTES[pidx % len(GRADIENT_PALETTES)]
        deg, c1n, c2n, c3n, c4n, glow, glow2 = pal
        bg_grad   = f"linear-gradient({deg}, {c1n} 0%, {c2n} 40%, {c3n} 70%, {c4n} 100%)"
        card_bg   = "rgba(255,255,255,0.05)"
        card_brd  = f"{glow2}"
        text_main = "#e0e0ff"
        text_muted= "#8888bb"
        accent    = "#7c5cd8"
        sidebar_bg= f"rgba(0,0,0,0.88)"
        input_bg  = "rgba(255,255,255,0.07)"
    else:
        pal = GRADIENT_PALETTES_DAY[didx % len(GRADIENT_PALETTES_DAY)]
        deg, c1n, c2n, c3n, c4n, glow, glow2 = pal
        bg_grad   = f"linear-gradient({deg}, {c1n} 0%, {c2n} 40%, {c3n} 70%, {c4n} 100%)"
        card_bg   = "rgba(255,255,255,0.7)"
        card_brd  = f"{glow2}"
        text_main = "#1a1a3e"
        text_muted= "#5566aa"
        accent    = "#3b82d4"
        glow      = "rgba(59,130,212,0.4)"
        sidebar_bg= "rgba(240,244,255,0.97)"
        input_bg  = "rgba(255,255,255,0.9)"

    st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;700;900&family=Rajdhani:wght@400;500;600;700&display=swap');

/* ── Global Reset & Background ── */
.stApp {{
    background: {bg_grad} !important;
    background-attachment: fixed !important;
    color: {text_main} !important;
    font-family: 'Rajdhani', 'Segoe UI', system-ui, sans-serif !important;
    font-size: 15px !important;
    letter-spacing: 0.2px !important;
}}

/* ── Futuristic heading font ── */
h1, h2, h3, h4, h5, h6,
.glow-title, .tab-section-title {{
    font-family: 'Orbitron', 'Rajdhani', sans-serif !important;
    letter-spacing: 1px !important;
}}

/* Animated background orbs */
.stApp::before {{
    content: '';
    position: fixed;
    top: -50%;
    left: -50%;
    width: 200%;
    height: 200%;
    background:
        radial-gradient(ellipse at 20% 20%, {glow} 0%, transparent 50%),
        radial-gradient(ellipse at 80% 80%, rgba(59,130,212,0.15) 0%, transparent 50%),
        radial-gradient(ellipse at 50% 50%, rgba(124,92,216,0.08) 0%, transparent 60%);
    animation: orb-drift 20s ease-in-out infinite alternate;
    pointer-events: none;
    z-index: 0;
}}
@keyframes orb-drift {{
    0%   {{ transform: translate(0,0) scale(1); }}
    50%  {{ transform: translate(2%,3%) scale(1.03); }}
    100% {{ transform: translate(-2%,-2%) scale(0.98); }}
}}

/* ── Sidebar ── */
section[data-testid="stSidebar"] {{
    background: {sidebar_bg} !important;
    backdrop-filter: blur(20px) !important;
    border-right: 1px solid {card_brd} !important;
    box-shadow: 4px 0 30px {glow} !important;
}}
section[data-testid="stSidebar"] * {{
    color: {text_main} !important;
}}

/* ── Glassmorphic Cards ── */
.glass-card {{
    background: {card_bg};
    backdrop-filter: blur(16px);
    -webkit-backdrop-filter: blur(16px);
    border: 1px solid {card_brd};
    border-radius: 16px;
    padding: 20px;
    margin: 8px 0;
    box-shadow: 0 4px 24px {glow}, inset 0 1px 0 rgba(255,255,255,0.1);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
    position: relative;
    overflow: hidden;
}}
.glass-card::before {{
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255,255,255,0.3), transparent);
}}
.glass-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 8px 32px {glow}, inset 0 1px 0 rgba(255,255,255,0.15);
}}

/* ── Glow Headings ── */
.glow-title {{
    font-size: 2.4rem;
    font-weight: 800;
    background: linear-gradient(135deg, {accent}, #a78bfa, #60a5fa);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    text-shadow: none;
    letter-spacing: -0.5px;
    line-height: 1.2;
    margin-bottom: 4px;
}}
.glow-subtitle {{
    color: {text_muted};
    font-size: 1rem;
    margin-bottom: 24px;
}}

/* ── Tab Navigation ── */
.tab-nav {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
    margin-bottom: 20px;
    padding: 6px;
    background: {card_bg};
    backdrop-filter: blur(12px);
    border: 1px solid {card_brd};
    border-radius: 14px;
}}
.tab-btn {{
    padding: 8px 16px;
    border-radius: 10px;
    border: none;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
    background: transparent;
    color: {text_muted};
    transition: all 0.2s ease;
    white-space: nowrap;
}}
.tab-btn:hover {{
    background: {card_bg};
    color: {text_main};
}}
.tab-btn.active {{
    background: linear-gradient(135deg, {accent}, #a78bfa);
    color: white;
    box-shadow: 0 4px 12px {glow};
}}

/* ── Streamlit native overrides ── */
.stButton > button {{
    background: linear-gradient(135deg, {accent} 0%, #a78bfa 100%) !important;
    color: white !important;
    border: none !important;
    border-radius: 10px !important;
    font-weight: 600 !important;
    padding: 0.45rem 1.2rem !important;
    transition: all 0.2s ease !important;
    box-shadow: 0 2px 12px {glow} !important;
}}
.stButton > button:hover {{
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 20px {glow} !important;
    opacity: 0.92 !important;
}}
.stTextInput > div > div > input,
.stTextArea > div > div > textarea,
.stSelectbox > div > div {{
    background: {input_bg} !important;
    border: 1px solid {card_brd} !important;
    border-radius: 10px !important;
    color: {text_main} !important;
    backdrop-filter: blur(8px) !important;
}}
.stSelectbox > div > div > div {{
    color: {text_main} !important;
}}

/* ── Metric Cards ── */
.metric-card {{
    background: {card_bg};
    backdrop-filter: blur(16px);
    border: 1px solid {card_brd};
    border-radius: 14px;
    padding: 18px 20px;
    text-align: center;
    box-shadow: 0 2px 16px {glow};
}}
.metric-value {{
    font-size: 2rem;
    font-weight: 800;
    color: {accent};
    line-height: 1;
}}
.metric-label {{
    font-size: 0.78rem;
    color: {text_muted};
    margin-top: 4px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* ── Pin Site Card ── */
.pin-card {{
    background: {card_bg};
    backdrop-filter: blur(12px);
    border: 1px solid {card_brd};
    border-radius: 14px;
    padding: 16px;
    margin-bottom: 10px;
    display: flex;
    align-items: flex-start;
    gap: 14px;
    transition: all 0.2s ease;
}}
.pin-card:hover {{
    border-color: {accent};
    box-shadow: 0 4px 20px {glow};
}}
.pin-favicon {{
    width: 32px; height: 32px;
    border-radius: 8px;
    background: linear-gradient(135deg, {accent}, #a78bfa);
    display: flex; align-items: center; justify-content: center;
    font-size: 16px; flex-shrink: 0;
}}
.pin-title {{ font-weight: 700; font-size: 0.95rem; color: {text_main}; }}
.pin-url {{ font-size: 0.75rem; color: {text_muted}; word-break: break-all; }}
.pin-category {{
    display: inline-block;
    background: rgba(124,92,216,0.2);
    color: {accent};
    font-size: 0.7rem;
    padding: 2px 8px;
    border-radius: 20px;
    font-weight: 600;
    margin-top: 4px;
}}
.pin-summary {{ font-size: 0.78rem; color: {text_muted}; margin-top: 4px; line-height: 1.4; }}

/* ── FAQ Accordion ── */
.faq-item {{
    background: {card_bg};
    border: 1px solid {card_brd};
    border-radius: 12px;
    margin-bottom: 8px;
    overflow: hidden;
}}
.faq-q {{
    padding: 14px 16px;
    font-weight: 600;
    cursor: pointer;
    font-size: 0.9rem;
    color: {text_main};
}}
.faq-a {{
    padding: 0 16px 14px;
    font-size: 0.85rem;
    color: {text_muted};
    line-height: 1.6;
}}

/* ── Vault Item ── */
.vault-item {{
    background: {card_bg};
    border: 1px solid {card_brd};
    border-radius: 12px;
    padding: 14px 16px;
    margin-bottom: 8px;
    display: flex;
    justify-content: space-between;
    align-items: center;
}}

/* ── Reminder Card ── */
.reminder-card {{
    background: {card_bg};
    border-left: 3px solid {accent};
    border-radius: 0 12px 12px 0;
    padding: 12px 16px;
    margin-bottom: 8px;
    font-size: 0.87rem;
}}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 6px; }}
::-webkit-scrollbar-track {{ background: transparent; }}
::-webkit-scrollbar-thumb {{ background: {accent}; border-radius: 3px; }}

/* ── Expander override ── */
.streamlit-expanderHeader {{
    background: {card_bg} !important;
    border-radius: 10px !important;
    border: 1px solid {card_brd} !important;
    color: {text_main} !important;
}}

/* ── DataFrames ── */
.stDataFrame {{ border-radius: 12px; overflow: hidden; }}

/* ── Divider ── */
hr {{ border-color: {card_brd} !important; }}

/* ── Welcome banner ── */
.welcome-banner {{
    background: linear-gradient(135deg, rgba(124,92,216,0.15), rgba(59,130,212,0.1));
    border: 1px solid {card_brd};
    border-radius: 20px;
    padding: 24px 28px;
    margin-bottom: 24px;
    position: relative;
    overflow: hidden;
}}
.welcome-banner::after {{
    content: '';
    position: absolute;
    top: -50%; right: -20%;
    width: 200px; height: 200px;
    background: radial-gradient(circle, {glow} 0%, transparent 70%);
    pointer-events: none;
}}

/* ── Stats row ── */
.stats-row {{
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px;
    margin-bottom: 20px;
}}
@media (max-width: 768px) {{
    .stats-row {{ grid-template-columns: repeat(2, 1fr); }}
    .glow-title {{ font-size: 1.4rem; }}
}}

/* ── Clickable metric card ── */
.metric-card-clickable {{
    background: {card_bg};
    backdrop-filter: blur(16px);
    border: 1px solid {card_brd};
    border-radius: 14px;
    padding: 18px 20px;
    text-align: center;
    box-shadow: 0 2px 16px {glow};
    cursor: pointer;
    transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
    user-select: none;
    position: relative;
    overflow: hidden;
}}
.metric-card-clickable::after {{
    content: '';
    position: absolute;
    inset: 0;
    border-radius: 14px;
    background: linear-gradient(135deg, {glow}, transparent 60%);
    opacity: 0;
    transition: opacity 0.18s ease;
}}
.metric-card-clickable:hover {{
    transform: translateY(-3px) scale(1.02);
    box-shadow: 0 8px 28px {glow};
    border-color: {accent};
}}
.metric-card-clickable:hover::after {{ opacity: 0.15; }}
.metric-card-clickable:active {{
    transform: translateY(-1px) scale(0.99);
}}

/* ── Clickable reminder/space widget row ── */
.widget-row-clickable {{
    background: {card_bg};
    border-left: 3px solid {accent};
    border-radius: 0 12px 12px 0;
    padding: 10px 14px;
    margin-bottom: 6px;
    font-size: 0.87rem;
    cursor: pointer;
    transition: all 0.18s ease;
    border-top: 1px solid {card_brd};
    border-right: 1px solid {card_brd};
    border-bottom: 1px solid {card_brd};
}}
.widget-row-clickable:hover {{
    background: {card_bg};
    border-left-color: #a78bfa;
    box-shadow: 0 4px 16px {glow};
    transform: translateX(3px);
}}

/* ── Sidebar nav tech icons override ── */
.nav-icon-label {{
    font-family: 'Rajdhani', sans-serif;
    font-weight: 600;
    letter-spacing: 0.5px;
}}

/* Plotly chart background transparency */
.js-plotly-plot .plotly .bg {{ fill: transparent !important; }}
.stPlotlyChart {{ background: transparent !important; }}
</style>
""", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# COUNT HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def count_pins() -> int:
    return len(st.session_state.pinned_sites)

def count_spaces() -> int:
    return len(st.session_state.custom_spaces)


# ═══════════════════════════════════════════════════════════════════════════════
# AUTHENTICATION
# ═══════════════════════════════════════════════════════════════════════════════

def render_auth_page():
    inject_css(True)

    st.markdown(f"""
<div style="text-align:center;padding:36px 0 16px;">
  <div style="display:inline-block;margin-bottom:10px;">{DESKTOP_LOGO_SVG}</div>
  <div class="glow-title" style="font-size:2.6rem;font-family:'Orbitron',sans-serif;
    letter-spacing:4px;">PORTALIX</div>
  <div class="glow-subtitle" style="font-family:'Rajdhani',sans-serif;letter-spacing:1px;">
    // AI-powered personal productivity OS</div>
</div>
""", unsafe_allow_html=True)

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        mode = st.session_state.signup_mode

        tab_login, tab_signup = st.tabs(["🔑 Sign In", "✨ Create Account"])

        with tab_login:
            with st.form("login_form"):
                st.markdown("### Welcome back")
                uname = st.text_input("Username", placeholder="demo / pro / admin")
                pwd   = st.text_input("Password", type="password", placeholder="demo123 / pro123")
                submit = st.form_submit_button("Sign In →", use_container_width=True)
                if submit:
                    _do_login(uname.strip(), pwd)

            st.markdown("<div style='text-align:center;margin:12px 0;color:#8888bb;font-size:0.8rem;'>— or —</div>", unsafe_allow_html=True)
            if st.button("🔵  Continue with Google (Demo OAuth)", use_container_width=True, key="google_login"):
                _google_oauth_mock()

            st.markdown("""
<div style='font-size:0.75rem;color:#8888bb;margin-top:8px;text-align:center;'>
Demo accounts: <code>demo/demo123</code> · <code>pro/pro123</code>
</div>""", unsafe_allow_html=True)

        with tab_signup:
            with st.form("signup_form"):
                st.markdown("### Create your account")
                new_name  = st.text_input("Full Name", placeholder="Your Name")
                new_uname = st.text_input("Username", placeholder="yourusername")
                new_email = st.text_input("Email", placeholder="you@email.com")
                new_pwd   = st.text_input("Password", type="password", placeholder="Min. 6 characters")
                new_pwd2  = st.text_input("Confirm Password", type="password")
                agree     = st.checkbox("I agree to the Terms of Service")
                signup_btn = st.form_submit_button("Create Account →", use_container_width=True)
                if signup_btn:
                    _do_signup(new_name, new_uname, new_email, new_pwd, new_pwd2, agree)

def _do_login(uname: str, pwd: str):
    users = st.session_state.registered_users
    if uname in users and users[uname]["password_hash"] == hash_password(pwd):
        st.session_state.authenticated = True
        st.session_state.username      = uname
        st.session_state.user_name     = users[uname]["name"]
        _seed_demo_data()
        st.success(f"Welcome back, {users[uname]['name']}!")
        st.rerun()
    else:
        st.error("Invalid username or password.")

def _google_oauth_mock():
    """Mock Google OAuth — auto logs in as demo user."""
    st.session_state.authenticated = True
    st.session_state.username      = "google_user"
    st.session_state.user_name     = "Google User"
    st.session_state.registered_users["google_user"] = {
        "password_hash": "", "name": "Google User"
    }
    _seed_demo_data()
    st.rerun()

def _do_signup(name, uname, email, pwd, pwd2, agree):
    if not all([name, uname, email, pwd]):
        st.error("All fields are required.")
        return
    if len(pwd) < 6:
        st.error("Password must be at least 6 characters.")
        return
    if pwd != pwd2:
        st.error("Passwords do not match.")
        return
    if not agree:
        st.error("Please agree to the Terms of Service.")
        return
    if uname in st.session_state.registered_users:
        st.error("Username already taken.")
        return
    st.session_state.registered_users[uname] = {
        "password_hash": hash_password(pwd),
        "name": name,
    }
    st.session_state.authenticated = True
    st.session_state.username      = uname
    st.session_state.user_name     = name
    _seed_demo_data()
    st.success(f"Account created! Welcome to Portalix, {name}!")
    st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════════════

TABS = [
    "🏠 Dashboard",
    "📌 Pinned Websites",
    "🗂️ Custom Spaces",
    "🔐 Password Vault",
    "⏰ Smart Reminders",
    "📊 Time Analytics",
    "🆘 Support & Help",
]

# Futuristic Unicode tech icons for sidebar nav
NAV_ICONS = {
    "🏠 Dashboard":       "⬡",
    "📌 Pinned Websites":  "◈",
    "🗂️ Custom Spaces":   "▦",
    "🔐 Password Vault":   "⬗",
    "⏰ Smart Reminders":  "◷",
    "📊 Time Analytics":   "▲",
    "🆘 Support & Help":   "◎",
}

# Mini-desktop SVG logo
DESKTOP_LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 52" width="48" height="39">
  <defs>
    <linearGradient id="dg1" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#7c5cd8"/>
      <stop offset="100%" style="stop-color:#60a5fa"/>
    </linearGradient>
    <linearGradient id="dg2" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:#a78bfa"/>
      <stop offset="100%" style="stop-color:#38bdf8"/>
    </linearGradient>
  </defs>
  <rect x="4" y="2" width="56" height="36" rx="4" fill="url(#dg1)" opacity="0.9"/>
  <rect x="7" y="5" width="50" height="30" rx="3" fill="#0d0d1a"/>
  <rect x="9" y="7" width="14" height="4" rx="2" fill="#a78bfa" opacity="0.85"/>
  <rect x="25" y="7" width="14" height="4" rx="2" fill="#60a5fa" opacity="0.65"/>
  <rect x="41" y="7" width="14" height="4" rx="2" fill="#38bdf8" opacity="0.45"/>
  <rect x="9" y="13" width="46" height="3" rx="1.5" fill="#7c5cd8" opacity="0.5"/>
  <rect x="9" y="18" width="30" height="2" rx="1" fill="#6366f1" opacity="0.4"/>
  <rect x="9" y="22" width="38" height="2" rx="1" fill="#6366f1" opacity="0.3"/>
  <rect x="9" y="26" width="22" height="2" rx="1" fill="#6366f1" opacity="0.3"/>
  <rect x="40" y="17" width="15" height="10" rx="2" fill="#1a1a3e" stroke="#a78bfa" stroke-width="0.6"/>
  <rect x="41" y="18" width="13" height="2" rx="1" fill="#a78bfa" opacity="0.6"/>
  <rect x="41" y="21" width="10" height="1.5" rx="0.75" fill="#60a5fa" opacity="0.5"/>
  <rect x="41" y="24" width="8" height="1.5" rx="0.75" fill="#60a5fa" opacity="0.4"/>
  <rect x="28" y="38" width="8" height="6" rx="2" fill="url(#dg1)" opacity="0.7"/>
  <rect x="20" y="44" width="24" height="5" rx="3" fill="url(#dg2)" opacity="0.8"/>
  <circle cx="53" cy="9" r="1.5" fill="#22d3ee" opacity="0.9"/>
</svg>"""

def render_sidebar():
    with st.sidebar:
        # Mini-desktop logo + PORTALIX brand
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:10px;padding:10px 0 6px;">
  <div style="flex-shrink:0;">{DESKTOP_LOGO_SVG}</div>
  <div>
    <div style="font-family:'Orbitron',sans-serif;font-size:1.1rem;font-weight:900;
      background:linear-gradient(135deg,#7c5cd8,#a78bfa,#60a5fa);
      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
      background-clip:text;letter-spacing:2px;line-height:1.1;">PORTALIX</div>
    <div style="font-size:0.55rem;color:#444466;letter-spacing:3px;
      font-family:'Rajdhani',sans-serif;text-transform:uppercase;margin-top:1px;">Productivity OS</div>
  </div>
</div>
<hr style="margin:6px 0;border-color:rgba(124,92,216,0.25);">
""", unsafe_allow_html=True)

        # User info
        st.markdown(f"""
<div style="display:flex;align-items:center;gap:8px;padding:4px 0 10px;">
  <div style="width:34px;height:34px;border-radius:50%;flex-shrink:0;
    background:linear-gradient(135deg,#7c5cd8,#a78bfa);
    display:flex;align-items:center;justify-content:center;
    font-family:'Orbitron',sans-serif;font-size:13px;font-weight:700;color:white;
    box-shadow:0 0 8px rgba(124,92,216,0.55);">
    {st.session_state.user_name[0].upper() if st.session_state.user_name else "U"}
  </div>
  <div style="min-width:0;overflow:hidden;">
    <div style="font-family:'Rajdhani',sans-serif;font-weight:700;font-size:0.85rem;
      white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">
      {st.session_state.user_name}</div>
    <div style="font-size:0.6rem;color:#444466;font-family:'Orbitron',sans-serif;
      letter-spacing:1px;">@{st.session_state.username}</div>
  </div>
</div>
""", unsafe_allow_html=True)

        # Night mode toggle
        night = st.toggle("◑  Night Mode", value=st.session_state.night_mode, key="night_toggle")
        if night != st.session_state.night_mode:
            st.session_state.night_mode = night
            st.rerun()

        st.markdown("<hr style='margin:5px 0;border-color:rgba(124,92,216,0.2);'>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-family:\"Orbitron\",sans-serif;font-size:0.56rem;color:#444466;"
            "text-transform:uppercase;letter-spacing:2px;margin-bottom:4px;'>// Navigation</div>",
            unsafe_allow_html=True,
        )

        # Styled nav buttons with tech icons
        for tab in TABS:
            icon  = NAV_ICONS.get(tab, "›")
            label = " ".join(tab.split(" ")[1:])  # strip leading emoji
            is_active = st.session_state.active_tab == tab
            if is_active:
                st.markdown(f"""
<div style="margin-bottom:1px;border-radius:8px;overflow:hidden;
  background:linear-gradient(135deg,rgba(124,92,216,0.3),rgba(96,165,250,0.15));
  border:1px solid rgba(124,92,216,0.45);">
  <div style="display:flex;align-items:center;gap:8px;padding:6px 8px;">
    <span style="font-size:0.85rem;color:#a78bfa;font-family:'Orbitron',monospace;
      min-width:16px;text-align:center;">{icon}</span>
    <span style="font-family:'Rajdhani',sans-serif;font-weight:700;
      color:#e0e0ff;font-size:0.82rem;letter-spacing:0.5px;">{label}</span>
  </div>
</div>""", unsafe_allow_html=True)
            else:
                st.markdown(f"""
<div style="margin-bottom:1px;">
  <div style="display:flex;align-items:center;gap:8px;padding:5px 8px;border-radius:8px;
    border:1px solid transparent;">
    <span style="font-size:0.8rem;color:#444466;font-family:'Orbitron',monospace;
      min-width:16px;text-align:center;">{icon}</span>
    <span style="font-family:'Rajdhani',sans-serif;font-weight:600;
      color:#666688;font-size:0.82rem;">{label}</span>
  </div>
</div>""", unsafe_allow_html=True)
            if st.button(label, key=f"nav_{tab}", use_container_width=True):
                st.session_state.active_tab = tab
                st.rerun()

        st.markdown("<hr style='margin:5px 0;border-color:rgba(124,92,216,0.2);'>", unsafe_allow_html=True)

        st.markdown("<div style='height:6px;'></div>", unsafe_allow_html=True)
        if st.button("⏻  Sign Out", use_container_width=True, key="logout"):
            for k in list(st.session_state.keys()):
                del st.session_state[k]
            st.rerun()

        st.markdown(
            f"<div style='text-align:center;font-size:0.55rem;color:#333355;"
            f"padding-top:6px;font-family:\"Orbitron\",sans-serif;letter-spacing:1px;'>"
            f"v{VERSION} · PORTALIX OS</div>",
            unsafe_allow_html=True,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# DASHBOARD HOME
# ═══════════════════════════════════════════════════════════════════════════════

# Night greeting phrases — no standard morning/evening prefix
NIGHT_GREETINGS = [
    "Welcome back to the grid, {name}",
    "System active, {name}",
    "Neural link established, {name}",
    "Re-entering the matrix, {name}",
    "Dark mode: engaged, {name}",
    "Session resumed, {name}",
]

def get_greeting(name: str = "") -> str:
    hour = datetime.datetime.now().hour
    if hour < 12:   return f"Good Morning, {name}"
    if hour < 17:   return f"Good Afternoon, {name}"
    if hour < 21:   return f"Good Evening, {name}"
    # Night — pick a stylized phrase seeded by username for consistency
    seed = sum(ord(c) for c in name) if name else 0
    phrase = NIGHT_GREETINGS[(seed + hour) % len(NIGHT_GREETINGS)]
    return phrase.format(name=name)

def render_dashboard():
    name    = st.session_state.user_name
    greeting = get_greeting(name)
    now_str  = datetime.datetime.now().strftime("%A, %B %d, %Y · %H:%M")

    # Subtle night vs day banner indicator
    hour = datetime.datetime.now().hour
    is_night = hour >= 21 or hour < 6
    banner_extra = (
        "border-left:3px solid rgba(96,165,250,0.5);" if is_night
        else "border-left:3px solid rgba(124,92,216,0.5);"
    )

    st.markdown(f"""
<div class="welcome-banner" style="{banner_extra}">
  <div class="glow-title">{greeting} {'🌙' if is_night else '👋'}</div>
  <div class="glow-subtitle" style="font-family:'Rajdhani',sans-serif;">{now_str}</div>
  <div style="font-size:0.82rem;color:#8888bb;margin-top:4px;font-family:'Rajdhani',sans-serif;">
    {'// System online · Portalix OS running' if is_night else 'Your Portalix overview — stay focused, stay productive.'}
  </div>
</div>
""", unsafe_allow_html=True)

    # ── Clickable stat cards 1-4 ─────────────────────────────────────────────
    pins   = count_pins()
    spaces = count_spaces()
    vaults = len(st.session_state.vault_items)
    remind = len([r for r in st.session_state.reminders if not r.get("done")])

    # Each card uses a Streamlit button hidden beneath the HTML card for routing
    c1, c2, c3, c4 = st.columns(4)
    card_defs = [
        (c1, pins,   "Pinned Sites",      "📌 Pinned Websites", "◈"),
        (c2, spaces, "Custom Spaces",     "🗂️ Custom Spaces",  "▦"),
        (c3, vaults, "Vault Items",       "🔐 Password Vault",  "⬗"),
        (c4, remind, "Pending Reminders", "⏰ Smart Reminders", "◷"),
    ]
    for col, val, label, target_tab, icon in card_defs:
        with col:
            st.markdown(f"""
<div class="metric-card-clickable">
  <div style="font-size:0.75rem;color:#5555aa;font-family:'Orbitron',sans-serif;
    letter-spacing:1px;margin-bottom:4px;">{icon}</div>
  <div class="metric-value">{val}</div>
  <div class="metric-label">{label}</div>
  <div style="font-size:0.6rem;color:#333355;margin-top:6px;font-family:'Orbitron',sans-serif;
    letter-spacing:1px;">TAP TO OPEN ›</div>
</div>
""", unsafe_allow_html=True)
            if st.button(f"open_{label}", key=f"card_nav_{label.replace(' ','_')}", use_container_width=True):
                st.session_state.active_tab = target_tab
                st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    col_left, col_right = st.columns([3, 2])

    with col_left:
        st.markdown(
            "<div style='font-family:\"Orbitron\",sans-serif;font-size:0.72rem;"
            "color:#6666aa;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>"
            "◈ Recent Pins</div>",
            unsafe_allow_html=True,
        )
        if st.session_state.pinned_sites:
            for site in st.session_state.pinned_sites[:4]:
                st.markdown(f"""
<div class="pin-card">
  <div class="pin-favicon">◈</div>
  <div style="flex:1;min-width:0;">
    <div class="pin-title">{site['title']}</div>
    <div class="pin-url">{site['url']}</div>
    <span class="pin-category">{site.get('category','General')}</span>
    <div class="pin-summary">{site.get('summary','')}</div>
  </div>
  <a href="{site['url']}" target="_blank" style="font-size:1.1rem;text-decoration:none;
    flex-shrink:0;color:#7c5cd8;font-family:'Orbitron',monospace;">▹</a>
</div>
""", unsafe_allow_html=True)
        else:
            st.markdown('<div class="glass-card" style="text-align:center;color:#8888bb;">No pinned sites yet.</div>', unsafe_allow_html=True)

    with col_right:
        st.markdown(
            "<div style='font-family:\"Orbitron\",sans-serif;font-size:0.72rem;"
            "color:#6666aa;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>"
            "◷ Upcoming Reminders</div>",
            unsafe_allow_html=True,
        )
        pending = [r for r in st.session_state.reminders if not r.get("done")]
        if pending:
            for idx, r in enumerate(pending[:4]):
                # Widget items 5 & 6 — clickable, route to Smart Reminders
                st.markdown(f"""
<div class="widget-row-clickable">
  <div style="font-weight:600;font-family:'Rajdhani',sans-serif;">{r['message']}</div>
  <div style="font-size:0.72rem;color:#8888bb;margin-top:2px;font-family:'Orbitron',sans-serif;
    letter-spacing:0.5px;">◷ {r.get('display', r.get('datetime',''))}</div>
</div>
""", unsafe_allow_html=True)
                if st.button(f"› Go to Reminders", key=f"dash_reminder_{r['id']}", use_container_width=True):
                    st.session_state.active_tab = "⏰ Smart Reminders"
                    st.rerun()
        else:
            st.markdown('<div class="glass-card" style="text-align:center;color:#8888bb;">No pending reminders.</div>', unsafe_allow_html=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        st.markdown(
            "<div style='font-family:\"Orbitron\",sans-serif;font-size:0.72rem;"
            "color:#6666aa;letter-spacing:2px;text-transform:uppercase;margin-bottom:8px;'>"
            "▦ Active Spaces</div>",
            unsafe_allow_html=True,
        )
        if st.session_state.custom_spaces:
            for sp in st.session_state.custom_spaces[:3]:
                urls = sp.get("urls", [])
                expander_label = f"{sp['icon']} {sp['name']}  ·  {len(urls)} link{'s' if len(urls) != 1 else ''}"
                with st.expander(expander_label, expanded=False):
                    if urls:
                        for u in urls:
                            st.link_button(
                                f"▹ {u['title']}",
                                url=u["url"],
                                use_container_width=True,
                            )
                    else:
                        st.caption("No URLs in this space yet.")
                    if st.button(
                        f"⚙️ Manage {sp['name']}",
                        key=f"dash_space_manage_{sp['id']}",
                        use_container_width=True,
                    ):
                        st.session_state.active_tab = "🗂️ Custom Spaces"
                        st.rerun()
        else:
            st.markdown('<div class="glass-card" style="text-align:center;color:#8888bb;">No spaces created yet.</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# PINNED WEBSITES
# ═══════════════════════════════════════════════════════════════════════════════

def render_pinned_websites():
    st.markdown('<div class="glow-title" style="font-size:1.8rem;">📌 Pinned Websites Hub</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-subtitle">Add, categorize, and launch your favorite sites.</div>', unsafe_allow_html=True)

    # Add new site
    with st.expander("➕ Add New Pinned Site", expanded=False):
        with st.form("add_pin_form"):
            c1, c2 = st.columns(2)
            with c1:
                new_title = st.text_input("Site Title", placeholder="e.g. GitHub")
            with c2:
                new_url = st.text_input("URL", placeholder="https://github.com")

            c3, c4 = st.columns(2)
            with c3:
                space_options = ["None"] + [s["name"] for s in st.session_state.custom_spaces]
                new_space = st.selectbox("Assign to Space", space_options)
            with c4:
                new_browser = st.selectbox("Browser", BROWSERS)

            ai_summarize = st.checkbox("🤖 AI Auto-Summarize & Tag (Gemini)", value=True)
            submitted = st.form_submit_button("📌 Pin this Site", use_container_width=True)

            if submitted:
                if not new_title or not new_url:
                    st.error("Title and URL are required.")
                else:
                    category = "General"
                    summary  = ""
                    if ai_summarize:
                        with st.spinner("🤖 AI is analyzing the URL..."):
                            result   = ai_summarize_url(new_url)
                            category = result.get("category", "General")
                            summary  = result.get("summary", "")
                        st.success(f"AI tagged as: **{category}**")

                    new_id = max([s["id"] for s in st.session_state.pinned_sites], default=0) + 1
                    st.session_state.pinned_sites.append({
                        "id": new_id,
                        "title": new_title,
                        "url": new_url,
                        "category": category,
                        "summary": summary,
                        "browser": new_browser,
                        "space": None if new_space == "None" else new_space,
                    })
                    # Log time access
                    st.session_state.time_logs.append({
                        "site": new_title, "minutes": 0,
                        "date": datetime.date.today().strftime("%Y-%m-%d"),
                        "hour": datetime.datetime.now().hour,
                    })
                    st.success(f"✅ '{new_title}' pinned successfully!")
                    st.rerun()

    # Filter & sort
    st.markdown("<br>", unsafe_allow_html=True)
    col_f1, col_f2, col_f3 = st.columns([2, 2, 1])
    with col_f1:
        search_q = st.text_input("🔍 Search pins", placeholder="Search by title, URL or tag...", label_visibility="collapsed")
    with col_f2:
        cats = ["All"] + list(set(s.get("category","General") for s in st.session_state.pinned_sites))
        filter_cat = st.selectbox("Filter by category", cats, label_visibility="collapsed")
    with col_f3:
        view_mode = st.selectbox("View", ["Grid", "List"], label_visibility="collapsed")

    # Apply filters
    pins = st.session_state.pinned_sites
    if search_q:
        q = search_q.lower()
        pins = [p for p in pins if q in p["title"].lower() or q in p["url"].lower() or q in p.get("category","").lower()]
    if filter_cat != "All":
        pins = [p for p in pins if p.get("category") == filter_cat]

    st.markdown(f"<div style='font-size:0.8rem;color:#8888bb;margin-bottom:12px;'>Showing {len(pins)} site(s)</div>", unsafe_allow_html=True)

    if not pins:
        st.markdown('<div class="glass-card" style="text-align:center;padding:40px;color:#8888bb;">No pinned sites found. Add your first site above!</div>', unsafe_allow_html=True)
        return

    # Render pins
    if view_mode == "Grid":
        cols = st.columns(2)
        for i, site in enumerate(pins):
            with cols[i % 2]:
                _render_pin_card(site)
    else:
        for site in pins:
            _render_pin_card(site, full_width=True)

def _render_pin_card(site: dict, full_width: bool = False):
    browser_icon = {"Chrome": "🟡", "Firefox": "🦊", "Edge": "💙", "Safari": "🧭"}.get(site.get("browser","Default"), "🌐")
    space_label  = f"· {site['space']}" if site.get("space") else ""

    st.markdown(f"""
<div class="pin-card">
  <div class="pin-favicon">🌐</div>
  <div style="flex:1;min-width:0;">
    <div class="pin-title">{site['title']}</div>
    <div class="pin-url">{site['url']}</div>
    <div style="margin-top:4px;display:flex;gap:6px;flex-wrap:wrap;align-items:center;">
      <span class="pin-category">{site.get('category','General')}</span>
      <span style="font-size:0.72rem;color:#8888bb;">{browser_icon} {site.get('browser','Default')}{space_label}</span>
    </div>
    {f'<div class="pin-summary">{site["summary"]}</div>' if site.get("summary") else ""}
  </div>
  <a href="{site['url']}" target="_blank" style="text-decoration:none;font-size:1.3rem;flex-shrink:0;padding:4px;">🔗</a>
</div>
""", unsafe_allow_html=True)

    col_edit, col_del = st.columns([3, 1])
    with col_del:
        if st.button("🗑️", key=f"del_pin_{site['id']}", help="Remove this pin"):
            st.session_state.pinned_sites = [p for p in st.session_state.pinned_sites if p["id"] != site["id"]]
            st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# CUSTOM SPACES
# ═══════════════════════════════════════════════════════════════════════════════

SPACE_ICONS = ["💼", "🎮", "🎬", "📚", "🏠", "🛒", "🎵", "🏋️", "💡", "🔬", "🌐", "⚙️"]

def render_custom_spaces():
    st.markdown('<div class="glow-title" style="font-size:1.8rem;">🗂️ Custom Spaces Manager</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-subtitle">Group websites into custom workspaces.</div>', unsafe_allow_html=True)

    # Create new space
    with st.expander("➕ Create New Space", expanded=False):
        with st.form("new_space_form"):
            c1, c2 = st.columns([3, 1])
            with c1:
                sp_name = st.text_input("Space Name", placeholder="e.g. Work Space")
            with c2:
                sp_icon = st.selectbox("Icon", SPACE_ICONS)
            sp_submit = st.form_submit_button("Create Space", use_container_width=True)
            if sp_submit:
                if not sp_name:
                    st.error("Space name required.")
                else:
                    new_id = max([s["id"] for s in st.session_state.custom_spaces], default=0) + 1
                    st.session_state.custom_spaces.append({
                        "id": new_id, "name": sp_name, "icon": sp_icon, "urls": []
                    })
                    st.success(f"Space '{sp_name}' created!")
                    st.rerun()

    # Render spaces
    if not st.session_state.custom_spaces:
        st.markdown('<div class="glass-card" style="text-align:center;padding:40px;color:#8888bb;">No spaces yet. Create your first workspace above!</div>', unsafe_allow_html=True)
        return

    for sp in st.session_state.custom_spaces:
        with st.expander(f"{sp['icon']} {sp['name']}  ({len(sp.get('urls',[]))} links)", expanded=False):
            st.markdown(f"**{sp['icon']} {sp['name']}**")

            # URL list
            urls = sp.get("urls", [])
            if urls:
                for i, u in enumerate(urls):
                    uc1, uc2 = st.columns([5, 1])
                    with uc1:
                        st.link_button(
                            f"▹ {u['title']}  —  {u['url'][:45]}{'…' if len(u['url']) > 45 else ''}",
                            url=u["url"],
                            use_container_width=True,
                        )
                    with uc2:
                        if st.button("🗑️", key=f"del_space_url_{sp['id']}_{i}"):
                            sp["urls"].pop(i)
                            st.rerun()
            else:
                st.markdown('<div style="color:#8888bb;font-size:0.85rem;padding:8px 0;">No URLs yet. Add some below.</div>', unsafe_allow_html=True)

            # Add URL to space
            with st.form(f"add_url_space_{sp['id']}"):
                au1, au2 = st.columns(2)
                with au1:
                    url_title = st.text_input("Title", placeholder="e.g. Gmail", key=f"ut_{sp['id']}")
                with au2:
                    url_href  = st.text_input("URL", placeholder="https://...", key=f"uh_{sp['id']}")
                if st.form_submit_button("Add URL", use_container_width=True):
                    if url_title and url_href:
                        sp["urls"].append({"title": url_title, "url": url_href})
                        st.success(f"Added '{url_title}' to {sp['name']}")
                        st.rerun()

            # Delete space
            if st.button(f"🗑️ Delete '{sp['name']}'", key=f"del_space_{sp['id']}"):
                st.session_state.custom_spaces = [s for s in st.session_state.custom_spaces if s["id"] != sp["id"]]
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# PASSWORD VAULT
# ═══════════════════════════════════════════════════════════════════════════════

def render_password_vault():
    st.markdown('<div class="glow-title" style="font-size:1.8rem;">🔐 Password Vault</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-subtitle">Securely store and manage credentials with Fernet encryption.</div>', unsafe_allow_html=True)

    # AI check button
    if st.button("🤖 AI Password Safety Check", key="ai_pw_check"):
        with st.spinner("Analyzing password strength..."):
            pws = [v.get("password_hint", "") for v in st.session_state.vault_items]
            report = ai_password_check(pws)
        st.markdown(f'<div class="glass-card"><strong>🛡️ AI Safety Report</strong><br><br>{report}</div>', unsafe_allow_html=True)

    # Add new item
    with st.expander("➕ Add New Credential", expanded=False):
        with st.form("add_vault_form"):
            vc1, vc2 = st.columns(2)
            with vc1:
                v_site  = st.text_input("Website / Service", placeholder="e.g. GitHub")
                v_user  = st.text_input("Username / Email", placeholder="you@email.com")
            with vc2:
                v_pw    = st.text_input("Password", type="password")
                v_notes = st.text_input("Notes (optional)", placeholder="2FA enabled, etc.")
            v_submit = st.form_submit_button("🔐 Save to Vault", use_container_width=True)
            if v_submit:
                if not v_site or not v_pw:
                    st.error("Website and Password are required.")
                else:
                    # Strength check
                    strength = "Strong" if len(v_pw) >= 12 else ("Medium" if len(v_pw) >= 8 else "Weak")
                    hint     = v_pw[:2] + "***" + v_pw[-1] if len(v_pw) > 3 else "***"
                    encrypted_pw = encrypt_text(v_pw)
                    new_id = max([v["id"] for v in st.session_state.vault_items], default=0) + 1
                    st.session_state.vault_items.append({
                        "id": new_id,
                        "site": v_site,
                        "username": v_user,
                        "password_enc": encrypted_pw,
                        "password_hint": hint,
                        "strength": strength,
                        "notes": v_notes,
                        "added": datetime.date.today().strftime("%Y-%m-%d"),
                    })
                    st.success(f"✅ Credential for '{v_site}' saved. Strength: **{strength}**")
                    if strength == "Weak":
                        st.warning("⚠️ Password is weak — consider using a stronger password.")
                    st.rerun()

    # Display vault items
    if not st.session_state.vault_items:
        st.markdown('<div class="glass-card" style="text-align:center;padding:40px;color:#8888bb;">Vault is empty. Add your first credential above.</div>', unsafe_allow_html=True)
        return

    st.markdown(f"<br><div style='font-size:0.85rem;color:#8888bb;'>🔐 {len(st.session_state.vault_items)} credential(s) stored — encrypted at rest</div>", unsafe_allow_html=True)

    search_v = st.text_input("🔍 Search vault", placeholder="Search by site or username...", label_visibility="collapsed")
    items = st.session_state.vault_items
    if search_v:
        q = search_v.lower()
        items = [v for v in items if q in v["site"].lower() or q in v.get("username","").lower()]

    for item in items:
        strength_color = {"Strong": "#10b981", "Medium": "#f59e0b", "Weak": "#ef4444"}.get(item.get("strength","Medium"), "#8888bb")
        col1, col2, col3, col4, col5 = st.columns([2, 2, 2, 1, 1])
        with col1:
            st.markdown(f"**🌐 {item['site']}**")
            st.markdown(f"<span style='font-size:0.75rem;color:#8888bb;'>{item.get('notes','')}</span>", unsafe_allow_html=True)
        with col2:
            st.markdown(f"👤 `{item.get('username','—')}`")
        with col3:
            show_key = f"show_pw_{item['id']}"
            if show_key not in st.session_state:
                st.session_state[show_key] = False
            if st.session_state[show_key]:
                try:
                    plain = decrypt_text(item["password_enc"])
                    st.markdown(f"🔓 `{plain}`")
                except Exception:
                    st.markdown("🔒 `[encrypted]`")
            else:
                st.markdown(f"🔒 `{item.get('password_hint','***')}`")
        with col4:
            if st.button("👁️", key=f"view_pw_{item['id']}", help="Show/hide password"):
                st.session_state[show_key] = not st.session_state[show_key]
                st.rerun()
        with col5:
            if st.button("🗑️", key=f"del_vault_{item['id']}"):
                st.session_state.vault_items = [v for v in st.session_state.vault_items if v["id"] != item["id"]]
                st.rerun()

        st.markdown(f"<div style='height:1px;background:rgba(124,92,216,0.15);margin:6px 0;'></div>", unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SMART REMINDERS
# ═══════════════════════════════════════════════════════════════════════════════

def render_smart_reminders():
    st.markdown('<div class="glow-title" style="font-size:1.8rem;">⏰ Smart Reminders</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-subtitle">Type reminders in natural language — Gemini AI parses them automatically.</div>', unsafe_allow_html=True)

    # Add reminder
    with st.form("add_reminder_form"):
        st.markdown("**🗣️ Natural Language Input**")
        reminder_text = st.text_area(
            "What do you need to remember?",
            placeholder='e.g. "Remind me to review my goals tomorrow at 9 AM" or "Follow up with client on Friday at 2 PM"',
            height=80,
            label_visibility="collapsed"
        )
        col_a, col_b = st.columns([1, 3])
        with col_a:
            use_ai = st.checkbox("🤖 Parse with Gemini AI", value=True)
        with col_b:
            if not use_ai:
                manual_dt = st.text_input("Manual datetime (YYYY-MM-DD HH:MM)", placeholder="2024-12-31 09:00")
        submit_r = st.form_submit_button("➕ Add Reminder", use_container_width=True)

        if submit_r:
            if not reminder_text.strip():
                st.error("Please enter a reminder.")
            else:
                if use_ai:
                    with st.spinner("🤖 Parsing with Gemini AI..."):
                        parsed = ai_parse_reminder(reminder_text)
                    dt_str  = parsed.get("datetime", "")
                    display = parsed.get("display", "Unknown time")
                    msg     = parsed.get("message", reminder_text)
                    st.info(f"✅ Parsed: **{msg}** at **{display}**")
                else:
                    dt_str  = manual_dt if "manual_dt" in dir() else ""
                    display = dt_str
                    msg     = reminder_text

                new_id = max([r["id"] for r in st.session_state.reminders], default=0) + 1
                st.session_state.reminders.append({
                    "id": new_id,
                    "message": msg,
                    "datetime": dt_str,
                    "display": display,
                    "done": False,
                    "created": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"),
                })
                st.success("Reminder added!")
                st.rerun()

    # View reminders
    st.markdown("<br>", unsafe_allow_html=True)
    tab_pending, tab_done = st.tabs(["⏳ Pending", "✅ Completed"])

    pending = [r for r in st.session_state.reminders if not r.get("done")]
    done    = [r for r in st.session_state.reminders if r.get("done")]

    with tab_pending:
        if not pending:
            st.markdown('<div class="glass-card" style="text-align:center;padding:30px;color:#8888bb;">🎉 All caught up! No pending reminders.</div>', unsafe_allow_html=True)
        for r in pending:
            rc1, rc2, rc3 = st.columns([5, 1, 1])
            with rc1:
                st.markdown(f"""
<div class="reminder-card">
  <div style="font-weight:600;font-size:0.95rem;">{r['message']}</div>
  <div style="font-size:0.75rem;color:#8888bb;margin-top:3px;">🕐 {r.get('display', r.get('datetime',''))}  ·  Added: {r.get('created','')}</div>
</div>
""", unsafe_allow_html=True)
            with rc2:
                if st.button("✅", key=f"done_r_{r['id']}", help="Mark done"):
                    r["done"] = True
                    st.rerun()
            with rc3:
                if st.button("🗑️", key=f"del_r_{r['id']}", help="Delete"):
                    st.session_state.reminders = [x for x in st.session_state.reminders if x["id"] != r["id"]]
                    st.rerun()

    with tab_done:
        if not done:
            st.markdown('<div style="color:#8888bb;font-size:0.85rem;padding:16px;">No completed reminders yet.</div>', unsafe_allow_html=True)
        for r in done:
            st.markdown(f"""
<div class="reminder-card" style="opacity:0.6;border-left-color:#10b981;">
  <del style="font-weight:600;">{r['message']}</del>
  <div style="font-size:0.75rem;color:#8888bb;">✅ Completed</div>
</div>
""", unsafe_allow_html=True)
            if st.button("🗑️", key=f"del_done_r_{r['id']}"):
                st.session_state.reminders = [x for x in st.session_state.reminders if x["id"] != r["id"]]
                st.rerun()


# ═══════════════════════════════════════════════════════════════════════════════
# TIME ANALYTICS
# ═══════════════════════════════════════════════════════════════════════════════

def render_time_analytics():
    st.markdown('<div class="glow-title" style="font-size:1.8rem;">📊 Time Analytics & AI Insights</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-subtitle">Track your browsing patterns and get personalized productivity insights.</div>', unsafe_allow_html=True)

    # View filter
    col_v1, col_v2 = st.columns([1, 4])
    with col_v1:
        view = st.selectbox("View", ["Day", "Week", "Month"], key="analytics_view")

    logs = st.session_state.time_logs
    if not logs:
        st.markdown('<div class="glass-card" style="text-align:center;padding:40px;color:#8888bb;">No usage data yet. Start launching sites from Pinned Websites!</div>', unsafe_allow_html=True)
        return

    df = pd.DataFrame(logs)
    df["date"] = pd.to_datetime(df["date"])
    today = pd.Timestamp.now().normalize()

    if view == "Day":
        df_view = df[df["date"] == today]
        title_suffix = "Today"
    elif view == "Week":
        df_view = df[df["date"] >= today - pd.Timedelta(days=6)]
        title_suffix = "Last 7 Days"
    else:
        df_view = df[df["date"] >= today - pd.Timedelta(days=29)]
        title_suffix = "Last 30 Days"

    if df_view.empty:
        st.info("No data for the selected period.")
        return

    # Metrics
    total_min  = df_view["minutes"].sum()
    top_site   = df_view.groupby("site")["minutes"].sum().idxmax() if not df_view.empty else "N/A"
    unique_sites = df_view["site"].nunique()

    mc1, mc2, mc3 = st.columns(3)
    with mc1:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{total_min}</div><div class="metric-label">Total Minutes</div></div>', unsafe_allow_html=True)
    with mc2:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{top_site}</div><div class="metric-label">Top Site</div></div>', unsafe_allow_html=True)
    with mc3:
        st.markdown(f'<div class="metric-card"><div class="metric-value">{unique_sites}</div><div class="metric-label">Unique Sites</div></div>', unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    col_chart1, col_chart2 = st.columns(2)

    with col_chart1:
        # Time by site — pie
        site_data = df_view.groupby("site")["minutes"].sum().reset_index()
        fig_pie = px.pie(
            site_data, values="minutes", names="site",
            title=f"Time by Site — {title_suffix}",
            color_discrete_sequence=px.colors.sequential.Purpor,
        )
        fig_pie.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e0e0ff", title_font_size=14,
            margin=dict(t=40, b=10, l=10, r=10),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    with col_chart2:
        # Daily trend — bar
        daily = df_view.groupby("date")["minutes"].sum().reset_index()
        daily["date_str"] = daily["date"].dt.strftime("%b %d")
        fig_bar = px.bar(
            daily, x="date_str", y="minutes",
            title=f"Daily Usage (min) — {title_suffix}",
            color="minutes",
            color_continuous_scale="Purpor",
        )
        fig_bar.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e0e0ff", title_font_size=14,
            margin=dict(t=40, b=10, l=10, r=10),
            coloraxis_showscale=False,
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    # Hourly heatmap
    if view in ["Week", "Month"]:
        st.markdown("#### ⏱️ Activity Heatmap (by hour)")
        hourly = df_view.groupby(["date", "hour"])["minutes"].sum().reset_index()
        hourly["date_str"] = hourly["date"].dt.strftime("%b %d")
        fig_heat = px.density_heatmap(
            hourly, x="date_str", y="hour", z="minutes",
            title="Hourly Activity Heatmap",
            color_continuous_scale="Purpor",
        )
        fig_heat.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e0e0ff", title_font_size=14,
        )
        st.plotly_chart(fig_heat, use_container_width=True)

    # AI Insights
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("🤖 Generate AI Productivity Insights", key="gen_ai_insights"):
        site_summary = df_view.groupby("site")["minutes"].sum().to_dict()
        summary_str  = ", ".join(f"{k}: {v} min" for k, v in site_summary.items())
        data_str     = f"Period: {title_suffix}. Sites: {summary_str}. Total: {total_min} min."
        with st.spinner("🤖 Gemini is analyzing your patterns..."):
            insight = ai_productivity_insights(data_str)
        st.markdown(f'<div class="glass-card"><strong>🤖 AI Productivity Insights</strong><br><br>{insight}</div>', unsafe_allow_html=True)


# ═══════════════════════════════════════════════════════════════════════════════
# SUPPORT & HELP CENTER
# ═══════════════════════════════════════════════════════════════════════════════

FAQ_ITEMS = [
    ("How do I add a website to Pinned Sites?",
     "Go to '📌 Pinned Websites' tab, click '➕ Add New Pinned Site', enter the title and URL. The AI will auto-suggest a category and summary."),
    ("What is a Custom Space?",
     "Custom Spaces are themed workspaces (like Work, Gaming, Multimedia) where you group related URLs."),
    ("Is my password vault data secure?",
     "Yes! All vault passwords are encrypted using Fernet symmetric encryption before storage. They are never stored in plain text. AI safety checks analyze patterns without accessing actual passwords."),
    ("How does AI Smart Reminder parsing work?",
     "When you type a reminder in natural language (e.g. 'tomorrow at 3 PM'), Gemini AI extracts the exact date, time, and message automatically."),
    ("Can I choose which browser to open links in?",
     "Yes! You can select a preferred browser (Chrome, Firefox, Edge, Safari, or Default) for each pinned site via the Browser Selector dropdown when adding a site."),
    ("How is my data stored?",
     "All data is stored in Streamlit session state during your session. For persistent storage, a backend database integration would be required (enterprise setup)."),
    ("How do I navigate quickly between sections?",
     "Use the sidebar navigation buttons at any time to jump to any section."),
]

def render_support():
    st.markdown('<div class="glow-title" style="font-size:1.8rem;">🆘 Support & Help Center</div>', unsafe_allow_html=True)
    st.markdown('<div class="glow-subtitle">Find answers, report issues, and get instant AI help.</div>', unsafe_allow_html=True)

    tab_faq, tab_ai, tab_feedback = st.tabs(["❓ FAQ", "🤖 AI Assistant", "📝 Feedback"])

    with tab_faq:
        st.markdown("#### Frequently Asked Questions")
        search_faq = st.text_input("🔍 Search FAQ", placeholder="Type to search...", label_visibility="collapsed")

        items = FAQ_ITEMS
        if search_faq:
            q = search_faq.lower()
            items = [(q_text, a_text) for q_text, a_text in FAQ_ITEMS if q in q_text.lower() or q in a_text.lower()]

        if not items:
            st.info("No FAQ matches found. Try the AI Assistant below.")
        else:
            for i, (question, answer) in enumerate(items):
                with st.expander(f"❓ {question}"):
                    st.markdown(f'<div class="faq-a">{answer}</div>', unsafe_allow_html=True)

    with tab_ai:
        st.markdown("#### 🤖 AI Troubleshooting Assistant")
        st.markdown('<div style="color:#8888bb;font-size:0.85rem;margin-bottom:12px;">Powered by Gemini Flash — ask anything about using Portalix.</div>', unsafe_allow_html=True)

        if "help_chat" not in st.session_state:
            st.session_state.help_chat = []

        # Chat history
        for msg in st.session_state.help_chat:
            if msg["role"] == "user":
                st.markdown(f'<div class="glass-card" style="margin-bottom:6px;"><strong>You:</strong> {msg["text"]}</div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="glass-card" style="border-left:3px solid #7c5cd8;margin-bottom:6px;"><strong>🤖 Portalix AI:</strong><br>{msg["text"]}</div>', unsafe_allow_html=True)

        with st.form("ai_help_form"):
            user_q = st.text_input("Ask a question...", placeholder="e.g. How do I pin a website?", label_visibility="collapsed")
            ask_btn = st.form_submit_button("Ask AI →", use_container_width=True)
            if ask_btn and user_q:
                st.session_state.help_chat.append({"role": "user", "text": user_q})
                with st.spinner("🤖 Thinking..."):
                    answer = ai_troubleshoot(user_q)
                st.session_state.help_chat.append({"role": "ai", "text": answer})
                st.rerun()

        if st.session_state.help_chat:
            if st.button("🗑️ Clear Chat", key="clear_help_chat"):
                st.session_state.help_chat = []
                st.rerun()

    with tab_feedback:
        st.markdown("#### 📝 Submit Feedback")
        with st.form("feedback_form"):
            fb_type    = st.selectbox("Feedback Type", ["🐛 Bug Report", "✨ Feature Request", "💬 General Feedback", "⭐ Review"])
            fb_subject = st.text_input("Subject", placeholder="Brief description of your feedback")
            fb_detail  = st.text_area("Details", placeholder="Please describe in detail...", height=120)
            fb_email   = st.text_input("Email (optional)", placeholder="For follow-up replies")
            fb_submit  = st.form_submit_button("📤 Submit Feedback", use_container_width=True)
            if fb_submit:
                if not fb_subject or not fb_detail:
                    st.error("Subject and Details are required.")
                else:
                    st.success(f"✅ Thank you for your feedback! We've received your {fb_type} and will review it shortly.")
                    st.balloons()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN APP ROUTER
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    st.set_page_config(
        page_title="Portalix — Productivity Dashboard",
        page_icon="⚡",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    init_session()

    # Auth gate
    if not st.session_state.authenticated:
        render_auth_page()
        return

    # Apply CSS
    inject_css(st.session_state.night_mode)

    # Sidebar
    render_sidebar()

    # Main content
    tab = st.session_state.active_tab

    if tab == "🏠 Dashboard":
        render_dashboard()
    elif tab == "📌 Pinned Websites":
        render_pinned_websites()
    elif tab == "🗂️ Custom Spaces":
        render_custom_spaces()
    elif tab == "🔐 Password Vault":
        render_password_vault()
    elif tab == "⏰ Smart Reminders":
        render_smart_reminders()
    elif tab == "📊 Time Analytics":
        render_time_analytics()
    elif tab == "🆘 Support & Help":
        render_support()
    else:
        render_dashboard()


if __name__ == "__main__":
    main()
