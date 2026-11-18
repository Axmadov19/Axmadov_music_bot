
import os
import re
import asyncio
import logging
import subprocess
import unicodedata
from pathlib import Path

import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)

import yt_dlp


# ==========================================
# SOZLAMALAR
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_TOKEN")
PORT = int(os.getenv("PORT", "8080"))

MUSIC_LIBRARY_DIR = Path("music_library")

MAX_VIDEO_BYTES = 48 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_langs = {}
search_results = {}

AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".aac",
    ".ogg", ".wav", ".flac"
}


# ==========================================
# TILLAR
# ==========================================

TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum!\n\n"
            "🎵 Qo'shiq nomini yozing yoki ovozli parcha yuboring.\n"
            "🎬 Video havolasini yuboring.\n"
            "🎥 Video yuborsangiz, dumaloq video qilib beraman.\n\n"
            "/music - Musiqa\n"
            "/video - Video\n"
            "/help - Yordam\n"
            "/lang - Til"
        ),
        "wait": "⏳ Kuting...",
        "recognizing": "🎧 Qo'shiq aniqlanmoqda...",
        "not_found": "😔 Qo'shiq topilmadi.",
        "not_library": (
            "Qo'shiq aniqlandi, lekin to'liq audio "
            "ruxsatli kutubxonamizda mavjud emas:"
        ),
        "error": "❌ Xatolik yuz berdi.",
        "no_audd": "AudD token sozlanmagan.",
        "no_song": "Qo'shiq topilmadi.",
        "language": "Tilni tanlang:"
    },

    "ru": {
        "start": (
            "👋 Добро пожаловать!\n\n"
            "Отправьте название песни, аудио или ссылку на видео.\n"
            "/music - Музыка\n"
            "/video - Видео\n"
            "/help - Помощь\n"
            "/lang - Язык"
        ),
        "wait": "⏳ Подождите...",
        "recognizing": "🎧 Определяю песню...",
        "not_found": "😔 Песня не найдена.",
        "not_library": "Песня определена, но аудио нет в библиотеке:",
        "error": "❌ Произошла ошибка.",
        "no_audd": "AudD token не настроен.",
        "no_song": "Песня не найдена.",
        "language": "Выберите язык:"
    },

    "en": {
        "start": (
            "👋 Welcome!\n\n"
            "Send a song title, audio snippet or video link.\n"
            "/music - Music\n"
            "/video - Video\n"
            "/help - Help\n"
            "/lang - Language"
        ),
        "wait": "⏳ Please wait...",
        "recognizing": "🎧 Identifying song...",
        "not_found": "😔 Song not found.",
        "not_library": "Song identified, but audio is not in our library:",
        "error": "❌ An error occurred.",
        "no_audd": "AudD token is not configured.",
        "no_song": "Song not found.",
        "language": "Choose language:"
    }
}


def get_text(user_id):
    lang = user_langs.get(user_id, "uz")
    return TEXTS.get(lang, TEXTS["uz"])


# ==========================================
# YORDAMCHI FUNKSIYALAR
# ==========================================

def normalize(text):
    text = unicodedata.normalize("NFKD", text).casefold()

    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    return re.sub(
        r"[^a-z0-9а-яё]+",
        " ",
        text
    ).strip()


def find_song(query):
    if not MUSIC_LIBRARY_DIR.exists():
        return None

    query = normalize(query)

    if not query:
        return None

    for file in MUSIC_LIBRARY_DIR.rglob("*"):
        if not file.is_file():
            continue

        if file.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        filename = normalize(file.stem)

        if query in filename or filename in query:
            return file

    return None


async def send_song(message, title, artist=""):
    query = f"{artist} {title}".strip()

    file = find_song(query)

    if not file:
        file = find_song(title)

    if not file:
        return False

    await message.answer_audio(
        FSInputFile(file),
        title=title[:64],
        performer=artist[:64] if artist else None
    )

    return True


async def run_ffmpeg(args):
    def execute():
        subprocess.run(
            ["ffmpeg", "-y"] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=180
        )

    await asyncio.to_thread(execute)


async def delete_message(message):
    try:
        await message.delete()
    except Exception:
        pass


def format_duration(milliseconds):
    seconds = milliseconds // 1000
    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"


# ==========================================
# START VA BUYRUQLAR
# ==========================================

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        get_text(message.from_user.id)["start"]
    )


@dp.message(Command("music"))
async def music_command(message: types.Message):
    await message.answer(
        "🎵 Qo'shiq nomini yozing yoki ovozli parcha yuboring."
    )


@dp.message(Command("video"))
async def video_command(message: types.Message):
    await message.answer(
        "🎬 Video havolasini yuboring yoki video fayl jo'nating."
    )


