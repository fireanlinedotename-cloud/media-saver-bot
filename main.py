import os
import re
import requests
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# 💰 Твоя реферальная/партнерская ссылка Linkni для монетизации
# Замени на свою реальную ссылку с сервиса
LINKNI_URL = "https://telegram.me/linknibot/app?startapp=x_2z50t"

def get_cobalt_video(url):
    instances = [
        "https://cobalt-api.kwiatekmom.tokyo",
        "https://api.cobalt.7777777.xyz",
        "https://cobalt-backend.jcloud.ik-server.com"
    ]
    payload = {"url": url, "videoQuality": "720"}
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    for instance in instances:
        try:
            res = requests.post(instance, json=payload, headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") in ["tunnel", "redirect"]:
                    return data.get("url")
        except Exception:
            continue
    return None

def get_tiktok_video(url):
    try:
        res = requests.post("https://www.tikwm.com/api/", data={"url": url}, timeout=10).json()
        if res.get("code") == 0:
            return res["data"]["play"]
    except Exception:
        pass
    return None

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

    direct_url = None

    if "tiktok.com" in url:
        direct_url = get_tiktok_video(url)
    
    if not direct_url:
        direct_url = get_cobalt_video(url)

    if not direct_url:
        bot.edit_message_text("❌ Не удалось получить ссылку на скачивание. Попробуйте позже.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        return

    file_size_mb = 0
    try:
        head_resp = requests.head(direct_url, allow_redirects=True, timeout=5)
        content_length = head_resp.headers.get('Content-Length')
        if content_length:
            file_size_mb = int(content_length) / (1024 * 1024)
    except Exception:
        pass

    # Создаем кнопку монетизации Linkni
    monetization_button = InlineKeyboardButton("🎁 Поддержать бота / Монетизация", url=LINKNI_URL)

    # Если видео больше 50 МБ — выдаем прямую кнопку скачивания + кнопку Linkni
    if file_size_mb > 50:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=direct_url),
            monetization_button
        )
        
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
            # Прикрепляем к видео кнопку монетизации
            markup = InlineKeyboardMarkup()
            markup.add(monetization_button)
            
            bot.send_video(
                message.chat.id, 
                direct_url, 
                caption="✅ Ваше видео успешно скачано!",
                reply_markup=markup
            )
            bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        except Exception:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("🌐 Скачать файл", url=direct_url),
                monetization_button
            )
            bot.edit_message_text(
                "⚠️ Не удалось отправить файл напрямую. Скачайте его по ссылке:",
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                reply_markup=markup
            )

if __name__ == "__main__":
    bot.infinity_polling()
