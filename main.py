import os
import re
import subprocess
import threading
import requests
import telebot
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, BotCommand

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)

# Партнёрская ссылка Linkni
LINKNI_URL = "https://telegram.me/linknibot/app?startapp=x_2z50t"

# --- Настройка меню команд ---
try:
    bot.set_my_commands([
        BotCommand("start", "🚀 Перезапустить бота"),
        BotCommand("donate", "☕ Поддержать проект / Монетизация")
    ])
except Exception:
    pass

# --- МИНИ-СЕРВЕР ДЛЯ RENDER ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()
# -----------------------------

def get_tiktok_video(url):
    """Парсер для TikTok"""
    try:
        res = requests.post("https://www.tikwm.com/api/", data={"url": url}, timeout=10).json()
        if res.get("code") == 0:
            return res["data"]["play"], res["data"].get("music")
    except Exception:
        pass
    return None, None

def get_vk_info_safely(url):
    """Быстро получает прямую ссылку и размер через yt-dlp"""
    command = [
        "yt-dlp",
        "--get-url",
        "--print", "filesize",
        "-f", "best[ext=mp4]/best",
        "--no-playlist",
        url
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            if len(lines) >= 2:
                file_size_bytes = lines[0].strip()
                direct_url = lines[1].strip()
                
                size_mb = 0
                if file_size_bytes.isdigit():
                    size_mb = int(file_size_bytes) / (1024 * 1024)
                return direct_url, size_mb
            elif len(lines) == 1 and lines[0].startswith('http'):
                return lines[0].strip(), 0
    except Exception:
        pass
    return None, 0

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "👋 Привет! Я твой загрузчик видео.\n\n"
        "📌 Поддерживаемые площадки:\n"
        "• TikTok\n"
        "• VK (Видео и Клипы)\n\n"
        "👇 Отправь мне ссылку на видео!"
    )

@bot.message_handler(commands=['donate'])
def send_donate(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 Поддержать автора", url=LINKNI_URL))
    bot.reply_to(
        message,
        "🤝 **Поддержка проекта**\n\n"
        "Бот работает бесплатно и без надоедливой рекламы.\n"
        "Если тебе нравится сервис, ты можешь поддержать разработчика по кнопке ниже!",
        reply_markup=markup,
        parse_mode="Markdown"
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
        status_msg = bot.reply_to(message, "⏳ Анализирую ссылку...")
    except Exception:
        status_msg = bot.send_message(message.chat.id, "⏳ Анализирую ссылку...")

    direct_url = None
    file_size_mb = 0

    # 1. TikTok
    if "tiktok.com" in url:
        direct_url, _ = get_tiktok_video(url)
        
        if not direct_url:
            bot.edit_message_text("❌ Не удалось получить ссылку на TikTok видео.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            return

        try:
            head_resp = requests.head(direct_url, allow_redirects=True, timeout=5)
            content_length = head_resp.headers.get('Content-Length')
            if content_length:
                file_size_mb = int(content_length) / (1024 * 1024)
        except Exception:
            pass

        if file_size_mb > 50:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=direct_url))
            bot.edit_message_text(
                f"⚠️ **Видео слишком большое ({file_size_mb:.1f} МБ)!**\n\n"
                f"Telegram ограничил отправку файлов до 50 МБ.\n"
                f"Скачайте напрямую:",
                chat_id=status_msg.chat.id, 
                message_id=status_msg.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

        bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

        try:
            bot.send_video(message.chat.id, direct_url)
            bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        except Exception:
            markup = InlineKeyboardMarkup()
            markup.add(InlineKeyboardButton("🌐 Скачать файл", url=direct_url))
            bot.send_message(message.chat.id, "⚠️ Не удалось отправить файл напрямую. Скачайте по ссылке:", reply_markup=markup)
        return

    # 2. VK Видео
    elif "vk.com" in url or "vkvideo.ru" in url:
        bot.edit_message_text("⏳ Анализирую видео из VK...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        direct_url, file_size_mb = get_vk_info_safely(url)
        
        if not direct_url:
            bot.edit_message_text("❌ Не удалось получить ссылку из VK.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            return

        if file_size_mb > 50 or file_size_mb == 0:
            size_text = f" ({file_size_mb:.1f} МБ)" if file_size_mb > 0 else ""
            markup_browser = InlineKeyboardMarkup()
            markup_browser.add(InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=direct_url))
            bot.edit_message_text(
                f"⚠️ **Видео из VK слишком большое{size_text}!**\n\n"
                f"Telegram ограничил отправку файлов до 50 МБ.\n"
                f"Скачайте напрямую:",
                chat_id=status_msg.chat.id, 
                message_id=status_msg.message_id,
                reply_markup=markup_browser,
                parse_mode="Markdown"
            )
            return

        bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        try:
            bot.send_video(message.chat.id, direct_url)
            bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        except Exception:
            markup_browser = InlineKeyboardMarkup()
            markup_browser.add(InlineKeyboardButton("🌐 Скачать файл", url=direct_url))
            bot.edit_message_text(
                "⚠️ Не удалось отправить файл напрямую. Скачайте по ссылке:",
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                reply_markup=markup_browser
            )
        return

    else:
        bot.edit_message_text("❌ Неподдерживаемая ссылка. Поддерживаются TikTok и VK.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
