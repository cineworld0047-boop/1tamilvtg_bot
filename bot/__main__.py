"""Main entry point for 1TamilVT-TG Telegram Bot."""
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

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=getattr(logging, getattr(Config, "LOG_LEVEL", "INFO")),
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Globals ──────────────────────────────────────────────────────────
scraper = TamilMVScraper()
last_scrape_time: datetime = datetime.min
last_movies: list = []

# ── Dummy Web Server for Render & UptimeRobot ────────────────────────
app_server = Flask(__name__)


@app_server.route("/")
def home():
    return "CineWorld Auto-Scraper is Alive and Running!"


def run_server():
    port = int(os.environ.get("PORT", getattr(Config, "PORT", 8080)))
    app_server.run(host="0.0.0.0", port=port)


# ── Helpers ──────────────────────────────────────────────────────────
def _build_movie_text(movie: dict, idx: int = None) -> str:
    """Format a single movie entry."""
    prefix = f"{idx}. " if idx else ""
    quality = movie.get("quality", "HD")
    url = movie.get("url", "#")
    title = movie.get("title", "Unknown Title")
    return (
        f"{prefix}🎬 <b>{title}</b>\n"
        f"📊 Quality: <code>{quality}</code>\n"
        f"🔗 <a href='{url}'>View on 1TamilMV</a>\n\n"
    )


def _build_keyboard(movie: dict) -> InlineKeyboardMarkup:
    """Build inline buttons for a movie."""
    buttons = [
        [InlineKeyboardButton("🌐 Open 1TamilMV", url=movie.get("url", "https://www.1tamilmv.fi"))],
    ]
    return InlineKeyboardMarkup(buttons)


