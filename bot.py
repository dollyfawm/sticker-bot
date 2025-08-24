
"""
Telegram Sticker/Emoji Converter Bot
-----------------------------------
- Send photo/PNG/JPG/WEBP -> static WEBP sticker
- Send GIF/video -> video WEBM sticker
- Per-user sticker packs (static + video) are auto-managed
- Optional: put an emoji in the caption to bind it to the sticker (defaults to 🧩)
"""

import asyncio
import io
import logging
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple

from PIL import Image
from telegram import (
    Update,
    InputFile,
    StickerFormat,
    StickerType,
    InputSticker,
)
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# -------------------- Config --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DEFAULT_EMOJI = "🧩"
STATIC_SUFFIX = "_static"
VIDEO_SUFFIX = "_video"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("stickerbot")

# -------------------- Helpers --------------------

def sanitize_username(username: str, user_id: int) -> str:
    if not username:
        return f"user{user_id}"
    return re.sub(r"[^a-zA-Z0-9_]", "_", username).lower()

async def tg_download_to_bytes(update: Update, context: ContextTypes.DEFAULT_TYPE) -> Tuple[bytes, str]:
    """Download the best variant of the incoming media and return (bytes, ext)."""
    if update.message is None:
        raise RuntimeError("No message to process.")

    msg = update.message

    if msg.photo:
        file = await msg.photo[-1].get_file()
        b = await file.download_as_bytearray()
        return bytes(b), ".jpg"

    if msg.animation:
        file = await msg.animation.get_file()
        b = await file.download_as_bytearray()
        return bytes(b), ".gif"

    if msg.video:
        file = await msg.video.get_file()
        b = await file.download_as_bytearray()
        ext = Path(file.file_path).suffix.lower() or ".mp4"
        return bytes(b), ext

    if msg.document:
        file = await msg.document.get_file()
        b = await file.download_as_bytearray()
        ext = Path(file.file_path).suffix.lower()
        return bytes(b), ext or ".bin"

    raise RuntimeError("Unsupported message type.")

# -------------------- Image → WEBP --------------------

def image_to_sticker_webp(src_bytes: bytes) -> bytes:
    """Convert an image to a Telegram-ready static WEBP sticker (max 512px)."""
    with Image.open(io.BytesIO(src_bytes)) as im:
        im = im.convert("RGBA")
        w, h = im.size
        scale = 512.0 / max(w, h)
        if scale < 1.0:
            im = im.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        out = io.BytesIO()
        im.save(out, format="WEBP", method=6, quality=95)
        return out.getvalue()

# -------------------- Video/GIF → WEBM (VP9) --------------------

@dataclass
class FfmpegPaths:
    ffmpeg: str = shutil.which("ffmpeg") or "ffmpeg"

FF = FfmpegPaths()

def ensure_ffmpeg() -> None:
    if not shutil.which(FF.ffmpeg):
        raise RuntimeError("FFmpeg not found. Please install FFmpeg and ensure it's in PATH.")

async def video_to_sticker_webm(src_bytes: bytes) -> bytes:
    """Convert video/GIF to a Telegram-ready WEBM (VP9) sticker."""
    ensure_ffmpeg()
    with tempfile.TemporaryDirectory() as td:
        in_path = Path(td) / "in.bin"
        out_path = Path(td) / "out.webm"
        in_path.write_bytes(src_bytes)

        cmd = [
            FF.ffmpeg, "-y",
            "-i", str(in_path),
            "-an",
            "-t", "3",
            "-vf", "scale='min(512,iw)':-2:force_original_aspect_ratio=decrease,fps=30",
            "-c:v", "libvpx-vp9",
            "-b:v", "420k",
            "-crf", "32",
            "-deadline", "realtime",
            str(out_path),
        ]
        import subprocess
        proc = subprocess.run(cmd, capture_output=True)
        if proc.returncode != 0 or not out_path.exists():
            raise RuntimeError(f"FFmpeg failed: {proc.stderr.decode(errors='ignore')[:500]}")
        return out_path.read_bytes()

# -------------------- Sticker set management --------------------

