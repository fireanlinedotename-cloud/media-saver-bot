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

def get_vk_direct_link_via_cobalt(url):
    """Моментально достает прямую ссылку через Cobalt API (без скачивания на сервер)"""
    instances = [
        "https://co.wuk.sh",
        "https://api.cobalt.7777777.xyz",
        "https://cobalt.api.kwiatekmom.tokyo",
        "https://dl.cobalt.best"
    ]
    payload = {"url": url, "videoQuality": "720"}
    headers = {"Accept": "application/json", "Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
    
    for instance in instances:
        try:
            res = requests.post(f"{instance}/api/json", json=payload, headers=headers, timeout=6)
            if res.status_code == 200:
                data = res.json()
                if data.get("status") in ["tunnel", "redirect"]:
                    return data.get("url")
                elif data.get("status") == "picker" and data.get("picker"):
                    return data["picker"][0].get("url")
        except Exception:
            continue
    return None

def download_vk_video_locally(url, output_filename="video.mp4"):
    """Резервная локальная загрузка через yt-dlp (если API не сработало)"""
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
        "• TikTok\n"
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

    monetization_button = InlineKeyboardButton("🎁 Поддержать бота / Монетизация", url=LINKNI_URL)
    direct_url = None
    file_size_mb = 0

    # 1. TikTok
    if "tiktok.com" in url:
        direct_url = get_tiktok_video(url)
    
    # 2. VK Видео
    elif "vk.com" in url or "vkvideo.ru" in url:
        direct_url = get_vk_direct_link_via_cobalt(url)

    if not direct_url and ("vk.com" in url or "vkvideo.ru" in url):
        bot.edit_message_text("📥 Большое видео, скачиваю на сервер...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        file_path = download_vk_video_locally(url, f"vk_{message.chat.id}.mp4")
        
        if file_path and os.path.exists(file_path):
            file_size_mb = os.path.getsize(file_path) / (1024 * 1024)
            markup = InlineKeyboardMarkup()
            markup.add(monetization_button)

            if file_size_mb > 50:
                bot.edit_message_text(
                    f"⚠️ **Видео слишком большое ({file_size_mb:.1f} МБ)!**\nTelegram не пропускает файлы больше 50 МБ.",
                    chat_id=status_msg.chat.id, message_id=status_msg.message_id
                )
            else:
                bot.edit_message_text("📥 Отправляю видео...", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
                with open(file_path, 'rb') as video_file:
                    bot.send_video(message.chat.id, video_file, caption="✅ Готово!", reply_markup=markup)
                bot.delete_message(chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            
            if os.path.exists(file_path):
                os.remove(file_path)
            return
        else:
            bot.edit_message_text("❌ Не удалось обработать это видео из VK.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
            return

    if not direct_url:
        bot.edit_message_text("❌ Не удалось получить ссылку на скачивание.", chat_id=status_msg.chat.id, message_id=status_msg.message_id)
        return

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
    markup = InlineKeyboardMarkup()
    markup.add(monetization_button)

    try:
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
        bot.send_message(
            message.chat.id,
            "⚠️ Не удалось отправить файл напрямую. Скачайте его по ссылке:",
            reply_markup=markup
        )

if __name__ == "__main__":
    bot.infinity_polling()
