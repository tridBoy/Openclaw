# 🤖 Telegram AI Bot

Bot Telegram serba bisa dengan fitur:
- 🤖 Chat AI (Groq - Llama 3.3)
- 🔍 Web Search
- 📊 Analisis Token Solana (DexScreener)
- 🐦 Data Twitter/X (via Nitter)

## Commands
| Command | Fungsi |
|---------|--------|
| `/ai [pertanyaan]` | Chat dengan AI |
| `/search [kata kunci]` | Cari info di web |
| `/token [nama/CA]` | Analisis token Solana |
| `/twitter [username]` | Cek profil Twitter |
| `/tweets [username]` | Lihat tweet terbaru |
| `/reset` | Reset history chat |

## Setup

### 1. Clone & Install
```bash
git clone <repo-kamu>
cd <repo-kamu>
pip install -r requirements.txt
```

### 2. Isi Environment Variables
Copy `.env.example` jadi `.env` lalu isi:
```
TELEGRAM_TOKEN=token_dari_botfather
GROQ_API_KEY=api_key_dari_groq.com
TAVILY_API_KEY=opsional_untuk_web_search
```

### 3. Jalankan
```bash
python bot.py
```

## Deploy ke Railway
1. Push ke GitHub
2. Connect repo di Railway
3. Set environment variables di Railway dashboard
4. Deploy!

## API yang Digunakan
- **Groq** - AI/LLM (gratis, daftar di groq.com)
- **DexScreener** - Data token Solana (gratis, tanpa key)
- **Nitter** - Data Twitter/X (gratis, tanpa key)
- **Tavily** - Web search (opsional, 1000 req/bulan gratis)
