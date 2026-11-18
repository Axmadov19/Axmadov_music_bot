
import os
import re
import asyncio
import logging
import tempfile
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
# 1. SOZLAMALAR
# ==========================================

BOT_TOKEN = os.getenv("BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_TOKEN")

PORT = int(os.getenv("PORT", "8080"))

MUSIC_LIBRARY_DIR = Path("music_library")

MAX_VIDEO_BYTES = 48 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024

MAX_SEARCH_RESULTS = 10
MAX_STORED_SEARCHES = 1000

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_langs = {}
search_results = {}

AUDIO_EXTENSIONS = {
    ".mp3", ".m4a", ".aac",
    ".ogg", ".wav", ".flac"
}


# ==========================================
# 2. TILLAR
# ==========================================

TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum!\n\n"
            "🎵 Qo'shiq nomini yozing.\n"
            "🎧 Ovozli parcha yuboring.\n"
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
        "no_library": (
            "😔 Bu qo'shiqning to'liq MP3 fayli "
            "kutubxonamizda mavjud emas."
        ),
        "error": "❌ Xatolik yuz berdi.",
        "no_audd": "AudD token sozlanmagan.",
        "too_large": "❌ Audio fayl juda katta.",
        "language": "Tilni tanlang:",
        "selected": "⏳ Qo'shiq qidirilmoqda...",
        "expired": "Qidiruv natijasi eskirgan. Qayta qidiring.",
        "video_ready": "📥 Video tayyor!",
        "help": (
            "ℹ️ Yordam:\n\n"
            "1. Qo'shiq nomini yozing.\n"
            "2. 1–10 raqamidan birini tanlang.\n"
            "3. Video havolasini yuboring.\n"
            "4. Videodan MP3 ajrating.\n"
            "5. Video yuborib dumaloq video oling.\n"
            "6. /lang orqali tilni o'zgartiring."
        )
    },

    "ru": {
        "start": (
            "👋 Добро пожаловать!\n\n"
            "🎵 Отправьте название песни.\n"
            "🎧 Отправьте аудио.\n"
            "🎬 Отправьте ссылку на видео.\n\n"
            "/music - Музыка\n"
            "/video - Видео\n"
            "/help - Помощь\n"
            "/lang - Язык"
        ),
        "wait": "⏳ Подождите...",
        "recognizing": "🎧 Определяю песню...",
        "not_found": "😔 Песня не найдена.",
        "no_library": "😔 Полной MP3-версии нет в библиотеке.",
        "error": "❌ Произошла ошибка.",
        "no_audd": "AudD token не настроен.",
        "too_large": "❌ Аудиофайл слишком большой.",
        "language": "Выберите язык:",
        "selected": "⏳ Ищу песню...",
        "expired": "Результаты устарели. Выполните поиск снова.",
        "video_ready": "📥 Видео готово!",
        "help": (
            "ℹ️ Помощь:\n\n"
            "1. Отправьте название песни.\n"
            "2. Выберите номер от 1 до 10.\n"
            "3. Отправьте ссылку на видео.\n"
            "4. Извлеките MP3 из видео.\n"
            "5. Отправьте видео для создания круглого видео.\n"
            "6. /lang - изменить язык."
        )
    },

    "en": {
        "start": (
            "👋 Welcome!\n\n"
            "🎵 Send a song title.\n"
            "🎧 Send an audio snippet.\n"
            "🎬 Send a video link.\n\n"
            "/music - Music\n"
            "/video - Video\n"
            "/help - Help\n"
            "/lang - Language"
        ),
        "wait": "⏳ Please wait...",
        "recognizing": "🎧 Identifying song...",
        "not_found": "😔 Song not found.",
        "no_library": "😔 Full MP3 is not available in the library.",
        "error": "❌ An error occurred.",
        "no_audd": "AudD token is not configured.",
        "too_large": "❌ Audio file is too large.",
        "language": "Choose a language:",
        "selected": "⏳ Searching for song...",
        "expired": "Search results expired. Please search again.",
        "video_ready": "📥 Video is ready!",
        "help": (
            "ℹ️ Help:\n\n"
            "1. Send a song title.\n"
            "2. Select a number from 1 to 10.\n"
            "3. Send a video link.\n"
            "4. Extract MP3 from a video.\n"
            "5. Send a video to create a round video.\n"
            "6. /lang - Change language."
        )
    }
}


def get_text(user_id):
    lang = user_langs.get(user_id, "uz")
    return TEXTS.get(lang, TEXTS["uz"])


# ==========================================
# 3. YORDAMCHI FUNKSIYALAR
# ==========================================

def normalize(text):
    text = unicodedata.normalize(
        "NFKD",
        str(text)
    ).casefold()

    text = "".join(
        char for char in text
        if not unicodedata.combining(char)
    )

    return re.sub(
        r"[^a-z0-9а-яёёўқғҳ]+",
        " ",
        text
    ).strip()


