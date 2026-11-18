
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
import time

from pathlib import Path
from difflib import SequenceMatcher
from contextlib import suppress

import aiohttp

from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# =========================================================
# AX MUSIC SETTINGS
# =========================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "").strip()
JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "").strip()

PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "tmp"
MUSIC_LIBRARY_DIR = BASE_DIR / "music_library"

DB_PATH = DATA_DIR / "bot.sqlite3"

JAMENDO_API = "https://api.jamendo.com/v3.0/tracks/"

MAX_RESULTS = 12
PAGE_SIZE = 4

MAX_AUDIO_BYTES = 48 * 1024 * 1024
MAX_VIDEO_BYTES = 48 * 1024 * 1024
MAX_VIDEO_SECONDS = 60

CACHE_LIMIT = 100
CACHE_TTL = 1800

AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".aac",
    ".ogg", ".wav", ".flac"
}

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
# LANGUAGE
# =========================================================

TEXTS = {
    "uz": {
        "start": (
            "🎵 <b>AX MUSIC</b>\n"
            "━━━━━━━━━━━━━━━━━━\n\n"
            "Assalomu alaykum!\n\n"
            "🎧 Qo'shiq nomini yuboring.\n"
            "🎤 Ovozli parcha yuboring.\n"
            "🎵 Audio fayl yuboring.\n"
            "🎬 Video yuboring.\n\n"
            "/music — Musiqa qidirish\n"
            "/video — Video yordam\n"
            "/lang — Tilni almashtirish\n"
            "/help — Yordam\n\n"
            "✨ <i>Smart Music Search</i>"
        ),
        "searching": "🔎 AX MUSIC qidirmoqda...",
        "recognizing": "🎧 Qo'shiq aniqlanmoqda...",
        "not_found": "😔 Qo'shiq topilmadi.",
        "error": "❌ Xatolik yuz berdi.",
        "wait": "⏳ Iltimos, kuting...",
        "downloading": "🎵 To'liq audio tayyorlanmoqda...",
        "download_error": "Audio yuklab olinmadi.",
        "no_audd": "AudD token sozlanmagan.",
        "no_jamendo": "Jamendo CLIENT_ID sozlanmagan.",
        "audio_large": "Audio fayl juda katta.",
        "video_large": "Video fayl juda katta.",
        "ffmpeg": "FFmpeg o'rnatilmagan.",
        "language": "Tilni tanlang:",
        "expired": "Qidiruv muddati tugagan. Qaytadan qidiring.",
        "video_ready": "🎥 Video tayyor!",
        "music_help": "🎵 Qo'shiq nomini yozing yoki audio yuboring.",
        "video_help": "🎬 Dumaloq video yaratish uchun video yuboring.",
        "no_full": "⚠️ Bu trekning to'liq versiyasini yuklab olishga ruxsat yo'q.",
        "preview": "Qisqa tinglash namunasi mavjud.",
        "match": "MOSLIK",
        "best": "ENG YAXSHI NATIJA",
        "similar": "O'XSHASH QO'SHIQLAR",
        "found": "TA TREK TOPILDI",
        "page": "SAHIFA",
        "online": "ONLINE",
        "full": "TO'LIQ AUDIO",
        "stream": "NAMUNA",
        "choose": "Tinglash uchun tugmani bosing."
    },
    "ru": {
        "start": (
            "🎵 <b>AX MUSIC</b>\n\n"
            "Отправьте название песни или аудио.\n"
            "Также можно отправить видео.\n\n"
            "/music — Музыка\n"
            "/video — Видео\n"
            "/lang — Язык\n"
            "/help — Помощь"
        ),
        "searching": "🔎 AX MUSIC ищет...",
        "recognizing": "🎧 Определяю песню...",
        "not_found": "😔 Песня не найдена.",
        "error": "❌ Произошла ошибка.",
        "wait": "⏳ Подождите...",
        "downloading": "🎵 Подготавливаю полную версию...",
        "download_error": "Не удалось загрузить аудио.",
        "no_audd": "AudD token не настроен.",
        "no_jamendo": "Jamendo CLIENT_ID не настроен.",
        "audio_large": "Аудиофайл слишком большой.",
        "video_large": "Видеофайл слишком большой.",
        "ffmpeg": "FFmpeg не установлен.",
        "language": "Выберите язык:",
        "expired": "Поиск истёк. Попробуйте снова.",
        "video_ready": "🎥 Видео готово!",
        "music_help": "Отправьте название песни или аудио.",
        "video_help": "Отправьте видео для создания круглого видео.",
        "no_full": "⚠️ Полная загрузка этого трека недоступна.",
        "preview": "Доступен короткий фрагмент.",
        "match": "СОВПАДЕНИЕ",
        "best": "ЛУЧШИЙ РЕЗУЛЬТАТ",
        "similar": "ПОХОЖИЕ ТРЕКИ",
        "found": "ТРЕКОВ НАЙДЕНО",
        "page": "СТРАНИЦА",
        "online": "ONLINE",
        "full": "ПОЛНОЕ АУДИО",
        "stream": "ФРАГМЕНТ",
        "choose": "Нажмите кнопку для прослушивания."
    },
    "en": {
        "start": (
            "🎵 <b>AX MUSIC</b>\n\n"
            "Send a song title or audio snippet.\n"
            "You can also send a video.\n\n"
            "/music — Music\n"
            "/video — Video\n"
            "/lang — Language\n"
            "/help — Help"
        ),
        "searching": "🔎 AX MUSIC is searching...",
        "recognizing": "🎧 Identifying song...",
        "not_found": "😔 Song not found.",
        "error": "❌ An error occurred.",
        "wait": "⏳ Please wait...",
        "downloading": "🎵 Preparing full audio...",
        "download_error": "Audio download failed.",
        "no_audd": "AudD token is not configured.",
        "no_jamendo": "Jamendo CLIENT_ID is not configured.",
        "audio_large": "Audio file is too large.",
        "video_large": "Video file is too large.",
        "ffmpeg": "FFmpeg is not installed.",
        "language": "Choose a language:",
        "expired": "Search expired. Please search again.",
        "video_ready": "🎥 Video ready!",
        "music_help": "Send a song title or audio.",
        "video_help": "Send a video to create a round video.",
        "no_full": "⚠️ Full download is not available for this track.",
        "preview": "A short preview is available.",
        "match": "MATCH",
        "best": "BEST MATCH",
        "similar": "SIMILAR TRACKS",
        "found": "TRACKS FOUND",
        "page": "PAGE",
        "online": "ONLINE",
        "full": "FULL AUDIO",
        "stream": "PREVIEW",
        "choose": "Press a button to listen."
    }
}


