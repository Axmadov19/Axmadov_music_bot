
import asyncio
import logging
import os
import re
import sys
import tempfile
import shutil
import threading

from pathlib import Path
from urllib.parse import urlparse

from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    BotCommand,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import yt_dlp


# ==========================================
# SOZLAMALAR
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stdout
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "").strip()

BOT_USERNAME = "@Axmadov_music_bot"

MAX_FILE_SIZE = 50 * 1024 * 1024

PORT = int(os.environ.get("PORT", 8080))

dp = Dispatcher()

user_lang = {}
user_mode = {}

# Har bir foydalanuvchi uchun faol yuklash
active_tasks = {}


# ==========================================
# TILLAR
# ==========================================

TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum! Botga xush kelibsiz.\n\n"
            "📥 Video yuklash: Instagram, TikTok yoki YouTube havolasini yuboring.\n"
            "🎵 Musiqa yuklash: Qo'shiq nomi yoki ijrochi ismini yozing.\n\n"
            "🎬 /video - Video yuklash\n"
            "🎵 /music - Musiqa qidirish\n"
            "🌐 /lang - Tilni o'zgartirish\n"
            "ℹ️ /help - Yordam"
        ),
        "music": "🎵 Qo'shiq nomi yoki ijrochi ismini yozing:",
        "video": "🎬 Instagram, TikTok yoki YouTube havolasini yuboring:",
        "help": (
            "ℹ️ YORDAM\n\n"
            "1. Video yuklash uchun havola yuboring.\n"
            "2. Musiqa topish uchun /music buyrug'ini bosing.\n"
            "3. Jarayonni to'xtatish uchun /stop buyrug'ini yuboring.\n"
            "4. Tilni o'zgartirish uchun /lang buyrug'idan foydalaning."
        ),
        "lang_select": "🌐 Tilni tanlang:",
        "lang_changed": "✅ Til O'zbek tiliga o'zgartirildi.",
        "stop_ok": "🛑 Yuklash jarayonini to'xtatish so'raldi.",
        "stop_none": "ℹ️ Hozirda faol jarayon mavjud emas.",
        "busy": "⏳ Sizda boshqa yuklash jarayoni davom etmoqda.",
        "downloading_video": "⏳ Video yuklanmoqda...",
        "searching_music": "🔎 Musiqa qidirilmoqda va yuklanmoqda...",
        "error": "❌ Xatolik yuz berdi. Havolani tekshiring yoki keyinroq urinib ko'ring.",
        "not_found": "❌ Hech narsa topilmadi. Boshqa nom bilan urinib ko'ring.",
        "too_large": "❌ Fayl hajmi 50 MB dan katta.",
        "invalid_url": "❌ Faqat Instagram, TikTok va YouTube havolalari qabul qilinadi.",
        "music_ready": "🎵 Musiqa tayyor!",
        "video_ready": "✅ Video tayyor!"
    },

    "ru": {
        "start": (
            "👋 Здравствуйте! Добро пожаловать!\n\n"
            "📥 Видео: отправьте ссылку Instagram, TikTok или YouTube.\n"
            "🎵 Музыка: напишите название песни или исполнителя.\n\n"
            "/video - Видео\n"
            "/music - Музыка\n"
            "/lang - Язык\n"
            "/help - Помощь"
        ),
        "music": "🎵 Напишите название песни или исполнителя:",
        "video": "🎬 Отправьте ссылку Instagram, TikTok или YouTube:",
        "help": (
            "ℹ️ ПОМОЩЬ\n\n"
            "1. Отправьте ссылку для загрузки видео.\n"
            "2. Используйте /music для поиска музыки.\n"
            "3. Используйте /stop для остановки процесса.\n"
            "4. Используйте /lang для смены языка."
        ),
        "lang_select": "🌐 Выберите язык:",
        "lang_changed": "✅ Язык изменен на Русский.",
        "stop_ok": "🛑 Запрошена остановка загрузки.",
        "stop_none": "ℹ️ Активных процессов нет.",
        "busy": "⏳ У вас уже выполняется другая загрузка.",
        "downloading_video": "⏳ Загружаю видео...",
        "searching_music": "🔎 Поиск и загрузка музыки...",
        "error": "❌ Произошла ошибка. Проверьте ссылку или попробуйте позже.",
        "not_found": "❌ Ничего не найдено.",
        "too_large": "❌ Размер файла превышает 50 МБ.",
        "invalid_url": "❌ Поддерживаются только Instagram, TikTok и YouTube.",
        "music_ready": "🎵 Музыка готова!",
        "video_ready": "✅ Видео готово!"
    },

    "en": {
        "start": (
            "👋 Hello! Welcome to the bot!\n\n"
            "📥 Video: Send an Instagram, TikTok or YouTube link.\n"
            "🎵 Music: Type a song title or artist name.\n\n"
            "/video - Video downloader\n"
            "/music - Music search\n"
            "/lang - Change language\n"
            "/help - Help"
        ),
        "music": "🎵 Type a song title or artist name:",
        "video": "🎬 Send an Instagram, TikTok or YouTube link:",
        "help": (
            "ℹ️ HELP\n\n"
            "1. Send a link to download a video.\n"
            "2. Use /music to search for music.\n"
            "3. Use /stop to stop a process.\n"
            "4. Use /lang to change language."
        ),
        "lang_select": "🌐 Choose language:",
        "lang_changed": "✅ Language changed to English.",
        "stop_ok": "🛑 Download cancellation requested.",
        "stop_none": "ℹ️ No active process.",
        "busy": "⏳ Another download is already running.",
        "downloading_video": "⏳ Downloading video...",
        "searching_music": "🔎 Searching and downloading music...",
        "error": "❌ An error occurred. Check the link or try again later.",
        "not_found": "❌ Nothing found.",
        "too_large": "❌ File size exceeds 50 MB.",
        "invalid_url": "❌ Only Instagram, TikTok and YouTube links are supported.",
        "music_ready": "🎵 Music is ready!",
        "video_ready": "✅ Video is ready!"
    }
}


# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================

def get_text(user_id, key):
    lang = user_lang.get(user_id, "uz")
    return TEXTS.get(lang, TEXTS["uz"]).get(key, key)


def is_valid_url(url):
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        allowed_domains = (
            "youtube.com",
            "youtu.be",
            "instagram.com",
            "tiktok.com"
        )

        return (
            parsed.scheme in ("http", "https")
            and any(
                host == domain or host.endswith("." + domain)
                for domain in allowed_domains
            )
        )

    except Exception:
        return False


def check_cancel(stop_event):
    if stop_event.is_set():
        raise yt_dlp.utils.DownloadError("Download cancelled")


def download_progress_hook(stop_event):
    def hook(data):
        check_cancel(stop_event)

    return hook


def get_downloaded_file(folder, extension=None):
    files = [
        f for f in Path(folder).iterdir()
        if f.is_file()
    ]

    if extension:
        files = [
            f for f in files
            if f.suffix.lower() == extension.lower()
        ]

    return files[0] if files else None


def cleanup_folder(folder):
    try:
        shutil.rmtree(folder, ignore_errors=True)
    except Exception:
        logging.exception("Fayllarni tozalashda xatolik")


# ==========================================
# VIDEO YUKLASH
# ==========================================

def download_video_sync(url, folder, stop_event):

    check_cancel(stop_event)

    ydl_opts = {
        "outtmpl": str(Path(folder) / "video.%(ext)s"),

        "format": (
            "best[ext=mp4][filesize<50M]/"
            "best[filesize<50M]/"
            "best[ext=mp4]/best"
        ),

        "merge_output_format": "mp4",

        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,

        "max_filesize": MAX_FILE_SIZE,

        "progress_hooks": [
            download_progress_hook(stop_event)
        ],

        "socket_timeout": 30,
        "retries": 3,
        "fragment_retries": 3
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        ydl.extract_info(url, download=True)

    check_cancel(stop_event)

    filepath = get_downloaded_file(folder)

    if not filepath:
        raise FileNotFoundError("Video fayli topilmadi")

    if filepath.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("Video 50 MB dan katta")

    return str(filepath)


# ==========================================
# MUSIQA YUKLASH
# ==========================================

def download_music_sync(query, folder, stop_event):

    check_cancel(stop_event)

    ydl_opts = {
        "outtmpl": str(Path(folder) / "music.%(ext)s"),

        "format": "bestaudio/best",

        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,

        "default_search": "ytsearch1",

        "progress_hooks": [
            download_progress_hook(stop_event)
        ],

        "socket_timeout": 30,
        "retries": 3,

        "postprocessors": [
            {
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "192"
            }
        ]
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:

        info = ydl.extract_info(
            "ytsearch1:" + query,
            download=True
        )

        if "entries" in info:
            entries = info.get("entries") or []

            if not entries:
                raise ValueError("Musiqa topilmadi")

            info = entries[0]

    check_cancel(stop_event)

    filepath = get_downloaded_file(folder, ".mp3")

    if not filepath:
        raise FileNotFoundError("MP3 fayli topilmadi")

    if filepath.stat().st_size > MAX_FILE_SIZE:
        raise ValueError("Musiqa 50 MB dan katta")

    title = info.get("title", "Unknown")
    artist = info.get("artist") or info.get("uploader") or "Unknown"

    return str(filepath), title, artist


# ==========================================
# BOT BUYRUQLARI
# ==========================================

async def set_bot_commands(bot):

    commands = [
        BotCommand(
            command="start",
            description="Botni ishga tushirish"
        ),
        BotCommand(
            command="music",
            description="Musiqa qidirish"
        ),
        BotCommand(
            command="video",
            description="Video yuklash"
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
            description="Yuklashni to'xtatish"
        )
    ]

    await bot.set_my_commands(commands)


# ==========================================
# START
# ==========================================

@dp.message(Command("start"))
async def cmd_start(message: types.Message):

    user_id = message.from_user.id

    user_mode[user_id] = "video"

    await message.answer(
        get_text(user_id, "start")
    )


# ==========================================
# MUSIC
# ==========================================

@dp.message(Command("music"))
async def cmd_music(message: types.Message):

    user_id = message.from_user.id

    user_mode[user_id] = "music"

    await message.answer(
        get_text(user_id, "music")
    )


# ==========================================
# VIDEO
# ==========================================

@dp.message(Command("video"))
async def cmd_video(message: types.Message):

    user_id = message.from_user.id

    user_mode[user_id] = "video"

    await message.answer(
        get_text(user_id, "video")
    )


# ==========================================
# HELP
# ==========================================

@dp.message(Command("help"))
async def cmd_help(message: types.Message):

    user_id = message.from_user.id

    await message.answer(
        get_text(user_id, "help")
    )


# ==========================================
# LANGUAGE
# ==========================================

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):

    user_id = message.from_user.id

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 O'zbekcha",
                    callback_data="lang_uz"
                ),
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang_ru"
                ),
                InlineKeyboardButton(
                    text="🇬🇧 English",
                    callback_data="lang_en"
                )
            ]
        ]
    )

    await message.answer(
        get_text(user_id, "lang_select"),
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("lang_"))
async def process_lang(callback: types.CallbackQuery):

    lang = callback.data.split("_", 1)[1]

    if lang not in TEXTS:
        await callback.answer("Invalid language")
        return

    user_id = callback.from_user.id

    user_lang[user_id] = lang

    await callback.message.edit_text(
        get_text(user_id, "lang_changed")
    )

    await callback.answer()


