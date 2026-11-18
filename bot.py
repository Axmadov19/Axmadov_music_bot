import os, asyncio, logging, subprocess, aiohttp, imageio_ffmpeg, yt_dlp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
langs = {}

T = {
    "uz": {
        "start": "👋 **Axmadov_music** botiga xush kelibsiz!\n\n🎵 Qo'shiq nomini yozing yoki **golos** yuboring.\n📥 **Instagram, TikTok, YouTube** linkini tashlang.\n🎥 Oddiy video yuborsangiz **dumaloq video** qilaman!",
        "music": "🎵 Qo'shiq nomini yozing yoki musiqadan parcha (golos) yuboring!",
        "video": "🎬 Video havolasini yuboring yoki dumaloq video uchun video fayl tashlang.",
        "help": "ℹ️ **Yordam:**\n1️⃣ Qo'shiq nomini yozing yoki golos yuboring.\n2️⃣ Video yuklash uchun link tashlang.\n3️⃣ Tilni o'zgartirish: /lang",
        "lang": "🌐 Tilni tanlang:", "set": "✅ Til: **O'zbek**",
        "wait": "⏳ Kuting...", "not_found": "❌ Musiqa topilmadi.", "err": "❌ Xatolik yuz berdi.",
        "cap_v": "📥 @Pleyistbot orqali yuklandi!", "cap_a": "🎵 @Pleyistbot orqali topildi!"
    },
    "ru": {
        "start": "👋 Добро пожаловать в **Axmadov_music**!\n\n🎵 Напишите название песни или отправьте **голосовое**.\n📥 Отправьте ссылку **Instagram, TikTok, YouTube**.\n🎥 Отправьте видео — сделаю **круглое видео**!",
        "music": "🎵 Напишите название песни или отправьте голосовое сообщение!",
        "video": "🎬 Отправьте ссылку на видео или видеофайл для кружка.",
        "help": "ℹ️ **Помощь:**\n1️⃣ Напишите название песни или отправьте голосовое.\n2️⃣ Отправьте ссылку для скачивания.\n3️⃣ Сменить язык: /lang",
        "lang": "🌐 Выберите язык:", "set": "✅ Язык: **Русский**",
        "wait": "⏳ Подождите...", "not_found": "❌ Музыка не найдена.", "err": "❌ Произошла ошибка.",
        "cap_v": "📥 Скачано через @Pleyistbot!", "cap_a": "🎵 Найдено через @Pleyistbot!"
    },
    "en": {
        "start": "👋 Welcome to **Axmadov_music**!\n\n🎵 Type a song name or send a **voice note**.\n📥 Send an **Instagram, TikTok, YouTube** link.\n🎥 Send a video to make a **round video**!",
        "music": "🎵 Type a song name or send a voice message!",
        "video": "🎬 Send a video link or a video file for a round note.",
        "help": "ℹ️ **Help:**\n1️⃣ Type a song name or send a voice note.\n2️⃣ Send a link to download video.\n3️⃣ Change language: /lang",
        "lang": "🌐 Choose language:", "set": "✅ Language: **English**",
        "wait": "⏳ Please wait...", "not_found": "❌ Song not found.", "err": "❌ An error occurred.",
        "cap_v": "📥 Downloaded via @Pleyistbot!", "cap_a": "🎵 Found via @Pleyistbot!"
    }
}

def gt(uid): return T.get(langs.get(uid, "uz"), T["uz"])

