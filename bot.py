import os
import asyncio
import logging
import subprocess
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_langs = {}

TEXTS = {
    "uz": {
        "start": (
            "👋 Assalomu alaykum! **Axmadov_music** botiga xush kelibsiz!\n\n"
            "📥 Menga **Instagram, TikTok yoki YouTube** havolasini (link) yuboring — "
            "men sizga videosini yuklab beraman.\n"
            "🎥 Oddiy video yuborsangiz, uni **dumaloq video** qilib beraman!"
        ),
        "music": "🎵 Musiqa yuklash uchun menga YouTube yoki Instagram havolasini yuboring — video tagidagi tugma orqali MP3 ajratib olasiz.",
        "video": "🎬 Video yuklash uchun havolani tashlang yoki dumaloq video yasash uchun video fayl yuboring.",
        "help": (
            "ℹ️ **Botdan foydalanish bo'yicha yordam:**\n\n"
            "1️⃣ **Video yuklash:** Instagram, TikTok yoki YouTube linkini yuboring.\n"
            "2️⃣ **Music va Round:** Yuklangan video tagidagi tugmalardan foydalaning yoki to'g'ridan-to'g'ri video tashlang.\n"
            "3️⃣ Tilni o'zgartirish uchun /lang buyrug'ini bosing."
        ),
        "choose_lang": "🌐 Kerakli tilni tanlang:",
        "lang_set": "✅ Til muvaffaqiyatli o'zgartirildi: **O'zbek tili**",
        "wait_vid": "⏳ Yuklanmoqda, iltimos kuting...",
        "wait_round": "⏳ Dumaloq video tayyorlanmoqda, biroz kuting...",
        "wait_audio": "⏳ Videodan MP3 musiqa ajratilmoqda...",
        "caption_vid": "📥 @Pleyistbot orqali yuklandi!",
        "caption_aud": "🎵 @Pleyistbot orqali ajratib olindi!",
        "err_vid": "❌ Videoni yuklab bo'lmadi (havola yopiq yoki hajmi 50MB dan katta).",
        "err_link": "❌ Havolani yuklashda xatolik yuz berdi. Boshqa havola yuborib ko'ring.",
        "err_proc": "❌ Xatolik yuz berdi."
    },
    "ru": {
        "start": (
            "👋 Здравствуйте! Добро пожаловать в бот **Axmadov_music**!\n\n"
            "📥 Отправьте мне ссылку из **Instagram, TikTok или YouTube** — "
            "и я скачаю для вас видео.\n"
            "🎥 Если отправите обычное видео, я сделаю из него **круглое видео**!"
        ),
        "music": "🎵 Чтобы скачать музыку, отправьте ссылку из YouTube или Instagram — вы сможете извлечь MP3 кнопкой под видео.",
        "video": "🎬 Отправьте ссылку для скачивания видео или отправьте видеофайл, чтобы сделать кружок.",
        "help": (
            "ℹ️ **Помощь по использованию бота:**\n\n"
            "1️⃣ **Скачать видео:** Отправьте ссылку из Instagram, TikTok или YouTube.\n"
            "2️⃣ **Music и Round:** Используйте кнопки под скачанным видео или просто отправьте видео боту.\n"
            "3️⃣ Для смены языка нажмите /lang."
        ),
        "choose_lang": "🌐 Выберите нужный язык:",
        "lang_set": "✅ Язык успешно изменён: **Русский**",
        "wait_vid": "⏳ Загрузка, пожалуйста, подождите...",
        "wait_round": "⏳ Создаётся круглое видео, подождите немного...",
        "wait_audio": "⏳ Извлечение MP3 музыки из видео...",
        "caption_vid": "📥 Скачано через @Pleyistbot!",
        "caption_aud": "🎵 Извлечено через @Pleyistbot!",
        "err_vid": "❌ Не удалось скачать видео (закрытый аккаунт или размер больше 50МБ).",
        "err_link": "❌ Ошибка при загрузке по ссылке. Попробуйте другую ссылку.",
        "err_proc": "❌ Произошла ошибка."
    },
    "en": {
        "start": (
            "👋 Hello! Welcome to **Axmadov_music** bot!\n\n"
            "📥 Send me a link from **Instagram, TikTok, or YouTube** — "
            "and I will download the video for you.\n"
            "🎥 If you send a regular video, I will turn it into a **round video note**!"
        ),
        "music": "🎵 To download music, send me a YouTube or Instagram link — you can extract MP3 using the button below the video.",
        "video": "🎬 Send a link to download a video or send a video file to create a round video note.",
        "help": (
            "ℹ️ **How to use the bot:**\n\n"
            "1️⃣ **Download video:** Send an Instagram, TikTok, or YouTube link.\n"
            "2️⃣ **Music & Round:** Use the buttons below the downloaded video or send any video directly.\n"
            "3️⃣ Press /lang to change the language."
        ),
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language successfully changed to: **English**",
        "wait_vid": "⏳ Downloading, please wait...",
        "wait_round": "⏳ Creating round video, please wait...",
        "wait_audio": "⏳ Extracting MP3 audio from video...",
        "caption_vid": "📥 Downloaded via @Pleyistbot!",
        "caption_aud": "🎵 Extracted via @Pleyistbot!",
        "err_vid": "❌ Could not download video (private link or size over 50MB).",
        "err_link": "❌ Error downloading link. Please try another one.",
        "err_proc": "❌ An error occurred."
    }
}

