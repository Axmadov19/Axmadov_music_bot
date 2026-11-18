import os
import re
import asyncio
import logging
import subprocess
import unicodedata
import sqlite3
import shutil
import uuid
import html

from pathlib import Path
from urllib.parse import urlparse
from difflib import SequenceMatcher

import aiohttp
import yt_dlp

from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.exceptions import TelegramBadRequest


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

PAGE_SIZE = 4
MAX_SEARCH_RESULTS = 12

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Qidiruv natijalari
SEARCH_CACHE = {}

# Telegram video xabarlari uchun vaqtinchalik ma'lumot
VIDEO_CACHE = {}


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
        "searching": "🔎 Musiqa qidirilmoqda...",
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
        "results": "🎧 <b>AX MUSIC QIDIRUV</b>",
        "match": "Moslik",
        "page": "Sahifa",
        "play": "▶️ Tinglash",
        "expired": "Qidiruv muddati tugagan. Qaytadan qidiring.",
        "no_preview": "Bu qo‘shiq uchun tinglash namunasi mavjud emas.",
        "preview": "30 soniyalik tinglash namunasi",
        "ffmpeg": "FFmpeg o‘rnatilmagan.",
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
        "searching": "🔎 Ищем музыку...",
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
        "results": "🎧 <b>AX MUSIC ПОИСК</b>",
        "match": "Совпадение",
        "page": "Страница",
        "play": "▶️ Слушать",
        "expired": "Срок поиска истёк. Попробуйте снова.",
        "no_preview": "Для этой песни нет доступного фрагмента.",
        "preview": "30-секундный фрагмент",
        "ffmpeg": "FFmpeg не установлен.",
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
        "searching": "🔎 Searching for music...",
        "not_found": "😔 Song not found.",
        "not_library": "Song found, but audio is not in our library:",
        "error": "❌ An error occurred.",
        "no_audd": "AudD token is not configured.",
        "no_song": "Song not found in library.",
        "language": "Choose a language:",
        "audio_large": "Audio file is too large.",
        "video_large": "Video file is too large.",
        "bad_url": "Invalid URL.",
        "video_ready": "📥 Video ready!",
        "music_help": "🎵 Send a song title or audio.",
        "video_help": "🎬 Send a video link or video file.",
        "results": "🎧 <b>AX MUSIC SEARCH</b>",
        "match": "Match",
        "page": "Page",
        "play": "▶️ Listen",
        "expired": "Search expired. Please search again.",
        "no_preview": "No preview is available for this song.",
        "preview": "30-second preview",
        "ffmpeg": "FFmpeg is not installed.",
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


def calculate_match(query, title, artist=""):
    query = normalize(query)
    target = normalize(f"{title} {artist}")

    if not query or not target:
        return 0

    score = SequenceMatcher(None, query, target).ratio()

    query_words = set(query.split())
    target_words = set(target.split())

    if query_words:
        overlap = len(query_words & target_words) / len(query_words)
        score = max(score, overlap)

    return min(100, round(score * 100))


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

        score = SequenceMatcher(None, query, filename).ratio()

        if query in filename or filename in query:
            score = max(score, 0.9)

        if score > best_score:
            best_match = file
            best_score = score

    if best_score >= 0.45:
        return best_match

    return None


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
        if path and path.exists():
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
# ITUNES MUSIQA QIDIRISH
# ==================================================

async def search_itunes(query):
    timeout = aiohttp.ClientTimeout(total=30)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(
            "https://itunes.apple.com/search",
            params={
                "term": query,
                "entity": "song",
                "limit": MAX_SEARCH_RESULTS
            }
        ) as response:

            response.raise_for_status()
            data = await response.json(content_type=None)

    results = []

    for item in data.get("results", []):
        title = item.get("trackName", "Unknown")
        artist = item.get("artistName", "Unknown")

        results.append({
            "title": title,
            "artist": artist,
            "album": item.get("collectionName", ""),
            "preview": item.get("previewUrl"),
            "link": item.get("trackViewUrl"),
            "artwork": item.get("artworkUrl100"),
            "score": calculate_match(query, title, artist)
        })

    results.sort(
        key=lambda item: item["score"],
        reverse=True
    )

    return results


