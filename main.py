import os
import telebot
from yt_dlp import YoutubeDL

# Безопасный забор токена из переменных Render
TOKEN = os.environ.get("BOT_TOKEN")
bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start'])
def start_message(message):
    text = (
        "👋 **Привет! Я твой персональный загрузчик видео.**\n\n"
        "Я могу быстро и в хорошем качестве скачать видеоролик без водяных знаков.\n\n"
        "📌 **Поддерживаемые площадки:**\n"
        "• TikTok\n"
        "• VK (Видео и Клипы)\n"
        "• YouTube (Shorts и обычные видео)\n\n"
        "👇 **Просто скопируй и отправь мне ссылку на видео прямо сюда!**"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(commands=['help'])
def help_message(message):
    text = (
        "❓ **Инструкция по скачиванию:**\n\n"
        "1. Открой приложение (TikTok, VK или YouTube).\n"
        "2. Нажми «Поделиться» ➔ «Скопировать ссылку».\n"
        "3. Вставь ссылку в этот чат и отправь сообщение.\n"
        "4. Дождись завершения обработки и забирай готовый файл!"
    )
    bot.send_message(message.chat.id, text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: message.text and ("http://" in message.text or "https://" in message.text))
def download_video(message):
    url = message.text.strip()
    
    status_msg = bot.reply_to(
        message, 
        "⚙️ **Принял ссылку в обработку!**\n"
        "Подключаюсь к серверу и начинаю скачивание видеоролика. Пожалуйста, подождите..."
    )
    
    ydl_opts = {
        'format': 'best[filesize<50M]/best',
        'outtmpl': 'video_%(id)s.%(ext)s',
        'quiet': True
    }
    
    filepath = None
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            filepath = ydl.prepare_filename(info)
        
        bot.edit_message_text(
            "⏳ **Видео успешно загружено на сервер!**\n"
            "Почти готово: сжимаем файл и отправляем его прямо в этот чат...",
            chat_id=message.chat.id,
            message_id=status_msg.message_id
        )
        
        with open(filepath, 'rb') as video:
            bot.send_video(
                message.chat.id, 
                video, 
                caption="✅ **Ваше видео успешно скачано!**\nПриятного просмотра 🚀",
                reply_to_message_id=message.message_id,
                parse_mode="Markdown"
            )
        
        bot.delete_message(message.chat.id, status_msg.message_id)
        
    except Exception as e:
        bot.edit_message_text(
            f"❌ **Произошла ошибка при скачивании:**\n`{str(e)[:150]}`\n\nПроверьте корректность ссылки и попробуйте ещё раз.",
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            parse_mode="Markdown"
        )
    
    finally:
        if filepath and os.path.exists(filepath):
            os.remove(filepath)

print("Бот запущен...")
bot.infinity_polling()