def get_t(user_id: int) -> dict:
    lang = user_langs.get(user_id, "uz")
    return TEXTS[lang]

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    t = get_t(message.from_user.id)
    await message.answer(t["start"], parse_mode="Markdown")

@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    t = get_t(message.from_user.id)
    await message.answer(t["music"])

@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    t = get_t(message.from_user.id)
    await message.answer(t["video"])

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    t = get_t(message.from_user.id)
    await message.answer(t["help"], parse_mode="Markdown")

@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    t = get_t(message.from_user.id)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="set_lang_uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru"),
            InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en")
        ]
    ])
    await message.answer(t["choose_lang"], reply_markup=kb)

@dp.callback_query(F.data.startswith("set_lang_"))
async def callback_set_lang(callback: types.CallbackQuery):
    lang_code = callback.data.split("_")[-1]
    user_langs[callback.from_user.id] = lang_code
    t = get_t(callback.from_user.id)
    await callback.answer()
    await callback.message.edit_text(t["lang_set"], parse_mode="Markdown")

@dp.message(F.video)
async def make_round_video_direct(message: types.Message):
    t = get_t(message.from_user.id)
    wait_msg = await message.answer(t["wait_round"])
    input_path = f"in_{message.message_id}.mp4"
    output_path = f"out_{message.message_id}.mp4"
    
    try:
        file = await bot.get_file(message.video.file_id)
        await bot.download_file(file.file_path, input_path)
        
        cmd = [
            "ffmpeg", "-y", "-i", input_path,
            "-t", "60",
            "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384",
            "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "128k", output_path
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(output_path):
            await message.answer_video_note(FSInputFile(output_path))
        else:
            await message.answer(t["err_proc"])
    except Exception:
        await message.answer(t["err_proc"])
    finally:
        await wait_msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

@dp.message(F.text.contains("http"))
async def download_media(message: types.Message):
    t = get_t(message.from_user.id)
    url = message.text.strip()
    wait_msg = await message.answer(t["wait_vid"])
    filename = f"vid_{message.message_id}.mp4"
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': filename,
        'max_filesize': 48 * 1024 * 1024,
        'quiet': True
    }
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎵 Music", callback_data="extract_audio"),
            InlineKeyboardButton(text="🎥 Round", callback_data="make_round")
        ]
    ])
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if os.path.exists(filename):
            video_file = FSInputFile(filename)
            await message.answer_video(
                video_file,
                caption=t["caption_vid"],
                reply_markup=keyboard
            )
        else:
            await message.answer(t["err_vid"])
    except Exception:
        await message.answer(t["err_link"])
    finally:
        await wait_msg.delete()
        if os.path.exists(filename): os.remove(filename)

@dp.callback_query(F.data == "extract_audio")
async def callback_extract_audio(callback: types.CallbackQuery):
    t = get_t(callback.from_user.id)
    await callback.answer()
    video = callback.message.video
    if not video:
        return
    
    wait_msg = await callback.message.answer(t["wait_audio"])
    in_vid = f"aud_in_{callback.id}.mp4"
    out_mp3 = f"aud_out_{callback.id}.mp3"
    
    try:
        file = await bot.get_file(video.file_id)
        await bot.download_file(file.file_path, in_vid)
        
        cmd = ["ffmpeg", "-y", "-i", in_vid, "-vn", "-ab", "192k", "-ar", "44100", out_mp3]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(out_mp3):
            await callback.message.answer_audio(
                FSInputFile(out_mp3),
                caption=t["caption_aud"]