# ==========================================
# STOP
# ==========================================

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):

    user_id = message.from_user.id

    stop_event = active_tasks.get(user_id)

    if stop_event:
        stop_event.set()

        await message.answer(
            get_text(user_id, "stop_ok")
        )

    else:
        await message.answer(
            get_text(user_id, "stop_none")
        )


# ==========================================
# ASOSIY XABARLARNI QAYTA ISHLASH
# ==========================================

@dp.message(F.text)
async def handle_messages(message: types.Message):

    user_id = message.from_user.id
    text = message.text.strip()

    if not text:
        return

    # Buyruqlarni qayta ishlamaslik
    if text.startswith("/"):
        return

    # Bir foydalanuvchiga bitta faol yuklash
    if user_id in active_tasks:
        await message.answer(
            get_text(user_id, "busy")
        )
        return

    url_match = re.search(
        r"https?://[^\s]+",
        text
    )

    is_video = bool(url_match)

    if is_video:

        url = url_match.group(0).rstrip(".,!?)]}")

        if not is_valid_url(url):
            await message.answer(
                get_text(user_id, "invalid_url")
            )
            return

        mode = "video"

    else:

        mode = user_mode.get(user_id, "video")

        if mode != "music":
            await message.answer(
                get_text(user_id, "video")
            )
            return

    stop_event = threading.Event()

    active_tasks[user_id] = stop_event

    folder = tempfile.mkdtemp(
        prefix=f"bot_{user_id}_"
    )

    wait_msg = None

    try:

        if mode == "video":

            wait_msg = await message.answer(
                get_text(user_id, "downloading_video")
            )

            filepath = await asyncio.to_thread(
                download_video_sync,
                url,
                folder,
                stop_event
            )

            check_cancel(stop_event)

            video_file = FSInputFile(filepath)

            await message.answer_video(
                video=video_file,
                caption=get_text(user_id, "video_ready"),
                supports_streaming=True
            )

        else:

            wait_msg = await message.answer(
                get_text(user_id, "searching_music")
            )

            filepath, title, artist = await asyncio.to_thread(
                download_music_sync,
                text,
                folder,
                stop_event
            )

            check_cancel(stop_event)

            audio_file = FSInputFile(filepath)

            await message.answer_audio(
                audio=audio_file,
                title=title,
                performer=artist,
                caption=get_text(user_id, "music_ready")
            )

    except Exception as e:

        if stop_event.is_set():

            logging.info(
                "Foydalanuvchi %s yuklashni to'xtatdi",
                user_id
            )

        else:

            logging.exception(
                "Yuklashda xatolik: %s",
                e
            )

            error_text = get_text(user_id, "error")

            if isinstance(e, ValueError) and "50 MB" in str(e):
                error_text = get_text(user_id, "too_large")

            elif isinstance(e, (FileNotFoundError,)):
                error_text = get_text(user_id, "not_found")

            await message.answer(error_text)

    finally:

        if active_tasks.get(user_id) is stop_event:
            active_tasks.pop(user_id, None)

        cleanup_folder(folder)

        if wait_msg:

            try:
                await wait_msg.delete()
            except Exception:
                pass


