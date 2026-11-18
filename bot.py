
"""
AX MUSIC PREMIUM V4.0
Telegram Music + Audio Recognition + Video Bot
Python 3.10+
"""

from __future__ import annotations

import asyncio
import html
import logging
import os
import re
import shutil
import sqlite3
import uuid

from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlparse
from difflib import SequenceMatcher

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)


# =========================================================
# CONFIGURATION
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "").strip()
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "").strip()

PORT = int(os.getenv("PORT", "8080"))

BASE_DIR = Path(__file__).resolve().parent

MUSIC_DIR = BASE_DIR / "music_library"
TEMP_DIR = BASE_DIR / "tmp"
DATA_DIR = BASE_DIR / "data"

DB_PATH = DATA_DIR / "ax_music.sqlite3"

JAMENDO_URL = "https://api.jamendo.com/v3.0/tracks/"
AUDD_URL = "https://api.audd.io/"

MAX_RESULTS = 10
PAGE_SIZE = 5

MAX_AUDIO_SIZE = 48 * 1024 * 1024
MAX_VIDEO_SIZE = 20 * 1024 * 1024

MAX_VIDEO_DURATION = 60
MAX_QUERY_LENGTH = 150

CACHE_TTL_SECONDS = 1800
MAX_SEARCH_CACHE = 200

MAX_CONCURRENT_JOBS = max(
    1,
    int(os.getenv("MAX_CONCURRENT_JOBS", "8"))
)

SUPPORTED_AUDIO = {
    ".mp3", ".m4a", ".aac",
    ".ogg", ".wav", ".flac"
}

LANGUAGES = ("uz", "ru", "en")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger("AX_MUSIC")

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(
        parse_mode=ParseMode.HTML
    )
)

dp = Dispatcher()

SEARCH_CACHE = {}
VIDEO_CACHE = {}
USER_JOBS = {}

JOB_SEMAPHORE = asyncio.Semaphore(
    MAX_CONCURRENT_JOBS
)


# =========================================================
# TRANSLATIONS
# =========================================================

TEXT = {
    "uz": {
        "start": (
            "👑 <b>AX MUSIC PREMIUM</b>\n"
            "<i>PREMIUM MUSIC EXPERIENCE</i>\n\n"
            "🎵 Qo'shiq nomini yuboring.\n"
            "🎧 Audio yoki ovozli xabar yuboring.\n"
            "🎬 Video yuboring.\n\n"
            "✦ Musiqa olamiga xush kelibsiz!"
        ),
        "searching": "🔎 Musiqa qidirilmoqda...",
        "recognizing": "🎧 Audio aniqlanmoqda...",
        "not_found": "😔 Musiqa topilmadi.",
        "error": "❌ Xatolik yuz berdi.",
        "expired": "Qidiruv muddati tugagan.",
        "music": "🎵 Qo'shiq nomini yuboring.",
        "video": "🎬 Video yuboring. Maksimal hajm 20 MB.",
        "language": "🌐 Tilni tanlang:",
        "downloading": "🎵 Audio tayyorlanmoqda...",
        "audio_large": "Audio fayl juda katta.",
        "video_large": "Video fayl juda katta.",
        "ffmpeg": "FFmpeg o'rnatilmagan.",
        "download_error": "Audio yuklab olinmadi.",
        "empty": "Sevimli qo'shiqlar mavjud emas.",
        "stopped": "Jarayon to'xtatildi.",
        "nothing_to_stop": "Faol jarayon mavjud emas.",
        "video_received": "Video qabul qilindi.",
        "video_missing": "Video topilmadi. Qayta yuboring.",
        "favorites_added": "⭐ Sevimlilarga qo'shildi!",
        "not_yours": "Bu qidiruv sizga tegishli emas.",
        "full": "FULL AUDIO",
        "preview": "PREVIEW",
        "page": "SAHIFA",
        "match": "MOSLIK"
    },

    "ru": {
        "start": (
            "👑 <b>AX MUSIC PREMIUM</b>\n\n"
            "🎵 Отправьте название песни.\n"
            "🎧 Отправьте аудио.\n"
            "🎬 Отправьте видео."
        ),
        "searching": "🔎 Ищу музыку...",
        "recognizing": "🎧 Распознаю аудио...",
        "not_found": "😔 Музыка не найдена.",
        "error": "❌ Произошла ошибка.",
        "expired": "Поиск истёк.",
        "music": "🎵 Отправьте название песни.",
        "video": "🎬 Отправьте видео. Максимум 20 МБ.",
        "language": "🌐 Выберите язык:",
        "downloading": "🎵 Готовлю аудио...",
        "audio_large": "Аудиофайл слишком большой.",
        "video_large": "Видео слишком большое.",
        "ffmpeg": "FFmpeg не установлен.",
        "download_error": "Не удалось загрузить аудио.",
        "empty": "Избранных песен пока нет.",
        "stopped": "Задача остановлена.",
        "nothing_to_stop": "Нет активной задачи.",
        "video_received": "Видео получено.",
        "video_missing": "Видео не найдено.",
        "favorites_added": "⭐ Добавлено в избранное!",
        "not_yours": "Этот поиск принадлежит другому пользователю.",
        "full": "FULL AUDIO",
        "preview": "PREVIEW",
        "page": "СТРАНИЦА",
        "match": "СОВПАДЕНИЕ"
    },

    "en": {
        "start": (
            "👑 <b>AX MUSIC PREMIUM</b>\n\n"
            "🎵 Send a song title.\n"
            "🎧 Send audio.\n"
            "🎬 Send a video."
        ),
        "searching": "🔎 Searching music...",
        "recognizing": "🎧 Recognizing audio...",
        "not_found": "😔 Music not found.",
        "error": "❌ Something went wrong.",
        "expired": "Search expired.",
        "music": "🎵 Send a song title.",
        "video": "🎬 Send a video. Maximum 20 MB.",
        "language": "🌐 Choose language:",
        "downloading": "🎵 Preparing audio...",
        "audio_large": "Audio file is too large.",
        "video_large": "Video file is too large.",
        "ffmpeg": "FFmpeg is not installed.",
        "download_error": "Audio download failed.",
        "empty": "No favorite songs yet.",
        "stopped": "Task stopped.",
        "nothing_to_stop": "No active task.",
        "video_received": "Video received.",
        "video_missing": "Video not found.",
        "favorites_added": "⭐ Added to favorites!",
        "not_yours": "This search belongs to another user.",
        "full": "FULL AUDIO",
        "preview": "PREVIEW",
        "page": "PAGE",
        "match": "MATCH"
    }
}


