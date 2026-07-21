# Reel Desk — Explainer Video Factory (Team Web App)

Team ke liye ek professional web page — keyword daalo, "Generate video"
dabao, background mein poori pipeline chalti hai (script, voiceover,
stock footage, captions), aur video preview + download mil jati hai.
Kisi ko Python install ya API keys apni taraf se lagane ki zaroorat
nahi — sab kuch server pe handle hota hai.

## Files
```
explainer-webapp/
├── server.py          <- backend (FastAPI + pipeline)
├── requirements.txt
├── static/
│   ├── index.html      <- webpage
│   ├── style.css
│   └── app.js
└── jobs/                <- generated videos yahan store hoti hain
```

## LOCAL TEST (apne computer pe pehle try karo)

### 1. Install
```bash
pip install -r requirements.txt
```
FFmpeg bhi chahiye: `ffmpeg -version` se check karo, agar nahi hai to
ffmpeg.org se install karo.

### 2. API keys set karo (environment variables se — code mein nahi likhni)

**Mac/Linux:**
```bash
export PEXELS_API_KEY="your_pexels_key"
export ANTHROPIC_API_KEY="your_anthropic_key"
```

**Windows (PowerShell):**
```powershell
$env:PEXELS_API_KEY="your_pexels_key"
$env:ANTHROPIC_API_KEY="your_anthropic_key"
```

Keys yahan se lo (dono free hain):
- Pexels: https://www.pexels.com/api/
- Anthropic: https://console.anthropic.com/

### 3. Server chalao
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

Browser mein kholo: **http://localhost:8000**

---

## TEAM DEPLOY (taake sab log ek link se use kar sakein)

Sabse aasan free/cheap option **Railway** ya **Render** hai — dono
Python + FFmpeg support karte hain.

### Railway (recommended, sabse aasan)
1. https://railway.app pe signup karo, "New Project" → "Deploy from GitHub repo"
2. Ye poora `explainer-webapp` folder GitHub repo mein push karo
3. Railway khud `requirements.txt` detect kar ke install kar lega
4. **Settings → Variables** mein `PEXELS_API_KEY` aur `ANTHROPIC_API_KEY` daalo
5. **Settings → Start Command** mein daalo:
   ```
   apt-get update && apt-get install -y ffmpeg && uvicorn server:app --host 0.0.0.0 --port $PORT
   ```
6. Deploy hote hi tumhe ek public URL milega (e.g. `reeldesk.up.railway.app`)
   — wahi link team ke sab logon ko de do

### Render (alternative)
1. https://render.com pe "New Web Service" banao, repo connect karo
2. **Build Command:** `apt-get update && apt-get install -y ffmpeg && pip install -r requirements.txt`
3. **Start Command:** `uvicorn server:app --host 0.0.0.0 --port $PORT`
4. Environment tab mein dono API keys daalo
5. Deploy — public URL mil jayega

---

## Team ko sirf ye batana hai
1. Link kholo
2. Topic likho
3. "Generate video" dabao
4. 2-4 minute wait karo, download kar lo

Koi setup, koi API key, koi installation — kuch nahi chahiye unko.

## Notes
- Ek waqt mein multiple log agar generate karein to sab jobs alag-alag
  chalti hain (background threads) — koi tickar nahi lagta, lekin agar
  team bohot bari hai (10+ log same time), ek proper job queue
  (Celery/Redis) lagana behtar hoga — abhi ke liye simple threading
  kaafi hai.
- Purani generated videos `jobs/` folder mein rehti hain — chahogay
  to ek cleanup script laga sakte ho jo X din purani files delete kar de.