def to_round(inp, outp):
    subprocess.run([FFMPEG, "-y", "-i", inp, "-t", "60", "-vf", "crop='min(iw,ih)':'min(iw,ih)',scale=384:384", "-c:v", "libx264", "-crf", "26", "-preset", "veryfast", "-c:a", "aac", "-b:a", "128k", outp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def to_mp3(inp, outp):
    subprocess.run([FFMPEG, "-y", "-i", inp, "-vn", "-ab", "192k", "-ar", "44100", outp], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def dl_mp3(q, base):
    opts = {'format': 'bestaudio/best', 'outtmpl': f"{base}.%(ext)s", 'default_search': 'ytsearch1', 'noplaylist': True, 'quiet': True, 'ffmpeg_location': FFMPEG, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]}
    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(q, download=True)
        return info['entries'][0].get('title', q) if 'entries' in info and info['entries'] else info.get('title', q)

@dp.message(Command("start"))
async def c_start(m: types.Message): await m.answer(gt(m.from_user.id)["start"], parse_mode="Markdown")

@dp.message(Command("music"))
async def c_music(m: types.Message): await m.answer(gt(m.from_user.id)["music"])

@dp.message(Command("video"))
async def c_video(m: types.Message): await m.answer(gt(m.from_user.id)["video"])

@dp.message(Command("help"))
async def c_help(m: types.Message): await m.answer(gt(m.from_user.id)["help"], parse_mode="Markdown")

@dp.message(Command("lang"))
async def c_lang(m: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🇺🇿 O'zbek", callback_data="l_uz"), InlineKeyboardButton(text="🇷🇺 Русский", callback_data="l_ru"), InlineKeyboardButton(text="🇬🇧 English", callback_data="l_en")]])
    await m.answer(gt(m.from_user.id)["lang"], reply_markup=kb)

@dp.callback_query(F.data.startswith("l_"))
async def cb_lang(c: types.CallbackQuery):
    langs[c.from_user.id] = c.data.split("_")[1]
    await c.answer()
    await c.message.edit_text(gt(c.from_user.id)["set"], parse_mode="Markdown")

@dp.message(F.voice | F.audio)
async def h_voice(m: types.Message):
    t = gt(m.from_user.id)
    w = await m.answer(t["wait"])
    inp, base, outp = f"v_{m.message_id}.ogg", f"f_{m.message_id}", f"f_{m.message_id}.mp3"
    try:
        f = await bot.get_file((m.voice or m.audio).file_id)
        await bot.download_file(f.file_path, inp)
        async with aiohttp.ClientSession() as s:
            with open(inp, "rb") as fp:
                d = aiohttp.FormData()
                d.add_field("api_token", "test")
                d.add_field("file", fp, filename="v.ogg")
                async with s.post("https://audd.io", data=d, timeout=15) as r:
                    res = await r.json()
        if res.get("status") == "success" and res.get("result"):
            title = f"{res['result'].get('artist', '')} - {res['result'].get('title', '')}".strip(" -")
            await asyncio.to_thread(dl_mp3, title, base)
            if os.path.exists(outp): await m.answer_audio(FSInputFile(outp), title=title, caption=f"🎶 {title}\n{t['cap_a']}")
            else: await m.answer(t["err"])
        else: await m.answer(t["not_found"])
    except Exception: await m.answer(t["not_found"])
    finally:
        await w.delete()
        for x in (inp, outp):
            if os.path.exists(x): os.remove(x)

@dp.message(F.video)
async def h_vid(m: types.Message):
    t = gt(m.from_user.id)
    w = await m.answer(t["wait"])
    inp, outp = f"i_{m.message_id}.mp4", f"o_{m.message_id}.mp4"
    try:
        f = await bot.get_file(m.video.file_id)
        await bot.download_file(f.file_path, inp)
        await asyncio.to_thread(to_round, inp, outp)
        if os.path.exists(outp): await m.answer_video_note(FSInputFile(outp))
        else: await m.answer(t["err"])
    except Exception: await m.answer(t["err"])
    finally:
        await w.delete()
        for x in (inp, outp):
            if os.path.exists(x): os.remove(x)

@dp.message(F.text.contains("http"))
async def h_link(m: types.Message):
    t = gt(m.from_user.id)
    w = await m.answer(t["wait"])
    fn = f"d_{m.message_id}.mp4"
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🎵 Music", callback_data="c_aud"), InlineKeyboardButton(text="🎥 Round", callback_data="c_rnd")]])
    try:
        def dl():
            with yt_dlp.YoutubeDL({'format': 'best[ext=mp4]/best', 'outtmpl': fn, 'max_filesize': 48*1024*1024, 'quiet': True}) as y: y.download([m.text.strip()])
        await asyncio.to_thread(dl)
        if os.path.exists(fn): await m.answer_video(FSInputFile(fn), caption=t["cap_v"], reply_markup=kb)
        else: await m.answer(t["err"])
    except Exception: await m.answer(t["err"])
    finally:
        await w.delete()
        if os.path.exists(fn): os.remove(fn)

@dp.message(F.text & ~F.text.startswith("/"))
async def h_text(m: types.Message):
    t = gt(m.from_user.id)
    w = await m.answer(t["wait"])
    base, outp = f"s_{m.message_id}", f"s_{m.message_id}.mp3"
    try:
        title = await asyncio.to_thread(dl_mp3, m.text.strip(), base)
        if os.path.exists(outp): await m.answer_audio(FSInputFile(outp), title=title, caption=f"🎶 {title}\n{t['cap_a']}")
        else: await m.answer(t["err"])
    except Exception: await m.answer(t["err"])
    finally:
        await w.delete()
        if os.path.exists(outp): os.remove(outp)

@dp.callback_query(F.data.in_({"c_aud", "c_rnd"}))
async def cb_media(c: types.CallbackQuery):
    t = gt(c.from_user.id)
    await c.answer()
    if not c.message.video: return
    w = await c.message.answer(t["wait"])
    inp = f"ci_{c.id}.mp4"
    outp = f"co_{c.id}.mp3" if c.data == "c_aud" else f"co_{c.id}.mp4"
    try:
        f = await bot.get_file(c.message.video.file_id)
        await bot.download_file(f.file_path, inp)
        await asyncio.to_thread(to_mp3 if c.data == "c_aud" else to_round, inp, outp)
        if os.path.exists(outp):
            if c.data == "c_aud": await c.message.answer_audio(FSInputFile(outp), caption=t["cap_a"])
            else: await c.message.answer_video_note(FSInputFile(outp))
        else: await c.message.answer(t["err"])
    except Exception: await c.message.answer(t["err"])
    finally:
        await w.delete()
        for x in (inp, outp):
            if os.path.exists(x): os.remove(x)

async def handle(r): return web.Response(text="Live 24/7")
async def loop():
    await asyncio.sleep(3)
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            await dp.start_polling(bot, handle_signals=False)
        except Exception: await asyncio.sleep(5)

async def start_bg(app): asyncio.create_task(loop())

if __name__ == "__main__":
    app = web.Application()
    app.router.add_get("/", handle)
    app.on_startup.append(start_bg)
    web.run_app(app, host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
