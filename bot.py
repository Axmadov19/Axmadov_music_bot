
import asyncio
import logging
import os
import re
import sys
import uuid
import shutil
import tempfile
import threading
import subprocess
import time

from pathlib import Path
from urllib.parse import urlparse

from aiohttp import web

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import yt_dlp


# ==========================================
# CONFIGURATION
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    stream=sys.stdout
)

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
PORT = int(os.getenv("PORT", "8080"))

MAX_SIZE = 49 * 1024 * 1024
CACHE_TTL = 30 * 60

dp = Dispatcher()

user_lang = {}
user_mode = {}
active_tasks = {}
video_cache = {}

SUPPORTED_DOMAINS = {
    "youtube.com", "youtu.be",
    "instagram.com",
    "tiktok.com",
    "facebook.com", "fb.watch",
    "twitter.com", "x.com",
    "pinterest.com", "pin.it",
    "reddit.com", "redd.it"
}


# ==========================================
# TRANSLATIONS
# ==========================================

TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum!\n"
            "Axmadov Music botga xush kelibsiz!\n\n"
            "📥 Video yuklash: ijtimoiy tarmoq havolasini yuboring.\n"
            "🎵 Musiqa: qo'shiq nomini yozing.\n\n"
            "/start - Botni ishga tushirish\n"
            "/music - Musiqa qidirish\n"
            "/video - Video yuklash\n"
            "/help - Yordam\n"
            "/lang - Tilni o'zgartirish\n"
            "/stop - Yuklashni to'xtatish"
        ),
        "music": "🎵 Qo'shiq nomi yoki ijrochi ismini yuboring:",
        "video": "🎬 Video havolasini yuboring:",
        "help": (
            "ℹ️ YORDAM\n\n"
            "1. Video yuklash uchun havola yuboring.\n"
            "2. Musiqa qidirish uchun /music bosing.\n"
            "3. ROUND tugmasi videoni dumaloq shaklda yuboradi.\n"
            "4. MUSIC tugmasi videodan MP3 ajratadi.\n"
            "5. /stop yuklashni to'xtatishni so'raydi.\n"
            "6. /lang tilni o'zgartiradi."
        ),
        "lang_select": "🌐 Tilni tanlang:",
        "lang_changed": "✅ Til O'zbek tiliga o'zgartirildi.",
        "video_wait": "⏳ Video yuklanmoqda...",
        "music_wait": "🔎 Musiqa qidirilmoqda...",
        "round_wait": "🔄 Dumaloq video tayyorlanmoqda...",
        "audio_wait": "🎵 MP3 tayyorlanmoqda...",
        "video_ready": "✅ Video tayyor!",
        "music_ready": "🎵 Musiqa tayyor!",
        "round_ready": "⭕ Dumaloq video tayyor!",
        "error": "❌ Xatolik yuz berdi. Boshqa havola bilan urinib ko'ring.",
        "not_found": "❌ Fayl topilmadi.",
        "invalid": "❌ Ushbu havola qo'llab-quvvatlanmaydi.",
        "large": "❌ Fayl 49 MB dan katta.",
        "busy": "⏳ Sizda boshqa jarayon davom etmoqda.",
        "stop": "🛑 To'xtatish so'rovi yuborildi.",
        "stop_none": "ℹ️ Faol jarayon mavjud emas.",
        "expired": "⌛ Ushbu video tugmalarining muddati tugagan. Videoni qaytadan yuboring.",
        "choose_music": "🎵 Musiqa qidirish uchun /music buyrug'ini bosing.",
        "choose_video": "🎬 Video havolasini yuboring.",
        "cancelled": "🛑 Jarayon bekor qilindi."
    },

    "ru": {
        "start": (
            "👋 Добро пожаловать в Axmadov Music!\n\n"
            "📥 Отправьте ссылку на видео.\n"
            "🎵 Напишите название песни.\n\n"
            "/start - Запуск\n/music - Музыка\n"
            "/video - Видео\n/help - Помощь\n"
            "/lang - Язык\n/stop - Остановка"
        ),
        "music": "🎵 Напишите название песни или исполнителя:",
        "video": "🎬 Отправьте ссылку на видео:",
        "help": (
            "ℹ️ ПОМОЩЬ\n\n"
            "Отправьте ссылку для загрузки видео.\n"
            "/music - Поиск музыки.\n"
            "ROUND - Круглое видео.\n"
            "MUSIC - Извлечение MP3.\n"
            "/stop - Остановка."
        ),
        "lang_select": "🌐 Выберите язык:",
        "lang_changed": "✅ Язык изменен на Русский.",
        "video_wait": "⏳ Загружаю видео...",
        "music_wait": "🔎 Ищу музыку...",
        "round_wait": "🔄 Создаю круглое видео...",
        "audio_wait": "🎵 Создаю MP3...",
        "video_ready": "✅ Видео готово!",
        "music_ready": "🎵 Музыка готова!",
        "round_ready": "⭕ Круглое видео готово!",
        "error": "❌ Ошибка. Попробуйте другую ссылку.",
        "not_found": "❌ Файл не найден.",
        "invalid": "❌ Эта ссылка не поддерживается.",
        "large": "❌ Файл больше 49 МБ.",
        "busy": "⏳ Другой процесс уже выполняется.",
        "stop": "🛑 Запрошена остановка.",
        "stop_none": "ℹ️ Нет активных процессов.",
        "expired": "⌛ Срок действия кнопок истек.",
        "choose_music": "🎵 Используйте /music.",
        "choose_video": "🎬 Отправьте ссылку на видео.",
        "cancelled": "🛑 Процесс отменен."
    },

    "en": {
        "start": (
            "👋 Welcome to Axmadov Music!\n\n"
            "📥 Send a social media video link.\n"
            "🎵 Type a song title.\n\n"
            "/start - Start\n/music - Music\n"
            "/video - Video\n/help - Help\n"
            "/lang - Language\n/stop - Stop"
        ),
        "music": "🎵 Enter a song title or artist:",
        "video": "🎬 Send a video link:",
        "help": (
            "ℹ️ HELP\n\n"
            "Send a video link to download.\n"
            "/music - Search music.\n"
            "ROUND - Create a round video.\n"
            "MUSIC - Extract MP3.\n"
            "/stop - Stop process."
        ),
        "lang_select": "🌐 Choose language:",
        "lang_changed": "✅ Language changed to English.",
        "video_wait": "⏳ Downloading video...",
        "music_wait": "🔎 Searching music...",
        "round_wait": "🔄 Creating round video...",
        "audio_wait": "🎵 Creating MP3...",
        "video_ready": "✅ Video ready!",
        "music_ready": "🎵 Music ready!",
        "round_ready": "⭕ Round video ready!",
        "error": "❌ An error occurred.",
        "not_found": "❌ File not found.",
        "invalid": "❌ Unsupported link.",
        "large": "❌ File exceeds 49 MB.",
        "busy": "⏳ Another process is running.",
        "stop": "🛑 Cancellation requested.",
        "stop_none": "ℹ️ No active process.",
        "expired": "⌛ These buttons have expired.",
        "choose_music": "🎵 Use /music.",
        "choose_video": "🎬 Send a video link.",
        "cancelled": "🛑 Process cancelled."
    }
}


