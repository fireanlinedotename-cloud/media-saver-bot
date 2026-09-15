import os
import re
import threading
import requests
import telebot
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# 💰 Партнёрская ссылка Linkni
LINKNI_URL = "https://telegram.me/linknibot/app?startapp=x_2z50t"

# --- МИНИ-СЕРВЕР ДЛЯ RENDER (чтобы не ругался на порты) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# Запускаем веб-сервер в отдельном потоке, чтобы он не мешал боту
threading.Thread(target=run_web_server, daemon=True).start()
# ---------------------------------------------------------

def get_vk_video(url):
    try:
        api_url = f"https://api.vkr.com.co/vk/video?url={url}"
        res = requests.get(api_url, timeout=10).json()
        if res.get("status") == True and "url" in res:
            return res.get("url")
        
        res2 = requests.get(f"https://dl.vkr.com.co/api/vk?url={url}", timeout=10).json()
        if "data" in res2 and "url" in res2["data"]:
            return res2["data"]["url"]
    except Exception:
        pass
    return None

def get_tiktok_video(url):
    try:
        res = requests.post("https://www.tikwm.com/api/", data={"url": url}, timeout=10).json()
        if res.get("code") == 0:
            return res["data"]["play"]
    except Exception:
        pass
    return None

def get_cobalt_video(url):
    instances = [
        "https://api.cobalt.7777777.xyz",
        "https://cobalt-api.kwiatekmom.tokyo",
        "https://cobalt-backend.jcloud.ik-server.com",
        "https://co.wuk.sh"
    ]
    payload = {"url": url, "videoQuality": "720"}
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    
    for instance in instances:
        try:
            res = requests.post(instance, json=payload, headers=headers, timeout=8)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") in ["tunnel", "redirect"]:
                    return data.get("url")
        except Exception:
            continue
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
    
    try:
        status_msg = bot.reply_to(message, "⏳ Обрабатываю ссылку...")
    except Exception:
        status_msg = bot.send_message(message.chat.id, "⏳ Обрабатываю ссылку...")

    direct_url = None

    if "vk.com" in url or "vkvideo.ru" in url:
        direct_url = get_vk_video(url)
    elif "tiktok.com" in url:
        direct_url = get_tiktok_video(url)
    
    if not direct_url:
        direct_url = get_cobalt_video(url)

    if not direct_url:
        try:
            bot.edit_message_text("❌ Не удалось получить ссылку на скачивание. Попробуйте позже.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        except Exception:
            pass
        return

    file_size_mb = 0
    try:
        head_resp = requests.head(direct_url, allow_redirects=True, timeout=5)
        content_length = head_resp.headers.get('Content-Length')
        if content_length:
            file_size_mb = int(content_length) / (1024 * 1024)
    except Exception:
        pass

    monetization_button = InlineKeyboardButton("🎁 Поддержать бота / Монетизация", url=LINKNI_URL)

    if file_size_mb > 50:
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(
            InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=direct_url),
            monetization_button
        )
        try:
            bot.edit_message_text(
                f"⚠️ **Видео слишком большое ({file_size_mb:.1f} МБ)!**\n\n"
                f"Telegram не позволяет ботам отправлять файлы больше 50 МБ.\n"
                f"Вы можете скачать его напрямую по кнопке ниже:",
                chat_id=status_msg.chat.id, 
                message_id=status_msg.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
        except Exception:
            pass
    else:
        try:
            bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        except Exception:
            pass

        markup = InlineKeyboardMarkup()
        markup.add(monetization_button)

        try:
            bot.send_video(
                message.chat.id, 
                direct_url, 
                caption="✅ Ваше видео успешно скачано!",
                reply_markup=markup
            )
            try:
                bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass
        except Exception:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("🌐 Скачать файл", url=direct_url),
                monetization_button
            )
            bot.send_message(
                message.chat.id,
                "⚠️ Не удалось отправить файл напрямую. Скачайте его по ссылке:",
                reply_markup=markup
            )

if __name__ == "__main__":
    bot.infinity_polling()