# =========================================================
# DATABASE
# =========================================================

@contextmanager
def db_connection():

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    conn = sqlite3.connect(
        DB_PATH,
        timeout=20
    )

    try:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")

        yield conn

        conn.commit()

    finally:
        conn.close()


def init_database():

    with db_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT NOT NULL DEFAULT 'uz',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                link TEXT DEFAULT '',
                UNIQUE(user_id,title,artist),
                FOREIGN KEY(user_id)
                REFERENCES users(user_id)
                ON DELETE CASCADE
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                query TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_favorites_user
            ON favorites(user_id)
        """)

        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_user
            ON search_history(user_id)
        """)


def ensure_user(user_id):

    with db_connection() as conn:

        conn.execute(
            "INSERT OR IGNORE INTO users(user_id) VALUES(?)",
            (user_id,)
        )


def get_lang(user_id):

    ensure_user(user_id)

    with db_connection() as conn:

        row = conn.execute(
            "SELECT language FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

    if row and row[0] in LANGUAGES:
        return row[0]

    return "uz"


def tr(user_id, key):

    language = get_lang(user_id)

    return TEXT[language].get(
        key,
        TEXT["uz"].get(key, key)
    )


def set_lang(user_id, language):

    if language not in LANGUAGES:
        return

    ensure_user(user_id)

    with db_connection() as conn:

        conn.execute(
            "UPDATE users SET language=? WHERE user_id=?",
            (language, user_id)
        )


def add_favorite(user_id, song):

    ensure_user(user_id)

    with db_connection() as conn:

        conn.execute("""
            INSERT OR IGNORE INTO favorites
            (user_id,title,artist,link)
            VALUES(?,?,?,?)
        """, (
            user_id,
            song.get("title", "Unknown"),
            song.get("artist", "Unknown"),
            song.get("link", "")
        ))


def get_favorites(user_id):

    with db_connection() as conn:

        return conn.execute("""
            SELECT title,artist,link
            FROM favorites
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 50
        """, (user_id,)).fetchall()


def add_history(user_id, query):

    ensure_user(user_id)

    with db_connection() as conn:

        conn.execute("""
            INSERT INTO search_history(user_id,query)
            VALUES(?,?)
        """, (user_id, query[:MAX_QUERY_LENGTH]))


# =========================================================
# HELPERS
# =========================================================

def esc(value):

    return html.escape(
        str(value or ""),
        quote=True
    )


def normalize(value):

    value = str(value or "").casefold()

    value = "".join(
        char for char in value
        if char.isalnum() or char.isspace()
    )

    return re.sub(
        r"\s+",
        " ",
        value
    ).strip()


def match_score(query, title, artist=""):

    q = normalize(query)

    target = normalize(
        f"{title} {artist}"
    )

    if not q or not target:
        return 0

    similarity = SequenceMatcher(
        None,
        q,
        target
    ).ratio()

    q_words = set(q.split())
    target_words = set(target.split())

    overlap = (
        len(q_words & target_words)
        / max(1, len(q_words))
    )

    return min(
        100,
        round(max(similarity, overlap) * 100)
    )


def format_duration(seconds):

    try:
        seconds = max(0, int(seconds or 0))
    except (ValueError, TypeError):
        seconds = 0

    return (
        f"{seconds // 60:02d}:"
        f"{seconds % 60:02d}"
    )


def ffmpeg_available():

    return shutil.which("ffmpeg") is not None


def main_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎵 MUSIC SEARCH",
                    callback_data="music"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎬 VIDEO SERVICES",
                    callback_data="video"
                )
            ],
            [
                InlineKeyboardButton(
                    text="⭐ FAVORITES",
                    callback_data="favorites"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🌐 LANGUAGE",
                    callback_data="language"
                )
            ]
        ]
    )


def language_keyboard():

    return InlineKeyboardMarkup(
        inline_keyboard=[[
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
        ]]
    )


async def safe_delete(path):

    if path:
        try:
            await asyncio.to_thread(
                path.unlink,
                missing_ok=True
            )
        except OSError:
            logger.exception("File cleanup error")