def T(user_id, key):
    lang = user_lang.get(user_id, "uz")
    return TEXTS.get(lang, TEXTS["uz"]).get(key, key)


# ==========================================
# VALIDATE URL
# ==========================================

def valid_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        return (
            parsed.scheme in ("http", "https")
            and any(
                host == domain or host.endswith("." + domain)
                for domain in SUPPORTED_DOMAINS
            )
        )
    except Exception:
        return False


# ==========================================
# DOWNLOAD HELPERS
# ==========================================

def check_cancel(event):
    if event.is_set():
        raise InterruptedError("Cancelled by user")


def progress_hook(event):
    def hook(data):
        check_cancel(event)
    return hook


def find_file(folder, extension=None):
    files = [
        p for p in Path(folder).iterdir()
        if p.is_file()
        and (extension is None or p.suffix.lower() == extension.lower())
    ]

    return max(files, key=lambda p: p.stat().st_size) if files else None


# ==========================================
# VIDEO DOWNLOAD
# ==========================================

def download_video(url, folder, event):
    check_cancel(event)

    options = {
        "outtmpl": str(Path(folder) / "video.%(ext)s"),
        "format": (
            "best[ext=mp4][filesize<49M]/"
            "best[filesize<49M]/"
            "best[ext=mp4]/best"
        ),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_SIZE,
        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3,
        "progress_hooks": [progress_hook(event)]
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.extract_info(url, download=True)

    check_cancel(event)

    path = find_file(folder)

    if not path:
        raise FileNotFoundError("Video not found")

    if path.stat().st_size > MAX_SIZE:
        raise ValueError("File too large")

    return str(path)


# ==========================================
# MUSIC SEARCH AND DOWNLOAD
# ==========================================

def download_music(query, folder, event):
    check_cancel(event)

    options = {
        "outtmpl": str(Path(folder) / "music.%(ext)s"),
        "format": "bestaudio/best",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "max_filesize": MAX_SIZE,
        "socket_timeout": 30,
        "retries": 3,
        "default_search": "ytsearch1",
        "progress_hooks": [progress_hook(event)],
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "mp3",
            "preferredquality": "192"
        }]
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        info = ydl.extract_info(
            "ytsearch1:" + query,
            download=True
        )

        if info.get("entries"):
            info = info["entries"][0]

    check_cancel(event)

    path = find_file(folder, ".mp3")

    if not path:
        raise FileNotFoundError("MP3 not found")

    if path.stat().st_size > MAX_SIZE:
        raise ValueError("Music too large")

    title = info.get("title", "Music")
    artist = info.get("artist") or info.get("uploader") or "Unknown"

    return str(path), title, artist


