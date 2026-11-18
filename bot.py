
import os
import re
import uuid
import asyncio
import logging
import sqlite3
import tempfile
import subprocess
from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import yt_dlp

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ChatAction
from aiogram.client.default import DefaultBotProperties
from aiogram.exceptions import TelegramBadRequest
from dotenv import load_dotenv
from aiohttp import web


# =========================
# CONFIG
# =========================

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET")
AUDD_TOKEN = os.getenv("AUDD_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN .env faylida ko'rsatilmagan")

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
VIDEO_DIR = DATA_DIR / "videos"
MUSIC_DIR = BASE_DIR / "music_library"

DATA_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)
MUSIC_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "bot.db"

MAX_VIDEO_SIZE = 45 * 1024 * 1024
MAX_VIDEO_DURATION = 60

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML")
)
dp = Dispatcher()

# Faqat ochiq, ruxsatli kontent manbalaridan foydalaning.
ALLOWED_VIDEO_DOMAINS = {
    "youtube.com",
    "www.youtube.com",
    "youtu.be",
    "m.youtube.com",
    "instagram.com",
    "www.instagram.com",
    "tiktok.com",
    "www.tiktok.com",
    "vm.tiktok.com",
    "vt.tiktok.com",
    "facebook.com",
    "www.facebook.com",
    "fb.watch",
    "x.com",
    "www.x.com",
    "twitter.com",
    "www.twitter.com"
}


# =========================
# DATABASE
# =========================

def init_db():
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'uz'
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS videos (
            video_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            file_path TEXT NOT NULL,
            created_at INTEGER DEFAULT (strftime('%s','now'))
        )
    """)

    con.commit()
    con.close()


def get_language(user_id):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute(
        "SELECT language FROM users WHERE user_id=?",
        (user_id,)
    )
    row = cur.fetchone()
    con.close()
    return row[0] if row else "uz"


def set_language(user_id, language):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO users(user_id, language)
        VALUES (?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET language=excluded.language
    """, (user_id, language))
    con.commit()
    con.close()


