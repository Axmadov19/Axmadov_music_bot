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
        "start": "👋 Assalomu alaykum! **Axmadov_music** botiga xush kelibsiz!\n\n📥 Menga **Instagram, TikTok yoki YouTube** havolasini (link) yuboring — men sizga videosini yuklab beraman.\n🎥 Oddiy video yuborsangiz, uni **dumaloq video** qilib beraman!",
        "music": "🎵 Musiqa yuklash uchun menga YouTube yoki Instagram havolasini yuboring — video tagidagi tugma orqali MP3 ajratib olasiz.",
        "video": "🎬 Video yuklash uchun havolani tashlang yoki dumaloq video yasash uchun video fayl yuboring.",
        "help": "ℹ️ **Yordam:**\n\n1️⃣ **Video yuklash:** Instagram, TikTok yoki YouTube linkini yuboring.\n2️⃣ **Music va Round:** Yuklangan video tagidagi tugmalardan foydalaning yoki video tashlang.\n3️⃣ Tilni o'zgartirish: /lang",
        "choose_lang": "🌐 Kerakli tilni tanlang:",
        "lang_set": "✅ Til o'zgartirildi: **O'zbek tili**",
        "wait_vid": "⏳ Yuklanmoqda, iltimos kuting...",
        "wait_round": "⏳ Dumaloq video tayyorlanmoqda...",
        "wait_audio": "⏳ MP3 musiqa ajratilmoqda...",
        "caption_vid": "📥 @Pleyistbot orqali yuklandi!",
        "caption_aud": "🎵 @Pleyistbot orqali ajratib olindi!",
        "err_vid": "❌ Videoni yuklab bo'lmadi (havola yopiq yoki hajmi 50MB dan katta).",
        "err_link": "❌ Havolani yuklashda xatolik yuz berdi.",
        "err_proc": "❌ Xatolik yuz berdi."
    },
    "ru": {
        "start": "👋 Здравствуйте! Добро пожаловать в бот **Axmadov_music**!\n\n📥 Отправьте ссылку из **Instagram, TikTok или YouTube** — я скачаю видео.\n🎥 Отправьте обычное видео, и я сделаю **круглое видео**!",
        "music": "🎵 Отправьте ссылку из YouTube или Instagram — вы сможете извлечь MP3 кнопкой под видео.",
        "video": "🎬 Отправьте ссылку для скачивания или видеофайл для создания кружка.",
        "help": "ℹ️ **Помощь:**\n\n1️⃣ **Скачать видео:** Отправьте ссылку из Instagram, TikTok или YouTube.\n2️⃣ **Music и Round:** Используйте кнопки под видео или отправьте видео боту.\n3️⃣ Сменить язык: /lang",
        "choose_lang": "🌐 Выберите нужный язык:",
        "lang_set": "✅ Язык изменён: **Русский**",
        "wait_vid": "⏳ Загрузка, подождите...",
        "wait_round": "⏳ Создаётся круглое видео...",
        "wait_audio": "⏳ Извлечение MP3 музыки...",
        "caption_vid": "📥 Скачано через @Pleyistbot!",
        "caption_aud": "🎵 Извлечено через @Pleyistbot!",
        "err_vid": "❌ Не удалось скачать видео (закрытый аккаунт или размер > 50МБ).",
        "err_link": "❌ Ошибка при загрузке по ссылке.",
        "err_proc": "❌ Произошла ошибка."
    },
    "en": {
        "start": "👋 Hello! Welcome to **Axmadov_music** bot!\n\n📥 Send a link from **Instagram, TikTok, or YouTube** — I will download the video.\n🎥 Send a regular video to turn it into a **round video note**!",
        "music": "🎵 Send a YouTube or Instagram link — extract MP3 using the button below the video.",
        "video": "🎬 Send a link to download a video or send a video file for a round video.",
        "help": "ℹ️ **Help:**\n\n1️⃣ **Download:** Send an Instagram, TikTok, or YouTube link.\n2️⃣ **Music & Round:** Use buttons below the video or send a video directly.\n3️⃣ Change language: /lang",
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language changed: **English**",
        "wait_vid": "⏳ Downloading, please wait...",
        "wait_round": "⏳ Creating round video...",
        "wait_audio": "⏳ Extracting MP3 audio...",
        "caption_vid": "📥 Downloaded via @Pleyistbot!",
        "caption_aud": "🎵 Extracted via @Pleyistbot!",
        "err_vid": "❌ Could not download video (private or over 50MB).",
        "err_link": "❌ Error downloading link.",
        "err_proc": "❌ An error occurred."
    }
}

