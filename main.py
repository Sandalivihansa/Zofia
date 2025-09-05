import os
import asyncio
import logging
from dotenv import load_dotenv
from pyrogram import Client, filters
from pyrogram.types import Message
from modules.song_downloader import download_song
from modules.admin import is_owner
from modules.rate_limiter import check_rate_limit

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
API_ID = int(os.getenv("5047271") or 0)
API_HASH = os.getenv("047d9ed308172e637d4265e1d9ef0c27") or None
OWNER_ID = int(os.getenv("OWNER_ID", "0"))
MAX_FILE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))

# logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = Client("song_bot", bot_token=BOT_TOKEN, api_id=API_ID or None, api_hash=API_HASH or None)

@app.on_message(filters.command("start") & filters.private)
async def start(_, message: Message):
    await message.reply_text("Send /song <song name> to download audio. Example:\n/song Shape of You - Ed Sheeran")

@app.on_message(filters.command("song") & filters.private)
async def song_handler(_, message: Message):
    user = message.from_user
    if not message.command or len(message.command) < 2:
        return await message.reply_text("Usage: /song <song name or artist - title>")

    if not check_rate_limit(user.id):
        return await message.reply_text("Too many requests. Try again later.")

    query = " ".join(message.command[1:])
    status_msg = await message.reply_text(f"🔎 Searching and downloading: **{query}**", parse_mode="markdown")

    try:
        # download_song returns dict with paths: {'audio': path, 'title':.., 'artist':.., 'thumbnail': path}
        result = await download_song(query, max_size_mb=MAX_FILE_MB)
    except Exception as e:
        logger.exception("Download failed")
        await status_msg.edit(f"❌ Failed to download: {e}")
        return

    audio_path = result["audio"]
    title = result.get("title") or query
    artist = result.get("artist") or "Unknown"
    thumb = result.get("thumbnail")

    # Send as audio so Telegram shows metadata
    caption = f"{title} — {artist}\n\nDownloaded by @{app.storage.session_name or 'song_bot'}"
    try:
        await status_msg.edit("⬆️ Uploading audio...")
        await message.reply_audio(
            audio=audio_path,
            title=title,
            performer=artist,
            thumb=thumb,
            caption=caption
        )
        await status_msg.delete()
    except Exception as e:
        logger.exception("Upload failed")
        await status_msg.edit(f"❌ Upload failed: {e}")
    finally:
        # cleanup files
        try:
            os.remove(audio_path)
            if thumb and os.path.exists(thumb):
                os.remove(thumb)
        except Exception:
            pass

if __name__ == "__main__":
    app.run()