# ==========================================
# ROUND VIDEO CONVERSION
# ==========================================

def create_round_video(source, output, event):
    check_cancel(event)

    command = [
        "ffmpeg",
        "-y",
        "-i", source,
        "-t", "60",
        "-vf",
        "crop=min(iw\\,ih):min(iw\\,ih),"
        "scale=360:360:force_original_aspect_ratio=increase,"
        "crop=360:360,fps=30,format=yuv420p",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "28",
        "-maxrate", "900k",
        "-bufsize", "1800k",
        "-c:a", "aac",
        "-b:a", "96k",
        "-movflags", "+faststart",
        output
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180
    )

    check_cancel(event)

    if result.returncode != 0 or not os.path.exists(output):
        raise RuntimeError("Round conversion failed")

    if os.path.getsize(output) > MAX_SIZE:
        raise ValueError("Round file too large")

    return output


# ==========================================
# EXTRACT MUSIC FROM VIDEO
# ==========================================

def extract_audio(source, output, event):
    check_cancel(event)

    command = [
        "ffmpeg",
        "-y",
        "-i", source,
        "-vn",
        "-codec:a", "libmp3lame",
        "-b:a", "192k",
        output
    ]

    result = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=180
    )

    check_cancel(event)

    if result.returncode != 0 or not os.path.exists(output):
        raise RuntimeError("Audio extraction failed")

    if os.path.getsize(output) > MAX_SIZE:
        raise ValueError("Audio too large")

    return output


# ==========================================
# INLINE VIDEO BUTTONS
# ==========================================

def video_keyboard(token):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="⭕ ROUND",
                    callback_data=f"round:{token}"
                ),
                InlineKeyboardButton(
                    text="🎵 MUSIC",
                    callback_data=f"audio:{token}"
                )
            ]
        ]
    )


# ==========================================
# CACHE CLEANUP
# ==========================================

def remove_cache(token):
    item = video_cache.pop(token, None)

    if item:
        shutil.rmtree(item["folder"], ignore_errors=True)


async def cache_cleaner():
    while True:
        await asyncio.sleep(60)

        now = time.time()

        for token, item in list(video_cache.items()):
            if now - item["created"] > CACHE_TTL:
                remove_cache(token)


# ==========================================
# BOT COMMANDS
# ==========================================