async def download_telegram_file(file_id, destination):

    info = await bot.get_file(file_id)

    if not info.file_path:
        raise RuntimeError("Telegram file path missing")

    await bot.download_file(
        info.file_path,
        destination=destination
    )


async def run_ffmpeg(args):

    if not ffmpeg_available():
        raise RuntimeError("FFmpeg missing")

    process = await asyncio.create_subprocess_exec(
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
        "-y",
        *args,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.PIPE
    )

    try:

        _, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=180
        )

    except asyncio.TimeoutError:

        process.kill()
        await process.wait()

        raise RuntimeError("FFmpeg timeout")

    if process.returncode != 0:

        detail = (
            stderr.decode(
                "utf-8",
                "replace"
            )[-1500:]
        )

        raise RuntimeError(
            f"FFmpeg failed: {detail}"
        )


def validate_media_url(url):

    parsed = urlparse(url or "")

    host = (parsed.hostname or "").lower()

    if (
        parsed.scheme != "https"
        or not (
            host == "jamendo.com"
            or host.endswith(".jamendo.com")
        )
    ):
        raise ValueError("Untrusted audio URL")

    return url


# =========================================================
# LOCAL MUSIC LIBRARY
# =========================================================

def find_local_song(query):

    if not MUSIC_DIR.exists():
        return None

    q = normalize(query)

    if not q:
        return None

    best_path = None
    best_score = 0

    for file in MUSIC_DIR.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in SUPPORTED_AUDIO:
            continue

        name = normalize(file.stem)

        if name == q:
            return file

        score = SequenceMatcher(
            None,
            q,
            name
        ).ratio()

        if q in name or name in q:
            score = max(score, 0.90)

        if score > best_score:
            best_score = score
            best_path = file

    return (
        best_path
        if best_score >= 0.45
        else None
    )


# =========================================================
# JAMENDO SEARCH
# =========================================================

async def search_jamendo(query):

    if not JAMENDO_CLIENT_ID:
        raise RuntimeError(
            "JAMENDO_CLIENT_ID missing"
        )

    timeout = aiohttp.ClientTimeout(
        total=35,
        connect=12,
        sock_read=25
    )

    params = {
        "client_id": JAMENDO_CLIENT_ID,
        "format": "json",
        "limit": MAX_RESULTS,
        "search": query,
        "audioformat": "mp32",
        "audiodlformat": "mp32",
        "imagesize": 300,
        "include": "licenses"
    }

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.get(
            JAMENDO_URL,
            params=params
        ) as response:

            body = await response.text()

            if response.status != 200:
                raise RuntimeError(
                    f"Jamendo HTTP {response.status}: {body[:500]}"
                )

            data = await response.json(
                content_type=None
            )

    if not isinstance(data, dict):
        raise RuntimeError("Invalid Jamendo response")

    header = data.get("headers") or {}

    if header.get("status") != "success":
        raise RuntimeError(
            header.get("error_message", "Jamendo error")
        )

    results = []

    for item in data.get("results", []):

        title = item.get("name") or "Unknown"
        artist = item.get("artist_name") or "Unknown"

        allowed_raw = item.get(
            "audiodownload_allowed",
            False
        )

        allowed = (
            allowed_raw is True
            or str(allowed_raw).lower() == "true"
        )

        try:
            duration = int(
                item.get("duration") or 0
            )
        except (TypeError, ValueError):
            duration = 0

        results.append({
            "id": str(item.get("id") or ""),
            "title": title,
            "artist": artist,
            "duration": format_duration(duration),
            "duration_seconds": duration,
            "preview": item.get("audio") or "",
            "download": (
                item.get("audiodownload") or ""
                if allowed else ""
            ),
            "download_allowed": allowed,
            "link": item.get("shareurl") or "",
            "license": item.get("license_ccurl") or "",
            "score": match_score(
                query,
                title,
                artist
            )
        })

    results.sort(
        key=lambda x: (
            x["score"],
            x["download_allowed"]
        ),
        reverse=True
    )

    return results[:MAX_RESULTS]


# =========================================================
# SEARCH CACHE
# =========================================================

def prune_search_cache():

    now = asyncio.get_running_loop().time()

    expired = [
        key
        for key, value in SEARCH_CACHE.items()
        if now - value.get("created", now)
        > CACHE_TTL_SECONDS
    ]

    for key in expired:
        SEARCH_CACHE.pop(key, None)

    while len(SEARCH_CACHE) > MAX_SEARCH_CACHE:

        SEARCH_CACHE.pop(
            next(iter(SEARCH_CACHE)),
            None
        )


def get_owned_search(callback, search_id):

    cached = SEARCH_CACHE.get(search_id)

    if not cached:
        return None

    if cached["user_id"] != callback.from_user.id:
        return False

    now = asyncio.get_running_loop().time()

    if now - cached["created"] > CACHE_TTL_SECONDS:

        SEARCH_CACHE.pop(search_id, None)

        return None

    return cached


# =========================================================
# SEARCH KEYBOARD
# =========================================================