@dp.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "ℹ️ Yordam:\n\n"
        "1. Video havolasini yuboring.\n"
        "2. Qo'shiq nomini yozing.\n"
        "3. Ovozli parcha yuboring.\n"
        "4. Video yuborib dumaloq video oling.\n"
        "5. /lang orqali tilni o'zgartiring."
    )


# ==========================================
# TIL TANLASH
# ==========================================

@dp.message(Command("lang"))
async def language_command(message: types.Message):

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
async def language_callback(callback: types.CallbackQuery):

    lang = callback.data.split("_")[1]

    if lang not in TEXTS:
        await callback.answer()
        return

    user_langs[callback.from_user.id] = lang

    await callback.answer("OK")

    await callback.message.edit_text(
        TEXTS[lang]["start"]
    )


# ==========================================
# DUMALOQ VIDEO
# ==========================================

async def create_round(message, file_id, prefix):

    t = get_text(message.from_user.id)

    input_file = f"{prefix}_input.mp4"
    output_file = f"{prefix}_round.mp4"

    wait = await message.answer(t["wait"])

    try:
        file = await bot.get_file(file_id)

        await bot.download_file(
            file.file_path,
            destination=input_file
        )

        await run_ffmpeg([
            "-i", input_file,
            "-t", "60",
            "-vf",
            "crop='min(iw,ih)':'min(iw,ih)',scale=384:384",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-c:a", "aac",
            "-b:a", "128k",
            output_file
        ])

        if os.path.exists(output_file):
            await message.answer_video_note(
                FSInputFile(output_file)
            )

    except Exception:
        logging.exception("Round video error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)

        for file in [input_file, output_file]:
            if os.path.exists(file):
                os.remove(file)


@dp.message(F.video)
async def video_message(message: types.Message):

    await create_round(
        message,
        message.video.file_id,
        f"round_{message.from_user.id}_{message.message_id}"
    )


# ==========================================
# VIDEO YUKLASH
# ==========================================

def download_video(url, filename):

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": filename,
        "max_filesize": MAX_VIDEO_BYTES,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])


