import os
import logging
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from groq import Groq

# ============================================================
# KONFIGURASI - Isi di file .env atau Railway Variables
# ============================================================
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")  # Opsional untuk web search

# ============================================================
# SETUP LOGGING
# ============================================================
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============================================================
# GROQ CLIENT
# ============================================================
groq_client = Groq(api_key=GROQ_API_KEY)

# History percakapan per user
chat_histories = {}

# ============================================================
# HELPER: AI CHAT (GROQ)
# ============================================================
def ask_groq(user_id: int, message: str, system_prompt: str = None) -> str:
    if user_id not in chat_histories:
        chat_histories[user_id] = []

    if not system_prompt:
        system_prompt = (
            "Kamu adalah asisten AI yang helpful. "
            "Jawab dalam bahasa yang sama dengan pengguna. "
            "Jika ditanya soal crypto/token Solana, berikan analisis yang informatif."
        )

    chat_histories[user_id].append({"role": "user", "content": message})

    # Batasi history 10 pesan terakhir biar hemat token
    history = chat_histories[user_id][-10:]

    response = groq_client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "system", "content": system_prompt}] + history,
        max_tokens=1024,
        temperature=0.7,
    )

    reply = response.choices[0].message.content
    chat_histories[user_id].append({"role": "assistant", "content": reply})
    return reply

# ============================================================
# HELPER: WEB SEARCH (TAVILY)
# ============================================================
def web_search(query: str) -> str:
    if not TAVILY_API_KEY:
        # Fallback: DuckDuckGo instant answer (tanpa API key)
        try:
            url = f"https://api.duckduckgo.com/?q={requests.utils.quote(query)}&format=json&no_html=1"
            res = requests.get(url, timeout=10)
            data = res.json()
            abstract = data.get("AbstractText", "")
            if abstract:
                return f"🔍 *Hasil Search:*\n{abstract}\n\nSumber: {data.get('AbstractURL', '')}"
            else:
                return "❌ Tidak ada hasil ditemukan. Coba kata kunci lain."
        except Exception as e:
            return f"❌ Error saat search: {str(e)}"

    # Pakai Tavily kalau ada API key
    try:
        headers = {"Authorization": f"Bearer {TAVILY_API_KEY}", "Content-Type": "application/json"}
        payload = {"query": query, "search_depth": "basic", "max_results": 3}
        res = requests.post("https://api.tavily.com/search", json=payload, headers=headers, timeout=15)
        data = res.json()
        results = data.get("results", [])
        if not results:
            return "❌ Tidak ada hasil ditemukan."
        text = "🔍 *Hasil Search:*\n\n"
        for i, r in enumerate(results[:3], 1):
            text += f"{i}. *{r.get('title', '')}*\n{r.get('content', '')[:200]}...\n🔗 {r.get('url', '')}\n\n"
        return text
    except Exception as e:
        return f"❌ Error search: {str(e)}"

# ============================================================
# HELPER: ANALISIS TOKEN SOLANA (DEXSCREENER + COINGECKO)
# ============================================================
def analyze_token(query: str) -> str:
    try:
        # Cari token di DexScreener
        url = f"https://api.dexscreener.com/latest/dex/search?q={requests.utils.quote(query)}"
        res = requests.get(url, timeout=10)
        data = res.json()
        pairs = data.get("pairs", [])

        # Filter Solana saja
        sol_pairs = [p for p in pairs if p.get("chainId") == "solana"]

        if not sol_pairs:
            return f"❌ Token *{query}* tidak ditemukan di Solana."

        # Ambil pair dengan liquidity tertinggi
        pair = sorted(sol_pairs, key=lambda x: float(x.get("liquidity", {}).get("usd", 0) or 0), reverse=True)[0]

        name = pair.get("baseToken", {}).get("name", "Unknown")
        symbol = pair.get("baseToken", {}).get("symbol", "?")
        address = pair.get("baseToken", {}).get("address", "")
        price_usd = pair.get("priceUsd", "N/A")
        price_change_1h = pair.get("priceChange", {}).get("h1", "N/A")
        price_change_24h = pair.get("priceChange", {}).get("h24", "N/A")
        volume_24h = pair.get("volume", {}).get("h24", "N/A")
        liquidity = pair.get("liquidity", {}).get("usd", "N/A")
        market_cap = pair.get("marketCap", "N/A")
        dex = pair.get("dexId", "Unknown")
        url_pair = pair.get("url", "")

        # Format angka
        def fmt(val):
            try:
                v = float(val)
                if v >= 1_000_000:
                    return f"${v/1_000_000:.2f}M"
                elif v >= 1_000:
                    return f"${v/1_000:.2f}K"
                else:
                    return f"${v:.4f}"
            except:
                return str(val)

        def pct(val):
            try:
                v = float(val)
                emoji = "🟢" if v >= 0 else "🔴"
                return f"{emoji} {v:+.2f}%"
            except:
                return str(val)

        text = (
            f"📊 *Analisis Token Solana*\n\n"
            f"🪙 *{name} ({symbol})*\n"
            f"📍 DEX: {dex.upper()}\n\n"
            f"💰 *Harga:* ${price_usd}\n"
            f"📈 *1H:* {pct(price_change_1h)}\n"
            f"📈 *24H:* {pct(price_change_24h)}\n\n"
            f"💧 *Likuiditas:* {fmt(liquidity)}\n"
            f"📦 *Volume 24H:* {fmt(volume_24h)}\n"
            f"🏷️ *Market Cap:* {fmt(market_cap)}\n\n"
            f"📋 *CA:* `{address}`\n\n"
            f"🔗 [Lihat di DexScreener]({url_pair})"
        )
        return text

    except Exception as e:
        return f"❌ Error analisis token: {str(e)}"

