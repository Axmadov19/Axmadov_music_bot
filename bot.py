
import asyncio
import aiohttp
from urllib.parse import quote
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, BotCommand, InlineKeyboardMarkup,
    InlineKeyboardButton, CallbackQuery
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

TOKEN = "BOT_TOKENINGIZNI_BU_YERGA_YOZING"

bot = Bot(token=TOKEN)
dp = Dispatcher()

languages = {}

TEXTS = {
    "uz": {
        "welcome": "🎵 Axmadov_music botiga xush kelibsiz!",
        "menu": "Kerakli xizmatni tanlang:",
        "music": "🎵 Musiqa nomini yuboring:",
        "video": "🎬 Video nomini yuboring:",
        "help": "📌 Buyruqlar:\n/start - Botni boshlash\n/music - Musiqa qidirish\n/video - Video qidirish\n/lang - Tilni o'zgartirish\n/stop - Bekor qilish",
        "stop": "✅ Amal bekor qilindi.",
        "choose": "🌐 Tilni tanlang:",
        "notfound": "❌ Hech narsa topilmadi.",
        "error": "⚠️ Xatolik yuz berdi.",
        "search": "🔎 Qidiruv natijasi:"
    },
    "ru": {
        "welcome": "🎵 Добро пожаловать в Axmadov_music!",
        "menu": "Выберите услугу:",
        "music": "🎵 Отправьте название музыки:",
        "video": "🎬 Отправьте название видео:",
        "help": "📌 Команды:\n/start - Запустить бота\n/music - Поиск музыки\n/video - Поиск видео\n/lang - Изменить язык\n/stop - Отмена",
        "stop": "✅ Действие отменено.",
        "choose": "🌐 Выберите язык:",
        "notfound": "❌ Ничего не найдено.",
        "error": "⚠️ Произошла ошибка.",
        "search": "🔎 Результат поиска:"
    }
}


def get_lang(user_id):
    return languages.get(user_id, "uz")


class SearchState(StatesGroup):
    music = State()
    video = State()


def menu_keyboard(lang):
    if lang == "ru":
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎵 Музыка", callback_data="music")],
            [InlineKeyboardButton(text="🎬 Видео", callback_data="video")],
            [InlineKeyboardButton(text="🌐 Язык", callback_data="lang")],
            [InlineKeyboardButton(text="❓ Помощь", callback_data="help")]
        ])

    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎵 Musiqa qidirish", callback_data="music")],
        [InlineKeyboardButton(text="🎬 Video qidirish", callback_data="video")],
        [InlineKeyboardButton(text="🌐 Tilni o'zgartirish", callback_data="lang")],
        [InlineKeyboardButton(text="❓ Yordam", callback_data="help")]
    ])


@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message.from_user.id)
    await message.answer(
        TEXTS[lang]["welcome"] + "\n\n" + TEXTS[lang]["menu"],
        reply_markup=menu_keyboard(lang)
    )


@dp.message(Command("help"))
async def help_command(message: Message):
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["help"])


@dp.message(Command("music"))
async def music_command(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    query = message.text.partition(" ")[2].strip()

    if query:
        await search_music(message, query)
    else:
        await state.set_state(SearchState.music)
        await message.answer(TEXTS[lang]["music"])


async def search_music(message: Message, query: str):
    lang = get_lang(message.from_user.id)

    try:
        async with aiohttp.ClientSession() as session:
            url = "https://itunes.apple.com/search"
            params = {
                "term": query,
                "entity": "song",
                "limit": 5
            }

            async with session.get(url, params=params) as response:
                data = await response.json()

        results = data.get("results", [])

        if not results:
            await message.answer(TEXTS[lang]["notfound"])
            return

        for item in results:
            name = item.get("trackName", "Noma'lum")
            artist = item.get("artistName", "Noma'lum")
            preview = item.get("previewUrl")

            text = f"🎵 {name}\n👤 {artist}"

            if preview:
                text += f"\n\n▶️ Tinglash: {preview}"

            await message.answer(text)

    except Exception:
        await message.answer(TEXTS[lang]["error"])


@dp.message(Command("video"))
async def video_command(message: Message, state: FSMContext):
    lang = get_lang(message.from_user.id)
    query = message.text.partition(" ")[2].strip()

    if query:
        await search_video(message, query)
    else:
        await state.set_state(SearchState.video)
        await message.answer(TEXTS[lang]["video"])


async def search_video(message: Message, query: str):
    lang = get_lang(message.from_user.id)

    url = "https://www.youtube.com/results?search_query=" + quote(query)

    await message.answer(
        f"{TEXTS[lang]['search']}\n\n"
        f"🎬 {query}\n\n"
        f"🔗 {url}\n\n"
        "Video YouTube orqali ochiladi."
    )


@dp.message(SearchState.music)
async def music_text(message: Message, state: FSMContext):
    await state.clear()
    await search_music(message, message.text)


@dp.message(SearchState.video)
async def video_text(message: Message, state: FSMContext):
    await state.clear()
    await search_video(message, message.text)


@dp.message(Command("lang"))
async def lang_command(message: Message):
    lang = get_lang(message.from_user.id)

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="lang_uz"),
            InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang_ru")
        ]
    ])

    await message.answer(TEXTS[lang]["choose"], reply_markup=keyboard)


@dp.message(Command("stop"))
async def stop_command(message: Message, state: FSMContext):
    await state.clear()
    lang = get_lang(message.from_user.id)
    await message.answer(TEXTS[lang]["stop"])


@dp.callback_query(F.data == "music")
async def music_button(callback: CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    await state.set_state(SearchState.music)
    await callback.message.answer(TEXTS[lang]["music"])
    await callback.answer()


@dp.callback_query(F.data == "video")
async def video_button(callback: CallbackQuery, state: FSMContext):
    lang = get_lang(callback.from_user.id)
    await state.set_state(SearchState.video)
    await callback.message.answer(TEXTS[lang]["video"])
    await callback.answer()


@dp.callback_query(F.data == "help")
async def help_button(callback: CallbackQuery):
    lang = get_lang(callback.from_user.id)
    await callback.message.answer(TEXTS[lang]["help"])
    await callback.answer()


@dp.callback_query(F.data == "lang")
async def lang_button(callback: CallbackQuery):
    await lang_command(callback.message)
    await callback.answer()


@dp.callback_query(F.data.startswith("lang_"))
async def change_language(callback: CallbackQuery):
    lang = callback.data.split("_")[1]
    languages[callback.from_user.id] = lang

    await callback.message.edit_text(
        TEXTS[lang]["welcome"],
        reply_markup=menu_keyboard(lang)
    )
    await callback.answer("Language changed!")


async def main():
    await bot.set_my_commands([
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="music", description="Musiqa qidirish"),
        BotCommand(command="video", description="Video qidirish"),
        BotCommand(command="help", description="Yordam"),
        BotCommand(command="lang", description="Tilni o'zgartirish"),
        BotCommand(command="stop", description="Jarayonni to'xtatish")
    ])

    print("Axmadov_music bot ishga tushdi!")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
