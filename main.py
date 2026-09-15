import os
import re
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "👋 Привет! Я твой персональный загрузчик видео.\n\n"
        "📌 Поддерживаемые площадки:\n"
        "• TikTok\n"
        "• VK (Видео и Клипы)\n"
        "• YouTube (Shorts и обычные видео)\n\n"
        "👇 Просто скопируй и отправь мне ссылку на видео прямо сюда!"
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    url_pattern = r'https?://[^\s]+'
    urls = re.findall(url_pattern, message.text)
    
    if not urls:
        bot.reply_to(message, "Пожалуйста, отправьте корректную ссылку на видео.")
        return

    url = urls[0]
    status_msg = bot.reply_to(message, "⏳ Обрабатываю ссылку...")

    try:
        payload = {
            "url": url,
            "videoQuality": "720"
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        response = requests.post("https://api.cobalt.tools/api/json", json=payload, headers=headers, timeout=20)
        data = response.json()

        status = data.get("status")

        if status in ["tunnel", "redirect"]:
            video_url = data.get("url")
            
            # Проверяем размер файла с помощью HEAD-запроса
            file_size_mb = 0
            try:
                head_resp = requests.head(video_url, allow_redirects=True, timeout=5)
                content_length = head_resp.headers.get('Content-Length')
                if content_length:
                    file_size_mb = int(content_length) / (1024 * 1024)
            except Exception:
                pass

            # Если размер больше 50 МБ (или не удалось точно узнать размер большой ссылки)
            if file_size_mb > 50:
                markup = InlineKeyboardMarkup()
                markup.add(InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=video_url))
                
                bot.edit_message_text(
                    f"⚠️ **Видео слишком большое ({file_size_mb:.1f} МБ)!**\n\n"
                    f"Telegram не позволяет ботам отправлять файлы больше 50 МБ.\n"
                    f"Вы можете скачать его напрямую по кнопке ниже:",
                    chat_id=status_msg.chat.id, 
                    message_id=status_msg.message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            else:
                bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
                try:
                    bot.send_video(message.chat.id, video_url)
                    bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
                except Exception:
                    # Если отправка через Telegram все же сорвалась из-за размера
                    markup = InlineKeyboardMarkup()
                    markup.add(InlineKeyboardButton("🌐 Скачать файл", url=video_url))
                    bot.edit_message_text(
                        "⚠️ Не удалось отправить файл напрямую. Скачайте его по ссылке:",
                        chat_id=status_msg.chat.id,
                        message_id=status_msg.message_id,
                        reply_markup=markup
                    )

        elif status == "picker":
            bot.edit_message_text("📥 Отправляю медиа...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            for item in data.get("picker", [])[:5]:
                if item.get("type") == "photo":
                    bot.send_photo(message.chat.id, item.get("url"))
                else:
                    bot.send_video(message.chat.id, item.get("url"))
            bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)

        else:
            error_text = data.get("text", "Не удалось получить ссылку на видео.")
            bot.edit_message_text(f"❌ Ошибка: {error_text}", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

    except Exception as e:
        bot.edit_message_text(f"❌ Произошла ошибка при скачивании: {e}", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
