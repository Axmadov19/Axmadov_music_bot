import os
import asyncio
import logging
import subprocess
import base64
import aiohttp
import imageio_ffmpeg
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

BOT_TOKEN = os.getenv("BOT_TOKEN")
FFMPEG_BIN = imageio_ffmpeg.get_ffmpeg_exe()

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
user_langs = {}

TEXTS = {
    "uz": {
        "start": "👋 Assalomu alaykum! **Axmadov_music** botiga xush kelibsiz!\n\n🎵 **Qo'shiq nomini yozing** yoki **ovozli xabar (golos)** yuboring — men musiqani topib beraman!\n📥 **Instagram, TikTok, YouTube** linkini yuborsangiz videosini yuklayman.\n🎥 Oddiy video yuborsangiz **dumaloq video** qilib beraman!",
        "music": "🎵 Qo'shiq nomi yoki ijrochi ismini yozing (masalan: *Konsta - Odamlar nima deydi*) yoki musiqadan parcha (golos) yuboring!",
        "video": "🎬 Video yuklash uchun havola tashlang yoki dumaloq video uchun video fayl yuboring.",
        "help": "ℹ️ **Yordam:**\n\n1️⃣ **Musiqa qidirish:** Qo'shiq nomini yozing yoki ovozli xabar (golos) tashlang.\n2️⃣ **Video yuklash:** Instagram, TikTok yoki YouTube linkini yuboring.\n3️⃣ **Music va Round:** Video tagidagi tugmalardan foydalaning.\n4️⃣ Tilni o'zgartirish: /lang",
        "choose_lang": "🌐 Kerakli tilni tanlang:",
        "lang_set": "✅ Til o'zgartirildi: **O'zbek tili**",
        "wait_vid": "⏳ Video yuklanmoqda, iltimos kuting...",
        "wait_music": "🔍 Musiqa qidirilmoqda, biroz kuting...",
        "wait_shazam": "🎧 Ovoz orqali musiqa aniqlanmoqda...",
        "wait_round": "⏳ Dumaloq video tayyorlanmoqda...",
        "wait_audio": "⏳ MP3 musiqa ajratilmoqda...",
        "caption_vid": "📥 @Pleyistbot orqali yuklandi!",
        "caption_aud": "🎵 @Pleyistbot orqali topildi!",
        "not_found": "❌ Ovoz orqali musiqa topilmadi. Aniqroq parcha yuboring yoki qo'shiq nomini yozing.",
        "err_vid": "❌ Videoni yuklab bo'lmadi (havola yopiq yoki hajmi 50MB dan katta).",
        "err_link": "❌ Havolani yuklashda xatolik yuz berdi.",
        "err_proc": "❌ Qayta ishlashda xatolik yuz berdi."
    },
    "ru": {
        "start": "👋 Здравствуйте! Добро пожаловать в **Axmadov_music**!\n\n🎵 **Напишите название песни** или отправьте **голосовое сообщение** — я найду трек!\n📥 Отправьте ссылку из **Instagram, TikTok, YouTube** — скачаю видео.\n🎥 Отправьте обычное видео — сделаю **круглое видео**!",
        "music": "🎵 Напишите название песни или исполнителя, либо отправьте голосовое сообщение с отрывком музыки!",
        "video": "🎬 Отправьте ссылку для скачивания или видеофайл для создания кружка.",
        "help": "ℹ️ **Помощь:**\n\n1️⃣ **Поиск музыки:** Напишите название песни или отправьте голосовое сообщение.\n2️⃣ **Скачать видео:** Отправьте ссылку из Instagram, TikTok или YouTube.\n3️⃣ **Music и Round:** Используйте кнопки под видео.\n4️⃣ Сменить язык: /lang",
        "choose_lang": "🌐 Выберите нужный язык:",
        "lang_set": "✅ Язык изменён: **Русский**",
        "wait_vid": "⏳ Видео загружается, подождите...",
        "wait_music": "🔍 Поиск музыки, подождите...",
        "wait_shazam": "🎧 Распознавание музыки по звуку...",
        "wait_round": "⏳ Создаётся круглое видео...",
        "wait_audio": "⏳ Извлечение MP3 музыки...",
        "caption_vid": "📥 Скачано через @Pleyistbot!",
        "caption_aud": "🎵 Найдено через @Pleyistbot!",
        "not_found": "❌ Музыка не распознана. Попробуйте другой отрывок или напишите название.",
        "err_vid": "❌ Не удалось скачать видео (закрытый аккаунт или размер > 50МБ).",
        "err_link": "❌ Ошибка при загрузке по ссылке.",
        "err_proc": "❌ Произошла ошибка."
    },
    "en": {
        "start": "👋 Hello! Welcome to **Axmadov_music**!\n\n🎵 **Type a song name** or send a **voice message** — I will find the music for you!\n📥 Send a link from **Instagram, TikTok, YouTube** to download video.\n🎥 Send a regular video to turn it into a **round video note**!",
        "music": "🎵 Type the song name or artist, or send a voice message with a music snippet!",
        "video": "🎬 Send a link to download a video or send a video file for a round video.",
        "help": "ℹ️ **Help:**\n\n1️⃣ **Search Music:** Type a song name or send a voice message.\n2️⃣ **Download Video:** Send an Instagram, TikTok, or YouTube link.\n3️⃣ **Music & Round:** Use buttons below the video.\n4️⃣ Change language: /lang",
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language changed: **English**",
        "wait_vid": "⏳ Downloading video, please wait...",
        "wait_music": "🔍 Searching for music, please wait...",
        "wait_shazam": "🎧 Recognizing music from audio...",
        "wait_round": "⏳ Creating round video...",
        "wait_audio": "⏳ Extracting MP3 audio...",
        "caption_vid": "📥 Downloaded via @Pleyistbot!",
        "caption_aud": "🎵 Found via @Pleyistbot!",
        "not_found": "❌ Could not recognize the song. Try a clearer snippet or type the song name.",
        "err_vid": "❌ Could not download video (private or over 50MB).",
        "err_link": "❌ Error downloading link.",
        "err_proc": "❌ An error occurred."
    }
}

