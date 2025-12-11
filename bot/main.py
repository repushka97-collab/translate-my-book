#!/usr/bin/env python3
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Загружаем токен из .env
ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT / "bot" / ".env"
if ENV_PATH.is_file():
    load_dotenv(ENV_PATH)

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я черновой бот проекта TranslateMyBook.\n"
        "Пока умею только принимать PDF.\n"
        "Скоро подключим полный конвейер книги."
    )


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    file_name = doc.file_name or "upload.pdf"
    if not file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Пока принимаю только PDF-файлы.")
        return

    await update.message.reply_text("Принял PDF. Сохраняю в ingest…")

    tg_file = await doc.get_file()

    ingest_dir = ROOT / "ingest"
    ingest_dir.mkdir(exist_ok=True)
    out_path = ingest_dir / file_name

    await tg_file.download_to_drive(out_path.as_posix())

    await update.message.reply_text(
        f"Файл сохранён как `{out_path.name}`.\n"
        f"Дальнейшая обработка будет добавлена позже.",
        parse_mode="Markdown"
    )


def main():
    if not BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN не найден в .env")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))

    print("Bot is starting…")
    app.run_polling()


if __name__ == "__main__":
    main()