async def get_or_create_set(update: Update, context: ContextTypes.DEFAULT_TYPE, kind: str) -> Tuple[str, str]:
    """Return (set_name, set_title). Create if missing. kind in {'static','video'}"""
    assert kind in ("static", "video")

    user = update.effective_user
    bot = context.bot
    bot_user = await bot.get_me()

    uname = sanitize_username(user.username or "", user.id)
    suffix = STATIC_SUFFIX if kind == "static" else VIDEO_SUFFIX
    set_name = f"{uname}{suffix}_by_{bot_user.username}"
    set_title = f"{user.first_name or 'User'}'s {'Static' if kind=='static' else 'Video'} Stickers"

    try:
        await bot.get_sticker_set(name=set_name)
        return set_name, set_title
    except Exception:
        pass

    # Create placeholder
    tiny = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    buf = io.BytesIO()
    tiny.save(buf, format="WEBP")
    placeholder = buf.getvalue()

    placeholder_sticker = InputSticker(
        sticker=InputFile(io.BytesIO(placeholder), filename="ph.webp"),
        emoji_list=[DEFAULT_EMOJI],
    )

    fmt = StickerFormat.WEBP if kind == "static" else StickerFormat.VIDEO

    await bot.create_new_sticker_set(
        user_id=user.id,
        name=set_name,
        title=set_title,
        stickers=[placeholder_sticker],
        sticker_format=fmt,
        sticker_type=StickerType.REGULAR,
    )

    # Remove placeholder
    try:
        stset = await bot.get_sticker_set(name=set_name)
        if stset.stickers:
            await bot.delete_sticker_from_set(stset.stickers[0].file_id)
    except Exception as e:
        logger.warning("Couldn't delete placeholder: %s", e)

    return set_name, set_title

async def add_to_set(update: Update, context: ContextTypes.DEFAULT_TYPE, set_name: str, sticker_bytes: bytes, kind: str, emoji: str) -> str:
    """Add sticker to a set and return file_id."""
    if kind == "static":
        input_sticker = InputSticker(
            sticker=InputFile(io.BytesIO(sticker_bytes), filename="sticker.webp"),
            emoji_list=[emoji or DEFAULT_EMOJI],
        )
    else:
        input_sticker = InputSticker(
            sticker=InputFile(io.BytesIO(sticker_bytes), filename="sticker.webm"),
            emoji_list=[emoji or DEFAULT_EMOJI],
        )

    await context.bot.add_sticker_to_set(
        user_id=update.effective_user.id,
        name=set_name,
        sticker=input_sticker,
    )

    stset = await context.bot.get_sticker_set(name=set_name)
    return stset.stickers[-1].file_id

# -------------------- Handlers --------------------

HELP_TEXT = (
    "Отправь мне фото/картинку/PNG/JPG/WEBP — я сделаю стикер.\n"
    "Отправь GIF/видео — сделаю видеостикер.\n\n"
    "Можно добавить смайлик в подписи (например: 😀) — он привяжется к стикеру.\n"
    "Я автоматически создам личные наборы: статичный и видео."
)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "Привет! Я конвертирую фото/видео в стикеры. "
        "Просто пришли файл. /help — подробности."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    try:
        await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.UPLOAD_DOCUMENT)
        src_bytes, ext = await tg_download_to_bytes(update, context)
        caption = (update.message.caption or "").strip()
        emoji = caption if caption and len(caption) <= 10 else DEFAULT_EMOJI

        if ext.lower() in (".gif", ".mp4", ".mov", ".mkv", ".webm", ".avi") or update.message.video or update.message.animation:
            kind = "video"
            sticker_bytes = await video_to_sticker_webm(src_bytes)
        else:
            kind = "static"
            sticker_bytes = image_to_sticker_webp(src_bytes)

        set_name, set_title = await get_or_create_set(update, context, kind)
        file_id = await add_to_set(update, context, set_name, sticker_bytes, kind, emoji)

        await update.message.reply_sticker(sticker=file_id)
        await update.message.reply_text(
            f"Добавлено в набор: {set_title}\nОткрыть: https://t.me/addstickers/{set_name}"
        )

    except Exception as e:
        logger.exception("Failed to process media: %s", e)
        await update.message.reply_text(
            "Ой! Не получилось сделать стикер. Убедись, что у меня есть права и установлен FFmpeg (для видео).\n"
            f"Тех. детали: {e}"
        )

# -------------------- App bootstrap --------------------

def main() -> None:
    token = BOT_TOKEN
    if not token:
        raise SystemExit("Please set BOT_TOKEN env var (from @BotFather)")

    use_webhook = os.getenv("USE_WEBHOOK", "false").lower() == "true"
    webhook_url = os.getenv("WEBHOOK_URL")
    port = int(os.getenv("PORT", "8080"))

    app: Application = ApplicationBuilder().token(token).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(
        MessageHandler(
            filters.ALL & (filters.PHOTO | filters.VIDEO | filters.ANIMATION | filters.Document.IMAGE | filters.Document.GIF),
            handle_media,
        )
    )

    logger.info("Bot starting in %s mode", "webhook" if use_webhook else "polling")
    if use_webhook:
        if not webhook_url:
            raise SystemExit("WEBHOOK_URL is required when USE_WEBHOOK=true")
        app.run_webhook(
            listen="0.0.0.0",
            port=port,
            webhook_url=webhook_url,
            close_loop=False,
        )
    else:
        app.run_polling(close_loop=False)

if __name__ == "__main__":
    main()