def find_song(query):
    if not MUSIC_LIBRARY_DIR.exists():
        return None

    query = normalize(query)

    if not query:
        return None

    query_words = set(query.split())

    best_file = None
    best_score = 0

    for file in MUSIC_LIBRARY_DIR.rglob("*"):

        if not file.is_file():
            continue

        if file.suffix.lower() not in AUDIO_EXTENSIONS:
            continue

        filename = normalize(file.stem)

        if filename == query:
            return file

        filename_words = set(filename.split())

        common = query_words & filename_words

        if not common:
            continue

        score = (
            len(common) /
            max(len(query_words), len(filename_words))
        )

        if query in filename:
            score += 0.5

        if score > best_score:
            best_score = score
            best_file = file

    if best_score >= 0.5:
        return best_file

    return None


async def send_song(message, title, artist=""):

    queries = [
        f"{artist} {title}".strip(),
        title
    ]

    file = None

    for query in queries:
        file = find_song(query)

        if file:
            break

    if not file:
        return False

    await message.answer_audio(
        FSInputFile(file),
        title=title[:64],
        performer=artist[:64] if artist else None
    )

    return True


def format_duration(milliseconds):
    if not milliseconds:
        return "?:??"

    seconds = milliseconds // 1000
    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes}:{seconds:02d}"


async def delete_message(message):
    try:
        await message.delete()
    except Exception:
        pass


async def run_ffmpeg(args):

    def execute():
        import subprocess

        subprocess.run(
            ["ffmpeg", "-y"] + args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
            timeout=180
        )

    await asyncio.to_thread(execute)


# ==========================================
# 4. START VA BUYRUQLAR
# ==========================================

@dp.message(Command("start"))
async def start(message: types.Message):

    await message.answer(
        get_text(message.from_user.id)["start"]
    )


@dp.message(Command("music"))
async def music_command(message: types.Message):

    await message.answer(
        "🎵 Qo'shiq nomini yozing."
    )


@dp.message(Command("video"))
async def video_command(message: types.Message):

    await message.answer(
        "🎬 Video havolasini yuboring yoki video fayl jo'nating."
    )


@dp.message(Command("help"))
async def help_command(message: types.Message):

    await message.answer(
        get_text(message.from_user.id)["help"]
    )


# ==========================================
# 5. TIL TANLASH
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

    lang = callback.data.split("_", 1)[1]

    if lang not in TEXTS:
        await callback.answer()
        return

    user_langs[callback.from_user.id] = lang

    await callback.answer("OK")

    await callback.message.edit_text(
        TEXTS[lang]["start"]
    )


# ==========================================
# 6. DUMALOQ VIDEO
# ==========================================

async def create_round(message, file_id, prefix):

    t = get_text(message.from_user.id)

    wait = await message.answer(t["wait"])

    with tempfile.TemporaryDirectory() as temp_dir:

        input_file = os.path.join(
            temp_dir,
            "input.mp4"
        )

        output_file = os.path.join(
            temp_dir,
            "round.mp4"
        )

        try:
            tg_file = await bot.get_file(file_id)

            await bot.download_file(
                tg_file.file_path,
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
                "-movflags", "+faststart",
                output_file
            ])

            if os.path.exists(output_file):
                await message.answer_video_note(
                    FSInputFile(output_file)
                )

        except Exception:
            logger.exception("Round video error")
            await message.answer(t["error"])

        finally:
            await delete_message(wait)


@dp.message(F.video)
async def video_message(message: types.Message):

    await create_round(
        message,
        message.video.file_id,
        f"round_{message.from_user.id}_{message.message_id}"
    )


# ==========================================
# 7. VIDEO YUKLASH
# ==========================================

def download_video(url, filename):

    if not url.startswith(("http://", "https://")):
        raise ValueError("Noto'g'ri video havolasi")

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": filename,
        "merge_output_format": "mp4",
        "max_filesize": MAX_VIDEO_BYTES,
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
        "socket_timeout": 30
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])


@dp.message(F.text.regexp(r"https?://"))
async def url_message(message: types.Message):

    t = get_text(message.from_user.id)

    wait = await message.answer(t["wait"])

    with tempfile.TemporaryDirectory() as temp_dir:

        filename = os.path.join(
            temp_dir,
            "video.mp4"
        )

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
                    caption=t["video_ready"],
                    reply_markup=keyboard
                )

            else:
                await message.answer(t["error"])

        except Exception:
            logger.exception("Video download error")
            await message.answer(t["error"])

        finally:
            await delete_message(wait)


# ==========================================
# 8. VIDEODAN MP3
# ==========================================

