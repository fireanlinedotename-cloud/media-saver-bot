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

LINKNI_URL = "https://telegram.me/linknibot/app?startapp=x_2z50t"

# Временное хранилище ссылок пользователей для обработки кнопок
user_urls = {}

try:
    bot.set_my_commands([
        BotCommand("start", "🚀 Перезапустить бота"),
        BotCommand("donate", "☕ Поддержать проект")
    ])
except Exception:
    pass

# --- Сервер для поддержания активности на Render ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running!")

def run_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

threading.Thread(target=run_web_server, daemon=True).start()
# --------------------------------------------------

def compress_video(input_path, output_path):
    """Сжатие видео через ffmpeg до размера менее 50 МБ"""
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-b:v", "800k", "-maxrate", "1000k", "-bufsize", "1000k",
        "-vf", "scale=-2:720",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "👋 **Привет! Я твой универсальный загрузчик.**\n\n"
        "Пришли мне ссылку на видео из TikTok, VK или YouTube, "
        "и я пришлю его тебе или переконвертирую в MP3!",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['donate'])
def send_donate(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 Поддержать автора", url=LINKNI_URL))
    bot.reply_to(
        message,
        "🤝 **Поддержка проекта**\n\n"
        "Бот работает бесплатно и без надоедливой рекламы.\n"
        "Если тебе нравится сервис, ты можете поддержать разработчика по кнопке ниже!",
        reply_markup=markup,
        parse_mode="Markdown"
    )

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    urls = re.findall(r'https?://[^\s]+', message.text)
    if not urls:
        bot.reply_to(message, "Пожалуйста, отправь корректную ссылку на видео.")
        return

    url = urls[0]
    user_urls[message.chat.id] = url

    # Клавиатура выбора формата
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Видео", callback_data="dl_video"),
        InlineKeyboardButton("🎵 MP3 (Аудио)", callback_data="dl_audio")
    )
    
    bot.reply_to(message, "🎯 **Выбери формат для скачивания:**", reply_markup=markup, parse_mode="Markdown")

@bot.callback_query_handler(func=lambda call: call.data in ["dl_video", "dl_audio"])
def process_download(call):
    chat_id = call.message.chat.id
    url = user_urls.get(chat_id)

    if not url:
        bot.answer_callback_query(call.id, "Ссылка устарела. Отправь её ещё раз.")
        return

    bot.answer_callback_query(call.id)
    status_msg = bot.send_message(chat_id, "⏳ Начинаю скачивание...")

    out_tmpl = f"downloads/{chat_id}_%(id)s.%(ext)s"
    os.makedirs("downloads", exist_ok=True)

    if call.data == "dl_audio":
        # Скачивание MP3
        cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", out_tmpl, url]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Поиск скачанного аудио
        audio_file = None
        for f in os.listdir("downloads"):
            if f.startswith(str(chat_id)) and f.endswith(".mp3"):
                audio_file = os.path.join("downloads", f)
                break

        if audio_file and os.path.exists(audio_file):
            bot.edit_message_text("📤 Отправляю аудио...", chat_id=chat_id, message_id=status_msg.message_id)
            with open(audio_file, "rb") as a:
                bot.send_audio(chat_id, a)
            os.remove(audio_file)
            bot.delete_message(chat_id, status_msg.message_id)
        else:
            bot.edit_message_text("❌ Не удалось извлечь аудио.", chat_id=chat_id, message_id=status_msg.message_id)

    elif call.data == "dl_video":
        # Скачивание видео
        cmd = ["yt-dlp", "-f", "best[ext=mp4]/best", "-o", out_tmpl, url]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        video_file = None
        for f in os.listdir("downloads"):
            if f.startswith(str(chat_id)) and not f.endswith(".mp3"):
                video_file = os.path.join("downloads", f)
                break

        if video_file and os.path.exists(video_file):
            file_size_mb = os.path.getsize(video_file) / (1024 * 1024)

            # Проверка размера файла и сжатие при необходимости
            if file_size_mb > 50:
                bot.edit_message_text("⚙️ Файл больше 50 МБ. Сжимаю видео через ffmpeg...", chat_id=chat_id, message_id=status_msg.message_id)
                compressed_file = f"downloads/compressed_{chat_id}.mp4"
                compress_video(video_file, compressed_file)
                os.remove(video_file)
                video_file = compressed_file

            bot.edit_message_text("📤 Отправляю видео...", chat_id=chat_id, message_id=status_msg.message_id)
            with open(video_file, "rb") as v:
                bot.send_video(chat_id, v)
            
            os.remove(video_file)
            bot.delete_message(chat_id, status_msg.message_id)
        else:
            bot.edit_message_text("❌ Не удалось скачать видео.", chat_id=chat_id, message_id=status_msg.message_id)

if __name__ == "__main__":
    bot.infinity_polling()