def make_search_keyboard(search_id, page, results):

    rows = [[
        InlineKeyboardButton(
            text="✦ PLAY BEST MATCH",
            callback_data=f"play:{search_id}:0"
        )
    ]]

    start = page * PAGE_SIZE

    end = min(
        start + PAGE_SIZE,
        len(results)
    )

    for index in range(start, end):

        song = results[index]

        rows.append([
            InlineKeyboardButton(
                text=(
                    f"♫ {index+1:02d} · "
                    f"{song['title'][:28]}"
                ),
                callback_data=(
                    f"play:{search_id}:{index}"
                )
            ),
            InlineKeyboardButton(
                text="☆",
                callback_data=(
                    f"fav:{search_id}:{index}"
                )
            )
        ])

    navigation = []

    if page > 0:

        navigation.append(
            InlineKeyboardButton(
                text="‹ PREVIOUS",
                callback_data=(
                    f"page:{search_id}:{page-1}"
                )
            )
        )

    if end < len(results):

        navigation.append(
            InlineKeyboardButton(
                text="NEXT ›",
                callback_data=(
                    f"page:{search_id}:{page+1}"
                )
            )
        )

    if navigation:
        rows.append(navigation)

    rows.append([
        InlineKeyboardButton(
            text="🏠 HOME",
            callback_data="home"
        )
    ])

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# =========================================================
# SEARCH RESULT TEXT
# =========================================================

def make_search_text(query, results, page, user_id):

    t = TEXT[get_lang(user_id)]

    best = results[0]

    pages = max(
        1,
        (len(results) + PAGE_SIZE - 1) // PAGE_SIZE
    )

    start = page * PAGE_SIZE

    current = results[
        start:start + PAGE_SIZE
    ]

    text = (
        "👑 <b>AX MUSIC</b>\n"
        "<i>PREMIUM MUSIC EXPERIENCE</i>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🔎 <b>{esc(query)}</b>\n\n"
        f"✦ <b>{esc(best['title'])}</b>\n"
        f"🎤 {esc(best['artist'])}\n"
        f"⏱ {esc(best['duration'])}\n"
        f"✨ {best['score']}% {t['match']}\n\n"
        f"📀 {len(results)} ta natija\n\n"
    )

    for index, song in enumerate(
        current,
        start=start
    ):

        status = (
            t["full"]
            if song.get("download_allowed")
            else t["preview"]
        )

        text += (
            f"<b>{index+1:02d}. "
            f"{esc(song['title'])}</b>\n"
            f"   {esc(song['artist'])}\n"
            f"   ⏱ {esc(song['duration'])}"
            f" · ✨ {song['score']}%"
            f" · {status}\n\n"
        )

    text += (
        "━━━━━━━━━━━━━━━━━━\n"
        f"✦ {t['page']} {page+1:02d}/{pages:02d}"
    )

    return text


# =========================================================
# MUSIC SEARCH
# =========================================================

async def perform_search(message, query):

    user_id = message.from_user.id

    query = query.strip()[:MAX_QUERY_LENGTH]

    if len(query) < 2:
        return

    ensure_user(user_id)

    add_history(user_id, query)

    wait = await message.answer(
        tr(user_id, "searching")
    )

    local_path = None
    results = []
    online_error = None

    try:

        local_path = await asyncio.to_thread(
            find_local_song,
            query
        )

        try:
            results = await search_jamendo(query)

        except Exception as exc:

            online_error = exc

            logger.warning(
                "Jamendo unavailable: %s",
                exc
            )

        if local_path:

            results.insert(0, {
                "id": "local",
                "title": local_path.stem,
                "artist": "AX MUSIC LIBRARY",
                "duration": "—",
                "duration_seconds": 0,
                "preview": "",
                "download": "",
                "download_allowed": True,
                "link": "",
                "license": "",
                "score": 100,
                "local_path": str(local_path.resolve())
            })

        if not results:

            text = tr(user_id, "not_found")

            if online_error:
                text += (
                    "\n\nOnline qidiruv vaqtincha ishlamayapti."
                )

            await wait.edit_text(text)

            return

        search_id = uuid.uuid4().hex[:10]

        SEARCH_CACHE[search_id] = {
            "user_id": user_id,
            "query": query,
            "results": results,
            "created": asyncio.get_running_loop().time()
        }

        prune_search_cache()

        await wait.edit_text(
            make_search_text(
                query,
                results,
                0,
                user_id
            ),
            reply_markup=make_search_keyboard(
                search_id,
                0,
                results
            )
        )

    except asyncio.CancelledError:

        await wait.edit_text(
            tr(user_id, "stopped")
        )

        raise

    except Exception:

        logger.exception("Search failed")

        await wait.edit_text(
            tr(user_id, "error")
        )


# =========================================================
# AUDIO DOWNLOAD
# =========================================================

async def download_audio(url, destination):

    url = validate_media_url(url)

    timeout = aiohttp.ClientTimeout(
        total=180,
        connect=15,
        sock_read=45
    )

    async with aiohttp.ClientSession(
        timeout=timeout
    ) as session:

        async with session.get(
            url,
            allow_redirects=False
        ) as response:

            if response.status in (
                301, 302, 303, 307, 308
            ):

                location = response.headers.get(
                    "Location",
                    ""
                )

                url = validate_media_url(location)

                async with session.get(
                    url,
                    allow_redirects=False
                ) as redirected:

                    await stream_audio(
                        redirected,
                        destination
                    )

            else:

                await stream_audio(
                    response,
                    destination
                )

    if (
        not destination.exists()
        or destination.stat().st_size == 0
    ):
        raise RuntimeError("Audio file is empty")


