import os
import asyncio
import logging
import subprocess
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
        "start": "👋 Assalomu alaykum! **Axmadov_music** botiga xush kelibsiz!\n\n📥 Menga **Instagram, TikTok yoki YouTube** havolasini (link) yuboring — videosini yuklab beraman.\n🎥 Oddiy video yuborsangiz, uni **dumaloq video** qilib beraman!",
        "music": "🎵 Musiqa yuklash uchun YouTube yoki Instagram havolasini yuboring — video tagidagi **Music** tugmasi orqali MP3 olasiz.",
        "video": "🎬 Video yuklash uchun havola tashlang yoki dumaloq video uchun video fayl yuboring.",
        "help": "ℹ️ **Yordam:**\n\n1️⃣ **Video yuklash:** Instagram, TikTok yoki YouTube linkini yuboring.\n2️⃣ **Music va Round:** Yuklangan video tagidagi tugmalarni bosing yoki video tashlang.\n3️⃣ Tilni o'zgartirish: /lang",
        "choose_lang": "🌐 Kerakli tilni tanlang:",
        "lang_set": "✅ Til o'zgartirildi: **O'zbek tili**",
        "wait_vid": "⏳ Yuklanmoqda, iltimos kuting...",
        "wait_round": "⏳ Dumaloq video tayyorlanmoqda...",
        "wait_audio": "⏳ MP3 musiqa ajratilmoqda...",
        "caption_vid": "📥 @Pleyistbot orqali yuklandi!",
        "caption_aud": "🎵 @Pleyistbot orqali ajratib olindi!",
        "err_vid": "❌ Videoni yuklab bo'lmadi (havola yopiq yoki hajmi 50MB dan katta).",
        "err_link": "❌ Havolani yuklashda xatolik yuz berdi.",
        "err_proc": "❌ Qayta ishlashda xatolik yuz berdi."
    },
    "ru": {
        "start": "👋 Здравствуйте! Добро пожаловать в **Axmadov_music**!\n\n📥 Отправьте ссылку из **Instagram, TikTok или YouTube** — я скачаю видео.\n🎥 Отправьте обычное видео, и я сделаю **круглое видео**!",
        "music": "🎵 Отправьте ссылку из YouTube или Instagram — нажмите кнопку **Music** под видео для получения MP3.",
        "video": "🎬 Отправьте ссылку для скачивания или видеофайл для создания кружка.",
        "help": "ℹ️ **Помощь:**\n\n1️⃣ **Скачать видео:** Отправьте ссылку из Instagram, TikTok или YouTube.\n2️⃣ **Music и Round:** Нажмите кнопки под видео или отправьте видео боту.\n3️⃣ Сменить язык: /lang",
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
        "start": "👋 Hello! Welcome to **Axmadov_music**!\n\n📥 Send a link from **Instagram, TikTok, or YouTube** — I will download the video.\n🎥 Send a regular video to turn it into a **round video note**!",
        "music": "🎵 Send a YouTube or Instagram link — press **Music** below the video to extract MP3.",
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

@dp.message(F.video)
async def make_round_direct(message: types.Message):
    t = get_t(message.from_user.id)
    wait_msg = await message.answer(t["wait_round"])
    in_p, out_p = f"in_{message.message_id}.mp4", f"out_{message.message_id}.mp4"
    try:
        file = await bot.get_file(message.video.file_id)
        await bot.download_file(file.file_path, in_p)
        await asyncio.to_thread(convert_to_round, in_p, out_p)
        if os.path.exists(out_p):
            await message.answer_video_note(FSInputFile(out_p))
        else:
            await message.answer(t["err_proc"])
    except Exception:
        await message.answer(t["err_proc"])
    finally:
        await wait_msg.delete()
        for f in (in_p, out_p):
            if os.path.exists(f): os.remove(f)

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
        def dl():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([message.text.strip()])
        await asyncio.to_thread(dl)
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
    in_v, out_m = f"ain_{callback.id}.mp4", f"aout_{callback.id}.mp3"
    try:
        file = await bot.get_file(callback.message.video.file_id)
        await bot.download_file(file.file_path, in_v)
        await asyncio.to_thread(extract_mp3, in_v, out_m)
        if os.path.exists(out_m):
            await callback.message.answer_audio(FSInputFile(out_m), caption=t["caption_aud"])
        else:
            await callback.message.answer(t["err_proc"])
    except Exception:
        await callback.message.answer(t["err_proc"])
    finally:
        await wait_msg.delete()
        for f in (in_v, out_m):
            if os.path.exists(f): os.remove(f)

@dp.callback_query(F.data == "make_round")
async def callback_make_round(callback: types.CallbackQuery):
    t = get_t(callback.from_user.id)
    await callback.answer()
    if not callback.message.video: return
    wait_msg = await callback.message.answer(t["wait_round"])
    in_v, out_v = f"rin_{callback.id}.mp4", f"rout_{callback.id}.mp4"
    try:
        file = await bot.get_file(callback.message.video.file_id)
        await bot.download_file(file.file_path, in_v)
        await asyncio.to_thread(convert_to_round, in_v, out_v)
        if os.path.exists(out_v):
            await callback.message.answer_video_note(FSInputFile(out_v))
        else:
            await callback.message.answer(t["err_proc"])
    except Exception:
        await callback.message.answer(t["err_proc"])
    finally:
        await wait_msg.delete()
        for f in (in_v, out_v):
