import asyncio
import logging
import os
import re
import glob
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import BotCommand, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# ==========================================
# ASOSIY SOZLAMALAR
# ==========================================
BOT_TOKEN = os.environ.get("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ")
BOT_USERNAME = "@Axmadov_music_bot"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_lang = {}
user_mode = {}
active_tasks = {}

# ==========================================
# KO'P TILLI MATNLAR LUG'ATI
# ==========================================
TEXTS = {
    "uz": {
        "start": "👋 Assalomu alaykum! Botga xush kelibsiz.\n\n📥 **Video yuklash:** Instagram, TikTok yoki YouTube havolasini yuboring.\n🎵 **Musiqa yuklash:** Qo'shiq nomi yoki ijrochi ismini yozing.",
        "music": "🎵 **Musiqa platformasi**\n\nQidirayotgan qo'shiq nomi yoki ijrochi ismini yozib yuboring:",
        "video": "🎬 **Video xizmatlari**\n\nInstagram Reels, TikTok yoki YouTube havolasini yuboring:",
        "help": "ℹ️ **Yordam bo'limi**\n\n1️⃣ Video yuklash uchun havolani (link) shunchaki chatga tashlang.\n2️⃣ Musiqa topish uchun qo'shiq nomini yozing.\n3️⃣ Jarayonni bekor qilish uchun /stop buyrug'ini bosing.",
        "lang_select": "🌐 Tilni tanlang / Выберите язык / Choose language:",
        "lang_changed": "✅ Til O'zbek tiliga o'zgartirildi.",
        "stop_ok": "🛑 Joriy jarayon to'xtatildi.",
        "stop_none": "ℹ️ Hozirda faol jarayon mavjud emas.",
        "downloading_video": "⏳ Video yuklanmoqda, biroz kuting...",
        "searching_music": "🔎 Musiqa qidirilmoqda va yuklanmoqda...",
        "error": "❌ Xatolik yuz berdi. Havola noto'g'ri, profil yopiq yoki fayl hajmi 50MB dan katta.",
        "not_found": "❌ Hech narsa topilmadi. Boshqa nom bilan urinib ko'ring."
    },
    "ru": {
        "start": "👋 Здравствуйте! Добро пожаловать в бот.\n\n📥 **Скачать видео:** Отправьте ссылку из Instagram, TikTok или YouTube.\n🎵 **Скачать музыку:** Напишите название песни или имя исполнителя.",
        "music": "🎵 **Музыкальная платформа**\n\nНапишите название песни или имя исполнителя:",
        "video": "🎬 **Видео сервисы**\n\nОтправьте ссылку на Instagram Reels, TikTok или YouTube:",
        "help": "ℹ️ **Раздел помощи**\n\n1️⃣ Чтобы скачать видео, просто отправьте ссылку в чат.\n2️⃣ Чтобы найти музыку, напишите название трека.\n3️⃣ Для отмены процесса нажмите /stop.",
        "lang_select": "🌐 Выберите язык:",
        "lang_changed": "✅ Язык изменен на Русский.",
        "stop_ok": "🛑 Текущий процесс остановлен.",
        "stop_none": "ℹ️ Активных процессов нет.",
        "downloading_video": "⏳ Видео загружается, пожалуйста подождите...",
        "searching_music": "🔎 Поиск и загрузка музыки...",
        "error": "❌ Произошла ошибка. Неверная ссылка, закрытый аккаунт или файл больше 50МБ.",
        "not_found": "❌ Ничего не найдено. Попробуйте другое название."
    },
    "en": {
        "start": "👋 Hello! Welcome to the bot.\n\n📥 **Download Video:** Send an Instagram, TikTok, or YouTube link.\n🎵 **Download Music:** Type a song title or artist name.",
        "music": "🎵 **Music Platform**\n\nType the song title or artist name you are looking for:",
        "video": "🎬 **Video Services**\n\nSend an Instagram Reels, TikTok, or YouTube link:",
        "help": "ℹ️ **Help Section**\n\n1️⃣ Just paste a link to download a video.\n2️⃣ Type a song name to search and download MP3.\n3️⃣ Use /stop to cancel an active process.",
        "lang_select": "🌐 Choose language:",
        "lang_changed": "✅ Language changed to English.",
        "stop_ok": "🛑 Current process stopped.",
        "stop_none": "ℹ️ No active process found.",
        "downloading_video": "⏳ Downloading video, please wait...",
        "searching_music": "🔎 Searching and downloading music...",
        "error": "❌ An error occurred. Invalid link, private account, or file exceeds 50MB.",
        "not_found": "❌ Nothing found. Try another search query."
    }
}

