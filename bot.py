import os
import asyncio
import logging
import subprocess
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile
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
    await message.answer("🎵 Musiqa yuklash uchun menga YouTube yoki Instagram havolasini yuboring.")

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
        "2️⃣ **Dumaloq video:** Oddiy videoni botga tashlang, u avtomatik dumaloq shaklda qaytadi.\n"
        "3️⃣ Muammo bo'lsa, qayta /start bosing."
    )
    await message.answer(text, parse_mode="Markdown")

# /lang buyrug'i
@dp.message(Command("lang"))
async def cmd_lang(message: types.Message):
    await message.answer("🌐 Hozircha faqat **O'zbek tili** faol. Tez orada Rus va Ingliz tillari qo'shiladi.", parse_mode="Markdown")

# Oddiy videoni Dumaloq video (Video Note) qilish
@dp.message(F.video)
async def make_round_video(message: types.Message):
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
            video_note = FSInputFile(output_path)
            await message.answer_video_note(video_note)
        else:
            await message.answer("❌ Videoni qayta ishlashda xatolik yuz berdi.")
    except Exception:
        await message.answer("❌ Xatolik: Video hajmi juda katta bo'lishi mumkin.")
    finally:
        await wait_msg.delete()
        if os.path.exists(input_path): os.remove(input_path)
        if os.path.exists(output_path): os.remove(output_path)

# Havola (Link) orqali video yuklash
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
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
            
        if os.path.exists(filename):
            video_file = FSInputFile(filename)
            await message.answer_video(video_file, caption="📥 @Pleyistbot orqali yuklandi!")
        else:
            await message.answer("❌ Videoni yuklab bo'lmadi (havola yopiq yoki hajmi 50MB dan katta).")
    except Exception:
        await message.answer("❌ Havolani yuklashda xatolik yuz berdi. Boshqa havola yuborib ko'ring.")
    finally:
        await wait_msg.delete()
        if os.path.exists(filename): os.remove(filename)

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