def make_music_keyboard(search_id, page, results):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE

    current = results[start:end]
    rows = []

    for index, song in enumerate(current, start=start):
        rows.append([
            InlineKeyboardButton(
                text=f"▶️ {song['title'][:28]}",
                callback_data=f"play:{search_id}:{index}"
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️",
                callback_data=f"page:{search_id}:{page - 1}"
            )
        )

    if end < len(results):
        navigation.append(
            InlineKeyboardButton(
                text="➡️",
                callback_data=f"page:{search_id}:{page + 1}"
            )
        )

    if navigation:
        rows.append(navigation)

    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_results_text(query, results, page, user_id):
    t = get_text(user_id)

    start = page * PAGE_SIZE
    current = results[start:start + PAGE_SIZE]

    safe_query = html.escape(query)

    text = (
        f"{t['results']}\n"
        "━━━━━━━━━━━━━━━━━━\n"
        f"🔎 <b>{safe_query}</b>\n\n"
    )

    for number, song in enumerate(current, start=start + 1):
        title = html.escape(song["title"])
        artist = html.escape(song["artist"])
        score = song["score"]

        text += (
            f"<b>{number}. {title}</b>\n"
            f"👤 {artist}\n"
            f"🎯 {t['match']}: <b>{score}%</b>\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

    total_pages = max(
        1,
        (len(results) + PAGE_SIZE - 1) // PAGE_SIZE
    )

    text += f"\n📄 {t['page']}: {page + 1}/{total_pages}"
    text += "\n\n<i>Qo‘shiqni tinglash uchun ▶️ tugmasini bosing.</i>"

    return text


async def show_music_results(message, query):
    user_id = message.from_user.id
    t = get_text(user_id)

    wait = await message.answer(t["searching"])

    try:
        results = await search_itunes(query)

        if not results:
            await wait.edit_text(t["not_found"])
            return

        search_id = uuid.uuid4().hex[:10]

        SEARCH_CACHE[search_id] = {
            "query": query,
            "results": results
        }

        # Kesh hajmini cheklash
        if len(SEARCH_CACHE) > 100:
            first_key = next(iter(SEARCH_CACHE))
            SEARCH_CACHE.pop(first_key, None)

        text = make_results_text(
            query,
            results,
            0,
            user_id
        )

        keyboard = make_music_keyboard(
            search_id,
            0,
            results
        )

        await wait.edit_text(
            text,
            reply_markup=keyboard
        )

    except Exception:
        logger.exception("Music search error")
        await wait.edit_text(t["error"])


# ==================================================
# MUSIQA SAHIFALASH
# ==================================================

@dp.callback_query(F.data.startswith("page:"))
async def page_callback(callback):
    try:
        _, search_id, page_text = callback.data.split(":")
        page = int(page_text)

        cached = SEARCH_CACHE.get(search_id)

        if not cached:
            await callback.answer(
                get_text(callback.from_user.id)["expired"],
                show_alert=True
            )
            return

        results = cached["results"]
        query = cached["query"]

        text = make_results_text(
            query,
            results,
            page,
            callback.from_user.id
        )

        keyboard = make_music_keyboard(
            search_id,
            page,
            results
        )

        await callback.message.edit_text(
            text,
            reply_markup=keyboard
        )

        await callback.answer()

    except Exception:
        logger.exception("Pagination error")
        await callback.answer("Xatolik yuz berdi.", show_alert=True)


# ==================================================
# MUSIQANI IJRO ETISH
# ==================================================

async def download_preview(url, destination):
    if not url:
        return False

    timeout = aiohttp.ClientTimeout(total=40)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                if response.status != 200:
                    return False

                content = await response.read()

                if len(content) > MAX_AUDIO_BYTES:
                    return False

                destination.write_bytes(content)

        return destination.exists()

    except Exception:
        logger.exception("Preview download error")
        return False


@dp.callback_query(F.data.startswith("play:"))
async def play_callback(callback):
    try:
        _, search_id, index_text = callback.data.split(":")
        index = int(index_text)

        cached = SEARCH_CACHE.get(search_id)

        if not cached:
            await callback.answer(
                get_text(callback.from_user.id)["expired"],
                show_alert=True
            )
            return

        results = cached["results"]

        if index < 0 or index >= len(results):
            await callback.answer("Qo‘shiq topilmadi.")
            return

        song = results[index]

        await callback.answer("Musiqa tayyorlanmoqda...")

        # Avval o‘z kutubxonamizdan qidiramiz
        local_file = (
            find_song(f"{song['artist']} {song['title']}")
            or find_song(song["title"])
        )

        if local_file:
            await callback.message.answer_audio(
                FSInputFile(local_file),
                title=song["title"][:64],
                performer=song["artist"][:64]
            )
            return

        # Kutubxonada bo‘lmasa, qisqa preview
        if not song.get("preview"):
            await callback.message.answer(
                get_text(callback.from_user.id)["no_preview"]
            )
            return

        path = TEMP_DIR / f"preview_{uuid.uuid4().hex}.m4a"
        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        try:
            success = await download_preview(
                song["preview"],
                path
            )

            if not success:
                await callback.message.answer("Audio yuklab olinmadi.")
                return

            await callback.message.answer_audio(
                FSInputFile(path),
                title=song["title"][:64],
                performer=song["artist"][:64],
                caption=get_text(callback.from_user.id)["preview"]
            )

        finally:
            await safe_delete(path)

    except Exception:
        logger.exception("Play callback error")
        await callback.message.answer(
            get_text(callback.from_user.id)["error"]
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
        "ℹ️ <b>Yordam:</b>\n\n"
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

async def create_round(
    message,
    file_id,
    prefix,
    file_size=None,
    user_id=None
):
    if user_id is None:
        user_id = message.from_user.id

    t = get_text(user_id)

    if file_size and file_size > MAX_VIDEO_BYTES:
        await message.answer(t["video_large"])
        return

    if not ffmpeg_available():
        await message.answer(t["ffmpeg"])
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    input_file = TEMP_DIR / f"{prefix}_input.mp4"
    output_file = TEMP_DIR / f"{prefix}_round.mp4"

    wait = await message.answer(t["wait"])

    try:
        await download_telegram_file(
            file_id,
            input_file
        )

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

        # yt-dlp yaratgan qo‘shimcha fayllarni ham tozalash
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
        await callback.message.answer(
            get_text(callback.from_user.id)["ffmpeg"]
        )
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

        if output_file.stat().st_size > MAX_AUDIO_BYTES:
            await callback.message.answer(
                get_text(callback.from_user.id)["audio_large"]
            )
            return

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
            video.file_size,
            user_id=callback.from_user.id
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
        await download_telegram_file(
            file_id,
            filename
        )

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

        # Kutubxonadan topilsa, audio yuboriladi
        sent = await send_song(
            message,
            title,
            artist
        )

        if sent:
            return

        link = result.get("song_link", "")

        text = (
            f"🎵 <b>{html.escape(title)}</b>\n"
            f"🎤 {html.escape(artist)}\n"
        )

        if album:
            text += f"💿 {html.escape(album)}\n"

        text += f"\n{t['not_library']}"

        if link:
            text += f"\n🔗 {html.escape(link)}"

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

    # Havolalar video handler orqali ishlanadi
    if re.match(r"^https?://", query, re.IGNORECASE):
        return

    await show_music_results(message, query)


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