# ==========================================
# RENDER HEALTH CHECK
# ==========================================

async def health_check(request):

    return web.json_response({
        "status": "ok",
        "bot": BOT_USERNAME
    })


async def start_health_server():

    app = web.Application()

    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)

    runner = web.AppRunner(app)

    await runner.setup()

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        PORT
    )

    await site.start()

    logging.info(
        "Health server ishga tushdi: %s",
        PORT
    )

    return runner


# ==========================================
# BOTNI ISHGA TUSHIRISH
# ==========================================

async def main():

    if not BOT_TOKEN:
        raise RuntimeError(
            "BOT_TOKEN Environment Variable kiritilmagan!"
        )

    bot = Bot(token=BOT_TOKEN)

    runner = None

    try:

        await set_bot_commands(bot)

        # Polling ishlatishdan oldin webhookni o'chirish
        await bot.delete_webhook(
            drop_pending_updates=True
        )

        # Render uchun health server
        runner = await start_health_server()

        logging.info("BOT ISHGA TUSHDI!")

        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types()
        )

    finally:

        if runner:
            await runner.cleanup()

        await bot.session.close()


if __name__ == "__main__":

    try:
        asyncio.run(main())

    except KeyboardInterrupt:
        logging.info("Bot to'xtatildi")

    except Exception:
        logging.exception("Bot ishga tushishida xatolik")
