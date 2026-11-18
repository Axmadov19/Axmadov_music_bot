
import os
import re
import logging
import asyncio
import tempfile
import difflib
from pathlib import Path
from collections import defaultdict

import aiohttp
import yt_dlp

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    FSInputFile,
    ReplyKeyboardRemove
)
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramBadRequest

from aiohttp import web


# =====================================================
# SOZLAMALAR
# =====================================================

BOT_TOKEN = os.getenv("BOT_TOKEN", "BOT_TOKENINGIZNI_BU_YERGA")
AUDD_TOKEN = os.getenv("AUDD_TOKEN", "")

BASE_DIR = Path(__file__).resolve().parent
MUSIC_DIR = BASE_DIR / "music_library"

MUSIC_EXTENSIONS = {
    ".mp3", ".m4a", ".ogg", ".flac", ".wav"
}

MAX_VIDEO_SIZE = 45 * 1024 * 1024
MAX_AUDIO_SIZE = 20 * 1024 * 1024

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

logger = logging.getLogger(__name__)


# =====================================================
# BOT
# =====================================================

bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)

dp = Dispatcher(storage=MemoryStorage())


# =====================================================
# HOLATLAR
# =====================================================

class MusicState(StatesGroup):
    waiting_for_song = State()


class LanguageState(StatesGroup):
    waiting_for_language = State()


# =====================================================
# TILLAR
# =====================================================

LANGUAGES = {
    "uz": {
        "welcome": (
            "👋 Assalomu alaykum!\n\n"
            "🎵 Qo‘shiq nomini yozing.\n"
            "🎧 Ovozli parcha yuboring.\n"
            "🎬 Video havolasini yuboring.\n"
            "📹 Video yuborsangiz, dumaloq video qilib beraman.\n\n"
            "/music - Musiqa\n"
            "/video - Video\n"
            "/help - Yordam\n"
            "/lang - Til"
        ),
        "ask_music": "🎵 Qo‘shiq nomini yozing.",
        "searching": "🔎 Musiqa qidirilmoqda...",
        "not_found": (
            "😕 Bu qo‘shiq kutubxonadan topilmadi.\n"
            "Boshqa nom bilan qidirib ko‘ring."
        ),
        "choose": "🎵 Topilgan qo‘shiqlardan birini tanlang:",
        "sending": "⏳ Qo‘shiq yuborilmoqda...",
        "error": "❌ Xatolik yuz berdi. Birozdan keyin qayta urinib ko‘ring.",
        "video_help": "🎬 Video havolasini yuboring.",
        "video_downloading": "⏳ Video yuklanmoqda...",
        "video_error": "❌ Videoni yuklab bo‘lmadi.",
        "audio_error": "❌ Ovozli faylni aniqlashda xatolik yuz berdi.",
        "no_audd": "⚠️ Ovozli qidiruv hozircha sozlanmagan.",
        "no_match": "😕 Bu qo‘shiq kutubxonangizdan topilmadi.",
        "recognized": "🎵 Aniqlangan qo‘shiq: ",
        "language": "🌐 Tilni tanlang:",
        "language_saved": "✅ Til o‘zgartirildi.",
        "help": "ℹ️ Bot orqali musiqa qidirishingiz, ovozli parcha yuborishingiz va video olishingiz mumkin."
    },
    "ru": {
        "welcome": (
            "👋 Здравствуйте!\n\n"
            "🎵 Напишите название песни.\n"
            "🎧 Отправьте голосовой фрагмент.\n"
            "🎬 Отправьте ссылку на видео.\n"
            "📹 Отправьте видео, и я сделаю круглое видео.\n\n"
            "/music - Музыка\n"
            "/video - Видео\n"
            "/help - Помощь\n"
            "/lang - Язык"
        ),
        "ask_music": "🎵 Напишите название песни.",
        "searching": "🔎 Ищу музыку...",
        "not_found": "😕 Песня не найдена в библиотеке.",
        "choose": "🎵 Выберите песню:",
        "sending": "⏳ Отправляю песню...",
        "error": "❌ Произошла ошибка. Попробуйте ещё раз.",
        "video_help": "🎬 Отправьте ссылку на видео.",
        "video_downloading": "⏳ Загружаю видео...",
        "video_error": "❌ Не удалось загрузить видео.",
        "audio_error": "❌ Ошибка распознавания аудио.",
        "no_audd": "⚠️ Поиск по голосу пока не настроен.",
        "no_match": "😕 Песня не найдена в библиотеке.",
        "recognized": "🎵 Найденная песня: ",
        "language": "🌐 Выберите язык:",
        "language_saved": "✅ Язык изменён.",
        "help": "ℹ️ Бот умеет искать музыку, распознавать аудио и обрабатывать видео."
    },
    "en": {
        "welcome": (
            "👋 Hello!\n\n"
            "🎵 Send a song name.\n"
            "🎧 Send an audio sample.\n"
            "🎬 Send a video link.\n"
            "📹 Send a video to convert it into a round video.\n\n"
            "/music - Music\n"
            "/video - Video\n"
            "/help - Help\n"
            "/lang - Language"
        ),
        "ask_music": "🎵 Send a song name.",
        "searching": "🔎 Searching for music...",
        "not_found": "😕 Song not found in your music library.",
        "choose": "🎵 Choose a song:",
        "sending": "⏳ Sending song...",
        "error": "❌ An error occurred. Please try again.",
        "video_help": "🎬 Send a video link.",
        "video_downloading": "⏳ Downloading video...",
        "video_error": "❌ Could not download the video.",
        "audio_error": "❌ Audio recognition failed.",
        "no_audd": "⚠️ Audio recognition is not configured.",
        "no_match": "😕 Song not found in your library.",
        "recognized": "🎵 Recognized song: ",
        "language": "🌐 Choose language:",
        "language_saved": "✅ Language changed.",
        "help": "ℹ️ Search music, recognize audio and process videos with this bot."
    }
}