async def stream_audio(response, destination):

    response.raise_for_status()

    content_type = response.headers.get(
        "Content-Type",
        ""
    ).lower()

    if (
        "text/html" in content_type
        or "application/json" in content_type
    ):
        raise RuntimeError("Invalid audio response")

    total = 0

    with destination.open("wb") as output:

        async for chunk in response.content.iter_chunked(
            64 * 1024
        ):

            total += len(chunk)

            if total > MAX_AUDIO_SIZE:
                raise ValueError("Audio too large")

            output.write(chunk)


# =========================================================
# PLAY MUSIC
# =========================================================

async def play_song(callback, song):

    user_id = callback.from_user.id

    temp_path = None

    wait = await callback.message.answer(
        tr(user_id, "downloading")
    )

    try:

        if song.get("local_path"):

            local_path = Path(
                song["local_path"]
            ).resolve()

            if (
                MUSIC_DIR.resolve()
                not in local_path.parents
                or not local_path.is_file()
            ):
                raise RuntimeError(
                    "Invalid local music path"
                )

            await callback.message.answer_audio(
                FSInputFile(local_path),
                title=song["title"][:64],
                performer=song["artist"][:64],
                caption=(
                    "👑 <b>AX MUSIC PREMIUM</b>\n"
                    "✦ LOCAL MUSIC LIBRARY"
                )
            )

            return

        source = (
            song.get("download")
            if (
                song.get("download_allowed")
                and song.get("download")
            )
            else song.get("preview")
        )

        if not source:

            await callback.message.answer(
                "Bu trek uchun audio mavjud emas."
            )

            return

        temp_path = TEMP_DIR / (
            f"track_{uuid.uuid4().hex}.mp3"
        )

        await download_audio(
            source,
            temp_path
        )

        is_full = bool(
            song.get("download_allowed")
            and song.get("download")
        )

        caption = (
            "👑 <b>AX MUSIC PREMIUM</b>\n"
            f"✦ {'FULL AUDIO' if is_full else 'PREVIEW'}\n"
            f"🎤 {esc(song['artist'])}"
        )

        if not is_full and song.get("link"):

            caption += (
                f'\n\n<a href="{esc(song["link"])}">'
                "✦ OPEN OFFICIAL TRACK</a>"
            )

        if is_full and song.get("license"):

            caption += (
                f'\n\n<a href="{esc(song["license"])}">'
                "License information</a>"
            )

        await callback.message.answer_audio(
            FSInputFile(temp_path),
            title=song["title"][:64],
            performer=song["artist"][:64],
            caption=caption
        )

    finally:

        await safe_delete(temp_path)

        try:
            await wait.delete()
        except Exception:
            pass


# =========================================================
# USER JOB MANAGEMENT
# =========================================================

async def run_user_job(
    message,
    coroutine,
    user_id=None
):

    user_id = user_id or message.from_user.id

    current = USER_JOBS.get(user_id)

    if current and not current.done():

        await message.answer(
            "⏳ Sizda boshqa jarayon ishlayapti. "
            "/stop orqali to'xtatishingiz mumkin."
        )

        coroutine.close()

        return

    async def runner():

        async with JOB_SEMAPHORE:

            await coroutine

    task = asyncio.create_task(
        runner(),
        name=f"ax-job-{user_id}"
    )

    USER_JOBS[user_id] = task

    try:

        await task

    finally:

        if USER_JOBS.get(user_id) is task:
            USER_JOBS.pop(user_id, None)


# =========================================================
# BOT COMMANDS
# =========================================================

async def set_bot_commands():

    await bot.set_my_commands([
        BotCommand(
            command="start",
            description="Botni ishga tushirish"
        ),
        BotCommand(
            command="music",
            description="Musiqa platformasi"
        ),
        BotCommand(
            command="video",
            description="Video xizmatlari"
        ),
        BotCommand(
            command="help",
            description="Yordam"
        ),
        BotCommand(
            command="lang",
            description="Tilni o'zgartirish"
        ),
        BotCommand(
            command="stop",
            description="Jarayonni to'xtatish"
        )
    ])


# =========================================================
# START
# =========================================================

@dp.message(Command("start"))
async def start_handler(message):

    ensure_user(message.from_user.id)

    await message.answer(
        tr(message.from_user.id, "start"),
        reply_markup=main_keyboard()
    )


# =========================================================
# MUSIC COMMAND
# =========================================================

@dp.message(Command("music"))
async def music_handler(message):

    await message.answer(
        tr(message.from_user.id, "music"),
        reply_markup=main_keyboard()
    )


# =========================================================
# VIDEO COMMAND
# =========================================================

@dp.message(Command("video"))
async def video_command_handler(message):

    await message.answer(
        tr(message.from_user.id, "video"),
        reply_markup=main_keyboard()
    )


# =========================================================
# HELP COMMAND
# =========================================================

@dp.message(Command("help"))
async def help_handler(message):

    await message.answer(
        "👑 <b>AX MUSIC PREMIUM HELP</b>\n\n"
        "🎵 Qo'shiq nomini yuboring.\n"
        "🎧 Audio yoki ovozli xabar yuboring.\n"
        "🎬 Video yuboring.\n\n"
        "/start — Bosh menyu\n"
        "/music — Musiqa\n"
        "/video — Video\n"
        "/favorites — Sevimlilar\n"
        "/lang — Til\n"
        "/stop — Jarayonni to'xtatish"
    )


