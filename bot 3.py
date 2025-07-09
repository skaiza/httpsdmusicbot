import logging
import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaAudio
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters

# Вставь сюда свой Telegram токен и VK токен
TELEGRAM_BOT_TOKEN = "7992632683:AAE2G9wO4xgie9VR78HTqC3vJhz6jC7yWBw"
VK_ACCESS_TOKEN = "vk1.a.tzMx2tlo57QqgcnrGRwgnjro61_7b-DBLl-OiGkAaA3-oilgoM--s__zNbylUPuUz3-pxfAxvUjUm2e7745nLgsPdlWGNP4GcJ0vj2s3rr9CJxihPnoTrCCH5IPpcz6pPlYGruuwrcF0tM9vJdBLguhRbGNfVJ8m5wkVlNh3eso6L0GrUjdW9DCQincgk93pdm90MvB9peJBcLo2EbphvQ"  #

# Настройки
VK_API_VERSION = "5.131"
TRACKS_PER_PAGE = 10
COMMON_COVER_URL = "https://pin.it/1s5SZsO3R"
COMMON_TEXT = (
    "_via_ [https://t.me/httpsdmusicbot](https://t.me/httpsdmusicbot) / "
    "_httpsd.link_ [https://t.me/psdhttp](https://t.me/psdhttp)"
)

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

logger = logging.getLogger(__name__)

# Хранилище состояний (в памяти, для демо)
user_states = {}

def vk_audio_search(query, offset=0, count=TRACKS_PER_PAGE):
    url = "https://api.vk.com/method/audio.search"
    params = {
        "q": query,
        "count": count,
        "offset": offset,
        "access_token": VK_ACCESS_TOKEN,
        "v": VK_API_VERSION,
        "auto_complete": 1,
        "lyrics": 0
    }
    resp = requests.get(url, params=params)
    if resp.status_code != 200:
        logger.error(f"VK API error: {resp.status_code} {resp.text}")
        return None
    data = resp.json()
    if "error" in data:
        logger.error(f"VK API returned error: {data['error']}")
        return None
    return data["response"]

async def start(update, context):
    # Нет приветствия, игнорируем /start
    pass

async def search(update, context):
    user_id = update.message.from_user.id
    query = update.message.text.strip()
    # Сохраняем поисковый запрос и сбрасываем offset
    user_states[user_id] = {"query": query, "offset": 0}
    results = vk_audio_search(query, offset=0)
    if not results or results["count"] == 0:
        await update.message.reply_text("По запросу ничего не найдено.")
        return
    await send_track_list(update, context, user_id, results)

async def send_track_list(update, context, user_id, results):
    offset = user_states[user_id]["offset"]
    tracks = results.get("items", [])
    keyboard = []
    for i, track in enumerate(tracks):
        # Кнопки с названием трека и исполнителем
        title = track.get("title", "Без названия")
        artist = track.get("artist", "")
        button_text = f"{title} — {artist}" if artist else title
        callback_data = f"track_{offset + i}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=callback_data)])

    # Навигация
    nav_buttons = []
    if offset > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ Назад", callback_data="prev"))
    if offset + TRACKS_PER_PAGE < results["count"]:
        nav_buttons.append(InlineKeyboardButton("▶️ Вперед", callback_data="next"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Отправляем сообщение с кнопками (но без обложки)
    if update.message:
        await update.message.reply_text("Выберите трек:", reply_markup=reply_markup)
    else:
        # В случае CallbackQuery — редактируем сообщение
        await update.callback_query.edit_message_text("Выберите трек:", reply_markup=reply_markup)

async def button_handler(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data

    # Обрабатываем навигацию
    if data == "next":
        user_states[user_id]["offset"] += TRACKS_PER_PAGE
    elif data == "prev":
        user_states[user_id]["offset"] = max(0, user_states[user_id]["offset"] - TRACKS_PER_PAGE)
    elif data.startswith("track_"):
        # Отправляем mp3 с единой обложкой и текстом
        index = int(data.split("_")[1])
        user_query = user_states[user_id]["query"]
        results = vk_audio_search(user_query, offset=(index // TRACKS_PER_PAGE)*TRACKS_PER_PAGE)
        if not results or results["count"] == 0:
            await query.answer("Ошибка при получении трека.")
            return
        track_index = index % TRACKS_PER_PAGE
        try:
            track = results["items"][track_index]
            audio_url = track.get("url")
            if not audio_url:
                await query.answer("URL аудио не найден.")
                return
            caption = COMMON_TEXT
            # Отправляем аудио с обложкой и подписью
            await context.bot.send_audio(
                chat_id=query.message.chat_id,
                audio=audio_url,
                thumb=COMMON_COVER_URL,
                caption=caption,
                parse_mode="Markdown"
            )
            await query.answer()
        except Exception as e:
            logger.error(f"Ошибка отправки аудио: {e}")
            await query.answer("Ошибка при отправке аудио.")
        return

    # Обновляем список треков при навигации
    user_query = user_states[user_id]["query"]
    offset = user_states[user_id]["offset"]
    results = vk_audio_search(user_query, offset=offset)
    if not results:
        await query.answer("Ошибка получения списка треков.")
        return
    await send_track_list(update, context, user_id, results)
    await query.answer()

async def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, search))
    application.add_handler(CallbackQueryHandler(button_handler))

    await application.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())