user_languages = defaultdict(lambda: "uz")

def tr(user_id, key):
    lang = user_languages[user_id]
    return LANGUAGES.get(lang, LANGUAGES["uz"]).get(
        key, LANGUAGES["uz"].get(key, "")
    )


# =====================================================
# MUSIQA KUTUBXONASI
# =====================================================

def normalize(text):
    text = text.lower()
    text = text.replace("o‘", "o")
    text = text.replace("g‘", "g")
    text = text.replace("ʻ", "")
    text = text.replace("'", "")
    text = text.replace("’", "")
    text = text.replace("_", " ")
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def get_music_files():
    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    files = []

    for file in MUSIC_DIR.rglob("*"):
        if file.is_file() and file.suffix.lower() in MUSIC_EXTENSIONS:
            files.append(file)

    return files


def search_songs(query, limit=10):
    files = get_music_files()

    if not files:
        logger.warning("music_library papkasida musiqa yo‘q")
        return []

    query_normalized = normalize(query)

    if not query_normalized:
        return []

    query_words = set(query_normalized.split())
    results = []

    for file in files:
        filename = normalize(file.stem)

        if not filename:
            continue

        filename_words = set(filename.split())

        common = query_words.intersection(filename_words)

        if query_normalized == filename:
            score = 1.0

        elif query_normalized in filename:
            score = 0.95

        elif filename in query_normalized:
            score = 0.90

        else:
            word_score = (
                len(common) / max(len(query_words), 1)
            )

            similarity = difflib.SequenceMatcher(
                None,
                query_normalized,
                filename
            ).ratio()

            score = max(word_score, similarity * 0.85)

        if score >= 0.35:
            results.append((score, file))

    results.sort(key=lambda item: item[0], reverse=True)

    return [file for score, file in results[:limit]]


