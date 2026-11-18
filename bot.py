
import os
import re
import html
import uuid
import asyncio
import logging
import sqlite3
import shutil
import subprocess
import unicodedata

from pathlib import Path
from difflib import SequenceMatcher

import aiohttp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# =========================================================
# AX MUSIC PREMIUM CONFIGURATION
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

MAX_RESULTS = 10
PAGE_SIZE = 5

MAX_AUDIO_SIZE = 48 * 1024 * 1024
MAX_VIDEO_SIZE = 20 * 1024 * 1024
MAX_VIDEO_DURATION = 60

SUPPORTED_AUDIO = {
    ".mp3", ".m4a", ".aac",
    ".ogg", ".wav", ".flac"
}

LANGUAGES = ("uz", "ru", "en")

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN topilmadi. Environment sozlamasini tekshiring."
    )


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


# =========================================================
# TRANSLATIONS
# =========================================================

TEXT = {
    "uz": {
        "start": (
            "👑 <b>AX MUSIC PREMIUM</b>\n\n"
            "Musiqa olamiga xush kelibsiz!\n\n"
            "🎵 Qo'shiq nomini yuboring.\n"
            "🎧 Ovozli parcha yuboring.\n"
            "🎬 Video yuboring.\n\n"
            "✦ <i>Discover your music.</i>"
        ),
        "searching": "✦ <b>AX MUSIC</b>\n\n🔎 Musiqa qidirilmoqda...",
        "recognizing": "🎧 Audio aniqlanmoqda...",
        "not_found": "😔 Mos musiqa topilmadi.",
        "error": "❌ Xatolik yuz berdi. Keyinroq urinib ko'ring.",
        "api_error": "Musiqa qidiruv serverida muammo bor.",
        "expired": "Qidiruv muddati tugagan. Qaytadan qidiring.",
        "music": "🎵 Qo'shiq nomini yozing.",
        "video": "🎬 Video yuboring.",
        "language": "🌐 Tilni tanlang:",
        "full": "FULL AUDIO",
        "preview": "PREVIEW",
        "downloading": "🎵 Audio tayyorlanmoqda...",
        "audio_large": "Audio fayl juda katta.",
        "video_large": "Video fayl juda katta.",
        "ffmpeg": "FFmpeg o'rnatilmagan.",
        "video_ready": "✦ Video tayyor!",
        "download_error": "Audio yuklab olinmadi.",
        "home": "🏠 Bosh menyu",
        "favorites": "⭐ Sevimlilar",
        "empty": "Hozircha sevimli qo'shiqlar yo'q."
    },
    "ru": {
        "start": (
            "👑 <b>AX MUSIC PREMIUM</b>\n\n"
            "Добро пожаловать!\n\n"
            "🎵 Отправьте название песни.\n"
            "🎧 Отправьте аудиофрагмент.\n"
            "🎬 Отправьте видео."
        ),
        "searching": "✦ <b>AX MUSIC</b>\n\n🔎 Ищу музыку...",
        "recognizing": "🎧 Определяю аудио...",
        "not_found": "😔 Музыка не найдена.",
        "error": "❌ Произошла ошибка.",
        "api_error": "Ошибка музыкального сервера.",
        "expired": "Поиск истёк. Попробуйте снова.",
        "music": "🎵 Отправьте название песни.",
        "video": "🎬 Отправьте видео.",
        "language": "🌐 Выберите язык:",
        "full": "FULL AUDIO",
        "preview": "PREVIEW",
        "downloading": "🎵 Готовлю аудио...",
        "audio_large": "Аудиофайл слишком большой.",
        "video_large": "Видео слишком большое.",
        "ffmpeg": "FFmpeg не установлен.",
        "video_ready": "✦ Видео готово!",
        "download_error": "Не удалось загрузить аудио.",
        "home": "🏠 Главное меню",
        "favorites": "⭐ Избранное",
        "empty": "Избранных песен пока нет."
    },
    "en": {
        "start": (
            "👑 <b>AX MUSIC PREMIUM</b>\n\n"
            "Welcome to your music experience!\n\n"
            "🎵 Send a song title.\n"
            "🎧 Send an audio snippet.\n"
            "🎬 Send a video."
        ),
        "searching": "✦ <b>AX MUSIC</b>\n\n🔎 Searching music...",
        "recognizing": "🎧 Recognizing audio...",
        "not_found": "😔 No matching music found.",
        "error": "❌ Something went wrong.",
        "api_error": "Music server error.",
        "expired": "Search expired. Try again.",
        "music": "🎵 Send a song title.",
        "video": "🎬 Send a video.",
        "language": "🌐 Choose language:",
        "full": "FULL AUDIO",
        "preview": "PREVIEW",
        "downloading": "🎵 Preparing audio...",
        "audio_large": "Audio file is too large.",
        "video_large": "Video file is too large.",
        "ffmpeg": "FFmpeg is not installed.",
        "video_ready": "✦ Video ready!",
        "download_error": "Audio download failed.",
        "home": "🏠 Main menu",
        "favorites": "⭐ Favorites",
        "empty": "No favorite songs yet."
    }
}


