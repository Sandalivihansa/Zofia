import os
import shutil
import asyncio
import tempfile
from yt_dlp import YoutubeDL
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, error
import aiohttp

DOWNLOAD_DIR = os.path.join(os.getcwd(), "data", "downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Blocking IO -> run in thread via asyncio.to_thread
async def download_song(query: str, max_size_mb: int = 50) -> dict:
    """
    Search YouTube and download best audio as MP3, embed thumbnail and metadata.
    Returns dict: {'audio': path, 'title':..., 'artist':..., 'thumbnail': path}
    """
    return await asyncio.to_thread(_download_song_blocking, query, max_size_mb)

def _download_song_blocking(query: str, max_size_mb: int = 50) -> dict:
    tmpdir = tempfile.mkdtemp(prefix="songdl_")
    try:
        opts = {
            "format": "bestaudio/best",
            "outtmpl": os.path.join(tmpdir, "%(title).200s.%(ext)s"),
            "noplaylist": True,
            "quiet": True,
            "no_warnings": True,
            "writethumbnail": True,
            "skip_download": False,
            "postprocessors": [
                # Extract audio to mp3 using ffmpeg
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "192"},
                # Add metadata (title, artist) to file
                {"key": "FFmpegMetadata"}
            ],
            # prefer ffmpeg
            "prefer_ffmpeg": True,
            "nocheckcertificate": True,
        }

        with YoutubeDL(opts) as ydl:
            # use ytsearch1 to search
            info = ydl.extract_info(f"ytsearch1:{query}", download=True)
            # yt-dlp returns a 'entries' list for search
            if "entries" in info and len(info["entries"]) > 0:
                info = info["entries"][0]
            # find mp3 file path
            title = info.get("title", "unknown")
            artist = info.get("uploader", "unknown")
            # find downloaded mp3 in tmpdir
            mp3_file = None
            for fname in os.listdir(tmpdir):
                if fname.lower().endswith(".mp3"):
                    mp3_file = os.path.join(tmpdir, fname)
                    break
            if not mp3_file:
                raise Exception("MP3 not found after download")

            # check file size
            size_mb = os.path.getsize(mp3_file) / (1024 * 1024)
            if size_mb > max_size_mb:
                raise Exception(f"File too large ({size_mb:.1f} MB). Max allowed {max_size_mb} MB.")

            # thumbnail handling: yt-dlp often writes jpg/png thumbnail into tmpdir
            thumb_path = None
            for fname in os.listdir(tmpdir):
                if fname.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
                    thumb_path = os.path.join(tmpdir, fname)
                    break

            # if no thumbnail, try to fetch thumbnail url from info
            if not thumb_path:
                thumb_url = None
                if info.get("thumbnail"):
                    thumb_url = info.get("thumbnail")
                if thumb_url:
                    thumb_path = os.path.join(tmpdir, "thumb.jpg")
                    # download thumbnail
                    try:
                        import requests
                        r = requests.get(thumb_url, timeout=15)
                        if r.status_code == 200:
                            with open(thumb_path, "wb") as f:
                                f.write(r.content)
                    except Exception:
                        thumb_path = None

            # embed metadata using mutagen
            try:
                audio = EasyID3(mp3_file)
            except Exception:
                from mutagen.id3 import ID3NoHeaderError
                try:
                    ID3(mp3_file).save()
                except Exception:
                    pass
                audio = EasyID3(mp3_file)
            audio["title"] = title
            audio["artist"] = artist
            audio.save()

            # embed cover art if thumbnail exists
            if thumb_path and os.path.exists(thumb_path):
                try:
                    id3 = ID3(mp3_file)
                except error:
                    id3 = ID3()
                with open(thumb_path, "rb") as albumart:
                    id3.add(APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=albumart.read()
                    ))
                id3.save(mp3_file)

            # move final mp3 to DOWNLOAD_DIR with safe name
            safe_name = f"{title[:150].strip().replace('/', '_')}.mp3"
            final_path = os.path.join(DOWNLOAD_DIR, safe_name)
            shutil.move(mp3_file, final_path)
            # if thumb exists, copy to downloads so main process can attach and then remove
            final_thumb = None
            if thumb_path and os.path.exists(thumb_path):
                final_thumb = os.path.join(DOWNLOAD_DIR, os.path.basename(thumb_path))
                shutil.copy(thumb_path, final_thumb)

            return {"audio": final_path, "title": title, "artist": artist, "thumbnail": final_thumb}
    finally:
        # cleanup tmpdir
        try:
            shutil.rmtree(tmpdir)
        except Exception:
            pass