# =====================================================
# MUSIQA NATIJALARINI SAQLASH
# =====================================================

music_results = {}


def create_music_keyboard(files, user_id):
    buttons = []

    for index, file in enumerate(files):
        name = file.stem

        if len(name) > 35:
            name = name[:32] + "..."

        buttons.append([
            InlineKeyboardButton(
                text=f"{index + 1}. {name}",
                callback_data=f"pick_{index}"
            )
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


# =====================================================
# START
# =====================================================

@dp.message(Command("start"))
async def start_handler(message: Message, state: FSMContext):
    await state.clear()

    await message.answer(
        tr(message.from_user.id, "welcome"),
        reply_markup=ReplyKeyboardRemove()
    )


# =====================================================
# MUSIC
# =====================================================

@dp.message(Command("music"))
async def music_handler(message: Message, state: FSMContext):
    await state.set_state(MusicState.waiting_for_song)

    await message.answer(
        tr(message.from_user.id, "ask_music")
    )


@dp.message(MusicState.waiting_for_song, F.text)
async def music_search_handler(message: Message, state: FSMContext):
    query = message.text.strip()

    if not query:
        await message.answer(tr(message.from_user.id, "ask_music"))
        return

    if query.startswith("/"):
        return

    status = await message.answer(
        tr(message.from_user.id, "searching")
    )

    try:
        results = await asyncio.to_thread(
            search_songs,
            query,
            10
        )

        if not results:
            await status.edit_text(
                tr(message.from_user.id, "not_found")
            )
            await state.clear()
            return

        music_results[message.from_user.id] = results

        keyboard = create_music_keyboard(
            results,
            message.from_user.id
        )

        await status.edit_text(
            tr(message.from_user.id, "choose"),
            reply_markup=keyboard
        )

        await state.clear()

    except Exception:
        logger.exception("Musiqa qidirish xatosi")

        await status.edit_text(
            tr(message.from_user.id, "error")
        )

        await state.clear()


# =====================================================
# MUSIQA TANLASH
# =====================================================

@dp.callback_query(F.data.startswith("pick_"))
async def choose_music_handler(callback: CallbackQuery):
    try:
        index = int(callback.data.split("_")[1])

        files = music_results.get(callback.from_user.id, [])

        if index < 0 or index >= len(files):
            await callback.answer(
                "Natija eskirgan. Qayta qidiring.",
                show_alert=True
            )
            return

        file_path = files[index]

        if not file_path.exists():
            await callback.answer(
                "Fayl topilmadi.",
                show_alert=True
            )
            return

        await callback.answer("Yuborilmoqda...")

        await callback.message.answer(
            tr(callback.from_user.id, "sending")
        )

        await callback.message.answer_audio(
            audio=FSInputFile(file_path),
            title=file_path.stem
        )

    except Exception:
        logger.exception("Musiqa yuborish xatosi")

        await callback.message.answer(
            tr(callback.from_user.id, "error")
        )


# =====================================================
# VIDEO BUYRUG‘I
# =====================================================

@dp.message(Command("video"))
async def video_command(message: Message):
    await message.answer(
        tr(message.from_user.id, "video_help")
    )


# =====================================================
# VIDEO HAVOLASINI YUKLASH
# =====================================================

def download_video(url, folder):
    output_template = str(Path(folder) / "video.%(ext)s")

    options = {
        "format": "best[ext=mp4]/best",
        "outtmpl": output_template,
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "socket_timeout": 30,
        "max_filesize": MAX_VIDEO_SIZE,
    }

    with yt_dlp.YoutubeDL(options) as ydl:
        ydl.download([url])

    files = list(Path(folder).glob("video.*"))

    if not files:
        raise FileNotFoundError("Yuklangan video topilmadi")

    return files[0]


def create_round_video(input_file, output_file):
    command = [
        "ffmpeg",
        "-y",
        "-i", str(input_file),
        "-vf",
        "scale=640:640:force_original_aspect_ratio=increase,"
        "crop=640:640,fps=30",
        "-c:v", "libx264",
        "-preset", "veryfast",
        "-crf", "28",
        "-c:a", "aac",
        "-b:a", "96k",
        "-t", "60",
        "-movflags", "+faststart",
        str(output_file)
    ]

    import subprocess

    subprocess.run(
        command,
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE
    )

    return output_file


@dp.message(F.text.regexp(r"https?://"))
async def video_link_handler(message: Message):
    url = message.text.strip()

    status = await message.answer(
        tr(message.from_user.id, "video_downloading")
    )

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            video_file = await asyncio.to_thread(
                download_video,
                url,
                temp_dir
            )

            if not video_file.exists():
                raise FileNotFoundError("Video fayl mavjud emas")

            if video_file.stat().st_size > MAX_VIDEO_SIZE:
                raise ValueError("Video juda katta")

            round_file = Path(temp_dir) / "round.mp4"

            await asyncio.to_thread(
                create_round_video,
                video_file,
                round_file
            )

            await message.answer_video_note(
                video_note=FSInputFile(round_file)
            )

        await status.delete()

    except Exception:
        logger.exception("Video havolasini yuklash xatosi")

        try:
            await status.edit_text(
                tr(message.from_user.id, "video_error")
            )
        except TelegramBadRequest:
            pass


# =====================================================
# TELEGRAM VIDEOSINI DUMALOQ QILISH
# =====================================================

@dp.message(F.video)
async def uploaded_video_handler(message: Message):
    status = await message.answer("⏳ Video tayyorlanmoqda...")

    try:
        video = message.video

        if video.file_size and video.file_size > MAX_VIDEO_SIZE:
            await status.edit_text("❌ Video hajmi juda katta.")
            return

        with tempfile.TemporaryDirectory() as temp_dir:
            input_file = Path(temp_dir) / "input.mp4"
            output_file = Path(temp_dir) / "round.mp4"

            telegram_file = await bot.get_file(video.file_id)

            await bot.download_file(
                telegram_file.file_path,
                destination=input_file
            )

            await asyncio.to_thread(
                create_round_video,
                input_file,
                output_file
            )

            await message.answer_video_note(
                video_note=FSInputFile(output_file)
            )

        await status.delete()

    except Exception:
        logger.exception("Yuborilgan videoni qayta ishlash xatosi")

        await status.edit_text("❌ Videoni qayta ishlashda xatolik.")


# =====================================================
# OVOZLI XABAR ORQALI QO‘SHIQNI ANIQLASH
# =====================================================

async def recognize_audio(file_path):
    if not AUDD_TOKEN:
        return None

    timeout = aiohttp.ClientTimeout(total=40)

    async with aiohttp.ClientSession(timeout=timeout) as session:
        with open(file_path, "rb") as audio_file:
            data = aiohttp.FormData()

            data.add_field("api_token", AUDD_TOKEN)
            data.add_field("return", "spotify")
            data.add_field(
                "file",
                audio_file,
                filename="audio.ogg",
                content_type="application/octet-stream"
            )

            async with session.post(
                "https://api.audd.io/",
                data=data
            ) as response:
                if response.status != 200:
                    raise RuntimeError(
                        f"AudD HTTP xatosi: {response.status}"
                    )

                result = await response.json()

    if result.get("status") != "success":
        return None

    return result.get("result")


async def process_audio(message: Message, file_id: str):
    if not AUDD_TOKEN:
        await message.answer(
            tr(message.from_user.id, "no_audd")
        )
        return

    status = await message.answer("🎧 Ovoz aniqlanmoqda...")

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            audio_path = Path(temp_dir) / "audio.ogg"

            telegram_file = await bot.get_file(file_id)

            if telegram_file.file_size and telegram_file.file_size > MAX_AUDIO_SIZE:
                await status.edit_text("❌ Audio fayl juda katta.")
                return

            await bot.download_file(
                telegram_file.file_path,
                destination=audio_path
            )

            result = await recognize_audio(audio_path)

            if not result:
                await status.edit_text(
                    tr(message.from_user.id, "not_found")
                )
                return

            title = result.get("title", "Noma'lum")
            artist = result.get("artist", "Noma'lum")

            await status.edit_text(
                f"🎵 {title}\n"
                f"👤 {artist}\n\n"
                f"🔎 Kutubxonadan qidirilmoqda..."
            )

            query = f"{artist} {title}"

            matches = await asyncio.to_thread(
                search_songs,
                query,
                10
            )

            if matches:
                music_results[message.from_user.id] = matches

                keyboard = create_music_keyboard(
                    matches,
                    message.from_user.id
                )

                await message.answer(
                    "🎵 Aniqlangan qo‘shiq kutubxonadan topildi:",
                    reply_markup=keyboard
                )
            else:
                await message.answer(
                    tr(message.from_user.id, "no_match")
                )

    except Exception:
        logger.exception("Audio aniqlash xatosi")

        await status.edit_text(
            tr(message.from_user.id, "audio_error")
        )


@dp.message(F.voice)
async def voice_handler(message: Message):
    await process_audio(
        message,
        message.voice.file_id
    )


@dp.message(F.audio)
async def audio_handler(message: Message):
    await process_audio(
        message,
        message.audio.file_id
    )


# =====================================================
# TIL O‘ZGARTIRISH
# =====================================================

@dp.message(Command("lang"))
async def language_handler(message: Message):
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🇺🇿 O‘zbekcha",
                    callback_data="lang_uz"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇷🇺 Русский",
                    callback_data="lang_ru"
                )
            ],
            [
                InlineKeyboardButton(
                    text="🇬🇧 English",
                    callback_data="lang_en"
                )
            ]
        ]
    )

    await message.answer(
        tr(message.from_user.id, "language"),
        reply_markup=keyboard
    )