# ── Handlers ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    channel_username = getattr(Config, "CHANNEL_USERNAME", "")
    welcome = (
        "👋 <b>Welcome to 1TamilVT-TG!</b>\n\n"
        "🎥 I fetch the <b>latest Tamil, Telugu, Malayalam & Hindi movies</b> "
        "from <i>1TamilMV</i> and deliver them straight to Telegram.\n\n"
        "📌 <b>Commands:</b>\n"
        "  /latest — Show newest uploads\n"
        "  /search <i>movie name</i> — Search movies\n"
        "  /status — Bot health check\n"
        "  /help — Show this help\n\n"
        "🔔 Join our channel for auto-updates!"
    )
    keyboard_buttons = []
    if channel_username:
        keyboard_buttons.append([InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{channel_username}")])
    keyboard_buttons.append([InlineKeyboardButton("🆘 Support", url="https://t.me/Opleech_WD")])

    keyboard = InlineKeyboardMarkup(keyboard_buttons)
    await update.message.reply_text(welcome, reply_markup=keyboard, parse_mode=ParseMode.HTML)


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help."""
    await start(update, context)


async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display latest movies."""
    global last_scrape_time, last_movies

    msg = await update.message.reply_text("⏳ Scraping 1TamilMV... Please wait.")

    try:
        movies = await scraper.get_latest(limit=10)
    except Exception as e:
        logger.error(f"Scraping failed: {e}")
        movies = []

    if not movies:
        await msg.edit_text(
            "❌ Could not reach 1TamilMV.\n"
            "The site may be down or domain changed. Try again later."
        )
        return

    last_movies = movies
    last_scrape_time = datetime.now()

    text = f"🆕 <b>Latest Movies on 1TamilMV</b> ({len(movies)} found)\n\n"
    for i, movie in enumerate(movies, 1):
        text += _build_movie_text(movie, i)

    await msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Search movies by query."""
    if not context.args:
        await update.message.reply_text(
            "⚠️ Usage: <code>/search Mufasa</code>", parse_mode=ParseMode.HTML
        )
        return

    query = " ".join(context.args)
    msg = await update.message.reply_text(f"🔍 Searching for '<i>{query}</i>'...", parse_mode=ParseMode.HTML)

    try:
        movies = await scraper.search(query, limit=10)
    except Exception as e:
        logger.error(f"Search failed: {e}")
        movies = []

    if not movies:
        await msg.edit_text(f"❌ No results found for '<b>{query}</b>'.", parse_mode=ParseMode.HTML)
        return

    text = f"🔍 <b>Search Results for '{query}'</b> ({len(movies)} found)\n\n"
    for i, movie in enumerate(movies, 1):
        text += _build_movie_text(movie, i)

    await msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot status."""
    uptime = datetime.now() - last_scrape_time if last_scrape_time != datetime.min else None
    uptime_str = f"{uptime.total_seconds():.0f}s ago" if uptime else "Never"

    working_domain = getattr(scraper, "working_domain", "N/A")
    channel_username = getattr(Config, "CHANNEL_USERNAME", "N/A")
    scrape_interval = getattr(Config, "SCRAPE_INTERVAL", 300)

    text = (
        f"🤖 <b>1TamilVT-TG Status</b>\n\n"
        f"📡 Working Domain: <code>{working_domain or 'N/A'}</code>\n"
        f"🕐 Last Scrape: {uptime_str}\n"
        f"📦 Movies Cached: {len(last_movies)}\n"
        f"🔧 Scrape Interval: {scrape_interval}s\n"
        f"📢 Channel: @{channel_username or 'N/A'}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)


async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle unknown commands."""
    await update.message.reply_text(
        "❓ Unknown command. Use /help to see available commands.",
        parse_mode=ParseMode.HTML,
    )


# ── Auto-Poster ──────────────────────────────────────────────────────
async def auto_post(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Background job: scrape and post new movies to channel."""
    global last_scrape_time, last_movies

    logger.info("Running auto-post job...")
    try:
        movies = await scraper.get_latest(limit=5)
    except Exception as e:
        logger.error(f"Auto-post scraping failed: {e}")
        return

    if not movies:
        logger.warning("Auto-post: no movies found.")
        return

    # Simple dedup: skip if same first title as before
    if last_movies and movies[0]["title"] == last_movies[0]["title"]:
        logger.info("Auto-post: no new movies.")
        return

    last_movies = movies
    last_scrape_time = datetime.now()

    channel_id = getattr(Config, "CHANNEL_ID", None)
    if not channel_id:
        logger.warning("CHANNEL_ID not set in Config. Skipping auto-post.")
        return

    for movie in movies[:3]:  # Post top 3
        text = (
            f"🎬 <b>{movie['title']}</b>\n"
            f"📊 Quality: <code>{movie.get('quality', 'HD')}</code>\n"
            f"🔗 <a href='{movie['url']}'>Get it on 1TamilMV</a>\n\n"
            f"#TamilMV #TamilMovies #1TamilMV"
        )
        try:
            await context.bot.send_message(
                chat_id=channel_id,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
                reply_markup=_build_keyboard(movie),
            )
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Failed to post to channel: {e}")


# ── Main Entry ───────────────────────────────────────────────────────
def main() -> None:
    """Start the bot and background web server."""
    if hasattr(Config, "validate"):
        Config.validate()

    # 1. Start background Flask server for Render health checks & UptimeRobot
    t = Thread(target=run_server)
    t.daemon = True
    t.start()
    logger.info("Background web server started for Render health checks.")

    # 2. Build Telegram Application
    application = Application.builder().token(Config.TOKEN).build()

    # Command Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("latest", latest))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Background auto-post job
    job_queue = application.job_queue
    if job_queue:
        interval = getattr(Config, "SCRAPE_INTERVAL", 300)
        job_queue.run_repeating(auto_post, interval=interval, first=10)

    logger.info("🚀 1TamilVT-TG Bot started!")

    # 3. Run Telegram Bot Polling
    application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        try:
            asyncio.run(scraper.close())
        except Exception:
            pass

