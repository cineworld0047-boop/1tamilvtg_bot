"""Main entry point for 1TamilVT-TG Telegram Bot."""
import asyncio
import logging
import sys
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.constants import ParseMode

from bot.config import Config
from bot.scraper import TamilMVScraper

# ── Logging ──────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s — %(name)s — %(levelname)s — %(message)s",
    level=getattr(logging, Config.LOG_LEVEL),
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

# ── Globals ──────────────────────────────────────────────────────────
scraper = TamilMVScraper()
last_scrape_time: datetime = datetime.min
last_movies: list = []

# ── Helpers ──────────────────────────────────────────────────────────
def _build_movie_text(movie: dict, idx: int) -> str:
    """Format a single movie entry."""
    return (
        f"🎬 <b>{movie['title']}</b>
"
        f"📊 Quality: <code>{movie['quality']}</code>
"
        f"🔗 <a href='{movie['url']}'>View on 1TamilMV</a>
"
    )

def _build_keyboard(movie: dict) -> InlineKeyboardMarkup:
    """Build inline buttons for a movie."""
    buttons = [
        [InlineKeyboardButton("🌐 Open 1TamilMV", url=movie["url"])],
    ]
    return InlineKeyboardMarkup(buttons)

# ── Handlers ─────────────────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send welcome message."""
    welcome = (
        "👋 <b>Welcome to 1TamilVT-TG!</b>

"
        "🎥 I fetch the <b>latest Tamil, Telugu, Malayalam & Hindi movies</b> "
        "from <i>1TamilMV</i> and deliver them straight to your Telegram.

"
        "📌 <b>Commands:</b>
"
        "  /latest — Show newest uploads
"
        "  /search <i>movie name</i> — Search movies
"
        "  /status — Bot health check
"
        "  /help — Show this help

"
        "🔔 Join our channel for auto-updates!"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Join Channel", url=f"https://t.me/{Config.CHANNEL_USERNAME}")],
        [InlineKeyboardButton("🆘 Support", url="https://t.me/Opleech_WD")],
    ])
    await update.message.reply_text(welcome, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help."""
    await start(update, context)

async def latest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Fetch and display latest movies."""
    global last_scrape_time, last_movies

    msg = await update.message.reply_text("⏳ Scraping 1TamilMV... Please wait.")

    movies = await scraper.get_latest(limit=10)
    if not movies:
        await msg.edit_text(
            "❌ Could not reach 1TamilMV.
"
            "The site may be down or domain changed. Try again later."
        )
        return

    last_movies = movies
    last_scrape_time = datetime.now()

    text = f"🆕 <b>Latest Movies on 1TamilMV</b> ({len(movies)} found)

"
    for i, movie in enumerate(movies, 1):
        text += f"{i}. {_build_movie_text(movie, i)}
"

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

    movies = await scraper.search(query, limit=10)
    if not movies:
        await msg.edit_text(f"❌ No results found for '<b>{query}</b>'.", parse_mode=ParseMode.HTML)
        return

    text = f"🔍 <b>Search Results for '{query}'</b> ({len(movies)} found)

"
    for i, movie in enumerate(movies, 1):
        text += f"{i}. {_build_movie_text(movie, i)}
"

    await msg.edit_text(text, parse_mode=ParseMode.HTML, disable_web_page_preview=True)

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show bot status."""
    uptime = datetime.now() - last_scrape_time if last_scrape_time != datetime.min else None
    uptime_str = f"{uptime.total_seconds():.0f}s ago" if uptime else "Never"

    text = (
        f"🤖 <b>1TamilVT-TG Status</b>

"
        f"📡 Working Domain: <code>{scraper.working_domain or 'N/A'}</code>
"
        f"🕐 Last Scrape: {uptime_str}
"
        f"📦 Movies Cached: {len(last_movies)}
"
        f"🔧 Scrape Interval: {Config.SCRAPE_INTERVAL}s
"
        f"📢 Channel: @{Config.CHANNEL_USERNAME or 'N/A'}"
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
    movies = await scraper.get_latest(limit=5)
    if not movies:
        logger.warning("Auto-post: no movies found.")
        return

    # Simple dedup: skip if same first title as before
    if last_movies and movies[0]["title"] == last_movies[0]["title"]:
        logger.info("Auto-post: no new movies.")
        return

    last_movies = movies
    last_scrape_time = datetime.now()

    for movie in movies[:3]:  # Post top 3
        text = (
            f"🎬 <b>{movie['title']}</b>
"
            f"📊 Quality: <code>{movie['quality']}</code>
"
            f"🔗 <a href='{movie['url']}'>Get it on 1TamilMV</a>

"
            f"#TamilMV #TamilMovies #1TamilMV"
        )
        try:
            await context.bot.send_message(
                chat_id=Config.CHANNEL_ID,
                text=text,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=False,
                reply_markup=_build_keyboard(movie),
            )
            await asyncio.sleep(2)
        except Exception as e:
            logger.error(f"Failed to post to channel: {e}")

# ── Main ─────────────────────────────────────────────────────────────
def main() -> None:
    """Start the bot."""
    Config.validate()

    application = Application.builder().token(Config.TOKEN).build()

    # Commands
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(CommandHandler("latest", latest))
    application.add_handler(CommandHandler("search", search))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(MessageHandler(filters.COMMAND, unknown))

    # Background auto-post job
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(auto_post, interval=Config.SCRAPE_INTERVAL, first=10)

    logger.info("🚀 1TamilVT-TG Bot started!")

    # Run
    if Config.WEBHOOK_URL:
        application.run_webhook(
            listen="0.0.0.0",
            port=Config.PORT,
            webhook_url=Config.WEBHOOK_URL,
        )
    else:
        application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    finally:
        asyncio.run(scraper.close())