# ============================================================
# HELPER: DATA TWITTER/X (SNSCRAPE VIA NITTER)
# ============================================================
def get_twitter_profile(username: str) -> str:
    try:
        # Gunakan Nitter sebagai proxy gratis
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.privacydev.net",
            "https://nitter.poast.org"
        ]

        username = username.lstrip("@")

        for instance in nitter_instances:
            try:
                url = f"{instance}/{username}"
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(url, headers=headers, timeout=10)

                if res.status_code == 200:
                    from html.parser import HTMLParser

                    class NitterParser(HTMLParser):
                        def __init__(self):
                            super().__init__()
                            self.data = {}
                            self.current_tag = ""
                            self.current_class = ""

                        def handle_starttag(self, tag, attrs):
                            self.current_tag = tag
                            attrs_dict = dict(attrs)
                            self.current_class = attrs_dict.get("class", "")

                        def handle_data(self, data):
                            data = data.strip()
                            if not data:
                                return
                            if "profile-stat-num" in self.current_class and data.isdigit() or "K" in data or "M" in data:
                                if "tweets" not in self.data:
                                    self.data["tweets"] = data
                                elif "following" not in self.data:
                                    self.data["following"] = data
                                elif "followers" not in self.data:
                                    self.data["followers"] = data

                    # Simple scraping nama & bio
                    import re
                    name_match = re.search(r'<a class="profile-card-fullname"[^>]*>([^<]+)</a>', res.text)
                    bio_match = re.search(r'<div class="profile-bio"><p>(.*?)</p>', res.text, re.DOTALL)
                    followers_match = re.search(r'Followers</span>\s*<span[^>]*>([^<]+)</span>', res.text)
                    following_match = re.search(r'Following</span>\s*<span[^>]*>([^<]+)</span>', res.text)
                    tweets_match = re.search(r'Tweets</span>\s*<span[^>]*>([^<]+)</span>', res.text)

                    name = name_match.group(1).strip() if name_match else username
                    bio = re.sub(r'<[^>]+>', '', bio_match.group(1)).strip() if bio_match else "N/A"
                    followers = followers_match.group(1).strip() if followers_match else "N/A"
                    following = following_match.group(1).strip() if following_match else "N/A"
                    tweets = tweets_match.group(1).strip() if tweets_match else "N/A"

                    return (
                        f"🐦 *Profil Twitter/X*\n\n"
                        f"👤 *Nama:* {name}\n"
                        f"🔖 *Username:* @{username}\n"
                        f"📝 *Bio:* {bio}\n\n"
                        f"👥 *Followers:* {followers}\n"
                        f"➡️ *Following:* {following}\n"
                        f"🐦 *Tweets:* {tweets}\n\n"
                        f"🔗 [Lihat Profil](https://twitter.com/{username})"
                    )
            except:
                continue

        return f"❌ Tidak bisa mengambil data @{username}. Coba lagi nanti."

    except Exception as e:
        return f"❌ Error: {str(e)}"

def get_twitter_tweets(username: str) -> str:
    try:
        username = username.lstrip("@")
        nitter_instances = [
            "https://nitter.net",
            "https://nitter.privacydev.net",
        ]

        for instance in nitter_instances:
            try:
                url = f"{instance}/{username}"
                headers = {"User-Agent": "Mozilla/5.0"}
                res = requests.get(url, headers=headers, timeout=10)

                if res.status_code == 200:
                    import re
                    tweets = re.findall(r'<div class="tweet-content[^"]*"[^>]*>(.*?)</div>', res.text, re.DOTALL)
                    tweets_clean = [re.sub(r'<[^>]+>', '', t).strip() for t in tweets[:5]]

                    if tweets_clean:
                        text = f"🐦 *Tweet Terbaru @{username}:*\n\n"
                        for i, tweet in enumerate(tweets_clean, 1):
                            if tweet:
                                text += f"{i}. {tweet[:200]}\n\n"
                        return text
            except:
                continue

        return f"❌ Tidak bisa mengambil tweet @{username}."
    except Exception as e:
        return f"❌ Error: {str(e)}"

