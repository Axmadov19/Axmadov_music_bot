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

# /start buyrug'i
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    text = (
        "👋 Assalomu alaykum! **Axmadov_music** botiga xush kelibsiz!\n\n"
        "📥 Menga **Instagram, TikTok yoki YouTube** havolasini (link) yuboring — "
        "men sizga videosini yuklab beraman.\n"
        "🎥 Oddiy video yuborsangiz, uni **dumaloq video** qilib beraman!"
    )
    await message.answer(text, parse_mode="Markdown")

# /music buyrug'i
@dp.message(Command("music"))
async def cmd_music(message: types.Message):
    await message.answer("🎵 Musiqa yuklash uchun menga YouTube yoki Instagram havolasini yuboring — video tagidagi tugma orqali MP3 ajratib olasiz.")

# /video buyrug'i
@dp.message(Command("video"))
async def cmd_video(message: types.Message):
    await message.answer("🎬 Video yuklash uchun havolani tashlang yoki dumaloq video yasash uchun video fayl yuboring.")

# /help buyrug'i
@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    text = (
        "ℹ️ **Botdan foydalanish bo'yicha yordam:**\n\n"
        "1️⃣ **Video yuklash:** Instagram, TikTok yoki YouTube linkini yuboring.\n"
        "2️⃣ **MP3 va Dumaloq video:** Yuklangan video tagidagi tugmalardan foydalaning yoki to'g'ridan-to'g'ri video tashlang.\n"
        "3️⃣ Muammo bo'lsa, qayta /start bosing."
    )
    await message.answer(text, parse_mode="Markdown")

# /lang buyrug'i
@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    await message.answer("🌐 Hozircha faqat **O'zbek tili** faol. Tez orada Rus va Ingliz tillari qo'shiladi.", parse_mode="Markdown")

# Oddiy video yuborilganda uni Dumaloq video qilish
@dp.message(F.video)
async def make_round_video_direct(message: types.Message):
    wait_msg = await message.answer("⏳ Dumaloq video tayyorlanmoqda, biroz kuting...")
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
            await message.answer("❌ Videoni qayta ishlashda xatolik yuz berdi.")
    except Exception:
        await message.answer("❌ Xatolik: Video hajmi juda katta bo'lishi mumkin.")
    finally:
        await wait_msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# Havola (Link) orqali video yuklash va tagiga 2 ta tugma qo'yish
@dp.message(F.text.contains("http"))
async def download_media(message: types.Message):
    url = message.text.strip()
    wait_msg = await message.answer("⏳ Yuklanmoqda, iltimos kuting...")
    filename = f"vid_{message.message_id}.mp4"
    
    ydl_opts = {
        'format': 'best[ext=mp4]/best',
        'outtmpl': filename,
        'max_filesize': 48 * 1024 * 1024,
        'quiet': True
    }
    
    # Video tagida chiqadigan 2 ta tugma (Music va Round)
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
                caption="📥 @Pleyistbot orqali yuklandi!",
                reply_markup=keyboard
            )
        else:
            await message.answer("❌ Videoni yuklab bo'lmadi (havola yopiq yoki hajmi 50MB dan katta).")
    except Exception:
        await message.answer("❌ Havolani yuklashda xatolik yuz berdi. Boshqa havola yuborib ko'ring.")
    finally:
        await wait_msg.delete()
        if os.path.exists(filename): os.remove(filename)

# Video tagidagi "🎵 Music" tugmasi bosilganda
@dp.callback_query(F.data == "extract_audio")
async def callback_extract_audio(callback: types.CallbackQuery):
    await callback.answer("⏳ Musiqa ajratilmoqda...")
    video = callback.message.video
    if not video:
        return
    
    wait_msg = await callback.message.answer("⏳ Videodan MP3 musiqa ajratilmoqda...")
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
                caption="🎵 @Pleyistbot orqali ajratib olindi!"
            )
        else:
            await callback.message.answer("❌ Musiqani ajratib bo'lmadi.")
    except Exception:
        await callback.message.answer("❌ Xatolik yuz berdi.")
    finally:
        await wait_msg.delete()
        if os.path.exists(in_vid): os.remove(in_vid)
        if os.path.exists(out_mp3): os.remove(out_mp3)

# Video tagidagi "🎥 Round" tugmasi bosilganda
@dp.callback_query(F.data == "make_round")
async def callback_make_round(callback: types.CallbackQuery):
    await callback.answer("⏳ Dumaloq video tayyorlanmoqda...")
    video = callback.message.video
    if not video:
        return
    
    wait_msg = await callback.message.answer("⏳ Dumaloq video tayyorlanmoqda, biroz kuting...")
    in_vid = f"rnd_in_{callback.id}.mp4"
    out_vid = f"rnd_out_{callback.id}.mp4"
    
    try:
        file = await bot.get_file(video.file_id)
        await bot.download_file(file.file_path, in_vid)
        
        cmd = [
            "ffmpeg", "-y", "-i", in_vid,
            "-t", "60",
            "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384",
            "-c:v", "libx264", "-crf", "26", "-preset", "veryfast",
            "-c:a", "aac", "-b:a", "128k", out_vid
        ]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        if os.path.exists(out_vid):
            await callback.message.answer_video_note(FSInputFile(out_vid))
        else:
            await callback.message.answer("❌ Dumaloq video tayyorlab bo'lmadi.")
    except Exception:
        await callback.message.answer("❌ Xatolik yuz berdi.")
    finally:
        await wait_msg.delete()
        if os.path.exists(in_vid): os.remove(in_vid)
        if os.path.exists(out_vid): os.remove(out_vid)

# Bepul server 24/7 uyg'oq turishi uchun kichik veb-server
async def handle(request):
    return web.Response(text="Bot 24/7 ishlamoqda!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()

async def main():
    await start_web_server()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main()) 