# =========================================================
# DATABASE
# =========================================================

def db_connection():
    return sqlite3.connect(DB_PATH, timeout=20)


def init_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with db_connection() as conn:

        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'uz'
            )
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                link TEXT DEFAULT '',
                UNIQUE(user_id, title, artist)
            )
        """)

        conn.commit()


def get_lang(user_id):
    with db_connection() as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

    if row and row[0] in LANGUAGES:
        return row[0]

    return "uz"


def tr(user_id, key):
    return TEXT[get_lang(user_id)].get(
        key,
        TEXT["uz"].get(key, key)
    )


def set_lang(user_id, language):
    if language not in LANGUAGES:
        return

    with db_connection() as conn:
        conn.execute("""
            INSERT INTO users(user_id, language)
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET language=excluded.language
        """, (user_id, language))

        conn.commit()


def add_favorite(user_id, song):
    with db_connection() as conn:
        conn.execute("""
            INSERT OR IGNORE INTO favorites
            (user_id, title, artist, link)
            VALUES (?, ?, ?, ?)
        """, (
            user_id,
            song["title"],
            song["artist"],
            song.get("link", "")
        ))

        conn.commit()


def get_favorites(user_id):
    with db_connection() as conn:
        return conn.execute("""
            SELECT title, artist, link
            FROM favorites
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 50
        """, (user_id,)).fetchall()


# =========================================================
# GENERAL HELPERS
# =========================================================

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value))
    value = value.casefold()

    value = "".join(
        c for c in value
        if not unicodedata.combining(c)
    )

    value = "".join(
        c if c.isalnum() else " "
        for c in value
    )

    return re.sub(r"\s+", " ", value).strip()


def match_score(query, title, artist=""):
    q = normalize(query)
    target = normalize(f"{title} {artist}")

    if not q or not target:
        return 0

    similarity = SequenceMatcher(
        None, q, target
    ).ratio()

    q_words = set(q.split())
    target_words = set(target.split())

    overlap = (
        len(q_words & target_words) / len(q_words)
        if q_words else 0
    )

    return min(
        100,
        round(max(similarity, overlap) * 100)
    )


def escape(value):
    return html.escape(str(value or ""))


def format_duration(seconds):
    try:
        seconds = int(seconds or 0)
    except (ValueError, TypeError):
        seconds = 0

    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


async def delete_file(path):
    try:
        if path and Path(path).exists():
            await asyncio.to_thread(Path(path).unlink)
    except OSError:
        logger.exception("Temporary file cleanup error")


async def delete_message(message):
    try:
        await message.delete()
    except Exception:
        pass


async def download_telegram_file(file_id, destination):
    info = await bot.get_file(file_id)

    await bot.download_file(
        info.file_path,
        destination=destination
    )


async def run_ffmpeg(args):
    def execute():
        subprocess.run(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel", "error",
                "-y"
            ] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            check=True,
            timeout=180
        )

    await asyncio.to_thread(execute)


# =========================================================
# LOCAL MUSIC LIBRARY
# =========================================================

def find_local_song(query):
    if not MUSIC_DIR.exists():
        return None

    query = normalize(query)

    if not query:
        return None

    best_file = None
    best_score = 0

    for file in MUSIC_DIR.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in SUPPORTED_AUDIO:
            continue

        filename = normalize(file.stem)

        if filename == query:
            return file

        score = SequenceMatcher(
            None, query, filename
        ).ratio()

        if query in filename or filename in query:
            score = max(score, 0.90)

        if score > best_score:
            best_score = score
            best_file = file

    return best_file if best_score >= 0.45 else None


# =========================================================
# JAMENDO MUSIC SEARCH
# =========================================================

async def search_jamendo(query):

    if not JAMENDO_CLIENT_ID:
        raise RuntimeError(
            "JAMENDO_CLIENT_ID sozlanmagan"
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

    headers = {
        "User-Agent": "AX-MUSIC-PREMIUM/3.0"
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        async with session.get(
            JAMENDO_URL,
            params=params
        ) as response:

            body = await response.text()

            if response.status != 200:
                logger.error(
                    "Jamendo HTTP %s: %s",
                    response.status,
                    body[:1000]
                )

                raise RuntimeError(
                    f"Jamendo HTTP {response.status}"
                )

            try:
                data = await response.json(
                    content_type=None
                )
            except Exception as exc:
                raise RuntimeError(
                    "Jamendo JSON xatosi"
                ) from exc

    if not isinstance(data, dict):
        raise RuntimeError("Jamendo javobi noto'g'ri")

    headers_data = data.get("headers") or {}

    if headers_data.get("status") != "success":
        raise RuntimeError(
            headers_data.get(
                "error_message",
                "Jamendo API xatosi"
            )
        )

    results = []

    for item in data.get("results", []):

        title = item.get("name") or "Unknown"
        artist = item.get("artist_name") or "Unknown"

        allowed_value = item.get(
            "audiodownload_allowed",
            False
        )

        allowed = (
            allowed_value is True
            or str(allowed_value).lower() == "true"
        )

        try:
            duration_seconds = int(
                item.get("duration") or 0
            )
        except (ValueError, TypeError):
            duration_seconds = 0

        results.append({
            "id": str(item.get("id") or ""),
            "title": title,
            "artist": artist,
            "duration": format_duration(duration_seconds),
            "duration_seconds": duration_seconds,
            "preview": item.get("audio") or "",
            "download": (
                item.get("audiodownload") or ""
                if allowed else ""
            ),
            "download_allowed": allowed,
            "link": item.get("shareurl") or "",
            "artwork": item.get("image") or "",
            "license": item.get("license_ccurl") or "",
            "score": match_score(
                query, title, artist
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
# PREMIUM SEARCH KEYBOARD
# =========================================================

def make_search_keyboard(search_id, page, results):

    rows = []

    start = page * PAGE_SIZE
    end = min(start + PAGE_SIZE, len(results))

    rows.append([
        InlineKeyboardButton(
            text="✦ PLAY BEST MATCH",
            callback_data=f"play:{search_id}:0"
        )
    ])

    for index in range(start, end):

        song = results[index]

        rows.append([
            InlineKeyboardButton(
                text=(
                    f"♫ {index + 1:02d} · "
                    f"{song['title'][:32]}"
                ),
                callback_data=f"play:{search_id}:{index}"
            ),
            InlineKeyboardButton(
                text="☆",
                callback_data=f"fav:{search_id}:{index}"
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="‹ PREVIOUS",
                callback_data=f"page:{search_id}:{page-1}"
            )
        )

    if end < len(results):
        navigation.append(
            InlineKeyboardButton(
                text="NEXT ›",
                callback_data=f"page:{search_id}:{page+1}"
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
# PREMIUM SEARCH RESULT
# =========================================================

def make_search_text(query, results, page, user_id):

    language = get_lang(user_id)

    labels = {
        "uz": {
            "search": "SMART MUSIC DISCOVERY",
            "best": "ENG YAXSHI NATIJA",
            "similar": "O'XSHASH TREKLAR",
            "found": "TA NATIJA TOPILDI",
            "match": "MOSLIK",
            "full": "FULL AUDIO",
            "preview": "PREVIEW",
            "page": "SAHIFA"
        },
        "ru": {
            "search": "ПОИСК МУЗЫКИ",
            "best": "ЛУЧШИЙ РЕЗУЛЬТАТ",
            "similar": "ПОХОЖИЕ ТРЕКИ",
            "found": "НАЙДЕНО",
            "match": "СОВПАДЕНИЕ",
            "full": "FULL AUDIO",
            "preview": "PREVIEW",
            "page": "СТРАНИЦА"
        },
        "en": {
            "search": "SMART MUSIC DISCOVERY",
            "best": "BEST MATCH",
            "similar": "SIMILAR TRACKS",
            "found": "RESULTS FOUND",
            "match": "MATCH",
            "full": "FULL AUDIO",
            "preview": "PREVIEW",
            "page": "PAGE"
        }
    }

    t = labels[language]

    best = results[0]

    total_pages = max(
        1,
        (len(results) + PAGE_SIZE - 1) // PAGE_SIZE
    )

    start = page * PAGE_SIZE
    current = results[start:start + PAGE_SIZE]

    text = (
        "👑 <b>AX MUSIC</b>\n"
        "<i>PREMIUM MUSIC EXPERIENCE</i>\n"
        "🟢 ONLINE\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🔎 <b>{escape(query)}</b>\n\n"
        "╭━━━━━━━━━━━━━━━━━━╮\n"
        f"  ✦ <b>{t['best']}</b>\n\n"
        f"  <b>{escape(best['title'])}</b>\n"
        f"  {escape(best['artist'])}\n"
        f"  ⏱ {best['duration']}\n"
        f"  ✨ {best['score']}% {t['match']}\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n\n"
        f"✦ <b>{t['similar']}</b>\n"
        f"📀 {len(results)} {t['found']}\n\n"
    )

    for index, song in enumerate(current, start=start):

        status = (
            t["full"]
            if song["download_allowed"]
            else t["preview"]
        )

        text += (
            f"<b>{index+1:02d}. "
            f"{escape(song['title'])}</b>\n"
            f"   {escape(song['artist'])}\n"
            f"   ⏱ {song['duration']} "
            f"· ✨ {song['score']}% "
            f"· {status}\n\n"
        )

    text += (
        "━━━━━━━━━━━━━━━━━━\n"
        f"✦ {t['page']} {page+1:02d}/{total_pages:02d}\n"
        "\n<i>Tanlangan qo'shiqni tinglash uchun tugmani bosing.</i>"
    )

    return text


# =========================================================
# SEARCH HANDLER
# =========================================================

async def perform_search(message, query):

    user_id = message.from_user.id

    wait = await message.answer(
        tr(user_id, "searching")
    )

    try:

        # First check user's local library
        local_file = await asyncio.to_thread(
            find_local_song,
            query
        )

        # Then search Jamendo
        results = await search_jamendo(query)

        # Local exact match is added to the beginning
        if local_file:

            local_song = {
                "id": "local",
                "title": local_file.stem,
                "artist": "AX MUSIC LIBRARY",
                "duration": "00:00",
                "duration_seconds": 0,
                "preview": "",
                "download": "",
                "download_allowed": True,
                "link": "",
                "artwork": "",
                "license": "",
                "score": 100,
                "local_path": str(local_file)
            }

            results.insert(0, local_song)

        if not results:
            await wait.edit_text(
                tr(user_id, "not_found")
            )
            return

        search_id = uuid.uuid4().hex[:10]

        SEARCH_CACHE[search_id] = {
            "user_id": user_id,
            "query": query,
            "results": results
        }

        # Limit memory usage
        while len(SEARCH_CACHE) > 150:
            SEARCH_CACHE.pop(
                next(iter(SEARCH_CACHE)),
                None
            )

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

    except Exception as exc:

        logger.exception(
            "Music search failed: %s",
            exc
        )

        await wait.edit_text(
            "❌ <b>Musiqa qidirishda xatolik.</b>\n\n"
            "Server yoki API sozlamalarini tekshiring.\n"
            "Render Logs orqali batafsil xatoni ko'ring."
        )


# =========================================================
# PAGINATION CALLBACK
# =========================================================

@dp.callback_query(F.data.startswith("page:"))
async def pagination_callback(callback: CallbackQuery):

    try:

        _, search_id, page_value = callback.data.split(":")

        cached = SEARCH_CACHE.get(search_id)

        if not cached:
            await callback.answer(
                tr(callback.from_user.id, "expired"),
                show_alert=True
            )
            return

        if cached["user_id"] != callback.from_user.id:
            await callback.answer(
                "Bu qidiruv sizga tegishli emas.",
                show_alert=True
            )
            return

        results = cached["results"]

        page = int(page_value)

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
        await callback.answer("Xatolik yuz berdi.")


# =========================================================
# FAVORITES
# =========================================================

@dp.callback_query(F.data.startswith("fav:"))
async def favorite_callback(callback: CallbackQuery):

    try:

        _, search_id, index_value = callback.data.split(":")

        cached = SEARCH_CACHE.get(search_id)

        if not cached or cached["user_id"] != callback.from_user.id:
            await callback.answer(
                tr(callback.from_user.id, "expired"),
                show_alert=True
            )
            return

        index = int(index_value)
        song = cached["results"][index]

        add_favorite(
            callback.from_user.id,
            song
        )

        await callback.answer(
            "⭐ Sevimlilarga qo'shildi!"
        )

    except Exception:
        logger.exception("Favorite error")
        await callback.answer("Xatolik yuz berdi.")


@dp.message(Command("favorites"))
async def favorites_handler(message: Message):

    favorites = get_favorites(message.from_user.id)

    if not favorites:
        await message.answer(
            tr(message.from_user.id, "empty")
        )
        return

    text = "⭐ <b>AX MUSIC FAVORITES</b>\n\n"

    for index, item in enumerate(favorites, 1):
        title, artist, link = item

        text += (
            f"<b>{index:02d}. {escape(title)}</b>\n"
            f"   {escape(artist)}\n\n"
        )

    await message.answer(text)


# =========================================================
# DOWNLOAD AUDIO SAFELY
# =========================================================

async def download_audio(url, destination):

    timeout = aiohttp.ClientTimeout(
        total=180,
        connect=15,
        sock_read=45
    )

    headers = {
        "User-Agent": "AX-MUSIC-PREMIUM/3.0"
    }

    total = 0

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        async with session.get(
            url,
            allow_redirects=True
        ) as response:

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" in content_type:
                raise RuntimeError(
                    "Audio o'rniga HTML qaytdi"
                )

            with open(destination, "wb") as file:

                async for chunk in response.content.iter_chunked(
                    64 * 1024
                ):

                    total += len(chunk)

                    if total > MAX_AUDIO_SIZE:
                        raise ValueError(
                            "Audio hajmi chegaradan oshdi"
                        )

                    file.write(chunk)

    if not destination.exists() or destination.stat().st_size == 0:
        raise RuntimeError("Audio fayl bo'sh")

    return True


# =========================================================
# PLAY SELECTED TRACK
# =========================================================

@dp.callback_query(F.data.startswith("play:"))
async def play_callback(callback: CallbackQuery):

    path = None
    wait = None

    try:

        _, search_id, index_value = callback.data.split(":")

        cached = SEARCH_CACHE.get(search_id)

        if not cached:
            await callback.answer(
                tr(callback.from_user.id, "expired"),
                show_alert=True
            )
            return

        if cached["user_id"] != callback.from_user.id:
            await callback.answer(
                "Bu qidiruv sizga tegishli emas.",
                show_alert=True
            )
            return

        index = int(index_value)

        results = cached["results"]

        if not 0 <= index < len(results):
            await callback.answer("Trek topilmadi.")
            return

        song = results[index]

        await callback.answer(
            "✦ Audio tayyorlanmoqda..."
        )

        wait = await callback.message.answer(
            tr(callback.from_user.id, "downloading")
        )

        # Local library file
        if song.get("local_path"):

            local_path = Path(song["local_path"])

            if local_path.exists():

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

        TEMP_DIR.mkdir(
            parents=True,
            exist_ok=True
        )

        path = TEMP_DIR / (
            f"track_{uuid.uuid4().hex}.mp3"
        )

        # Licensed full version
        if (
            song.get("download_allowed")
            and song.get("download")
        ):

            await download_audio(
                song["download"],
                path
            )

            caption = (
                "👑 <b>AX MUSIC PREMIUM</b>\n"
                "✦ FULL AUDIO\n"
                f"🎤 {escape(song['artist'])}\n"
            )

            if song.get("license"):
                caption += (
                    f'\n<a href="{escape(song["license"])}">'
                    "License information</a>"
                )

            await callback.message.answer_audio(
                FSInputFile(path),
                title=song["title"][:64],
                performer=song["artist"][:64],
                caption=caption
            )

            return

        # If full version is unavailable, send preview
        if song.get("preview"):

            await download_audio(
                song["preview"],
                path
            )

            caption = (
                "👑 <b>AX MUSIC PREMIUM</b>\n"
                "✦ PREVIEW VERSION\n"
                f"🎤 {escape(song['artist'])}\n\n"
                "To'liq versiya uchun rasmiy manbani tekshiring."
            )

            if song.get("link"):
                caption += (
                    f'\n\n<a href="{escape(song["link"])}">'
                    "✦ OPEN OFFICIAL TRACK</a>"
                )

            await callback.message.answer_audio(
                FSInputFile(path),
                title=song["title"][:64],
                performer=song["artist"][:64],
                caption=caption
            )

            return

        await callback.message.answer(
            "Bu trek uchun audio fayl mavjud emas."
        )

    except Exception:

        logger.exception("Play callback error")

        await callback.message.answer(
            tr(callback.from_user.id, "download_error")
        )

    finally:

        if wait:
            await delete_message(wait)

        if path:
            await delete_file(path)


# =========================================================
# HOME MENU
# =========================================================

def home_keyboard():

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


@dp.callback_query(F.data == "home")
async def home_callback(callback):

    await callback.answer()

    await callback.message.answer(
        tr(callback.from_user.id, "start"),
        reply_markup=home_keyboard()
    )


@dp.callback_query(F.data == "music")
async def music_callback(callback):

    await callback.answer()

    await callback.message.answer(
        tr(callback.from_user.id, "music")
    )


@dp.callback_query(F.data == "favorites")
async def favorites_callback(callback):

    await callback.answer()

    favorites = get_favorites(callback.from_user.id)

    if not favorites:
        await callback.message.answer(
            tr(callback.from_user.id, "empty")
        )
        return

    text = "⭐ <b>AX MUSIC FAVORITES</b>\n\n"

    for i, item in enumerate(favorites, 1):
        text += (
            f"{i:02d}. <b>{escape(item[0])}</b>\n"
            f"   {escape(item[1])}\n\n"
        )

    await callback.message.answer(text)


# =========================================================
# LANGUAGE
# =========================================================

@dp.message(Command("lang"))
async def language_command(message):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 Uzbek",
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

    await message.answer(
        tr(message.from_user.id, "language"),
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("lang:"))
async def language_callback(callback):

    language = callback.data.split(":")[1]

    if language not in LANGUAGES:
        await callback.answer()
        return

    set_lang(
        callback.from_user.id,
        language
    )

    await callback.answer("Language updated!")

    await callback.message.edit_text(
        TEXT[language]["start"],
        reply_markup=home_keyboard()
    )


# =========================================================
# COMMANDS
# =========================================================

@dp.message(Command("start"))
async def start_handler(message):

    await message.answer(
        tr(message.from_user.id, "start"),
        reply_markup=home_keyboard()
    )


@dp.message(Command("music"))
async def music_handler(message):

    await message.answer(
        tr(message.from_user.id, "music")
    )


@dp.message(Command("help"))
async def help_handler(message):

    await message.answer(
        "👑 <b>AX MUSIC PREMIUM HELP</b>\n\n"
        "🎵 Qo'shiq nomini yuboring.\n"
        "🎧 Ovozli parcha yuboring.\n"
        "🎬 Video yuboring.\n\n"
        "/start — Bosh menyu\n"
        "/music — Musiqa qidirish\n"
        "/favorites — Sevimlilar\n"
        "/lang — Tilni o'zgartirish"
    )


# =========================================================
# AUDIO RECOGNITION - AUDD
# =========================================================

async def recognize_audio(message, file_id, file_size):

    user_id = message.from_user.id

    if not AUDD_TOKEN:
        await message.answer(
            "⚠️ AUDD_TOKEN sozlanmagan.\n"
            "Qo'shiq nomi bilan qidiruv ishlashda davom etadi."
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

        timeout = aiohttp.ClientTimeout(total=60)

        with open(path, "rb") as audio:

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
                    "https://api.audd.io/",
                    data=form
                ) as response:

                    response.raise_for_status()

                    data = await response.json(
                        content_type=None
                    )

        result = data.get("result")

        if data.get("status") != "success" or not result:

            await message.answer(
                tr(user_id, "not_found")
            )
            return

        title = result.get("title", "")
        artist = result.get("artist", "")

        query = f"{artist} {title}".strip()

        await perform_search(
            message,
            query
        )

    except Exception:

        logger.exception(
            "Audio recognition error"
        )

        await message.answer(
            tr(user_id, "error")
        )

    finally:

        await delete_message(wait)
        await delete_file(path)


@dp.message(F.voice)
async def voice_handler(message):

    await recognize_audio(
        message,
        message.voice.file_id,
        message.voice.file_size or 0
    )


@dp.message(F.audio)
async def audio_handler(message):

    await recognize_audio(
        message,
        message.audio.file_id,
        message.audio.file_size or 0
    )


# =========================================================
# VIDEO UPLOAD
# =========================================================

@dp.message(F.video)
async def video_handler(message):

    video = message.video

    if video.file_size and video.file_size > MAX_VIDEO_SIZE:
        await message.answer(
            tr(message.from_user.id, "video_large")
        )
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🎵 MP3",
                    callback_data="extract"
                ),
                InlineKeyboardButton(
                    text="🎥 ROUND",
                    callback_data="round"
                )
            ]
        ]
    )

    await message.answer(
        "👑 <b>AX MUSIC VIDEO TOOLS</b>\n\n"
        "Video qabul qilindi.\n"
        "Kerakli funksiyani tanlang.",
        reply_markup=keyboard
    )

    # Store video reference in chat data using a temporary
    # in-memory mapping keyed by user and message.
    VIDEO_CACHE[message.chat.id] = {
        "file_id": video.file_id,
        "file_size": video.file_size or 0,
        "user_id": message.from_user.id
    }


VIDEO_CACHE = {}


# =========================================================
# VIDEO CALLBACK HELPER
# =========================================================

async def get_cached_video(callback):

    cached = VIDEO_CACHE.get(callback.message.chat.id)

    if not cached:
        return None

    if cached["user_id"] != callback.from_user.id:
        return None

    return cached


# =========================================================
# VIDEO TO MP3
# =========================================================

@dp.callback_query(F.data == "extract")
async def extract_callback(callback):

    await callback.answer()

    cached = await get_cached_video(callback)

    if not cached:
        await callback.message.answer(
            "Video ma'lumoti topilmadi. Videoni qayta yuboring."
        )
        return

    if not ffmpeg_available():
        await callback.message.answer(
            tr(callback.from_user.id, "ffmpeg")
        )
        return

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

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

        await download_telegram_file(
            cached["file_id"],
            input_path
        )

        await run_ffmpeg([
            "-i", str(input_path),
            "-vn",
            "-b:a", "192k",
            str(output_path)
        ])

        if output_path.stat().st_size > MAX_AUDIO_SIZE:
            raise ValueError("Audio juda katta")

        await callback.message.answer_audio(
            FSInputFile(output_path),
            caption="👑 <b>AX MUSIC PREMIUM</b>\n✦ MP3 AUDIO"
        )

    except Exception:

        logger.exception("Video to MP3 error")

        await callback.message.answer(
            tr(callback.from_user.id, "error")
        )

    finally:

        await delete_message(wait)
        await delete_file(input_path)
        await delete_file(output_path)


# =========================================================
# VIDEO TO ROUND
# =========================================================

@dp.callback_query(F.data == "round")
async def round_callback(callback):

    await callback.answer()

    cached = await get_cached_video(callback)

    if not cached:
        await callback.message.answer(
            "Video topilmadi. Videoni qayta yuboring."
        )
        return

    if not ffmpeg_available():
        await callback.message.answer(
            tr(callback.from_user.id, "ffmpeg")
        )
        return

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    input_path = TEMP_DIR / (
        f"round_input_{uuid.uuid4().hex}.mp4"
    )

    output_path = TEMP_DIR / (
        f"round_output_{uuid.uuid4().hex}.mp4"
    )

    wait = await callback.message.answer(
        "🎥 <b>ROUND VIDEO</b>\n\nTayyorlanmoqda..."
    )

    try:

        await download_telegram_file(
            cached["file_id"],
            input_path
        )

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

        await callback.message.answer_video_note(
            FSInputFile(output_path)
        )

    except Exception:

        logger.exception("Round conversion error")

        await callback.message.answer(
            tr(callback.from_user.id, "error")
        )

    finally:

        await delete_message(wait)
        await delete_file(input_path)
        await delete_file(output_path)


# =========================================================
# TEXT MUSIC SEARCH
# =========================================================

@dp.message(F.text)
async def text_search_handler(message):

    query = (message.text or "").strip()

    if not query:
        return

    if query.startswith("/"):
        return

    if len(query) < 2 or len(query) > 150:
        return

    await perform_search(
        message,
        query
    )


# =========================================================
# HEALTH SERVER
# =========================================================

from aiohttp import web


async def health_handler(request):

    return web.json_response({
        "status": "online",
        "service": "AX MUSIC PREMIUM",
        "version": "3.0"
    })


# =========================================================
# APPLICATION START
# =========================================================

async def main():

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

    logger.info("=" * 45)
    logger.info("AX MUSIC PREMIUM STARTING")
    logger.info("=" * 45)

    if not JAMENDO_CLIENT_ID:
        logger.warning(
            "JAMENDO_CLIENT_ID is missing. Online search unavailable."
        )

    if not AUDD_TOKEN:
        logger.warning(
            "AUDD_TOKEN is missing. Audio recognition unavailable."
        )

    if not ffmpeg_available():
        logger.warning(
            "FFmpeg is missing. Video conversion unavailable."
        )

    app = web.Application()

    app.router.add_get("/", health_handler)
    app.router.add_get("/health", health_handler)

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

        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except (KeyboardInterrupt, SystemExit):
        logger.info("AX MUSIC stopped.")