def get_t(user_id: int) -> dict:
    return TEXTS.get(user_langs.get(user_id, "uz"), TEXTS["uz"])

def convert_to_round(in_path: str, out_path: str):
    cmd = [
        FFMPEG_BIN, "-y", "-i", in_path, "-t", "60",
        "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384",
        "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
        "-c:a", "aac", "-b:a", "128k", out_path
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def extract_mp3(in_path: str, out_path: str):
    cmd = [FFMPEG_BIN, "-y", "-i", in_path, "-vn", "-ab", "192k", "-ar", "44100", out_path]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def search_and_download_mp3(query: str, out_base: str) -> str:
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{out_base}.%(ext)s",
        'default_search': 'ytsearch1',
        'noplaylist': True,
        'quiet': True,
        'ffmpeg_location': FFMPEG_BIN,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(query, download=True)
        if 'entries' in info and info['entries']:
            return info['entries'][0].get('title', query)
        return info.get('title', query)

async def recognize_audio_shazam(ogg_path: str) -> str:
    raw_path = f"{ogg_path}.raw"
    try:
        cmd = [FFMPEG_BIN, "-y", "-i", ogg_path, "-t", "5", "-f", "s16le", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "1", raw_path]
        await asyncio.to_thread(subprocess.run, cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not os.path.exists(raw_path):
            return ""
        with open(raw_path, "rb") as f:
            b64_data = base64.b64encode(f.read()).decode("utf-8")
        
        url = "https://rapidapi.com"
        # Agar RapidAPI kalit bo'lmasa, ochiq AudD demo API orqali tekshiramiz
        async with aiohttp.ClientSession() as session:
            data = aiohttp.FormData()
            data.add_field("api_token", "test")
            data.add_field("file", open(ogg_path, "rb"), filename="voice.ogg")
            async with session.post("https://audd.io", data=data, timeout=15) as resp:
                res = await resp.json()
                if res.get("status") == "success" and res.get("result"):
                    r = res["result"]
                    return f"{r.get('artist', '')} - {r.get('title', '')}".strip(" -")
    except Exception:
        pass
    finally:
        if os.path.exists(raw_path):
            os.remove(raw_path)
    return ""

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(get_t(message.from_user.id)["start"], parse_mode="Markdown")

@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    await message.answer(get_t(message.from_user.id)["music"], parse_mode="Markdown")

@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    await message.answer(get_t(message.from_user.id)["video"])

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(get_t(message.from_user.id)["help"], parse_mode="Markdown")

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="set_lang_uz"),
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
        InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")
    ]])
    await message.answer(get_t(message.from_user.id)["choose_lang"], reply_markup=kb)

@dp.callback_query(F.data.startswith("set_lang_"))
async def callback_set_lang(callback: types.CallbackQuery):
    user_langs[callback.from_user.id] = callback.data.split("_")[-1]
    await callback.answer()
    await callback.message.edit_text(get_t(callback.from_user.id)["lang_set"], parse_mode="Markdown")

# Ovozli xabar (golos) yoki audio tashlanganda musiqani aniqlash va yuklash
@dp.message(F.voice | F.audio)
async def recognize_and_send_music(message: types.Message):
    t = get_t(message.from_user.id)
    wait_msg = await message.answer(t["wait_shazam"])
    media = message.voice or message.audio
    in_audio = f"shz_{message.message_id}.ogg"
    out_base = f"found_{message.message_id}"
    out_mp3 = f"{out_base}.mp3"
    
    try:
        file = await bot.get_file(media.file_id)
        await bot.download_file(file.file_path, in_audio)
        