# =========================================================
# LANGUAGE COMMAND
# =========================================================

@dp.message(Command("lang"))
async def lang_handler(message):

    await message.answer(
        tr(message.from_user.id, "language"),
        reply_markup=language_keyboard()
    )


# =========================================================
# STOP COMMAND
# =========================================================

@dp.message(Command("stop"))
async def stop_handler(message):

    task = USER_JOBS.get(
        message.from_user.id
    )

    if task and not task.done():

        task.cancel()

        await message.answer(
            tr(message.from_user.id, "stopped")
        )

    else:

        await message.answer(
            tr(message.from_user.id, "nothing_to_stop")
        )


# =========================================================
# MAIN MENU CALLBACKS
# =========================================================

@dp.callback_query(F.data == "home")
async def home_callback(callback):

    await callback.answer()

    await callback.message.answer(
        tr(callback.from_user.id, "start"),
        reply_markup=main_keyboard()
    )


@dp.callback_query(F.data == "music")
async def music_callback(callback):

    await callback.answer()

    await callback.message.answer(
        tr(callback.from_user.id, "music")
    )


@dp.callback_query(F.data == "video")
async def video_callback(callback):

    await callback.answer()

    await callback.message.answer(
        tr(callback.from_user.id, "video")
    )


@dp.callback_query(F.data == "language")
async def language_callback(callback):

    await callback.answer()

    await callback.message.answer(
        tr(callback.from_user.id, "language"),
        reply_markup=language_keyboard()
    )


@dp.callback_query(F.data.startswith("lang:"))
async def set_language_callback(callback):

    language = callback.data.split(":", 1)[1]

    if language not in LANGUAGES:

        await callback.answer()

        return

    set_lang(
        callback.from_user.id,
        language
    )

    await callback.answer(
        "Language updated!"
    )

    await callback.message.edit_text(
        TEXT[language]["start"],
        reply_markup=main_keyboard()
    )


# =========================================================
# FAVORITES
# =========================================================

@dp.message(Command("favorites"))
async def favorites_handler(message):

    favorites = get_favorites(
        message.from_user.id
    )

    if not favorites:

        await message.answer(
            tr(message.from_user.id, "empty")
        )

        return

    lines = [
        "⭐ <b>AX MUSIC FAVORITES</b>\n"
    ]

    for i, (title, artist, link) in enumerate(
        favorites,
        1
    ):

        lines.append(
            f"<b>{i:02d}. {esc(title)}</b>\n"
            f"   {esc(artist)}"
        )

    await message.answer(
        "\n\n".join(lines)
    )


@dp.callback_query(F.data == "favorites")
async def favorites_callback(callback):

    await callback.answer()

    favorites = get_favorites(
        callback.from_user.id
    )

    if not favorites:

        await callback.message.answer(
            tr(callback.from_user.id, "empty")
        )

        return

    lines = [
        "⭐ <b>AX MUSIC FAVORITES</b>\n"
    ]

    for i, (title, artist, link) in enumerate(
        favorites,
        1
    ):

        lines.append(
            f"<b>{i:02d}. {esc(title)}</b>\n"
            f"   {esc(artist)}"
        )

    await callback.message.answer(
        "\n\n".join(lines)
    )


# =========================================================
# PAGINATION
# =========================================================

@dp.callback_query(F.data.startswith("page:"))
async def page_callback(callback):

    try:

        _, search_id, page_text = (
            callback.data.split(":")
        )

        cached = get_owned_search(
            callback,
            search_id
        )

        if cached is None:

            await callback.answer(
                tr(callback.from_user.id, "expired"),
                show_alert=True
            )

            return

        if cached is False:

            await callback.answer(
                tr(callback.from_user.id, "not_yours"),
                show_alert=True
            )

            return

        results = cached["results"]

        page = int(page_text)

        max_page = max(
            0,
            (len(results) - 1) // PAGE_SIZE
        )

        if not 0 <= page <= max_page:

            await callback.answer()

            return

        await callback.message.edit_text(
            make_search_text(
                cached["query"],
                results,
                page,
                callback.from_user.id
            ),
            reply_markup=make_search_keyboard(
                search_id,
                page,
                results
            )
        )

        await callback.answer()

    except Exception:

        logger.exception("Pagination error")

        await callback.answer(
            tr(callback.from_user.id, "error"),
            show_alert=True
        )


# =========================================================
# ADD FAVORITE CALLBACK
# =========================================================

@dp.callback_query(F.data.startswith("fav:"))
async def favorite_callback(callback):

    try:

        _, search_id, index_text = (
            callback.data.split(":")
        )

        cached = get_owned_search(
            callback,
            search_id
        )

        if cached is None or cached is False:

            await callback.answer(
                tr(callback.from_user.id, "expired"),
                show_alert=True
            )

            return

        index = int(index_text)

        if not 0 <= index < len(cached["results"]):

            await callback.answer(
                "Track not found",
                show_alert=True
            )

            return

        add_favorite(
            callback.from_user.id,
            cached["results"][index]
        )

        await callback.answer(
            tr(callback.from_user.id, "favorites_added")
        )

    except Exception:

        logger.exception("Favorite error")

        await callback.answer(
            tr(callback.from_user.id, "error"),
            show_alert=True
        )


# =========================================================
# PLAY CALLBACK
# =========================================================