def get_t(user_id: int) -> dict:
    return TEXTS.get(user_langs.get(user_id, "uz"), TEXTS["uz"])

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(get_t(message.from_user.id)["start"], parse_mode="Markdown")

@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    await message.answer(get_t(message.from_user.id)["music"])

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

@dp.message(F.video)
async def make_round_video_direct(message: types.Message):
    t = get_t(message.from_user.id)
    wait_msg = await message.answer(t["wait_round"])
    in_p = f"in_{message.message_id}.mp4"
    out_p = f"out_{message.message_id}.mp4"
    try:
        file = await bot.get_file(message.video.file_id)
        await bot.download_file(file.file_path, in_p)
        subprocess.run(["ffmpeg", "-y", "-i", in_p, "-t", "60", "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k", out_p], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out_p):
            await message.answer_video_note(FSInputFile(out_p))
        else:
            await message.answer(t["err_proc"])
    except Exception:
        await message.answer(t["err_proc"])
    finally:
        await wait_msg.delete()
        if os.path.exists(in_p): os.remove(in_p)
        if os.path.exists(out_p): os.remove(out_p)

@dp.message(F.text.contains("http"))
async def download_media(message: types.Message):
    t = get_t(message.from_user.id)
    wait_msg = await message.answer(t["wait_vid"])
    fname = f"vid_{message.message_id}.mp4"
    ydl_opts = {'format': 'best[ext=mp4]/best', 'outtmpl': fname, 'max_filesize': 48 * 1024 * 1024, 'quiet': True}
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🎵 Music", callback_data="extract_audio"),
        InlineKeyboardButton(text="🎥 Round", callback_data="make_round")
    ]])
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([message.text.strip()])
        if os.path.exists(fname):
            await message.answer_video(FSInputFile(fname), caption=t["caption_vid"], reply_markup=kb)
        else:
            await message.answer(t["err_vid"])
    except Exception:
        await message.answer(t["err_link"])
    finally:
        await wait_msg.delete()
        if os.path.exists(fname): os.remove(fname)

@dp.callback_query(F.data == "extract_audio")
async def callback_extract_audio(callback: types.CallbackQuery):
    t = get_t(callback.from_user.id)
    await callback.answer()
    if not callback.message.video: return
    wait_msg = await callback.message.answer(t["wait_audio"])
    in_v = f"ain_{callback.id}.mp4"
    out_m = f"aout_{callback.id}.mp3"
    try:
        file = await bot.get_file(callback.message.video.file_id)
        await bot.download_file(file.file_path, in_v)
        subprocess.run(["ffmpeg", "-y", "-i", in_v, "-vn", "-ab", "192k", "-ar", "44100", out_m], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out_m):
            await callback.message.answer_audio(FSInputFile(out_m), caption=t["caption_aud"])
        else:
            await callback.message.answer(t["err_proc"])
    except Exception:
        await callback.message.answer(t["err_proc"])
    finally:
        await wait_msg.delete()
        if os.path.exists(in_v): os.remove(in_v)
        if os.path.exists(out_m): os.remove(out_m)

@dp.callback_query(F.data == "make_round")
async def callback_make_round(callback: types.CallbackQuery):
    t = get_t(callback.from_user.id)
    await callback.answer()
    if not callback.message.video: return
    wait_msg = await callback.message.answer(t["wait_round"])
    in_v = f"rin_{callback.id}.mp4"
    out_v = f"rout_{callback.id}.mp4"
    try:
        file = await bot.get_file(callback.message.video.file_id)
        await bot.download_file(file.file_path, in_v)
        subprocess.run(["ffmpeg", "-y", "-i", in_v, "-t", "60", "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k", out_v], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if os.path.exists(out_v):
            await callback.message.answer_video_note(FSInputFile(out_v))
        else:
            await callback.message.answer(t["err_proc"])
    except Exception:
        await callback.message.answer(t["err_proc"])
    finally:
        await wait_msg.delete()
        if os.path.exists(in_v): os.remove(in_v)
        if os.path.exists(out_v): os.remove(out_v)

async def handle(request):
    return web.Response(text="Bot 24/7 ishlamoqda!")

async def run_bot():
    await asyncio.sleep(2)
