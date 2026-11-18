import os
import re
import asyncio
import logging
import subprocess
import unicodedata
import sqlite3
import shutil

from pathlib import Path
from urllib.parse import urlparse

import aiohttp
import yt_dlp

from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)


# ==================================================
# SOZLAMALAR
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "")
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

BASE_DIR = Path(__file__).resolve().parent

MUSIC_LIBRARY_DIR = BASE_DIR / "music_library"
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "tmp"
DATABASE_PATH = DATA_DIR / "bot.sqlite3"

MAX_VIDEO_BYTES = 48 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_VIDEO_SECONDS = 60

AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".aac",
    ".ogg", ".wav", ".flac"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# ==================================================
# TILLAR
# ==================================================

TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum!\n\n"
            "🎵 Qo‘shiq nomini yozing yoki ovozli parcha yuboring.\n"
            "🎬 Video havolasini yuboring.\n"
            "🎥 Video yuborsangiz, dumaloq video qilib beraman.\n\n"
            "/music - Musiqa\n"
            "/video - Video\n"
            "/help - Yordam\n"
            "/lang - Til"
        ),
        "wait": "⏳ Kuting...",
        "recognizing": "🎧 Qo‘shiq aniqlanmoqda...",
        "not_found": "😔 Qo‘shiq topilmadi.",
        "not_library": (
            "Qo‘shiq aniqlandi, lekin to‘liq audio "
            "kutubxonamizda mavjud emas:"
        ),
        "error": "❌ Xatolik yuz berdi.",
        "no_audd": "AudD token sozlanmagan.",
        "no_song": "Kutubxonada bu qo‘shiq topilmadi.",
        "language": "Tilni tanlang:",
        "audio_large": "Audio fayl juda katta.",
        "video_large": "Video fayl juda katta.",
        "bad_url": "Noto‘g‘ri havola.",
        "video_ready": "📥 Video tayyor!",
        "music_help": "🎵 Qo‘shiq nomini yozing yoki audio yuboring.",
        "video_help": "🎬 Video havolasini yuboring yoki video jo‘nating.",
    },

    "ru": {
        "start": (
            "👋 Добро пожаловать!\n\n"
            "Отправьте название песни или аудио.\n"
            "Отправьте ссылку на видео.\n\n"
            "/music - Музыка\n"
            "/video - Видео\n"
            "/help - Помощь\n"
            "/lang - Язык"
        ),
        "wait": "⏳ Подождите...",
        "recognizing": "🎧 Определяю песню...",
        "not_found": "😔 Песня не найдена.",
        "not_library": "Песня найдена, но аудио отсутствует в библиотеке:",
        "error": "❌ Произошла ошибка.",
        "no_audd": "AudD token не настроен.",
        "no_song": "Песня не найдена в библиотеке.",
        "language": "Выберите язык:",
        "audio_large": "Аудиофайл слишком большой.",
        "video_large": "Видеофайл слишком большой.",
        "bad_url": "Неверная ссылка.",
        "video_ready": "📥 Видео готово!",
        "music_help": "🎵 Отправьте название песни или аудио.",
        "video_help": "🎬 Отправьте ссылку или видео.",
    },

    "en": {
        "start": (
            "👋 Welcome!\n\n"
            "Send a song title or audio snippet.\n"
            "Send a video link.\n\n"
            "/music - Music\n"
            "/video - Video\n"
            "/help - Help\n"
            "/lang - Language"
        ),
        "wait": "⏳ Please wait...",
        "recognizing": "🎧 Identifying song...",
        "not_found": "😔 Song not found.",
        "not_library": "Song found, but audio is not in our library:",
        "error": "❌ An error occurred.",
        "no_audd": "AudD token is not configured.",
        "no_song": "Song not found in library.",
        "language": "Choose language:",
        "audio_large": "Audio file is too large.",
        "video_large": "Video file is too large.",
        "bad_url": "Invalid URL.",
        "video_ready": "📥 Video ready!",
        "music_help": "🎵 Send a song title or audio.",
        "video_help": "🎬 Send a video link or video file.",
    }
}


# ==================================================
# DATABASE
# ==================================================

