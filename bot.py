
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
    InlineKeyboardButton
)
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode


# ==================================================
# SETTINGS
# ==================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "").strip()
JAMENDO_CLIENT_ID = os.getenv("JAMENDO_CLIENT_ID", "").strip()
PORT = int(os.getenv("PORT", "8080"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN Render Environment'da topilmadi!")

BASE_DIR = Path(__file__).resolve().parent

MUSIC_LIBRARY_DIR = BASE_DIR / "music_library"
DATA_DIR = BASE_DIR / "data"
TEMP_DIR = BASE_DIR / "tmp"
DATABASE_PATH = DATA_DIR / "bot.sqlite3"

JAMENDO_URL = "https://api.jamendo.com/v3.0/tracks/"

MAX_VIDEO_BYTES = 48 * 1024 * 1024
MAX_AUDIO_BYTES = 48 * 1024 * 1024
MAX_VIDEO_SECONDS = 60

MAX_SEARCH_RESULTS = 12
PAGE_SIZE = 4

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


# ==================================================
# LANGUAGES
# ==================================================

TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum!\n\n"
            "🎵 Qo'shiq nomini yozing.\n"
            "🎧 Ovozli parcha yuboring.\n"
            "🎬 Ruxsat etilgan video havolasini yuboring.\n"
            "🎥 Video yuborsangiz, dumaloq video qilaman.\n\n"
            "/music - Musiqa\n"
            "/video - Video\n"
            "/help - Yordam\n"
            "/lang - Til"
        ),
        "wait": "⏳ Kuting...",
        "recognizing": "🎧 Qo'shiq aniqlanmoqda...",
        "searching": "🔎 AX MUSIC qidirmoqda...",
        "not_found": "😔 Qo'shiq topilmadi.",
        "error": "❌ Xatolik yuz berdi.",
        "no_audd": "AudD token sozlanmagan.",
        "no_jamendo": "Jamendo CLIENT_ID sozlanmagan.",
        "language": "Tilni tanlang:",
        "audio_large": "Audio fayl juda katta.",
        "video_large": "Video fayl juda katta.",
        "bad_url": "Noto'g'ri havola.",
        "video_ready": "📥 Video tayyor!",
        "music_help": "🎵 Qo'shiq nomini yozing yoki audio yuboring.",
        "video_help": "🎬 Video havolasini yuboring yoki video jo'nating.",
        "expired": "Qidiruv muddati tugagan. Qaytadan qidiring.",
        "ffmpeg": "FFmpeg o'rnatilmagan.",
        "downloading": "🎵 To'liq audio tayyorlanmoqda...",
        "download_error": "Audio yuklab olinmadi."
    },
    "ru": {
        "start": (
            "👋 Добро пожаловать!\n\n"
            "Отправьте название песни или аудио.\n"
            "Отправьте разрешённую ссылку на видео.\n\n"
            "/music - Музыка\n"
            "/video - Видео\n"
            "/help - Помощь\n"
            "/lang - Язык"
        ),
        "wait": "⏳ Подождите...",
        "recognizing": "🎧 Определяю песню...",
        "searching": "🔎 AX MUSIC ищет...",
        "not_found": "😔 Песня не найдена.",
        "error": "❌ Произошла ошибка.",
        "no_audd": "AudD token не настроен.",
        "no_jamendo": "Jamendo CLIENT_ID не настроен.",
        "language": "Выберите язык:",
        "audio_large": "Аудиофайл слишком большой.",
        "video_large": "Видеофайл слишком большой.",
        "bad_url": "Неверная ссылка.",
        "video_ready": "📥 Видео готово!",
        "music_help": "🎵 Отправьте название песни или аудио.",
        "video_help": "🎬 Отправьте ссылку или видео.",
        "expired": "Срок поиска истёк.",
        "ffmpeg": "FFmpeg не установлен.",
        "downloading": "🎵 Подготавливаю полную версию...",
        "download_error": "Не удалось загрузить аудио."
    },
    "en": {
        "start": (
            "👋 Welcome!\n\n"
            "Send a song title or audio snippet.\n"
            "Send a permitted video link.\n\n"
            "/music - Music\n"
            "/video - Video\n"
            "/help - Help\n"
            "/lang - Language"
        ),
        "wait": "⏳ Please wait...",
        "recognizing": "🎧 Identifying song...",
        "searching": "🔎 AX MUSIC searching...",
        "not_found": "😔 Song not found.",
        "error": "❌ An error occurred.",
        "no_audd": "AudD token is not configured.",
        "no_jamendo": "Jamendo CLIENT_ID is not configured.",
        "language": "Choose a language:",
        "audio_large": "Audio file is too large.",
        "video_large": "Video file is too large.",
        "bad_url": "Invalid URL.",
        "video_ready": "📥 Video ready!",
        "music_help": "🎵 Send a song title or audio.",
        "video_help": "🎬 Send a video link or video file.",
        "expired": "Search expired.",
        "ffmpeg": "FFmpeg is not installed.",
        "downloading": "🎵 Preparing the full version...",
        "download_error": "Audio download failed."
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


def get_text(user_id):
    return TEXTS[get_language(user_id)]


def set_language(user_id, language):
    if language not in TEXTS:
        return

    with sqlite3.connect(DATABASE_PATH) as conn:
        conn.execute("""
            INSERT INTO user_settings(user_id, language)
            VALUES(?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET language=excluded.language
        """, (user_id, language))
        conn.commit()


# ==================================================
# HELPERS
# ==================================================

def normalize(value):
    value = unicodedata.normalize("NFKD", str(value)).casefold()

    value = "".join(
        char for char in value
        if not unicodedata.combining(char)
    )

    value = "".join(
        char if char.isalnum() else " "
        for char in value
    )

    return re.sub(r"\s+", " ", value).strip()


def calculate_match(query, title, artist=""):
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
        overlap = len(query_words & target_words) / len(query_words)
        score = max(score, overlap)

    return min(100, round(score * 100))


def format_duration(seconds):
    try:
        seconds = int(seconds or 0)
    except (TypeError, ValueError):
        seconds = 0

    return f"{seconds // 60}:{seconds % 60:02d}"


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

        score = SequenceMatcher(
            None, query, filename
        ).ratio()

        if query in filename or filename in query:
            score = max(score, 0.90)

        if score > best_score:
            best_match = file
            best_score = score

    return best_match if best_score >= 0.45 else None


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
        logger.warning("Temporary file delete error: %s", path)


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


async def download_telegram_file(file_id, destination):
    file_info = await bot.get_file(file_id)

    await bot.download_file(
        file_info.file_path,
        destination=destination
    )


# ==================================================
# JAMENDO SEARCH
# ==================================================

async def search_jamendo(query):
    client_id = JAMENDO_CLIENT_ID.strip()

    if not client_id:
        raise RuntimeError(
            "JAMENDO_CLIENT_ID Render Environment'da mavjud emas"
        )

    query = (query or "").strip()

    if not query:
        return []

    timeout = aiohttp.ClientTimeout(
        total=40,
        connect=15,
        sock_read=30
    )

    params = {
        "client_id": client_id,
        "format": "json",
        "limit": MAX_SEARCH_RESULTS,
        "search": query,
        "type": "single albumtrack",
        "audioformat": "mp32",
        "audiodlformat": "mp32",
        "imagesize": 300,
        "include": "licenses"
    }

    headers = {
        "User-Agent": "AX-MUSIC-BOT/2.0"
    }

    try:
        async with aiohttp.ClientSession(
            timeout=timeout,
            headers=headers
        ) as session:

            async with session.get(
                JAMENDO_URL,
                params=params
            ) as response:

                response_text = await response.text()

                if response.status != 200:
                    logger.error(
                        "Jamendo HTTP error: status=%s body=%s",
                        response.status,
                        response_text[:1500]
                    )

                    raise RuntimeError(
                        f"Jamendo HTTP {response.status}"
                    )

                try:
                    data = await response.json(
                        content_type=None
                    )
                except Exception as exc:
                    logger.error(
                        "Jamendo JSON error: %s | body=%s",
                        exc,
                        response_text[:1500]
                    )
                    raise RuntimeError(
                        "Jamendo noto'g'ri JSON qaytardi"
                    ) from exc

    except asyncio.TimeoutError as exc:
        logger.exception("Jamendo timeout")
        raise RuntimeError(
            "Jamendo server javob bermadi"
        ) from exc

    except aiohttp.ClientError as exc:
        logger.exception("Jamendo connection error")
        raise RuntimeError(
            "Jamendo bilan ulanishda xatolik"
        ) from exc

    if not isinstance(data, dict):
        raise RuntimeError("Jamendo javobi noto'g'ri formatda")

    api_headers = data.get("headers") or {}

    if api_headers.get("status") != "success":
        error_message = api_headers.get(
            "error_message",
            "Noma'lum Jamendo API xatosi"
        )

        logger.error(
            "Jamendo API rejected request: %s | headers=%s",
            error_message,
            api_headers
        )

        raise RuntimeError(
            f"Jamendo API: {error_message}"
        )

    results = []

    for item in data.get("results", []):
        try:
            title = item.get("name") or "Unknown"
            artist = item.get("artist_name") or "Unknown"

            duration = int(item.get("duration") or 0)

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
                "duration": format_duration(duration),
                "duration_seconds": duration,
                "preview": item.get("audio") or None,
                "download": download_url,
                "download_allowed": allowed,
                "link": item.get("shareurl") or "",
                "artwork": item.get("image") or "",
                "license": item.get("license_ccurl") or "",
                "score": calculate_match(
                    query,
                    title,
                    artist
                )
            })

        except (TypeError, ValueError, AttributeError):
            logger.exception(
                "Jamendo track parsing error: %s",
                item
            )

    results.sort(
        key=lambda item: (
            item["score"],
            item["download_allowed"]
        ),
        reverse=True
    )

    logger.info(
        "Jamendo search successful: query=%r results=%d",
        query,
        len(results)
    )

    return results