@dp.callback_query(F.data.startswith("play:"))
async def play_callback(callback):

    try:

        _, search_id, index_text = (
            callback.data.split(":")
        )

        cached = get_owned_search(
            callback,
            search_id
        )

        if cached is None:

            await callback.answer(
                tr(callback.from_user.id, "expired"),
                show_alert=True
            )

            return

        if cached is False:

            await callback.answer(
                tr(callback.from_user.id, "not_yours"),
                show_alert=True
            )

            return

        index = int(index_text)

        if not 0 <= index < len(cached["results"]):

            await callback.answer(
                "Track not found",
                show_alert=True
            )

            return

        await callback.answer(
            "Preparing audio..."
        )

        await run_user_job(
            callback.message,
            play_song(
                callback,
                cached["results"][index]
            ),
            callback.from_user.id
        )

    except Exception:

        logger.exception("Play callback error")

        await callback.message.answer(
            tr(callback.from_user.id, "download_error")
        )


# =========================================================
# AUDIO RECOGNITION
# =========================================================

async def recognize_audio(
    message,
    file_id,
    file_size
):

    user_id = message.from_user.id

    if not AUDD_TOKEN:

        await message.answer(
            "⚠️ AUDD_TOKEN sozlanmagan."
        )

        return

    if file_size and file_size > MAX_AUDIO_SIZE:

        await message.answer(
            tr(user_id, "audio_large")
        )

        return

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    path = TEMP_DIR / (
        f"recognize_{uuid.uuid4().hex}.audio"
    )

    wait = await message.answer(
        tr(user_id, "recognizing")
    )

    try:

        await download_telegram_file(
            file_id,
            path
        )

        if path.stat().st_size > MAX_AUDIO_SIZE:

            await message.answer(
                tr(user_id, "audio_large")
            )

            return

        timeout = aiohttp.ClientTimeout(
            total=60,
            connect=15
        )

        with path.open("rb") as audio:

            form = aiohttp.FormData()

            form.add_field(
                "api_token",
                AUDD_TOKEN
            )

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
                    AUDD_URL,
                    data=form
                ) as response:

                    response.raise_for_status()

                    data = await response.json(
                        content_type=None
                    )

        result = (
            data.get("result")
            if isinstance(data, dict)
            else None
        )

        if not result:

            await message.answer(
                tr(user_id, "not_found")
            )

            return

        query = (
            f"{result.get('artist', '')} "
            f"{result.get('title', '')}"
        ).strip()

        if query:

            await perform_search(
                message,
                query
            )

        else:

            await message.answer(
                tr(user_id, "not_found")
            )

    except asyncio.CancelledError:

        raise

    except Exception:

        logger.exception("Audio recognition error")

        await message.answer(
            tr(user_id, "error")
        )

    finally:

        try:
            await wait.delete()
        except Exception:
            pass

        await safe_delete(path)


@dp.message(F.voice)
async def voice_handler(message):

    await run_user_job(
        message,
        recognize_audio(
            message,
            message.voice.file_id,
            message.voice.file_size
        )
    )


@dp.message(F.audio)
async def audio_handler(message):

    await run_user_job(
        message,
        recognize_audio(
            message,
            message.audio.file_id,
            message.audio.file_size
        )
    )


# =========================================================
# VIDEO UPLOAD
# =========================================================

@dp.message(F.video)
async def video_handler(message):

    video = message.video

    if (
        video.file_size
        and video.file_size > MAX_VIDEO_SIZE
    ):

        await message.answer(
            tr(message.from_user.id, "video_large")
        )

        return

    key = (
        message.chat.id,
        message.from_user.id
    )

    VIDEO_CACHE[key] = {
        "file_id": video.file_id,
        "file_size": video.file_size or 0,
        "message_id": message.message_id
    }

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[[
            InlineKeyboardButton(
                text="🎵 MP3",
                callback_data=f"extract:{message.message_id}"
            ),
            InlineKeyboardButton(
                text="🎥 ROUND",
                callback_data=f"round:{message.message_id}"
            )
        ]]
    )

    await message.answer(
        tr(message.from_user.id, "video_received"),
        reply_markup=keyboard
    )


def get_cached_video(callback, message_id):

    key = (
        callback.message.chat.id,
        callback.from_user.id
    )

    cached = VIDEO_CACHE.get(key)

    if not cached:
        return None

    if cached["message_id"] != message_id:
        return None

    return cached


# =========================================================
# VIDEO TO MP3
# =========================================================

async def convert_video_to_mp3(
    callback,
    cached
):

    input_path = TEMP_DIR / (
        f"video_{uuid.uuid4().hex}.mp4"
    )

    output_path = TEMP_DIR / (
        f"audio_{uuid.uuid4().hex}.mp3"
    )

    wait = await callback.message.answer(
        "🎵 <b>MP3 CONVERSION</b>\n\nTayyorlanmoqda..."
    )

    try:

        TEMP_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        await download_telegram_file(
            cached["file_id"],
            input_path
        )

        if input_path.stat().st_size > MAX_VIDEO_SIZE:
            raise ValueError("Video too large")

        await run_ffmpeg([
            "-i", str(input_path),
            "-vn",
            "-b:a", "192k",
            str(output_path)
        ])

        if (
            not output_path.exists()
            or output_path.stat().st_size == 0
            or output_path.stat().st_size > MAX_AUDIO_SIZE
        ):
            raise ValueError("Invalid MP3 output")

        await callback.message.answer_audio(
            FSInputFile(output_path),
            caption=(
                "👑 <b>AX MUSIC PREMIUM</b>\n"
                "✦ MP3 AUDIO"
            )
        )

    except asyncio.CancelledError:

        raise

    except Exception:

        logger.exception("MP3 conversion error")

        await callback.message.answer(
            tr(callback.from_user.id, "error")
        )

    finally:

        try:
            await wait.delete()
        except Exception:
            pass

        await safe_delete(input_path)
        await safe_delete(output_path)