def save_video(video_id, user_id, file_path):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        INSERT INTO videos(video_id, user_id, file_path)
        VALUES (?, ?, ?)
    """, (video_id, user_id, str(file_path)))
    con.commit()
    con.close()


def get_video(video_id, user_id):
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    cur.execute("""
        SELECT file_path FROM videos
        WHERE video_id=? AND user_id=?
    """, (video_id, user_id))
    row = cur.fetchone()
    con.close()

    if not row:
        return None

    path = Path(row[0])
    return path if path.exists() else None


def cleanup_old_videos():
    import time

    cutoff = int(time.time()) - 3600

    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    cur.execute("""
        SELECT video_id, file_path FROM videos
        WHERE created_at < ?
    """, (cutoff,))

    rows = cur.fetchall()

    for video_id, file_path in rows:
        try:
            Path(file_path).unlink(missing_ok=True)
        except OSError:
            logger.exception("Eski video o'chirilmadi")

        cur.execute(
            "DELETE FROM videos WHERE video_id=?",
            (video_id,)
        )

    con.commit()
    con.close()


# =========================
# TRANSLATIONS
# =========================

TEXTS = {
    "uz": {
        "welcome": (
            "🎵 <b>Universal Music & Video Bot</b>\n\n"
            "Qo'shiq nomini yozing yoki video havolasini yuboring.\n\n"
            "🎬 Video yuborsangiz, Round qilaman.\n"
            "🎵 Audio yuborsangiz, musiqani aniqlashga harakat qilaman."
        ),
        "searching": "🔎 Qidirilmoqda...",
        "not_found": "❌ Hech narsa topilmadi.",
        "downloading": "⏳ Video yuklanmoqda...",
        "video_ready": "🎬 Video tayyor!",
        "download_error": "❌ Videoni olishning imkoni bo'lmadi.",
        "round_working": "🔵 Round tayyorlanmoqda...",
        "music_working": "🎵 Audio ajratilmoqda...",
        "music_error": "❌ Audio ajratilmadi.",
        "recognized": "🎧 Aniqlangan musiqa:",
        "not_recognized": "❌ Musiqa aniqlanmadi.",
        "choose_language": "Tilni tanlang:",
        "round_button": "🔵 Round",
        "music_button": "🎵 Music",
        "file_too_large": "❌ Video hajmi ruxsat etilgan chegaradan katta.",
        "video_too_long": "❌ Video 60 soniyadan uzun. Round uchun qisqaroq video yuboring.",
        "spotify_only": (
            "Spotify trek ma'lumotlarini ko'rsatadi. "
            "Audio fayl faqat bot kutubxonasida mavjud va "
            "tarqatishga ruxsatli bo'lsa yuboriladi."
        )
    },
    "ru": {
        "welcome": (
            "🎵 <b>Универсальный Music & Video Bot</b>\n\n"
            "Напишите название песни или отправьте ссылку на видео."
        ),
        "searching": "🔎 Поиск...",
        "not_found": "❌ Ничего не найдено.",
        "downloading": "⏳ Загружаю видео...",
        "video_ready": "🎬 Видео готово!",
        "download_error": "❌ Не удалось загрузить видео.",
        "round_working": "🔵 Создаю Round...",
        "music_working": "🎵 Извлекаю аудио...",
        "music_error": "❌ Не удалось извлечь аудио.",
        "recognized": "🎧 Найденная музыка:",
        "not_recognized": "❌ Музыка не распознана.",
        "choose_language": "Выберите язык:",
        "round_button": "🔵 Round",
        "music_button": "🎵 Music",
        "file_too_large": "❌ Видео слишком большое.",
        "video_too_long": "❌ Видео длиннее 60 секунд.",
        "spotify_only": "Spotify показывает информацию о треках. Аудио отправляется только из разрешённой локальной библиотеки."
    },
    "en": {
        "welcome": (
            "🎵 <b>Universal Music & Video Bot</b>\n\n"
            "Send a song name or a video link."
        ),
        "searching": "🔎 Searching...",
        "not_found": "❌ Nothing found.",
        "downloading": "⏳ Downloading video...",
        "video_ready": "🎬 Video is ready!",
        "download_error": "❌ Could not download the video.",
        "round_working": "🔵 Creating round video...",
        "music_working": "🎵 Extracting audio...",
        "music_error": "❌ Could not extract audio.",
        "recognized": "🎧 Recognized music:",
        "not_recognized": "❌ Music not recognized.",
        "choose_language": "Choose a language:",
        "round_button": "🔵 Round",
        "music_button": "🎵 Music",
        "file_too_large": "❌ Video file is too large.",
        "video_too_long": "❌ Video is longer than 60 seconds.",
        "spotify_only": "Spotify provides track information. Audio is sent only from the licensed local library."
    }
}


def tr(user_id, key):
    lang = get_language(user_id)
    return TEXTS.get(lang, TEXTS["uz"]).get(key, key)


# =========================
# FFMPEG
# =========================

def run_ffmpeg(args):
    result = subprocess.run(
        ["ffmpeg", "-y"] + args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.decode(errors="ignore")[-1500:]
        )


def make_round(input_path, output_path):
    # Telegram video note uchun kvadrat video.
    run_ffmpeg([
        "-i", str(input_path),
        "-t", str(MAX_VIDEO_DURATION),
        "-vf",
        "scale=640:640:force_original_aspect_ratio=increase,"
        "crop=640:640,fps=30,setsar=1",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        str(output_path)
    ])

    if output_path.stat().st_size > MAX_VIDEO_SIZE:
        raise ValueError("Round video juda katta")


def extract_music(input_path, output_path):
    run_ffmpeg([
        "-i", str(input_path),
        "-vn",
        "-acodec", "libmp3lame",
        "-b:a", "192k",
        str(output_path)
    ])


def convert_to_mp4(input_path, output_path):
    run_ffmpeg([
        "-i", str(input_path),
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "27",
        "-c:a", "aac",
        "-b:a", "128k",
        "-movflags", "+faststart",
        str(output_path)
    ])


# =========================
# URL VALIDATION
# =========================

def validate_video_url(url):
    try:
        parsed = urlparse(url.strip())

        if parsed.scheme != "https":
            return False

        host = (parsed.hostname or "").lower()

        if host not in ALLOWED_VIDEO_DOMAINS:
            return False

        if parsed.username or parsed.password:
            return False

        return True

    except Exception:
        return False


# =========================
# SOCIAL VIDEO DOWNLOAD
# =========================

def download_social_video(url, output_dir):
    output_dir = Path(output_dir)

    options = {
        "format": (
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/"
            "best[ext=mp4]/best"
        ),
        "outtmpl": str(output_dir / "download.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 20,
        "max_filesize": MAX_VIDEO_SIZE,
        "retries": 2,
        "overwrites": True,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    files = list(output_dir.glob("download.*"))

    if not files:
        raise FileNotFoundError("Video topilmadi")

    mp4_files = [p for p in files if p.suffix.lower() == ".mp4"]

    if mp4_files:
        video_path = mp4_files[0]
    else:
        video_path = files[0]
        converted = output_dir / "converted.mp4"
        convert_to_mp4(video_path, converted)
        video_path = converted

    if video_path.stat().st_size > MAX_VIDEO_SIZE:
        raise ValueError("Video hajmi juda katta")

    return video_path


# =========================
# SPOTIFY SEARCH
# =========================

spotify_token = None
spotify_token_expiry = 0


async def get_spotify_token():
    global spotify_token, spotify_token_expiry

    import time

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET:
        return None

    if spotify_token and time.time() < spotify_token_expiry:
        return spotify_token

    auth = aiohttp.BasicAuth(
        SPOTIFY_CLIENT_ID,
        SPOTIFY_CLIENT_SECRET
    )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://accounts.spotify.com/api/token",
            data={"grant_type": "client_credentials"},
            auth=auth,
            timeout=aiohttp.ClientTimeout(total=20)
        ) as response:
            if response.status != 200:
                logger.error("Spotify token error: %s", response.status)
                return None

            data = await response.json()

    spotify_token = data["access_token"]
    spotify_token_expiry = time.time() + data.get("expires_in", 3600) - 60

    return spotify_token


async def spotify_search(query):
    token = await get_spotify_token()

    if not token:
        return []

    headers = {"Authorization": f"Bearer {token}"}

    params = {
        "q": query,
        "type": "track",
        "limit": 5
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://api.spotify.com/v1/search",
            headers=headers,
            params=params,
            timeout=aiohttp.ClientTimeout(total=20)
        ) as response:
            if response.status != 200:
                logger.error("Spotify search error: %s", response.status)
                return []

            data = await response.json()

    return data.get("tracks", {}).get("items", [])


# =========================
# LOCAL LICENSED MUSIC
# =========================

def find_local_music(query):
    query_words = set(re.findall(r"\w+", query.lower()))

    if not query_words:
        return None

    best_path = None
    best_score = 0

    for path in MUSIC_DIR.iterdir():
        if not path.is_file():
            continue

        if path.suffix.lower() not in {
            ".mp3", ".m4a", ".ogg", ".wav", ".flac"
        }:
            continue

        filename_words = set(
            re.findall(r"\w+", path.stem.lower())
        )

        score = len(query_words & filename_words)

        if score > best_score:
            best_score = score
            best_path = path

    return best_path if best_score > 0 else None


async def send_music_search(message, query):
    user_id = message.from_user.id

    status = await message.answer(tr(user_id, "searching"))

    local_file = find_local_music(query)

    if local_file:
        await message.answer_audio(
            audio=FSInputFile(local_file),
            caption="🎵 " + local_file.stem
        )

    tracks = await spotify_search(query)

    if tracks:
        lines = ["🎧 <b>Spotify natijalari:</b>\n"]

        for i, track in enumerate(tracks, start=1):
            artists = ", ".join(
                artist["name"]
                for artist in track.get("artists", [])
            )

            lines.append(
                f"{i}. <b>{track.get('name', 'Unknown')}</b>\n"
                f"👤 {artists}\n"
                f"💿 {track.get('album', {}).get('name', '')}\n"
                f"🔗 {track.get('external_urls', {}).get('spotify', '')}\n"
            )

        lines.append(tr(user_id, "spotify_only"))

        await message.answer("\n".join(lines), disable_web_page_preview=True)

    elif not local_file:
        await message.answer(tr(user_id, "not_found"))

    await status.delete()


# =========================
# AUDD MUSIC RECOGNITION
# =========================

async def recognize_music(file_path):
    if not AUDD_TOKEN:
        return None

    form = aiohttp.FormData()
    form.add_field("api_token", AUDD_TOKEN)

    with open(file_path, "rb") as audio_file:
        form.add_field(
            "file",
            audio_file,
            filename="audio.mp3",
            content_type="application/octet-stream"
        )

        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://api.audd.io/",
                data=form,
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status != 200:
                    return None

                data = await response.json()

    return data.get("result")


async def download_telegram_file(file_id, output_path):
    telegram_file = await bot.get_file(file_id)

    await bot.download_file(
        telegram_file.file_path,
        destination=output_path
    )


# =========================
# KEYBOARDS
# =========================

def video_keyboard(video_id, user_id):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=tr(user_id, "round_button"),
                    callback_data=f"round:{video_id}"
                ),
                InlineKeyboardButton(
                    text=tr(user_id, "music_button"),
                    callback_data=f"music:{video_id}"
                )
            ]
        ]
    )


def language_keyboard():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 O'zbekcha",
                    callback_data="lang:uz"
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang:ru"
                ),
                InlineKeyboardButton(
                    text="🇬🇧 English",
                    callback_data="lang:en"
                )
            ]
        ]
    )


# =========================
# START / HELP / LANGUAGE
# =========================

@dp.message(CommandStart())
async def start_handler(message: Message):
    init_db()

    user_id = message.from_user.id

    await message.answer(
        tr(user_id, "welcome"),
        reply_markup=language_keyboard()
    )


@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        "🎵 Qo'shiq nomini yozing — musiqa qidiriladi.\n"
        "🎬 Video havolasini yuboring — oddiy video qaytadi.\n"
        "🔵 Round tugmasi — dumaloq video.\n"
        "🎵 Music tugmasi — videodan audio.\n"
        "🎧 Audio yuboring — musiqa aniqlanadi.\n"
        "/language — tilni o'zgartirish."
    )


@dp.message(Command("language"))
async def language_handler(message: Message):
    await message.answer(
        "Tilni tanlang:",
        reply_markup=language_keyboard()
    )


@dp.callback_query(F.data.startswith("lang:"))
async def language_callback(callback: CallbackQuery):
    language = callback.data.split(":")[1]

    if language not in {"uz", "ru", "en"}:
        await callback.answer()
        return

    set_language(callback.from_user.id, language)

    await callback.answer("Language updated!")

    try:
        await callback.message.edit_text(
            tr(callback.from_user.id, "welcome")
        )
    except TelegramBadRequest:
        pass


# =========================
# SOCIAL VIDEO URL HANDLER
# IMPORTANT: before general text handler
# =========================

@dp.message(F.text)
async def text_handler(message: Message):
    text = (message.text or "").strip()
    user_id = message.from_user.id

    if text.startswith("/"):
        return

    # URL bo'lsa, avval xavfsizligini tekshiramiz.
    if text.lower().startswith(("https://", "http://")):
        if not validate_video_url(text):
            await message.answer(
                "❌ Bu havola qo'llab-quvvatlanmaydi. "
                "Faqat ruxsatli ochiq video havolalarini yuboring."
            )
            return

        status = await message.answer(tr(user_id, "downloading"))

        try:
            with tempfile.TemporaryDirectory() as temp_dir:
                video_path = await asyncio.to_thread(
                    download_social_video,
                    text,
                    temp_dir
                )

                # Vaqtinchalik papka o'chib ketmasligi uchun
                # videoni doimiy katalogga nusxalaymiz.
                video_id = uuid.uuid4().hex[:12]
                saved_path = VIDEO_DIR / f"{video_id}.mp4"

                import shutil
                shutil.copy2(video_path, saved_path)

            if saved_path.stat().st_size > MAX_VIDEO_SIZE:
                saved_path.unlink(missing_ok=True)
                raise ValueError("Video juda katta")

            save_video(video_id, user_id, saved_path)

            await message.answer_video(
                video=FSInputFile(saved_path),
                caption=tr(user_id, "video_ready"),
                supports_streaming=True,
                reply_markup=video_keyboard(video_id, user_id)
            )

            await status.delete()

        except Exception:
            logger.exception("Video download error")

            await status.edit_text(
                tr(user_id, "download_error")
            )

        return

    # URL bo'lmasa, musiqa qidiriladi.
    await send_music_search(message, text)


# =========================
# ROUND BUTTON
# =========================

@dp.callback_query(F.data.startswith("round:"))
async def round_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    video_id = callback.data.split(":", 1)[1]

    source = get_video(video_id, user_id)

    if not source:
        await callback.answer(
            "Video topilmadi yoki muddati tugagan.",
            show_alert=True
        )
        return

    await callback.answer(tr(user_id, "round_working"))

    output_path = VIDEO_DIR / f"{video_id}_round.mp4"

    status = await callback.message.answer(
        tr(user_id, "round_working")
    )

    try:
        await asyncio.to_thread(
            make_round,
            source,
            output_path
        )

        await callback.message.answer_video_note(
            video_note=FSInputFile(output_path)
        )

    except Exception:
        logger.exception("Round conversion error")
        await callback.message.answer(
            "❌ Round tayyorlashda xatolik yuz berdi."
        )

    finally:
        output_path.unlink(missing_ok=True)

        try:
            await status.delete()
        except TelegramBadRequest:
            pass


# =========================
# MUSIC BUTTON
# =========================

@dp.callback_query(F.data.startswith("music:"))
async def music_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    video_id = callback.data.split(":", 1)[1]

    source = get_video(video_id, user_id)

    if not source:
        await callback.answer(
            "Video topilmadi yoki muddati tugagan.",
            show_alert=True
        )
        return

    await callback.answer(tr(user_id, "music_working"))

    output_path = VIDEO_DIR / f"{video_id}_audio.mp3"

    status = await callback.message.answer(
        tr(user_id, "music_working")
    )

    try:
        await asyncio.to_thread(
            extract_music,
            source,
            output_path
        )

        await callback.message.answer_audio(
            audio=FSInputFile(output_path),
            title="Extracted audio",
            caption="🎵 Video audiosi"
        )

    except Exception:
        logger.exception("Audio extraction error")
        await callback.message.answer(tr(user_id, "music_error"))

    finally:
        output_path.unlink(missing_ok=True)

        try:
            await status.delete()
        except TelegramBadRequest:
            pass


# =========================
# DIRECT TELEGRAM VIDEO
# Automatically converts to round
# =========================

@dp.message(F.video)
async def telegram_video_handler(message: Message):
    user_id = message.from_user.id

    video = message.video

    if video.file_size and video.file_size > MAX_VIDEO_SIZE:
        await message.answer(tr(user_id, "file_too_large"))
        return

    if video.duration and video.duration > MAX_VIDEO_DURATION:
        await message.answer(tr(user_id, "video_too_long"))
        return

    status = await message.answer(
        tr(user_id, "round_working")
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        source = Path(temp_dir) / "input.mp4"
        output = Path(temp_dir) / "round.mp4"

        try:
            await download_telegram_file(
                video.file_id,
                source
            )

            await asyncio.to_thread(
                make_round,
                source,
                output
            )

            await message.answer_video_note(
                video_note=FSInputFile(output)
            )

        except Exception:
            logger.exception("Telegram video conversion error")

            await message.answer(
                "❌ Videoni Round formatiga aylantirib bo'lmadi."
            )

        finally:
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


# =========================
# AUDIO / VOICE RECOGNITION
# =========================

@dp.message(F.audio | F.voice)
async def audio_handler(message: Message):
    user_id = message.from_user.id

    audio = message.audio or message.voice

    if audio.file_size and audio.file_size > 20 * 1024 * 1024:
        await message.answer(
            "❌ Audio fayl juda katta."
        )
        return

    status = await message.answer(
        "🎧 Musiqa aniqlanmoqda..."
    )

    with tempfile.TemporaryDirectory() as temp_dir:
        audio_path = Path(temp_dir) / "audio.bin"

        try:
            await download_telegram_file(
                audio.file_id,
                audio_path
            )

            result = await recognize_music(audio_path)

            if not result:
                await message.answer(
                    tr(user_id, "not_recognized")
                )
            else:
                title = result.get("title", "Unknown")
                artist = result.get("artist", "Unknown")
                album = result.get("album", "Unknown")
                spotify_url = (
                    result.get("song_link")
                    or result.get("spotify", {}).get("external_urls", {}).get("spotify")
                )

                response = (
                    f"{tr(user_id, 'recognized')}\n\n"
                    f"🎵 <b>{title}</b>\n"
                    f"👤 {artist}\n"
                    f"💿 {album}"
                )

                if spotify_url:
                    response += f"\n🔗 {spotify_url}"

                await message.answer(response)

        except Exception:
            logger.exception("AudD recognition error")
            await message.answer(
                "❌ Audioni aniqlashda xatolik yuz berdi."
            )

        finally:
            try:
                await status.delete()
            except TelegramBadRequest:
                pass


# =========================
# HEALTH CHECK FOR RENDER
# =========================

async def health(request):
    return web.Response(text="Bot is running!")


async def start_health_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "8080"))

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    logger.info("Health server started on port %s", port)

    return runner


# =========================
# MAIN
# =========================

async def main():
    init_db()

    runner = await start_health_server()

    try:
        logger.info("Bot started")

        await bot.delete_webhook(drop_pending_updates=True)

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