# ==================================================
# MUSIC SEARCH RESULT UI
# ==================================================

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
        rows.append([
            InlineKeyboardButton(
                text=f"🎵 {song['title'][:30]}",
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

    return InlineKeyboardMarkup(inline_keyboard=rows)


def make_results_text(query, results, page, user_id):
    language = get_language(user_id)

    labels = {
        "uz": {
            "search": "SMART MUSIQA QIDIRUVI",
            "result": "QIDIRUV NATIJASI",
            "best": "ENG YAXSHI NATIJA",
            "similar": "O'XSHASH QO'SHIQLAR",
            "found": "TA TREK TOPILDI",
            "match": "MOSLIK",
            "page": "SAHIFA",
            "online": "ONLINE"
        },
        "ru": {
            "search": "ПОИСК МУЗЫКИ",
            "result": "РЕЗУЛЬТАТ ПОИСКА",
            "best": "ЛУЧШИЙ РЕЗУЛЬТАТ",
            "similar": "ПОХОЖИЕ ТРЕКИ",
            "found": "ТРЕКОВ НАЙДЕНО",
            "match": "СОВПАДЕНИЕ",
            "page": "СТРАНИЦА",
            "online": "ONLINE"
        },
        "en": {
            "search": "SMART MUSIC SEARCH",
            "result": "SEARCH RESULT",
            "best": "BEST MATCH",
            "similar": "SIMILAR TRACKS",
            "found": "TRACKS FOUND",
            "match": "MATCH",
            "page": "PAGE",
            "online": "ONLINE"
        }
    }

    t = labels[language]

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
        f"<i>{t['search']}</i>\n"
        f"🟢 <b>{t['online']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"🔎 <b>{html.escape(query)}</b>\n\n"
        "╭━━━━━━━━━━━━━━━━━━╮\n"
        f"  <b>{t['result']} / 001</b>\n\n"
        f"  🎧 <b>{html.escape(best['title'])}</b>\n"
        f"  👤 {html.escape(best['artist'])}\n"
        f"  ⏱ {best['duration']}\n"
        f"  ⭐ {t['best']}: {best['score']}%\n"
        "╰━━━━━━━━━━━━━━━━━━╯\n\n"
        f"🎼 <b>{t['similar']}</b>\n"
        "━━━━━━━━━━━━━━━━━━\n\n"
        f"📀 <b>{total} {t['found']}</b>\n\n"
    )

    for index, song in enumerate(
        current,
        start=page * PAGE_SIZE + 1
    ):
        status = (
            "✅ FULL AUDIO"
            if song["download_allowed"]
            else "🔗 STREAM ONLY"
        )

        text += (
            f"<b>{index:02d}. "
            f"{html.escape(song['title'])}</b>\n"
            f"👤 {html.escape(song['artist'])}\n"
            f"⏱ {song['duration']}  "
            f"🎯 {t['match']}: {song['score']}%\n"
            f"📥 {status}\n"
            "━━━━━━━━━━━━━━━━━━\n"
        )

    text += (
        f"\n📄 <b>{t['page']} "
        f"{page + 1:02d}/{total_pages:02d}</b>\n"
        "\n👇 <i>Tinglash uchun tugmani bosing.</i>"
    )

    return text


async def show_music_results(message, query):
    user_id = message.from_user.id
    t = get_text(user_id)

    wait = await message.answer(t["searching"])

    try:
        results = await search_jamendo(query)

        if not results:
            await wait.edit_text(t["not_found"])
            return

        search_id = uuid.uuid4().hex[:10]

        SEARCH_CACHE[search_id] = {
            "query": query,
            "results": results,
            "user_id": user_id
        }

        while len(SEARCH_CACHE) > 100:
            SEARCH_CACHE.pop(
                next(iter(SEARCH_CACHE)),
                None
            )

        await wait.edit_text(
            make_results_text(query, results, 0, user_id),
            reply_markup=make_music_keyboard(
                search_id, 0, results
            )
        )

    except RuntimeError as exc:
        logger.error(
            "Music search API/configuration error: %s",
            exc
        )

        await wait.edit_text(
            "❌ Musiqa qidirishda xatolik.\n"
            "Render Logs va Environment sozlamalarini tekshiring."
        )

    except Exception:
        logger.exception("Unexpected music search error")

        await wait.edit_text(
            "❌ Kutilmagan xatolik yuz berdi."
        )


# ==================================================
# PAGINATION
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

        if cached["user_id"] != callback.from_user.id:
            await callback.answer(
                "Bu qidiruv boshqa foydalanuvchiga tegishli.",
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
        logger.exception("Pagination error")
        await callback.answer(
            "Xatolik yuz berdi.",
            show_alert=True
        )


# ==================================================
# LICENSED AUDIO DOWNLOAD
# ==================================================

async def download_licensed_audio(url, destination):
    timeout = aiohttp.ClientTimeout(total=180)

    headers = {
        "User-Agent": "AX-MUSIC-BOT/2.0"
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
                    "Audio o'rniga HTML javobi olindi"
                )

            total = 0

            with open(destination, "wb") as file:
                async for chunk in response.content.iter_chunked(
                    64 * 1024
                ):
                    total += len(chunk)

                    if total > MAX_AUDIO_BYTES:
                        raise ValueError(
                            "Audio fayl hajmi chegaradan oshdi"
                        )

                    file.write(chunk)

    if (
        not destination.exists()
        or destination.stat().st_size == 0
    ):
        raise RuntimeError("Audio fayl bo'sh")

    return True


@dp.callback_query(F.data.startswith("play:"))
async def play_callback(callback):
    path = None
    wait = None

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

        await callback.answer("Audio tayyorlanmoqda...")

        local_file = (
            find_song(f"{song['artist']} {song['title']}")
            or find_song(song["title"])
        )

        if local_file:
            await callback.message.answer_audio(
                FSInputFile(local_file),
                title=song["title"][:64],
                performer=song["artist"][:64],
                caption="🎵 AX MUSIC | FULL AUDIO"
            )
            return

        if (
            not song.get("download_allowed")
            or not song.get("download")
        ):
            text = (
                f"🎵 <b>{html.escape(song['title'])}</b>\n"
                f"👤 {html.escape(song['artist'])}\n\n"
                "⚠️ Bu trekni to'liq yuklab olishga ruxsat yo'q.\n"
            )

            if song.get("preview"):
                text += "\n🔊 Qisqa tinglash namunasi mavjud."

            if song.get("link"):
                text += (
                    f'\n\n<a href="{html.escape(song["link"], quote=True)}">'
                    "Rasmiy sahifani ochish</a>"
                )

            if song.get("license"):
                text += (
                    f'\n<a href="{html.escape(song["license"], quote=True)}">'
                    "Litsenziya shartlari</a>"
                )

            await callback.message.answer(
                text,
                disable_web_page_preview=True
            )
            return

        TEMP_DIR.mkdir(parents=True, exist_ok=True)

        path = TEMP_DIR / (
            f"jamendo_{uuid.uuid4().hex}.mp3"
        )

        wait = await callback.message.answer(
            get_text(callback.from_user.id)["downloading"]
        )

        await download_licensed_audio(
            song["download"],
            path
        )

        caption = (
            "🎵 <b>AX MUSIC | FULL VERSION</b>\n"
            f"👤 {html.escape(song['artist'])}\n"
        )

        if song.get("license"):
            caption += (
                f'\n<a href="{html.escape(song["license"], quote=True)}">'
                "Creative Commons license</a>"
            )

        await callback.message.answer_audio(
            FSInputFile(path),
            title=song["title"][:64],
            performer=song["artist"][:64],
            caption=caption
        )

    except Exception:
        logger.exception("Play callback error")

        await callback.message.answer(
            get_text(callback.from_user.id)["download_error"]
        )

    finally:
        if wait:
            await delete_message(wait)

        if path:
            await safe_delete(path)


# ==================================================
# COMMANDS
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
    t = get_text(message.from_user.id)

    await message.answer(
        "ℹ️ <b>Yordam</b>\n\n"
        f"{t['music_help']}\n"
        f"{t['video_help']}\n"
        "/lang - Tilni o'zgartirish"
    )


# ==================================================
# LANGUAGE SELECTION
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
    language = callback.data.split("_", 1)[1]

    if language not in TEXTS:
        await callback.answer()
        return

    set_language(callback.from_user.id, language)

    await callback.answer("OK")

    await callback.message.edit_text(
        TEXTS[language]["start"]
    )


# ==================================================
# ROUND VIDEO
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
# VIDEO DOWNLOAD
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
        info = ydl.extract_info(
            url,
            download=True
        )

        return ydl.prepare_filename(info)


@dp.message(F.text.regexp(r"^https?://"))
async def url_message(message):
    t = get_text(message.from_user.id)
    url = message.text.strip()

    parsed = urlparse(url)

    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
    ):
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

        for candidate in TEMP_DIR.glob(
            f"video_{message.from_user.id}_{message.message_id}.*"
        ):
            await safe_delete(candidate)


# ==================================================
# VIDEO TO MP3
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
# ROUND BUTTON
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
# AUDD MUSIC RECOGNITION
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

                    data = await response.json(
                        content_type=None
                    )

        result = data.get("result")

        if data.get("status") != "success" or not result:
            await message.answer(t["not_found"])
            return

        title = result.get("title", "Unknown")
        artist = result.get("artist", "Unknown")

        await show_music_results(
            message,
            f"{artist} {title}"
        )

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
# SEARCH BY SONG TITLE
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

    if re.match(r"^https?://", query, re.IGNORECASE):
        return

    await show_music_results(
        message,
        query
    )


# ==================================================
# RENDER HEALTH SERVER
# ==================================================

async def handle(request):
    return web.json_response({
        "status": "ok",
        "service": "AX MUSIC BOT"
    })


# ==================================================
# START BOT
# ==================================================

async def main():
    MUSIC_LIBRARY_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    DATA_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    TEMP_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

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
            "FFmpeg o'rnatilmagan!"
        )

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

    logger.info(
        "Web server started on port %s",
        PORT
    )

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
        logger.info("Bot to'xtatildi.")
