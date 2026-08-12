"""Main entry point for 1TamilVT-TG Telegram Bot with manual URL input."""
import asyncio
import logging
import os
import sys
from datetime import datetime
from threading import Thread

from flask import Flask
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from bot.config import Config
from bot.scraper import TamilMVScraper

logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=logging.INFO,
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

scraper = TamilMVScraper()

# Web server for Render health checks
app_server = Flask(__name__)

@app_server.route("/")
def home():
    return "CineWorld Bot Active"

def run_server():
    port = int(os.environ.get("PORT", 8080))
    app_server.run(host="0.0.0.0", port=port)

# Handlers
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Ask user for the live URL."""
    welcome = (
        "🎬 <b>CineWorld 47 Link Generator</b>\n\n"
        "Send me any active 1TamilMV URL or a direct movie page link.\n"
        "<i>Example: https://www.1tamilmv.ing/</i>"
    )
    await update.message.reply_text(welcome, parse_mode=ParseMode.HTML)

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Process sent URL."""
    url = update.message.text.strip()
    
    if not url.startswith("http"):
        await update.message.reply_text("⚠️ Please send a valid link starting with http:// or https://")
        return

    msg = await update.message.reply_text("⏳ Processing page...")
    
    # Store custom URL as active domain
    scraper.working_domain = url
    
    movies = await scraper.get_latest(limit=10)
    
    if not movies:
        await msg.edit_text("❌ Could not parse links from this URL. Make sure it is a valid 1TamilMV page.")
        return

    text = f"🍿 <b>Found Movies / Links:</b>\n\n"
    for i, m in enumerate(movies, 1):
        text += f"{i}. <b>{m['title']}</b>\n🔗 <a href='{m['url']}'>Open Link</a>\n\n"

    await msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

def main() -> None:
    t = Thread(target=run_server)
    t.daemon = True
    t.start()

    application = Application.builder().token(Config.TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))

    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
