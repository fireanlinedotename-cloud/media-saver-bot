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

    if "tiktok.com" in url:
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