@dp.callback_query(F.data == "extract")
async def extract_audio(callback: types.CallbackQuery):

    await callback.answer()

    if not callback.message.video:
        return

    with tempfile.TemporaryDirectory() as temp_dir:

        input_file = os.path.join(
            temp_dir,
            "input.mp4"
        )

        output_file = os.path.join(
            temp_dir,
            "audio.mp3"
        )

        try:
            tg_file = await bot.get_file(
                callback.message.video.file_id
            )

            await bot.download_file(
                tg_file.file_path,
                destination=input_file
            )

            await run_ffmpeg([
                "-i", input_file,
                "-vn",
                "-codec:a", "libmp3lame",
                "-b:a", "192k",
                output_file
            ])

            await callback.message.answer_audio(
                FSInputFile(output_file)
            )

        except Exception:
            logger.exception("MP3 extraction error")

            await callback.message.answer(
                get_text(callback.from_user.id)["error"]
            )


# ==========================================
# 9. ROUND TUGMASI
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
# 10. AUDD MUSIQA ANIQLASH
# ==========================================

async def recognize_music(message, file_id, file_size):

    t = get_text(message.from_user.id)

    if not AUDD_TOKEN:
        await message.answer(t["no_audd"])
        return

    if file_size and file_size > MAX_AUDIO_BYTES:
        await message.answer(t["too_large"])
        return

    wait = await message.answer(t["recognizing"])

    with tempfile.TemporaryDirectory() as temp_dir:

        filename = os.path.join(
            temp_dir,
            "audio_sample"
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
                f"{t['no_library']}"
            )

            if link:
                text += f"\n{link}"

            await message.answer(text)

        except Exception:
            logger.exception("Recognition error")
            await message.answer(t["error"])

        finally:
            await delete_message(wait)


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
# 11. MUSIQA QIDIRISH
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
                    "limit": MAX_SEARCH_RESULTS
                },
                timeout=aiohttp.ClientTimeout(total=20)
            ) as response:

                if response.status != 200:
                    raise RuntimeError("iTunes API xatosi")

                data = await response.json()

        results = data.get("results", [])

        if not results:
            await message.answer(t["not_found"])
            return

        songs = []

        for song in results:

            title = song.get("trackName")
            artist = song.get("artistName")

            if not title or not artist:
                continue

            songs.append({
                "title": title,
                "artist": artist,
                "duration": song.get("trackTimeMillis", 0)
            })

        if not songs:
            await message.answer(t["not_found"])
            return

        text = f"🔍 {query}\n\n"

        for i, song in enumerate(songs, start=1):

            duration = format_duration(
                song["duration"]
            )

            text += (
                f"{i}. {song['artist']} – "
                f"{song['title']} {duration}\n"
            )

        buttons = []

        for i in range(len(songs)):

            buttons.append(
                InlineKeyboardButton(
                    text=str(i + 1),
                    callback_data=f"pick_{i}"
                )
            )

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                buttons[i:i + 5]
                for i in range(0, len(buttons), 5)
            ]
        )

        result_message = await message.answer(
            text,
            reply_markup=keyboard
        )

        key = (
            message.from_user.id,
            message.chat.id,
            result_message.message_id
        )

        # Eski natijalarni cheklash
        if len(search_results) >= MAX_STORED_SEARCHES:
            search_results.clear()

        search_results[key] = songs

    except Exception:
        logger.exception("Music search error")
        await message.answer(t["error"])

    finally:
        await delete_message(wait)


# ==========================================
# 12. RAQAM ORQALI QO'SHIQ TANLASH
# ==========================================

@dp.callback_query(F.data.startswith("pick_"))
async def select_song(callback: types.CallbackQuery):

    try:
        index = int(callback.data.split("_", 1)[1])

        key = (
            callback.from_user.id,
            callback.message.chat.id,
            callback.message.message_id
        )

        songs = search_results.get(key)

        if not songs or index < 0 or index >= len(songs):

            await callback.answer(
                get_text(callback.from_user.id)["expired"],
                show_alert=True
            )
            return

        song = songs[index]

        await callback.answer(
            get_text(callback.from_user.id)["selected"]
        )

        title = song["title"]
        artist = song["artist"]

        # To'liq MP3 kutubxonadan qidirish
        sent = await send_song(
            callback.message,
            title,
            artist
        )

        if sent:
            return

        await callback.message.answer(
            f"🎵 {title}\n"
            f"🎤 {artist}\n\n"
            f"{get_text(callback.from_user.id)['no_library']}\n\n"
            "📁 MP3 faylni music_library papkasiga joylashtiring."
        )

    except Exception:
        logger.exception("Song selection error")

        await callback.answer(
            get_text(callback.from_user.id)["error"],
            show_alert=True
        )


# ==========================================
# 13. WEB SERVER
# ==========================================

async def handle(request):

    return web.Response(
        text="Axmadov_music_bot is running!"
    )


# ==========================================
# 14. BOTNI ISHGA TUSHIRISH
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

    logger.info(
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