def init_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'uz'
            )
        """)
        conn.commit()


def get_language(user_id):
    with sqlite3.connect(DATABASE_PATH) as conn:
        row = conn.execute(
            "SELECT language FROM user_settings WHERE user_id=?",
            (user_id,)
        ).fetchone()

    if row and row[0] in TEXTS:
        return row[0]

    return "uz"


def set_language(user_id, language):
    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("""
            INSERT INTO user_settings(user_id, language)
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET language=excluded.language
        """, (user_id, language))
        conn.commit()


def get_text(user_id):
    return TEXTS[get_language(user_id)]


# ==================================================
# YORDAMCHI FUNKSIYALAR
# ==================================================

def normalize(text):
    text = unicodedata.normalize("NFKD", text).casefold()

    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    text = "".join(
        char if char.isalnum() else " "
        for char in text
    )

    return re.sub(r"\s+", " ", text).strip()


def find_song(query):
    if not MUSIC_LIBRARY_DIR.exists():
        return None

    query = normalize(query)

    if not query:
        return None

    best_match = None
    best_score = 0

    for file in MUSIC_LIBRARY_DIR.rglob("*"):
        if not file.is_file():
            continue

        if file.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        filename = normalize(file.stem)

        if query == filename:
            return file

        if query in filename or filename in query:
            score = min(len(query), len(filename))

            if score > best_score:
                best_match = file
                best_score = score

    return best_match


async def send_song(message, title, artist=""):
    query = f"{artist} {title}".strip()

    file = find_song(query) or find_song(title)

    if not file:
        return False

    await message.answer_audio(
        FSInputFile(file),
        title=title[:64],
        performer=artist[:64] if artist else None
    )

    return True


async def delete_message(message):
    try:
        await message.delete()
    except Exception:
        pass


async def safe_delete(path):
    try:
        if path.exists():
            await asyncio.to_thread(path.unlink)
    except OSError:
        logger.warning("Faylni o‘chirishda xatolik: %s", path)


async def run_ffmpeg(args):
    def execute():
        subprocess.run(
            ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
            timeout=180
        )

    await asyncio.to_thread(execute)


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


async def download_telegram_file(file_id, destination):
    file = await bot.get_file(file_id)

    await bot.download_file(
        file.file_path,
        destination=destination
    )


# ==================================================
# START VA BUYRUQLAR
# ==================================================

@dp.message(Command("start"))
async def start_handler(message):
    await message.answer(
        get_text(message.from_user.id)["start"]
    )


@dp.message(Command("music"))
async def music_handler(message):
    await message.answer(
        get_text(message.from_user.id)["music_help"]
    )


@dp.message(Command("video"))
async def video_handler(message):
    await message.answer(
        get_text(message.from_user.id)["video_help"]
    )


@dp.message(Command("help"))
async def help_handler(message):
    user_id = message.from_user.id
    t = get_text(user_id)

    await message.answer(
        "ℹ️ Yordam:\n\n"
        f"{t['music_help']}\n"
        f"{t['video_help']}\n"
        "/lang - Tilni o‘zgartirish"
    )


# ==================================================
# TIL TANLASH
# ==================================================

@dp.message(Command("lang"))
async def language_handler(message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🇺🇿 Uzbek",
                callback_data="lang_uz"
            ),
            InlineKeyboardButton(
                text="🇷🇺 Russian",
                callback_data="lang_ru"
            ),
            InlineKeyboardButton(
                text="🇬🇧 English",
                callback_data="lang_en"
            )
        ]]
    )

    await message.answer(
        get_text(message.from_user.id)["language"],
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("lang_"))
async def language_callback(callback):
    language = callback.data.split("_")[1]

    if language not in TEXTS:
        await callback.answer()
        return

    set_language(callback.from_user.id, language)

    await callback.answer("OK")

    await callback.message.edit_text(
        TEXTS[language]["start"]
    )


# ==================================================
# DUMALOQ VIDEO
# ==================================================

async def create_round(message, file_id, prefix, file_size=None):
    user_id = message.from_user.id
    t = get_text(user_id)

    if file_size and file_size > MAX_VIDEO_BYTES:
        await message.answer(t["video_large"])
        return

    if not ffmpeg_available():
        await message.answer("FFmpeg o‘rnatilmagan.")
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    input_file = TEMP_DIR / f"{prefix}_input.mp4"
    output_file = TEMP_DIR / f"{prefix}_round.mp4"

    wait = await message.answer(t["wait"])

    try:
        await download_telegram_file(file_id, input_file)

        if input_file.stat().st_size > MAX_VIDEO_BYTES:
            await message.answer(t["video_large"])
            return

        await run_ffmpeg([
            "-i", str(input_file),
            "-t", str(MAX_VIDEO_SECONDS),
            "-vf",
            "crop='min(iw,ih)':'min(iw,ih)',scale=384:384,fps=30",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_file)
        ])

        if not output_file.exists():
            raise RuntimeError("Video yaratilmadi")

        await message.answer_video_note(
            FSInputFile(output_file)
        )

    except Exception:
        logger.exception("Round video error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)
        await safe_delete(input_file)
        await safe_delete(output_file)


@dp.message(F.video)
async def video_message(message):
    await create_round(
        message,
        message.video.file_id,
        f"round_{message.from_user.id}_{message.message_id}",
        message.video.file_size
    )


# ==================================================
# VIDEO YUKLASH
# ==================================================

def download_video(url, filename):
    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": filename,
        "max_filesize": MAX_VIDEO_BYTES,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 25,
        "retries": 2
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)


@dp.message(F.text.regexp(r"^https?://"))
async def url_message(message):
    t = get_text(message.from_user.id)
    url = message.text.strip()

    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        await message.answer(t["bad_url"])
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    filename = str(
        TEMP_DIR /
        f"video_{message.from_user.id}_{message.message_id}.%(ext)s"
    )

    wait = await message.answer(t["wait"])

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🎵 MP3",
                callback_data="extract"
            ),
            InlineKeyboardButton(
                text="🎥 Round",
                callback_data="round"
            )
        ]]
    )

    downloaded_path = None

    try:
        downloaded_path = await asyncio.to_thread(
            download_video,
            url,
            filename
        )

        downloaded_path = Path(downloaded_path)

        if not downloaded_path.exists():
            raise FileNotFoundError("Video topilmadi")

        if downloaded_path.stat().st_size > MAX_VIDEO_BYTES:
            await message.answer(t["video_large"])
            return

        await message.answer_video(
            FSInputFile(downloaded_path),
            caption=t["video_ready"],
            reply_markup=keyboard
        )

    except Exception:
        logger.exception("Video download error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)

        if downloaded_path:
            await safe_delete(downloaded_path)

        for candidate in TEMP_DIR.glob(
            f"video_{message.from_user.id}_{message.message_id}.*"
        ):
            await safe_delete(candidate)


# ==================================================
# VIDEODAN MP3
# ==================================================

@dp.callback_query(F.data == "extract")
async def extract_audio(callback):
    await callback.answer()

    video = callback.message.video

    if not video:
        return

    if video.file_size and video.file_size > MAX_VIDEO_BYTES:
        await callback.message.answer(
            get_text(callback.from_user.id)["video_large"]
        )
        return

    if not ffmpeg_available():
        await callback.message.answer("FFmpeg o‘rnatilmagan.")
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    input_file = TEMP_DIR / f"extract_{callback.id}.mp4"
    output_file = TEMP_DIR / f"extract_{callback.id}.mp3"

    wait = await callback.message.answer(
        get_text(callback.from_user.id)["wait"]
    )

    try:
        await download_telegram_file(
            video.file_id,
            input_file
        )

        await run_ffmpeg([
            "-i", str(input_file),
            "-vn",
            "-b:a", "192k",
            str(output_file)
        ])

        await callback.message.answer_audio(
            FSInputFile(output_file)
        )

    except Exception:
        logger.exception("MP3 extraction error")

        await callback.message.answer(
            get_text(callback.from_user.id)["error"]
        )

    finally:
        await delete_message(wait)
        await safe_delete(input_file)
        await safe_delete(output_file)


# ==================================================
# ROUND TUGMASI
# ==================================================

@dp.callback_query(F.data == "round")
async def round_callback(callback):
    await callback.answer()

    video = callback.message.video

    if video:
        await create_round(
            callback.message,
            video.file_id,
            f"button_{callback.id}",
            video.file_size
        )


# ==================================================
# AUDD MUSIQA ANIQLASH
# ==================================================

async def recognize_music(message, file_id, file_size):
    user_id = message.from_user.id
    t = get_text(user_id)

    if not AUDD_TOKEN:
        await message.answer(t["no_audd"])
        return

    if file_size and file_size > MAX_AUDIO_BYTES:
        await message.answer(t["audio_large"])
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    filename = TEMP_DIR / (
        f"recognize_{user_id}_{message.message_id}.audio"
    )

    wait = await message.answer(t["recognizing"])

    try:
        await download_telegram_file(file_id, filename)

        if filename.stat().st_size > MAX_AUDIO_BYTES:
            await message.answer(t["audio_large"])
            return

        timeout = aiohttp.ClientTimeout(total=60)

        with open(filename, "rb") as audio:
            form = aiohttp.FormData()

            form.add_field("api_token", AUDD_TOKEN)

            form.add_field(
                "file",
                audio,
                filename="audio_sample",
                content_type="application/octet-stream"
            )

            async with aiohttp.ClientSession(
                timeout=timeout
            ) as session:

                async with session.post(
                    "https://api.audd.io/",
                    data=form
                ) as response:

                    response.raise_for_status()
                    data = await response.json(content_type=None)

        result = data.get("result")

        if data.get("status") != "success" or not result:
            await message.answer(t["not_found"])
            return

        title = result.get("title", "Unknown")
        artist = result.get("artist", "Unknown")
        album = result.get("album", "")

        sent = await send_song(
            message,
            title,
            artist
        )

        if sent:
            return

        link = result.get("song_link", "")

        text = (
            f"🎵 {title}\n"
            f"🎤 {artist}\n"
        )

        if album:
            text += f"💿 {album}\n"

        text += f"\n{t['not_library']}"

        if link:
            text += f"\n{link}"

        await message.answer(text)

    except Exception:
        logger.exception("Recognition error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)
        await safe_delete(filename)


@dp.message(F.voice)
async def voice_handler(message):
    await recognize_music(
        message,
        message.voice.file_id,
        message.voice.file_size or 0
    )


@dp.message(F.audio)
async def audio_handler(message):
    await recognize_music(
        message,
        message.audio.file_id,
        message.audio.file_size or 0
    )


# ==================================================
# QO‘SHIQ NOMI BILAN QIDIRISH
# ==================================================

async def search_itunes(query):
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.get(
            "https://itunes.apple.com/search",
            params={
                "term": query,
                "entity": "song",
                "limit": 5
            }
        ) as response:

            response.raise_for_status()
            data = await response.json(content_type=None)

    return data.get("results", [])


@dp.message(F.text)
async def search_song(message):
    query = (message.text or "").strip()

    if (
        not query
        or query.startswith("/")
        or len(query) < 2
        or len(query) > 150
    ):
        return

    t = get_text(message.from_user.id)
    wait = await message.answer(t["wait"])

    try:
        file = find_song(query)

        if file:
            await message.answer_audio(FSInputFile(file))
            return

        results = await search_itunes(query)

        if not results:
            await message.answer(t["no_song"])
            return

        song = results[0]

        title = song.get("trackName", query)
        artist = song.get("artistName", "")
        album = song.get("collectionName", "")
        link = song.get("trackViewUrl", "")

        sent = await send_song(
            message,
            title,
            artist
        )

        if sent:
            return

        text = (
            f"🎵 {title}\n"
            f"🎤 {artist}\n"
        )

        if album:
            text += f"💿 {album}\n"

        text += f"\n{t['not_library']}"

        if link:
            text += f"\n{link}"

        await message.answer(text)

    except Exception:
        logger.exception("Song search error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)


# ==================================================
# WEB SERVER
# ==================================================

async def handle(request):
    return web.json_response({
        "status": "ok",
        "service": "Axmadov_music_bot"
    })


# ==================================================
# BOTNI ISHGA TUSHIRISH
# ==================================================

async def main():
    MUSIC_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    init_database()

    if not ffmpeg_available():
        logger.warning("FFmpeg o‘rnatilmagan!")

    app = web.Application()

    app.router.add_get("/", handle)
    app.router.add_get("/health", handle)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    logger.info("Web server started on port %s", PORT)
    logger.info("Axmadov Music Bot ishga tushdi!")

    try:
        await dp.start_polling(bot)

    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to‘xtatildi.")