# =========================================================
# DATABASE
# =========================================================

def init_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                language TEXT DEFAULT 'uz'
            )
        """)
        conn.commit()


def get_language(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT language FROM users WHERE user_id=?",
            (user_id,)
        ).fetchone()

    if row and row[0] in TEXTS:
        return row[0]

    return "uz"


def T(user_id):
    return TEXTS[get_language(user_id)]


def set_language(user_id, language):
    if language not in TEXTS:
        return

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            INSERT INTO users(user_id, language)
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET language=excluded.language
        """, (user_id, language))
        conn.commit()


# =========================================================
# HELPERS
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


def match_score(query, title, artist):
    query = normalize(query)
    target = normalize(f"{title} {artist}")

    if not query or not target:
        return 0

    score = SequenceMatcher(
        None, query, target
    ).ratio()

    query_words = set(query.split())
    target_words = set(target.split())

    if query_words:
        overlap = (
            len(query_words & target_words)
            / len(query_words)
        )

        score = max(score, overlap)

    return min(100, round(score * 100))


def format_duration(seconds):
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        seconds = 0

    return f"{seconds // 60}:{seconds % 60:02d}"


def ffmpeg_available():
    return shutil.which("ffmpeg") is not None


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


async def safe_delete(path):
    if not path:
        return

    try:
        path = Path(path)

        if path.exists():
            await asyncio.to_thread(path.unlink)

    except OSError:
        logger.warning("File cleanup error: %s", path)


async def delete_message(message):
    with suppress(Exception):
        await message.delete()