async def setup_commands(bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="music", description="Musiqa qidirish"),
        BotCommand(command="video", description="Video yuklash"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="lang", description="Tilni o'zgartirish"),
        BotCommand(command="stop", description="Yuklashni to'xtatish")
    ]

    await bot.set_my_commands(commands)


# ==========================================
# START
# ==========================================

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_mode[message.from_user.id] = "video"
    await message.answer(T(message.from_user.id, "start"))


# ==========================================
# MUSIC MODE
# ==========================================

@dp.message(Command("music"))
async def music_handler(message: types.Message):
    user_mode[message.from_user.id] = "music"
    await message.answer(T(message.from_user.id, "music"))


# ==========================================
# VIDEO MODE
# ==========================================

@dp.message(Command("video"))
async def video_handler(message: types.Message):
    user_mode[message.from_user.id] = "video"
    await message.answer(T(message.from_user.id, "video"))


# ==========================================
# HELP
# ==========================================

@dp.message(Command("help"))
async def help_handler(message: types.Message):
    await message.answer(T(message.from_user.id, "help"))


# ==========================================
# LANGUAGE
# ==========================================

@dp.message(Command("lang"))
async def lang_handler(message: types.Message):
    keyboard = InlineKeyboardMarkup(
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

    await message.answer(
        T(message.from_user.id, "lang_select"),
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("lang:"))
async def change_language(callback: types.CallbackQuery):
    lang = callback.data.split(":")[1]

    if lang not in TEXTS:
        await callback.answer("Invalid language", show_alert=True)
        return

    user_lang[callback.from_user.id] = lang

    await callback.message.edit_text(
        T(callback.from_user.id, "lang_changed")
    )

    await callback.answer()


# ==========================================
# STOP
# ==========================================

@dp.message(Command("stop"))
async def stop_handler(message: types.Message):
    user_id = message.from_user.id
    event = active_tasks.get(user_id)

    if event:
        event.set()
        await message.answer(T(user_id, "stop"))
    else:
        await message.answer(T(user_id, "stop_none"))


# ==========================================
# ROUND BUTTON
# ==========================================

@dp.callback_query(F.data.startswith("round:"))
async def round_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    token = callback.data.split(":", 1)[1]

    item = video_cache.get(token)

    if not item or item["owner"] != user_id:
        await callback.answer(
            T(user_id, "expired"),
            show_alert=True
        )
        return

    if user_id in active_tasks:
        await callback.answer(T(user_id, "busy"), show_alert=True)
        return

    event = threading.Event()
    active_tasks[user_id] = event

    await callback.answer()

    wait = await callback.message.answer(
        T(user_id, "round_wait")
    )

    try:
        output = str(Path(item["folder"]) / "round.mp4")

        await asyncio.to_thread(
            create_round_video,
            item["video"],
            output,
            event
        )

        check_cancel(event)

        await callback.message.answer_video_note(
            video=FSInputFile(output)
        )

    except InterruptedError:
        await callback.message.answer(T(user_id, "cancelled"))

    except Exception:
        logging.exception("Round conversion error")
        await callback.message.answer(T(user_id, "error"))

    finally:
        if active_tasks.get(user_id) is event:
            active_tasks.pop(user_id, None)

        try:
            await wait.delete()
        except Exception:
            pass


# ==========================================
# MUSIC BUTTON
# ==========================================

@dp.callback_query(F.data.startswith("audio:"))
async def audio_handler(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    token = callback.data.split(":", 1)[1]

    item = video_cache.get(token)

    if not item or item["owner"] != user_id:
        await callback.answer(
            T(user_id, "expired"),
            show_alert=True
        )
        return

    if user_id in active_tasks:
        await callback.answer(T(user_id, "busy"), show_alert=True)
        return

    event = threading.Event()
    active_tasks[user_id] = event

    await callback.answer()

    wait = await callback.message.answer(
        T(user_id, "audio_wait")
    )

    try:
        output = str(Path(item["folder"]) / "extracted.mp3")

        await asyncio.to_thread(
            extract_audio,
            item["video"],
            output,
            event
        )

        check_cancel(event)

        await callback.message.answer_audio(
            audio=FSInputFile(output),
            title="Extracted Music",
            performer="Axmadov Music Bot"
        )

    except InterruptedError:
        await callback.message.answer(T(user_id, "cancelled"))

    except Exception:
        logging.exception("Audio extraction error")
        await callback.message.answer(T(user_id, "error"))

    finally:
        if active_tasks.get(user_id) is event:
            active_tasks.pop(user_id, None)

        try:
            await wait.delete()
        except Exception:
            pass


# ==========================================
# MAIN MESSAGE HANDLER
# ==========================================

@dp.message(F.text)
async def message_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    if not text or text.startswith("/"):
        return

    if user_id in active_tasks:
        await message.answer(T(user_id, "busy"))
        return

    match = re.search(r"https?://\S+", text)

    is_video = bool(match)

    if is_video:
        url = match.group(0).rstrip(".,!?)]}")

        if not valid_url(url):
            await message.answer(T(user_id, "invalid"))
            return

        mode = "video"

    else:
        mode = user_mode.get(user_id, "video")

        if mode != "music":
            await message.answer(T(user_id, "choose_music"))
            return

    event = threading.Event()
    active_tasks[user_id] = event

    folder = tempfile.mkdtemp(prefix="axmadov_")
    wait = None
    token = None

    try:
        if mode == "video":

            wait = await message.answer(
                T(user_id, "video_wait")
            )

            filepath = await asyncio.to_thread(
                download_video,
                url,
                folder,
                event
            )

            check_cancel(event)

            token = uuid.uuid4().hex[:16]

            video_cache[token] = {
                "owner": user_id,
                "video": filepath,
                "folder": folder,
                "created": time.time()
            }

            await message.answer_video(
                video=FSInputFile(filepath),
                caption=T(user_id, "video_ready"),
                reply_markup=video_keyboard(token),
                supports_streaming=True
            )

            # Cache folder now belongs to video_cache
            folder = None

        else:

            wait = await message.answer(
                T(user_id, "music_wait")
            )

            filepath, title, artist = await asyncio.to_thread(
                download_music,
                text,
                folder,
                event
            )

            check_cancel(event)

            await message.answer_audio(
                audio=FSInputFile(filepath),
                title=title,
                performer=artist,
                caption=T(user_id, "music_ready")
            )

    except InterruptedError:
        await message.answer(T(user_id, "cancelled"))

    except Exception as error:
        logging.exception("Main handler error: %s", error)

        if isinstance(error, ValueError) and "large" in str(error).lower():
            await message.answer(T(user_id, "large"))
        else:
            await message.answer(T(user_id, "error"))

    finally:
        if active_tasks.get(user_id) is event:
            active_tasks.pop(user_id, None)

        if folder:
            shutil.rmtree(folder, ignore_errors=True)

        if wait:
            try:
                await wait.delete()
            except Exception:
                pass


# ==========================================
# RENDER HEALTH CHECK
# ==========================================

async def health(request):
    return web.json_response({
        "status": "running",
        "bot": "Axmadov Music"
    })


async def start_server():
    app = web.Application()

    app.router.add_get("/", health)
    app.router.add_get("/health", health)

    runner = web.AppRunner(app)
    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    return runner


# ==========================================
# START BOT
# ==========================================

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN topilmadi!")

    if not shutil.which("ffmpeg"):
        raise RuntimeError(
            "FFmpeg o'rnatilmagan! Render'da FFmpeg o'rnating."
        )

    bot = Bot(token=BOT_TOKEN)

    runner = None
    cleaner = None

    try:
        await setup_commands(bot)

        await bot.delete_webhook(
            drop_pending_updates=True
        )

        runner = await start_server()

        cleaner = asyncio.create_task(cache_cleaner())

        logging.info("AXMADOV MUSIC BOT ISHGA TUSHDI!")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    finally:
        if cleaner:
            cleaner.cancel()

            try:
                await cleaner
            except asyncio.CancelledError:
                pass

        for item in list(video_cache.values()):
            shutil.rmtree(
                item["folder"],
                ignore_errors=True
            )

        video_cache.clear()

        if runner:
            await runner.cleanup()

        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi")

    except Exception:
        logging.exception("Bot ishga tushmadi")
