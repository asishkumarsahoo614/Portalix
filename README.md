# Portalix ⚡

A **production-ready personal productivity dashboard** built entirely in Python with Streamlit — featuring AI-powered tools, custom workspaces, password vault, smart reminders, and a futuristic glassmorphic UI.

> **Current version:** `v1.1.0`

---

## ✨ Features

| Feature | Description |
|---|---|
| 🏠 **Dashboard** | Live overview with clickable stat cards, recent pins, upcoming reminders, and active spaces |
| 📌 **Pinned Websites** | Add, tag, and launch favourite sites with AI auto-categorisation; Grid/List view; search & category filter |
| 🗂️ **Custom Spaces** | Group URLs into themed workspaces (Work, Gaming, Multimedia, etc.); manage links per space |
| 🔐 **Password Vault** | Fernet-encrypted credential storage with show/hide toggle, strength indicator, and AI safety check |
| ⏰ **Smart Reminders** | Natural-language input parsed by Gemini AI; Pending / Completed tabs; manual datetime fallback |
| 📊 **Time Analytics** | Day/Week/Month view with pie chart, daily bar chart, hourly activity heatmap, and AI insights |
| 🆘 **Support & Help** | Searchable FAQ, persistent AI chat assistant (Gemini), and feedback submission form |

---

## 🎨 UI Highlights

- **Glassmorphic design** — translucent cards, glowing borders, blurred backdrops
- **6 night + 3 day gradient palettes** — randomised per login session
- **Day/Night mode toggle** in the sidebar with dynamic gradient backgrounds
- **Futuristic typography** — Orbitron headings + Rajdhani body via Google Fonts
- **Animated background orbs** (`@keyframes orb-drift`)
- **Clickable dashboard stat cards** — navigate directly to any section
- Custom **tech-icon sidebar navigation** with active-state highlighting

---

## 🤖 AI Features (Powered by Google Gemini)

- **Smart Link Summarizer** — auto-categorises and summarises URLs when pinning
- **Natural Language Reminders** — e.g. *"Remind me to call Sam on Friday at 3 PM"* → structured datetime
- **Password Safety Check** — analyses vault entries for weak or duplicate credentials
- **Productivity Insights** — AI analysis of your Day/Week/Month browsing patterns
- **AI Troubleshooting Assistant** — persistent chat assistant inside Support & Help

All AI features use the `google-genai` SDK (`gemini-3.6-flash` model) and gracefully degrade when no API key is present.

---

## 🚀 Quick Start

### Local Development

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd portalix

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY

# 5. Run the app
streamlit run app.py
```

### Streamlit Community Cloud Deployment

1. Push this repo to GitHub
2. Go to [share.streamlit.io](https://share.streamlit.io)
3. Connect your GitHub repo
4. Set **Main file path**: `app.py`
5. Under **Advanced settings → Secrets**, add:
   ```toml
   GEMINI_API_KEY = "your_gemini_api_key_here"
   ```
6. Click **Deploy**

---

## 🔑 Environment Variables

| Variable | Required | Description |
|---|---|---|
| `GEMINI_API_KEY` | ✅ Yes | Google Gemini API key for all AI features |
| `ENCRYPTION_KEY` | ❌ No | Base64 Fernet key for the password vault (auto-derived from a fixed seed if absent) |

---

## 🏗️ Project Structure

```
portalix/
├── app.py              # Main Streamlit application (single-file)
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variable template
├── README.md           # This file
└── .streamlit/
    └── config.toml     # Streamlit theme (dark glassmorphic palette)
```

---

## 👤 Demo Accounts

Three built-in accounts are available for immediate testing (session-only, not persisted):

| Username | Password | Notes |
|---|---|---|
| `demo` | `demo123` | Standard demo user |
| `pro` | `pro123` | Pro demo user |
| `admin` | `admin123` | Admin user |

You can also click **Continue with Google (Demo OAuth)** for a one-click mock login, or **Create Account** to register a new session-scoped user.

---

## 🔒 Security Notes

- Vault passwords are **Fernet-encrypted** before storage — never kept in plain text
- If `ENCRYPTION_KEY` is not set, a stable key is derived from a fixed seed (suitable for demos; set a real key for production)
- API keys are loaded exclusively via `os.getenv()` — never hard-coded
- Password strength is evaluated on save (Weak / Medium / Strong) with a visual indicator
- Session state is cleared completely on sign-out

---

## 📄 License

MIT License — build freely, ship boldly.