@dp.callback_query(F.data.startswith("extract:"))
async def extract_callback(callback):

    await callback.answer()

    try:

        message_id = int(
            callback.data.split(":")[1]
        )

        cached = get_cached_video(
            callback,
            message_id
        )

        if not cached:

            await callback.message.answer(
                tr(callback.from_user.id, "video_missing")
            )

            return

        if not ffmpeg_available():

            await callback.message.answer(
                tr(callback.from_user.id, "ffmpeg")
            )

            return

        await run_user_job(
            callback.message,
            convert_video_to_mp3(
                callback,
                cached
            ),
            callback.from_user.id
        )

    except Exception:

        logger.exception("Video conversion callback error")

        await callback.message.answer(
            tr(callback.from_user.id, "error")
        )


# =========================================================
# VIDEO TO ROUND
# =========================================================

async def convert_to_round(
    callback,
    cached
):

    input_path = TEMP_DIR / (
        f"round_in_{uuid.uuid4().hex}.mp4"
    )

    output_path = TEMP_DIR / (
        f"round_out_{uuid.uuid4().hex}.mp4"
    )

    wait = await callback.message.answer(
        "🎥 <b>ROUND VIDEO</b>\n\nTayyorlanmoqda..."
    )

    try:

        TEMP_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        await download_telegram_file(
            cached["file_id"],
            input_path
        )

        if input_path.stat().st_size > MAX_VIDEO_SIZE:
            raise ValueError("Video too large")

        await run_ffmpeg([
            "-i", str(input_path),
            "-t", str(MAX_VIDEO_DURATION),
            "-vf",
            "crop='min(iw,ih)':'min(iw,ih)',"
            "scale=384:384,fps=30",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_path)
        ])

        if (
            not output_path.exists()
            or output_path.stat().st_size == 0
        ):
            raise ValueError("Invalid round video")

        await callback.message.answer_video_note(
            FSInputFile(output_path)
        )

    except asyncio.CancelledError:

        raise

    except Exception:

        logger.exception("Round conversion error")

        await callback.message.answer(
            tr(callback.from_user.id, "error")
        )

    finally:

        try:
            await wait.delete()
        except Exception:
            pass

        await safe_delete(input_path)
        await safe_delete(output_path)


@dp.callback_query(F.data.startswith("round:"))
async def round_callback(callback):

    await callback.answer()

    try:

        message_id = int(
            callback.data.split(":")[1]
        )

        cached = get_cached_video(
            callback,
            message_id
        )

        if not cached:

            await callback.message.answer(
                tr(callback.from_user.id, "video_missing")
            )

            return

        if not ffmpeg_available():

            await callback.message.answer(
                tr(callback.from_user.id, "ffmpeg")
            )

            return

        await run_user_job(
            callback.message,
            convert_to_round(
                callback,
                cached
            ),
            callback.from_user.id
        )

    except Exception:

        logger.exception("Round callback error")

        await callback.message.answer(
            tr(callback.from_user.id, "error")
        )


# =========================================================
# TEXT SEARCH
# =========================================================

@dp.message(F.text)
async def text_search_handler(message):

    query = (
        message.text or ""
    ).strip()

    if (
        not query
        or query.startswith("/")
        or len(query) < 2
        or len(query) > MAX_QUERY_LENGTH
    ):
        return

    await run_user_job(
        message,
        perform_search(
            message,
            query
        )
    )


# =========================================================
# HEALTH SERVER
# =========================================================

async def health_handler(request):

    return web.json_response({
        "status": "online",
        "service": "AX MUSIC PREMIUM",
        "version": "4.0"
    })


# =========================================================
# STARTUP
# =========================================================

async def on_startup():

    MUSIC_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    init_database()

    await set_bot_commands()

    logger.info("AX MUSIC PREMIUM V4.0 started")

    if not JAMENDO_CLIENT_ID:

        logger.warning(
            "JAMENDO_CLIENT_ID missing"
        )

    if not AUDD_TOKEN:

        logger.warning(
            "AUDD_TOKEN missing"
        )

    if not ffmpeg_available():

        logger.warning(
            "FFmpeg missing"
        )


# =========================================================
# MAIN
# =========================================================

async def main():

    await on_startup()

    app = web.Application()

    app.router.add_get(
        "/",
        health_handler
    )

    app.router.add_get(
        "/health",
        health_handler
    )

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    logger.info(
        "Health server running on port %s",
        PORT
    )

    try:

        await dp.start_polling(bot)

    finally:

        for task in list(USER_JOBS.values()):

            if not task.done():
                task.cancel()

        if USER_JOBS:

            await asyncio.gather(
                *USER_JOBS.values(),
                return_exceptions=True
            )

        await runner.cleanup()

        await bot.session.close()


if __name__ == "__main__":

    try:

        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):

        logger.info("AX MUSIC stopped")