async def download_telegram_file(file_id, destination):
    file_info = await bot.get_file(file_id)

    await bot.download_file(
        file_info.file_path,
        destination=destination
    )


# =========================================================
# CACHE
# =========================================================

def clean_cache():
    now = time.time()

    expired = [
        key for key, value in SEARCH_CACHE.items()
        if now - value["created"] > CACHE_TTL
    ]

    for key in expired:
        SEARCH_CACHE.pop(key, None)

    while len(SEARCH_CACHE) > CACHE_LIMIT:
        oldest = min(
            SEARCH_CACHE,
            key=lambda k: SEARCH_CACHE[k]["created"]
        )
        SEARCH_CACHE.pop(oldest, None)


# =========================================================
# JAMENDO MUSIC SEARCH
# =========================================================

async def search_jamendo(query):
    if not JAMENDO_CLIENT_ID:
        raise RuntimeError("JAMENDO_CLIENT_ID sozlanmagan")

    if not query.strip():
        return []

    timeout = aiohttp.ClientTimeout(
        total=40,
        connect=15,
        sock_read=30
    )

    params = {
        "client_id": JAMENDO_CLIENT_ID,
        "format": "json",
        "limit": MAX_RESULTS,
        "search": query,
        "type": "single albumtrack",
        "audioformat": "mp32",
        "audiodlformat": "mp32",
        "imagesize": 300,
        "include": "licenses"
    }

    headers = {
        "User-Agent": "AX-MUSIC-BOT/3.0"
    }

    async with aiohttp.ClientSession(
        timeout=timeout,
        headers=headers
    ) as session:

        async with session.get(
            JAMENDO_API,
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

            data = await response.json(
                content_type=None
            )

    if not isinstance(data, dict):
        raise RuntimeError("Jamendo javobi noto'g'ri")

    api_status = (data.get("headers") or {}).get("status")

    if api_status != "success":
        error = (data.get("headers") or {}).get(
            "error_message",
            "API error"
        )
        raise RuntimeError(str(error))

    results = []

    for item in data.get("results", []):
        try:
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

            download_url = (
                item.get("audiodownload")
                if allowed else None
            )

            results.append({
                "id": str(item.get("id") or ""),
                "title": title,
                "artist": artist,
                "album": item.get("album_name") or "",
                "duration": format_duration(
                    item.get("duration")
                ),
                "duration_seconds": int(
                    item.get("duration") or 0
                ),
                "preview": item.get("audio") or None,
                "download": download_url,
                "download_allowed": bool(
                    allowed and download_url
                ),
                "link": item.get("shareurl") or "",
                "artwork": item.get("image") or "",
                "license": item.get("license_ccurl") or "",
                "score": match_score(
                    query, title, artist
                )
            })

        except (ValueError, TypeError, AttributeError):
            logger.exception("Track parsing error")

    # Full download permission is prioritized,
    # then the relevance score.
    results.sort(
        key=lambda x: (
            x["download_allowed"],
            x["score"]
        ),
        reverse=True
    )

    return results


# =========================================================
# RESULT KEYBOARD
# =========================================================

def make_music_keyboard(search_id, page, results):
    start = page * PAGE_SIZE
    end = start + PAGE_SIZE

    current = results[start:end]
    rows = []

    if results:
        rows.append([
            InlineKeyboardButton(
                text="▶️ PLAY TOP RESULT",
                callback_data=f"play:{search_id}:0"
            )
        ])

    for index, song in enumerate(current, start=start):
        title = song["title"][:30]

        rows.append([
            InlineKeyboardButton(
                text=f"🎵 {title}",
                callback_data=f"play:{search_id}:{index}"
            )
        ])

    navigation = []

    if page > 0:
        navigation.append(
            InlineKeyboardButton(
                text="⬅️ PREVIOUS",
                callback_data=f"page:{search_id}:{page - 1}"
            )
        )

    if end < len(results):
        navigation.append(
            InlineKeyboardButton(
                text="NEXT ➡️",
                callback_data=f"page:{search_id}:{page + 1}"
            )
        )

    if navigation:
        rows.append(navigation)

    return InlineKeyboardMarkup(
        inline_keyboard=rows
    )


# =========================================================
# RESULT TEXT
# =========================================================

def make_results_text(query, results, page, user_id):
    t = T(user_id)

    total = len(results)

    total_pages = max(
        1,
        (total + PAGE_SIZE - 1) // PAGE_SIZE
    )

    current = results[
        page * PAGE_SIZE:
        page * PAGE_SIZE + PAGE_SIZE
    ]

    best = results[0]

    text = (
        "🎵 <b>AX MUSIC</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"🟢 <b>{t['online']}</b>\n\n"
        f"🔎 <b>{html.escape(query)}</b>\n\n"
        "╭━━━━━━━━━━━━━━━━━━╮\n"
        f"  <b>{t['best']}</b>\n\n"
        f"  🎧 <b>{html.escape(best['title'])}</b>\n"
        f"  👤 {html.escape(best['artist'])}\n"
        f"  ⏱ {best['duration']}\n"
        f"  ⭐ {best['score']}%\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n\n"
        f"🎼 <b>{t['similar']}</b>\n"
        f"📀 <b>{total} {t['found']}</b>\n\n"
    )

    for index, song in enumerate(
        current,
        start=page * PAGE_SIZE + 1
    ):
        status = (
            f"✅ {t['full']}"
            if song["download_allowed"]
            else f"🔊 {t['stream']}"
        )

        text += (
            f"<b>{index:02d}. "
            f"{html.escape(song['title'])}</b>\n"
            f"👤 {html.escape(song['artist'])}\n"
            f"⏱ {song['duration']}  "
            f"🎯 {t['match']}: {song['score']}%\n"
            f"{status}\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

    text += (
        f"\n📄 <b>{t['page']} "
        f"{page + 1:02d}/{total_pages:02d}</b>\n\n"
        f"👇 <i>{t['choose']}</i>"
    )

    return text


# =========================================================
# SHOW SEARCH RESULTS
# =========================================================

async def show_music_results(message, query):
    user_id = message.from_user.id
    t = T(user_id)

    wait = await message.answer(t["searching"])

    try:
        results = await search_jamendo(query)

        if not results:
            await wait.edit_text(t["not_found"])
            return

        clean_cache()

        search_id = uuid.uuid4().hex[:10]

        SEARCH_CACHE[search_id] = {
            "query": query,
            "results": results,
            "user_id": user_id,
            "created": time.time()
        }

        await wait.edit_text(
            make_results_text(
                query,
                results,
                0,
                user_id
            ),
            reply_markup=make_music_keyboard(
                search_id,
                0,
                results
            )
        )

    except Exception:
        logger.exception("Music search error")

        await wait.edit_text(
            "❌ Musiqa qidirishda xatolik.\n"
            "Render Logs va API sozlamalarini tekshiring."
        )


# =========================================================
# PAGINATION
# =========================================================

@dp.callback_query(F.data.startswith("page:"))
async def page_callback(callback):
    try:
        _, search_id, page_text = callback.data.split(":")
        page = int(page_text)

        clean_cache()

        cached = SEARCH_CACHE.get(search_id)

        if not cached:
            await callback.answer(
                T(callback.from_user.id)["expired"],
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

        max_page = max(
            0,
            (len(results) - 1) // PAGE_SIZE
        )

        if page < 0 or page > max_page:
            await callback.answer()
            return

        await callback.message.edit_text(
            make_results_text(
                cached["query"],
                results,
                page,
                callback.from_user.id
            ),
            reply_markup=make_music_keyboard(
                search_id,
                page,
                results
            )
        )

        await callback.answer()

    except Exception:
        logger.exception("Page callback error")
        await callback.answer(
            "Xatolik yuz berdi.",
            show_alert=True
        )


# =========================================================
# DOWNLOAD LICENSED FULL AUDIO
# =========================================================

async def download_audio(url, destination):
    timeout = aiohttp.ClientTimeout(
        total=180,
        connect=20,
        sock_read=60
    )

    headers = {
        "User-Agent": "AX-MUSIC-BOT/3.0"
    }

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

            total = 0

            with open(destination, "wb") as file:
                async for chunk in response.content.iter_chunked(
                    64 * 1024
                ):
                    total += len(chunk)

                    if total > MAX_AUDIO_BYTES:
                        raise ValueError(
                            "Audio hajmi chegaradan oshdi"
                        )

                    file.write(chunk)

    if (
        not destination.exists()
        or destination.stat().st_size == 0
    ):
        raise RuntimeError("Audio fayl bo'sh")

    return True


# =========================================================
# PREVIEW DOWNLOAD
# =========================================================

async def download_preview(url, destination):
    await download_audio(url, destination)


# =========================================================
# PLAY MUSIC
# =========================================================

@dp.callback_query(F.data.startswith("play:"))
async def play_callback(callback):
    path = None
    wait = None

    try:
        _, search_id, index_text = callback.data.split(":")
        index = int(index_text)

        clean_cache()

        cached = SEARCH_CACHE.get(search_id)

        if not cached:
            await callback.answer(
                T(callback.from_user.id)["expired"],
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

        if index < 0 or index >= len(results):
            await callback.answer(
                "Qo'shiq topilmadi.",
                show_alert=True
            )
            return

        song = results[index]

        await callback.answer("🎵 Audio tayyorlanmoqda...")

        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        path = TEMP_DIR / (
            f"music_{uuid.uuid4().hex}.mp3"
        )

        # Full licensed version
        if (
            song["download_allowed"]
            and song.get("download")
        ):
            wait = await callback.message.answer(
                T(callback.from_user.id)["downloading"]
            )

            await download_audio(
                song["download"],
                path
            )

            caption = (
                "🎵 <b>AX MUSIC | FULL AUDIO</b>\n"
                f"👤 {html.escape(song['artist'])}\n"
                f"🎧 {html.escape(song['title'])}\n"
            )

            if song.get("license"):
                caption += (
                    "\n<a href=\""
                    + html.escape(song["license"], quote=True)
                    + "\">License information</a>"
                )

            await callback.message.answer_audio(
                FSInputFile(path),
                title=song["title"][:64],
                performer=song["artist"][:64],
                caption=caption
            )

        # Preview only when full download is unavailable
        elif song.get("preview"):
            wait = await callback.message.answer(
                "🔊 Qisqa audio namuna tayyorlanmoqda..."
            )

            await download_preview(
                song["preview"],
                path
            )

            await callback.message.answer_audio(
                FSInputFile(path),
                title=(song["title"] + " Preview")[:64],
                performer=song["artist"][:64],
                caption=(
                    "🎵 <b>AX MUSIC | PREVIEW</b>\n"
                    "⚠️ Bu to'liq qo'shiq emas, qisqa namuna."
                )
            )

            if song.get("link"):
                await callback.message.answer(
                    "🔗 <a href=\""
                    + html.escape(song["link"], quote=True)
                    + "\">Rasmiy trek sahifasi</a>",
                    disable_web_page_preview=True
                )

        else:
            text = (
                f"🎵 <b>{html.escape(song['title'])}</b>\n"
                f"👤 {html.escape(song['artist'])}\n\n"
                f"{T(callback.from_user.id)['no_full']}"
            )

            if song.get("link"):
                text += (
                    "\n\n<a href=\""
                    + html.escape(song["link"], quote=True)
                    + "\">Rasmiy sahifani ochish</a>"
                )

            await callback.message.answer(
                text,
                disable_web_page_preview=True
            )

    except Exception:
        logger.exception("Play error")

        await callback.message.answer(
            T(callback.from_user.id)["download_error"]
        )

    finally:
        if wait:
            await delete_message(wait)

        if path:
            await safe_delete(path)


# =========================================================
# AUDD MUSIC RECOGNITION
# =========================================================

async def recognize_music(message, file_id, file_size):
    user_id = message.from_user.id
    t = T(user_id)

    if not AUDD_TOKEN:
        await message.answer(t["no_audd"])
        return

    if file_size and file_size > MAX_AUDIO_BYTES:
        await message.answer(t["audio_large"])
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    path = TEMP_DIR / (
        f"recognize_{uuid.uuid4().hex}.audio"
    )

    wait = await message.answer(t["recognizing"])

    try:
        await download_telegram_file(
            file_id,
            path
        )

        if path.stat().st_size > MAX_AUDIO_BYTES:
            await message.answer(t["audio_large"])
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
            await message.answer(t["not_found"])
            return

        title = result.get("title") or ""
        artist = result.get("artist") or ""

        if not title:
            await message.answer(t["not_found"])
            return

        await show_music_results(
            message,
            f"{artist} {title}".strip()
        )

    except Exception:
        logger.exception("Recognition error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)
        await safe_delete(path)


# =========================================================
# COMMANDS
# =========================================================

@dp.message(Command("start"))
async def start_handler(message):
    await message.answer(
        T(message.from_user.id)["start"]
    )


@dp.message(Command("music"))
async def music_handler(message):
    await message.answer(
        T(message.from_user.id)["music_help"]
    )


@dp.message(Command("video"))
async def video_handler(message):
    await message.answer(
        T(message.from_user.id)["video_help"]
    )


@dp.message(Command("help"))
async def help_handler(message):
    t = T(message.from_user.id)

    await message.answer(
        "ℹ️ <b>AX MUSIC HELP</b>\n\n"
        f"{t['music_help']}\n"
        f"{t['video_help']}\n\n"
        "/lang — Tilni almashtirish"
    )


# =========================================================
# LANGUAGE
# =========================================================

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
        T(message.from_user.id)["language"],
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("lang_"))
async def language_callback(callback):
    language = callback.data.split("_", 1)[1]

    if language not in TEXTS:
        await callback.answer()
        return

    set_language(
        callback.from_user.id,
        language
    )

    await callback.answer("Language changed")

    await callback.message.edit_text(
        TEXTS[language]["start"]
    )


# =========================================================
# VIDEO TO ROUND VIDEO
# =========================================================

async def create_round(message, file_id, file_size=0):
    user_id = message.from_user.id
    t = T(user_id)

    if file_size and file_size > MAX_VIDEO_BYTES:
        await message.answer(t["video_large"])
        return

    if not ffmpeg_available():
        await message.answer(t["ffmpeg"])
        return

    TEMP_DIR.mkdir(parents=True, exist_ok=True)

    prefix = uuid.uuid4().hex

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
            "crop='min(iw,ih)':'min(iw,ih)',"
            "scale=384:384:force_original_aspect_ratio=decrease,"
            "pad=384:384:(ow-iw)/2:(oh-ih)/2,"
            "fps=30",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "96k",
            "-movflags", "+faststart",
            str(output_file)
        ])

        if not output_file.exists():
            raise RuntimeError("Round video yaratilmadi")

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
async def video_handler_message(message):
    await create_round(
        message,
        message.video.file_id,
        message.video.file_size or 0
    )


# =========================================================
# VIDEO TO MP3
# =========================================================

@dp.message(F.document)
async def document_handler(message):
    document = message.document

    if not document.mime_type:
        return

    if not document.mime_type.startswith("audio/"):
        return

    await recognize_music(
        message,
        document.file_id,
        document.file_size or 0
    )


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


# =========================================================
# SEARCH BY TEXT
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

    await show_music_results(
        message,
        query
    )


# =========================================================
# HEALTH SERVER
# =========================================================

async def health_handler(request):
    return web.json_response({
        "status": "ok",
        "service": "AX MUSIC",
        "version": "3.0"
    })


async def start_health_server():
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
        "AX MUSIC health server started on %s",
        PORT
    )

    return runner


# =========================================================
# MAIN
# =========================================================

async def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    MUSIC_LIBRARY_DIR.mkdir(parents=True, exist_ok=True)

    init_database()

    if not JAMENDO_CLIENT_ID:
        logger.warning(
            "JAMENDO_CLIENT_ID sozlanmagan!"
        )

    if not AUDD_TOKEN:
        logger.warning(
            "AUDD_TOKEN sozlanmagan!"
        )

    if not ffmpeg_available():
        logger.warning(
            "FFmpeg o'rnatilmagan. Video funksiyasi ishlamaydi."
        )

    runner = await start_health_server()

    logger.info("AX MUSIC BOT ishga tushdi!")

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
