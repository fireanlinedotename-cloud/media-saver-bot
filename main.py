import os
import asyncio
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, MenuButtonCommands, BotCommand

TOKEN = "ТВОЙ_ТОКЕН_БОТА"
bot = Bot(token=TOKEN)
dp = Dispatcher()

# Установка меню команд при старте
async def set_main_menu(bot: Bot):
    commands = [
        BotCommand(command="start", description="🚀 Перезапустить бота"),
        BotCommand(command="donate", description="☕ Поддержать проект"),
        BotCommand(command="help", description="❓ Как пользоваться")
    ]
    await bot.set_my_commands(commands)

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Привет! Я Save Media Bot.**\n\n"
        "Отправь мне ссылку на видео из TikTok, Reels, Shorts или YouTube, "
        "и я мгновенно пришлю его тебе без водяных знаков!",
        parse_mode="Markdown"
    )

@dp.message(Command("donate"))
async def cmd_donate(message: types.Message):
    # Компактное и эстетичное сообщение для донатов
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❤️ Поддержать автора (Linkni)", url="https://linkni.ru/your_link")]
    ])
    await message.answer(
        "🤝 **Поддержка проекта**\n\n"
        "Бот работает бесплатно и без рекламы. Если он тебе полезен, "
        "ты можешь поддержать разработчика любой суммой!",
        reply_markup=keyboard,
        parse_mode="Markdown"
    )

# Пример обработки ссылки на видео
@dp.message(F.text.startswith("http"))
async def handle_link(message: types.Message):
    status_msg = await message.answer("⏳ Загружаю...")
    
    # --- Здесь твоя логика скачивания через yt-dlp / API ---
    # Например: video_path = "video.mp4", audio_path = "audio.mp3", file_size_mb = 15
    
    file_size_mb = 15  # Для примера
    video_path = "downloads/sample.mp4" # Для примера
    
    # 1. Если файл больше 50 МБ (ограничение Telegram Bot API на отправку)
    if file_size_mb > 50:
        download_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🌐 Скачать в браузере", url="https://your-download-link.com")]
        ])
        await status_msg.edit_text(
            "⚠️ Видео слишком большое для отправки в Telegram (больше 50 МБ).\n"
            "Вы можете скачать его напрямую по кнопке ниже:",
            reply_markup=download_kb
        )
        return

    # 2. Если файл нормального размера — отправляем ЧИСТОЕ ВИДЕО БЕЗ КНОПОК
    await status_msg.delete()
    
    # Используем InputFile или FSInputFile
    video_file = types.FSInputFile(video_path)
    await message.answer_video(
        video=video_file,
        caption="✨ Скачано с помощью @YourBotName"  # Лаконичная подпись
    )
    
    # Если нужно отправить и аудио (например, из TikTok/Reels):
    # audio_file = types.FSInputFile(audio_path)
    # await message.answer_audio(audio=audio_file, title="Аудио из видео")

async def main():
    await set_main_menu(bot)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
