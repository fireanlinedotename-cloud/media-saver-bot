import os
import re
import subprocess
import threading
import requests
import telebot
from http.server import HTTPServer, BaseHTTPRequestHandler
from telebot.types import (
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    BotCommand, 
    InlineQueryResultArticle, 
    InputTextMessageContent,
    InputMediaPhoto
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, threaded=True, num_threads=5)

LINKNI_URL = "https://telegram.me/linknibot/app?startapp=x_2z50t"
user_urls = {}

try:
    bot.set_my_commands([
        BotCommand("start", "🚀 Перезапустить бота"),
        BotCommand("donate", "☕ Поддержать проект")
    ])
except Exception:
    pass

# --- Сервер для Render ---
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
# -------------------------

def compress_video(input_path, output_path):
    """Сжатие видео через ffmpeg до размера < 50 МБ"""
    command = [
        "ffmpeg", "-y", "-i", input_path,
        "-b:v", "800k", "-maxrate", "1000k", "-bufsize", "1000k",
        "-vf", "scale=-2:720",
        "-c:a", "aac", "-b:a", "128k",
        output_path
    ]
    subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def get_tiktok_data(url):
    """Парсер TikTok с поддержкой видео, аудио и каруселей фото"""
    try:
        res_full = requests.get(url, allow_redirects=True, timeout=10)
        final_url = res_full.url
        res = requests.post("https://www.tikwm.com/api/", data={"url": final_url}, timeout=10).json()
        if res.get("code") == 0:
            data = res["data"]
            # Проверка на карусель (images)
            images = data.get("images", [])
            return {
                "type": "images" if images else "video",
                "images": images,
                "video": data.get("play"),
                "audio": data.get("music")
            }
    except Exception:
        pass
    return None

@bot.message_handler(commands=['start'])
def send_welcome(message):
    bot.reply_to(
        message, 
        "👋 **Привет! Я твой универсальный загрузчик.**\n\n"
        "Отправь мне ссылку на видео (TikTok, VK, YouTube), "
        "и я скачаю его, сконвертирую в MP3 или соберу карусель фото!\n\n"
        "💡 *Совет:* Меня можно вызывать прямо в любом чате: `@имя_бота ссылка`",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['donate'])
def send_donate(message):
    markup = InlineKeyboardMarkup()
    markup.add(InlineKeyboardButton("🎁 Поддержать автора", url=LINKNI_URL))
    bot.reply_to(
        message,
        "🤝 **Поддержка проекта**\n\n"
        "Если тебе нравится сервис, ты можете поддержать разработчика по кнопке ниже!",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# --- ИНЛАЙН-РЕЖИМ (@bot <ссылка>) ---
@bot.inline_handler(func=lambda query: len(query.query) > 0)
def query_text(inline_query):
    try:
        url_match = re.search(r'https?://[^\s]+', inline_query.query)
        if not url_match:
            return
            
        url = url_match.group(0)
        results = [
            InlineQueryResultArticle(
                id="1",
                title="🎬 Скачать Видео / Медиа",
                description=f"Отправить ссылку на обработку: {url}",
                input_message_content=InputTextMessageContent(url)
            )
        ]
        bot.answer_inline_query(inline_query.id, results)
    except Exception as e:
        print(f"Inline error: {e}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    urls = re.findall(r'https?://[^\s]+', message.text)
    if not urls:
        bot.reply_to(message, "Пожалуйста, отправь корректную ссылку на видео.")
        return

    url = urls[0]
    user_urls[message.chat.id] = url

    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("🎬 Видео / Фото", callback_data="dl_video"),
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
    status_msg = bot.send_message(chat_id, "⏳ Начинаю обработку...")

    # --- 1. TikTok (Карусели + Видео + MP3) ---
    if "tiktok.com" in url:
        tt_data = get_tiktok_data(url)
        if not tt_data:
            bot.edit_message_text("❌ Не удалось обработать ссылку TikTok.", chat_id=chat_id, message_id=status_msg.message_id)
            return

        bot.edit_message_text("📤 Отправляю...", chat_id=chat_id, message_id=status_msg.message_id)
        try:
            if call.data == "dl_video":
                if tt_data["type"] == "images":
                    # Карусель из нескольких фото
                    media_group = [InputMediaPhoto(img) for img in tt_data["images"][:10]]
                    bot.send_media_group(chat_id, media_group)
                else:
                    bot.send_video(chat_id, tt_data["video"])
            elif call.data == "dl_audio":
                if tt_data["audio"]:
                    bot.send_audio(chat_id, tt_data["audio"])
                else:
                    bot.send_message(chat_id, "❌ Не удалось извлечь аудио.")
            bot.delete_message(chat_id, status_msg.message_id)
        except Exception:
            bot.edit_message_text("❌ Ошибка при отправке TikTok.", chat_id=chat_id, message_id=status_msg.message_id)
        return

    # --- 2. YouTube, VK и прочее (yt-dlp + ffmpeg сжатие) ---
    os.makedirs("downloads", exist_ok=True)
    out_tmpl = f"downloads/{chat_id}_%(id)s.%(ext)s"

    if call.data == "dl_audio":
        cmd = ["yt-dlp", "-x", "--audio-format", "mp3", "-o", out_tmpl, url]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
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
        cmd = ["yt-dlp", "-f", "best[ext=mp4]/best", "-o", out_tmpl, url]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        video_file = None
        for f in os.listdir("downloads"):
            if f.startswith(str(chat_id)) and not f.endswith(".mp3"):
                video_file = os.path.join("downloads", f)
                break

        if video_file and os.path.exists(video_file):
            file_size_mb = os.path.getsize(video_file) / (1024 * 1024)

            # Авто-сжатие если видео больше 50 МБ
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