@dp.message(F.text.regexp(r"https?://"))
async def url_message(message: types.Message):

    t = get_text(message.from_user.id)

    filename = (
        f"video_{message.from_user.id}_"
        f"{message.message_id}.mp4"
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

    try:
        await asyncio.to_thread(
            download_video,
            message.text.strip(),
            filename
        )

        if os.path.exists(filename):
            await message.answer_video(
                FSInputFile(filename),
                caption="📥 Video tayyor!",
                reply_markup=keyboard
            )
        else:
            await message.answer(t["error"])

    except Exception:
        logging.exception("Download error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)

        if os.path.exists(filename):
            os.remove(filename)


# ==========================================
# VIDEODAN MP3
# ==========================================

@dp.callback_query(F.data == "extract")
async def extract_audio(callback: types.CallbackQuery):

    await callback.answer()

    if not callback.message.video:
        return

    input_file = f"extract_{callback.id}.mp4"
    output_file = f"extract_{callback.id}.mp3"

    try:
        file = await bot.get_file(
            callback.message.video.file_id
        )

        await bot.download_file(
            file.file_path,
            destination=input_file
        )

        await run_ffmpeg([
            "-i", input_file,
            "-vn",
            "-b:a", "192k",
            output_file
        ])

        await callback.message.answer_audio(
            FSInputFile(output_file)
        )

    except Exception:
        logging.exception("MP3 extraction error")

        await callback.message.answer(
            get_text(callback.from_user.id)["error"]
        )

    finally:
        for file in [input_file, output_file]:
            if os.path.exists(file):
                os.remove(file)


# ==========================================
# ROUND TUGMASI
# ==========================================

@dp.callback_query(F.data == "round")
async def round_callback(callback: types.CallbackQuery):

    await callback.answer()

    if callback.message.video:
        await create_round(
            callback.message,
            callback.message.video.file_id,
            f"button_{callback.id}"
        )


# ==========================================
# AUDD MUSIQA ANIQLASH
# ==========================================

async def recognize_music(message, file_id, file_size):

    t = get_text(message.from_user.id)

    if not AUDD_TOKEN:
        await message.answer(t["no_audd"])
        return

    if file_size and file_size > MAX_AUDIO_BYTES:
        await message.answer("Audio fayl juda katta.")
        return

    wait = await message.answer(t["recognizing"])

    filename = (
        f"recognize_{message.from_user.id}_"
        f"{message.message_id}.audio"
    )

    try:
        tg_file = await bot.get_file(file_id)

        await bot.download_file(
            tg_file.file_path,
            destination=filename
        )

        timeout = aiohttp.ClientTimeout(total=60)

        async with aiohttp.ClientSession(
            timeout=timeout
        ) as session:

            with open(filename, "rb") as audio:

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

                async with session.post(
                    "https://api.audd.io/",
                    data=form
                ) as response:

                    data = await response.json()

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
            f"💿 {album}\n\n"
            f"{t['not_library']}"
        )

        if link:
            text += f"\n{link}"

        await message.answer(text)

    except Exception:
        logging.exception("Recognition error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)

        if os.path.exists(filename):
            os.remove(filename)


@dp.message(F.voice)
async def voice_handler(message: types.Message):

    await recognize_music(
        message,
        message.voice.file_id,
        message.voice.file_size or 0
    )


@dp.message(F.audio)
async def audio_handler(message: types.Message):

    await recognize_music(
        message,
        message.audio.file_id,
        message.audio.file_size or 0
    )


# ==========================================
# QO'SHIQ NOMI BILAN QIDIRISH
# RASMDAGIDEK 10 TA NATIJA
# ==========================================

@dp.message(F.text)
async def search_song(message: types.Message):

    query = message.text.strip()

    if len(query) < 2 or len(query) > 150:
        return

    if query.startswith("/"):
        return

    t = get_text(message.from_user.id)

    wait = await message.answer(t["wait"])

    try:
        async with aiohttp.ClientSession() as session:

            async with session.get(
                "https://itunes.apple.com/search",
                params={
                    "term": query,
                    "entity": "song",
                    "limit": 10
                },
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:

                data = await response.json()

        results = data.get("results", [])

        if not results:
            await message.answer(t["not_found"])
            return

        songs = []

        for song in results:

            songs.append({
                "title": song.get("trackName", "Unknown"),
                "artist": song.get("artistName", "Unknown"),
                "duration": song.get("trackTimeMillis", 0),
                "link": song.get("trackViewUrl", "")
            })

        # Natijalar ro'yxati

        text = f"🔍 {query}\n\n"

        for i, song in enumerate(songs, start=1):

            duration = format_duration(
                song["duration"]
            )

            text += (
                f"{i}. {song['artist']} – "
                f"{song['title']} {duration}\n"
            )

        # Raqamli tugmalar

        keyboard_buttons = []

        for i in range(len(songs)):

            keyboard_buttons.append(
                InlineKeyboardButton(
                    text=str(i + 1),
                    callback_data=f"pick_{i}"
                )
            )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                keyboard_buttons[i:i + 5]
                for i in range(0, len(keyboard_buttons), 5)
            ]
        )

        result_message = await message.answer(
            text,
            reply_markup=keyboard
        )

        # Foydalanuvchi natijalarini alohida saqlash

        key = (
            message.from_user.id,
            message.chat.id,
            result_message.message_id
        )

        search_results[key] = songs

    except Exception:
        logging.exception("Music search error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)


# ==========================================
# QO'SHIQ TANLASH
# ==========================================

@dp.callback_query(F.data.startswith("pick_"))
async def select_song(callback: types.CallbackQuery):

    try:
        index = int(callback.data.split("_")[1])

        key = (
            callback.from_user.id,
            callback.message.chat.id,
            callback.message.message_id
        )

        songs = search_results.get(key)

        if not songs or index < 0 or index >= len(songs):

            await callback.answer(
                "Qidiruv natijasi topilmadi!",
                show_alert=True
            )
            return

        song = songs[index]

        await callback.answer(
            "⏳ Qo'shiq tekshirilmoqda..."
        )

        title = song["title"]
        artist = song["artist"]

        sent = await send_song(
            callback.message,
            title,
            artist
        )

        if sent:
            return

        link = song.get("link")

        if link:
            await callback.message.answer(
                f"🎵 {title}\n"
                f"🎤 {artist}\n\n"
                "To'liq qo'shiqni rasmiy manbadan tinglang:\n"
                f"{link}"
            )
        else:
            await callback.message.answer(
                "😔 Qo'shiq kutubxonada mavjud emas."
            )

    except Exception:
        logging.exception("Song selection error")

        await callback.answer(
            "Xatolik yuz berdi!",
            show_alert=True
        )


# ==========================================
# WEB SERVER
# ==========================================

async def handle(request):

    return web.Response(
        text="Axmadov_music_bot is running!"
    )


# ==========================================
# BOTNI ISHGA TUSHIRISH
# ==========================================

async def main():

    MUSIC_LIBRARY_DIR.mkdir(
        parents=True,
        exist_ok=True
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

    logging.info(
        "Web server started on port %s",
        PORT
    )

    try:
        await dp.start_polling(bot)

    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