# ============================================================
# COMMAND HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🤖 Chat AI", callback_data="help_ai"),
         InlineKeyboardButton("🔍 Web Search", callback_data="help_search")],
        [InlineKeyboardButton("📊 Analisis Token", callback_data="help_token"),
         InlineKeyboardButton("🐦 Twitter/X", callback_data="help_twitter")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "👋 *Halo! Gua bot AI serba bisa!*\n\n"
        "Pilih fitur yang mau kamu gunakan:\n\n"
        "🤖 */ai* - Chat dengan AI\n"
        "🔍 */search* - Cari info di web\n"
        "📊 */token* - Analisis token Solana\n"
        "🐦 */twitter* - Cek profil/tweet Twitter\n"
        "🐦 */tweets* - Lihat tweet terbaru\n"
        "🗑️ */reset* - Reset history chat\n",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Cara Penggunaan:*\n\n"
        "🤖 `/ai [pertanyaan]` - Chat dengan AI\n"
        "   Contoh: `/ai apa itu blockchain?`\n\n"
        "🔍 `/search [kata kunci]` - Cari di web\n"
        "   Contoh: `/search harga bitcoin hari ini`\n\n"
        "📊 `/token [nama/CA token]` - Analisis token Solana\n"
        "   Contoh: `/token BONK` atau `/token So111...`\n\n"
        "🐦 `/twitter [username]` - Cek profil Twitter\n"
        "   Contoh: `/twitter elonmusk`\n\n"
        "🐦 `/tweets [username]` - Lihat tweet terbaru\n"
        "   Contoh: `/tweets elonmusk`\n\n"
        "🗑️ `/reset` - Reset history percakapan AI",
        parse_mode="Markdown"
    )

async def ai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ Contoh: `/ai apa itu DeFi?`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    user_id = update.effective_user.id

    msg = await update.message.reply_text("🤔 Sedang berpikir...")

    try:
        reply = ask_groq(user_id, query)
        await msg.edit_text(reply, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ Contoh: `/search harga solana hari ini`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text("🔍 Sedang mencari...")

    try:
        result = web_search(query)
        await msg.edit_text(result, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def token_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ Contoh: `/token BONK` atau `/token WIF`", parse_mode="Markdown")
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text("📊 Mengambil data token...")

    try:
        result = analyze_token(query)
        await msg.edit_text(result, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def twitter_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ Contoh: `/twitter elonmusk`", parse_mode="Markdown")
        return

    username = context.args[0]
    msg = await update.message.reply_text("🐦 Mengambil data profil...")

    try:
        result = get_twitter_profile(username)
        await msg.edit_text(result, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def tweets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("❓ Contoh: `/tweets elonmusk`", parse_mode="Markdown")
        return

    username = context.args[0]
    msg = await update.message.reply_text("🐦 Mengambil tweet terbaru...")

    try:
        result = get_twitter_tweets(username)
        await msg.edit_text(result, parse_mode="Markdown", disable_web_page_preview=True)
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

async def reset_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in chat_histories:
        chat_histories[user_id] = []
    await update.message.reply_text("🗑️ History chat sudah direset!")

# Handle pesan biasa (tanpa command) → langsung ke AI
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    msg = await update.message.reply_text("🤔 Sedang berpikir...")

    try:
        reply = ask_groq(user_id, text)
        await msg.edit_text(reply, parse_mode="Markdown")
    except Exception as e:
        await msg.edit_text(f"❌ Error: {str(e)}")

# Handle inline button
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    helps = {
        "help_ai": "🤖 *Chat AI*\nGunakan: `/ai [pertanyaan]`\nContoh: `/ai jelaskan apa itu Solana`",
        "help_search": "🔍 *Web Search*\nGunakan: `/search [kata kunci]`\nContoh: `/search harga SOL hari ini`",
        "help_token": "📊 *Analisis Token Solana*\nGunakan: `/token [nama/CA]`\nContoh: `/token BONK`",
        "help_twitter": "🐦 *Twitter/X*\nGunakan: `/twitter [username]` untuk profil\nGunakan: `/tweets [username]` untuk tweet terbaru",
    }

    await query.edit_message_text(
        helps.get(query.data, "❓ Unknown"),
        parse_mode="Markdown"
    )

# ============================================================
# MAIN
# ============================================================
def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ai", ai_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("token", token_command))
    app.add_handler(CommandHandler("twitter", twitter_command))
    app.add_handler(CommandHandler("tweets", tweets_command))
    app.add_handler(CommandHandler("reset", reset_command))
    app.add_handler(CallbackQueryHandler(button_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