@dp.callback_query(F.data.startswith("lang_"))
async def language_callback(callback: CallbackQuery):
    lang = callback.data.replace("lang_", "")

    if lang in LANGUAGES:
        user_languages[callback.from_user.id] = lang

    await callback.answer()

    await callback.message.edit_text(
        tr(callback.from_user.id, "language_saved")
    )


# =====================================================
# HELP
# =====================================================

@dp.message(Command("help"))
async def help_handler(message: Message):
    await message.answer(
        tr(message.from_user.id, "help")
    )


# =====================================================
# BEGONA MATNLAR
# =====================================================

@dp.message(F.text)
async def unknown_text_handler(message: Message):
    await message.answer(
        "❓ Tushunmadim.\n"
        "/music - musiqa qidirish\n"
        "/video - video\n"
        "/help - yordam"
    )


# =====================================================
# XATOLARNI LOGGA YOZISH
# =====================================================

@dp.error()
async def global_error_handler(event, exception):
    logger.exception(
        "Kutilmagan bot xatosi",
        exc_info=exception
    )

    return True


# =====================================================
# WEB SERVER (RENDER UCHUN)
# =====================================================

async def health(request):
    return web.Response(text="Bot is running!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.getenv("PORT", "8080"))

    site = web.TCPSite(
        runner,
        "0.0.0.0",
        port
    )

    await site.start()

    logger.info("Web server ishga tushdi: %s", port)


# =====================================================
# MAIN
# =====================================================

async def main():
    if BOT_TOKEN == "BOT_TOKENINGIZNI_BU_YERGA":
        raise RuntimeError(
            "BOT_TOKEN ni kiriting yoki BOT_TOKEN environment variable yarating."
        )

    MUSIC_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Bot ishga tushmoqda...")

    await start_web_server()

    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot to‘xtatildi.")
