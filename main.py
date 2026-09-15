import os
import re
import subprocess
import threading
import requests
import telebot
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)

# 💰 Партнёрская ссылка Linkni
LINKNI_URL = "https://telegram.me/linknibot/app?startapp=x_2z50t"

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
    """Быстро получает прямую ссылку и размер через yt-dlp без скачивания файла на диск"""
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
        "👋 Привет! Я твой персональный загрузчик видео.\n\n"
        "📌 Поддерживаемые площадки:\n"
        "• TikTok (видео + музыка)\n"
        "• VK (Видео и Клипы)\n\n"
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
        status_msg = bot.reply_to(message, "⏳ Анализирую ссылку...")
    except Exception:
        status_msg = bot.send_message(message.chat.id, "⏳ Анализирую ссылку...")

    bot_info = bot.get_me()
    ref_link = f"https://telegram.me/{bot_info.username}?start=ref_{message.from_user.id}"
    
    monetization_button = InlineKeyboardButton("🎁 Поддержать бота / Монетизация", url=LINKNI_URL)
    share_button = InlineKeyboardButton("👥 Пригласить друга", url=f"https://t.me/share/url?url={ref_link}&text=🔥%20Скачивай%20видео%20из%20TikTok%20и%20VK%20без%20водяных%20знаков%20в%20этом%20боте!")

    direct_url = None
    tiktok_audio_url = None
    file_size_mb = 0

    # 1. TikTok
    if "tiktok.com" in url:
        direct_url, tiktok_audio_url = get_tiktok_video(url)
        
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

        markup = InlineKeyboardMarkup(row_width=1)
        if file_size_mb > 50:
            markup.add(
                InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=direct_url),
                share_button,
                monetization_button
            )
            bot.edit_message_text(
                f"⚠️ **Видео слишком большое ({file_size_mb:.1f} МБ)!**\n\n"
                f"Telegram разрешает отправлять ботам файлы только до 50 МБ.\n"
                f"Вы можете скачать его напрямую по кнопке ниже:",
                chat_id=status_msg.chat.id, 
                message_id=status_msg.message_id,
                reply_markup=markup,
                parse_mode="Markdown"
            )
            return

        bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        if tiktok_audio_url:
            markup.add(InlineKeyboardButton("🎵 Скачать аудио (MP3)", url=tiktok_audio_url))
        markup.add(share_button, monetization_button)

        try:
            bot.send_video(message.chat.id, direct_url, caption="✅ Ваше видео успешно скачано!", reply_markup=markup)
            bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        except Exception:
            bot.send_message(message.chat.id, "⚠️ Не удалось отправить файл напрямую. Скачайте его по ссылке:", reply_markup=markup)
        return

    # 2. VK Видео
    elif "vk.com" in url or "vkvideo.ru" in url:
        bot.edit_message_text("⏳ Анализирую видео из VK...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        direct_url, file_size_mb = get_vk_info_safely(url)
        
        if not direct_url:
            bot.edit_message_text("❌ Не удалось получить ссылку из VK. Возможно, видео защищено.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            return

        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(share_button, monetization_button)

        if file_size_mb > 50 or file_size_mb == 0:
            size_text = f" ({file_size_mb:.1f} МБ)" if file_size_mb > 0 else ""
            markup_browser = InlineKeyboardMarkup(row_width=1)
            markup_browser.add(
                InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=direct_url),
                share_button,
                monetization_button
            )
            bot.edit_message_text(
                f"⚠️ **Видео из VK слишком большое{size_text}!**\n\n"
                f"Telegram разрешает отправлять ботам файлы только до 50 МБ.\n"
                f"Вы можете скачать его напрямую по кнопке ниже:",
                chat_id=status_msg.chat.id, 
                message_id=status_msg.message_id,
                reply_markup=markup_browser,
                parse_mode="Markdown"
            )
            return

        bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        try:
            bot.send_video(message.chat.id, direct_url, caption="✅ Ваше видео из VK успешно скачано!", reply_markup=markup)
            bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        except Exception:
            markup_browser = InlineKeyboardMarkup(row_width=1)
            markup_browser.add(
                InlineKeyboardButton("🌐 Скачать файл", url=direct_url),
                share_button,
                monetization_button
            )
            bot.edit_message_text(
                "⚠️ Не удалось отправить файл напрямую в Telegram. Скачайте его по ссылке:",
                chat_id=status_msg.chat.id,
                message_id=status_msg.message_id,
                reply_markup=markup_browser
            )
        return

    else:
        bot.edit_message_text("❌ Неподдерживаемая ссылка. Поддерживаются только TikTok и VK.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