def get_text(user_id: int, key: str) -> str:
    lang = user_lang.get(user_id, "uz")
    return TEXTS[lang][key]

# ==========================================
# BOT MENYUSINI SOZLASH
# ==========================================
async def set_bot_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="music", description="Musiqa platformasi"),
        BotCommand(command="video", description="Video xizmatlari"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="lang", description="Tilni o'zgartirish"),
        BotCommand(command="stop", description="Jarayonni to'xtatish"),
    ]
    await bot.set_my_commands(commands)

# ==========================================
# BUYRUQLAR HANDLERLARI
# ==========================================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "video"
    await message.answer(get_text(user_id, "start"), parse_mode="Markdown")

@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "music"
    await message.answer(get_text(user_id, "music"), parse_mode="Markdown")

@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    user_id = message.from_user.id
    user_mode[user_id] = "video"
    await message.answer(get_text(user_id, "video"), parse_mode="Markdown")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    user_id = message.from_user.id
    await message.answer(get_text(user_id, "help"), parse_mode="Markdown")

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    user_id = message.from_user.id
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="lang_en"),
        ]
    ])
    await message.answer(get_text(user_id, "lang_select"), reply_markup=keyboard)

@dp.callback_query(F.data.startswith("lang_"))
async def process_lang(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_id = callback.from_user.id
    user_lang[user_id] = lang
    await callback.message.edit_text(get_text(user_id, "lang_changed"))

@dp.message(Command("stop"))
async def cmd_stop(message: types.Message):
    user_id = message.from_user.id
    if active_tasks.get(user_id):
        active_tasks[user_id] = False
        await message.answer(get_text(user_id, "stop_ok"))
    else:
        await message.answer(get_text(user_id, "stop_none"))

# ==========================================
# YUKLASH FUNKSIYALARI (YT-DLP)
# ==========================================
def download_video_sync(url: str, base_filename: str):
    ydl_opts = {
        'outtmpl': f"{base_filename}.%(ext)s",
        'format': 'best[ext=mp4][filesize<50M]/best[filesize<50M]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return ydl.prepare_filename(info)

def download_music_sync(query: str, base_filename: str):
    ydl_opts = {
        'outtmpl': f"{base_filename}.%(ext)s",
        'format': 'bestaudio/best',
        'default_search': 'ytsearch1',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info:
            info = info['entries'][0]
        title = info.get('title', 'Music')
        artist = info.get('uploader', BOT_USERNAME)
        return f"{base_filename}.mp3", title, artist

def cleanup_files(pattern: str):
    for f in glob.glob(f"{pattern}*"):
        try:
            os.remove(f)
        except Exception:
            pass

# ==========================================
# XABARLARNI QAYTA ISHLASH
# ==========================================
@dp.message(F.text)
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    text = message.text.strip()

    # Havola yuborilganda -> Video yuklash
    url_match = re.search(r'https?://\S+', text)
    if url_match:
        url = url_match.group(0)
        active_tasks[user_id] = True
        wait_msg = await message.answer(get_text(user_id, "downloading_video"))
        base_name = f"vid_{user_id}_{message.message_id}"

        try:
            filepath = await asyncio.to_thread(download_video_sync, url, base_name)
            if not active_tasks.get(user_id):
                cleanup_files(base_name)
                return

            if os.path.exists(filepath):
                video_file = FSInputFile(filepath)
                await message.answer_video(video=video_file, caption=f"✅ {BOT_USERNAME}")
            else:
                await message.answer(get_text(user_id, "error"))
        except Exception as e:
            logging.error(f"Video yuklash xatosi: {e}")
            if active_tasks.get(user_id):
                await message.answer(get_text(user_id, "error"))
        finally:
            active_tasks[user_id] = False
            cleanup_files(base_name)
            try:
                await wait_msg.delete()
            except Exception:
                pass
        return

    # Matn yuborilganda -> Musiqa qidirish
    active_tasks[user_id] = True
