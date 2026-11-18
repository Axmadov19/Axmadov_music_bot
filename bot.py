import os
import re
import asyncio
import logging
import subprocess
import unicodedata
from pathlib import Path

import aiohttp
from aiohttp import web
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
import yt_dlp


# =============== SOZLAMALAR ===============

BOT_TOKEN = os.getenv("BOT_TOKEN")
AUDD_TOKEN = os.getenv("AUDD_TOKEN")
PORT = int(os.getenv("PORT", "8080"))

MUSIC_LIBRARY_DIR = Path("music_library")

MAX_VIDEO_BYTES = 48 * 1024 * 1024
MAX_AUDIO_BYTES = 10 * 1024 * 1024

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi!")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

user_langs = {}

AUDIO_EXTENSIONS = {
    ".mp3",
    ".m4a",
    ".aac",
    ".ogg",
    ".wav",
    ".flac"
}
