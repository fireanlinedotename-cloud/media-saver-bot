import os
import re
import subprocess
import threading
import requests
import telebot
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Многопоточность на 5 одновременных пользователей
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
    """Быстрый парсер для TikTok"""
    try:
        res = requests.post("https://www.tikwm.com/api/", data={"url": url}, timeout=10).json()
        if res.get("code") == 0:
            return res["data"]["play"]
    except Exception:
        pass
    return None

def download_vk_video_locally(url, output_filename="video.mp4"):
    """Локальная загрузка VK Видео через yt-dlp"""
    if os.path.exists(output_filename):
        try:
            os.remove(output_filename)
        except Exception:
            pass
            
    command = [
        "yt-dlp",
        "-f", "best[ext=mp4]/best",
        "-o", output_filename,
        "--no-playlist",
        url
    ]
    try:
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=45)
        if result.returncode == 0 and os.path.exists(output_filename):
            return output_filename
    except Exception:
        pass
    return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "👋 Привет! Я твой персональный загрузчик видео.\n\n"
        "📌 Поддерживаемые площадки:\n"
        "• TikTok (через API)\n"
        "• VK Видео и Клипы (локальная загрузка)\n\n"
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

    monetization_button = InlineKeyboardButton("🎁 Поддержать бота / Монетизация", url=LINKNI_URL)

    # 1. Обработка TikTok (прямая ссылка)
    if "tiktok.com" in url:
        direct_url = get_tiktok_video(url)
        if not direct_url:
            try:
                bot.edit_message_text("❌ Не удалось получить видео из TikTok.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
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

        if file_size_mb > 50:
            markup = InlineKeyboardMarkup(row_width=1)
            markup.add(
                InlineKeyboardButton("🌐 Скачать видео (Браузер)", url=direct_url),
                monetization_button
            )
            bot.edit_message_text(
                f"⚠️ **Видео слишком большое ({file_size_mb:.1f} МБ)!**\nСкачайте его по ссылке:",
                chat_id=status_msg.chat.id, message_id=status_msg.message_id, reply_markup=markup, parse_mode="Markdown"
            )
        else:
            bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            markup = InlineKeyboardMarkup()
            markup.add(monetization_button)
            try:
                bot.send_video(message.chat.id, direct_url, caption="✅ Готово!", reply_markup=markup)
                bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass

    # 2. Обработка VK Видео (через локальный yt-dlp)
    elif "vk.com" in url or "vkvideo.ru" in url:
        bot.edit_message_text("📥 Скачиваю видео с VK...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        
        file_path = download_vk_video_locally(url, f"vk_{message.chat.id}.mp4")
        
        if not file_path or not os.path.exists(file_path):
            try:
                bot.edit_message_text("❌ Не удалось скачать видео из VK. Проверьте ссылку.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass
            return

        file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
        markup = InlineKeyboardMarkup()
        markup.add(monetization_button)

        if file_size_mb > 50:
            try:
                bot.edit_message_text(
                    f"⚠️ **Видео из VK слишком большое ({file_size_mb:.1f} МБ)!**\nTelegram не пропускает файлы больше 50 МБ.",
                    chat_id=status_msg.chat.id, message_id=status_msg.message_id
                )
            except Exception:
                pass
        else:
            try:
                with open(file_path, 'rb') as video_file:
                    bot.send_video(
                        message.chat.id, 
                        video_file, 
                        caption="✅ Ваше видео из VK успешно скачано!",
                        reply_markup=markup
                    )
                bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            except Exception:
                pass
        
        # Удаляем временный файл со следов сервера
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception:
            pass
    else:
        bot.edit_message_text("📌 Поддерживаются только ссылки на TikTok и VK.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
