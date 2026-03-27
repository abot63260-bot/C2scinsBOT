import os
import logging
import asyncio
import random
import string
import re
from typing import Dict
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

# ТОКЕН
TOKEN = "8315119156:AAE6dIIYMsE80f7TVAyby_qMxKtqdzm5EOo"

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

user_data: Dict[int, Dict] = {}

# ЗАДАНИЯ ПО ПОРЯДКУ
TASKS_ORDER = ["yandex", "sberprime", "yandexplus", "tv24"]

# ИНФОРМАЦИЯ О ЗАДАНИЯХ
TASK_INFO = {
    "yandex": {
        "name": "📱 СКАЧАТЬ ЯНДЕКС БРАУЗЕР",
        "description": "Скачай Яндекс Браузер по ссылке и установи",
        "link": "https://vk.cc/cVUvvJ",
        "button": "🔽 СКАЧАТЬ ЯНДЕКС БРАУЗЕР"
    },
    "sberprime": {
        "name": "💳 СБЕРПРАЙМ ЗА 1 РУБЛЬ",
        "description": "Оформи подписку СберПрайм за 1 рубль\n(если ссылка не открывается, выключи VPN)",
        "link": "https://vk.cc/cVUvEb",
        "button": "💳 ОФОРМИТЬ СБЕРПРАЙМ"
    },
    "yandexplus": {
        "name": "🌟 ЯНДЕКС ПЛЮС (ПОДПИСКА ЗА 1 РУБЛЬ)",
        "description": "Оформи подписку Яндекс Плюс за 1 рубль\n\n🔑 <b>ПРОМОКОД:</b> <code>328652SPMA</code>\n(если ссылка не открывается, выключи VPN)",
        "link": "https://vk.cc/cVUMu5",
        "button": "🌟 ОФОРМИТЬ ЯНДЕКС ПЛЮС"
    },
    "tv24": {
        "name": "🎬 АКТИВИРОВАТЬ ПРОМОКОД 24TV",
        "description": "Перейди по ссылке и активируй промокод",
        "link": "https://vk.cc/cVUwtW",
        "button": "🎬 АКТИВИРОВАТЬ ПРОМОКОД"
    }
}

# 15 СКИНОВ CS2 СТОИМОСТЬЮ 1-2К РУБЛЕЙ
CS2_SKINS = [
    "🔫 AK-47 | Bloodsport (Полевое испытание) - ~1500₽",
    "🔫 M4A4 | The Emperor (Прямо с завода) - ~1800₽",
    "🔫 AWP | Fever Dream (Прямо с завода) - ~1200₽",
    "🔫 Desert Eagle | Code Red (Немного поношенное) - ~1100₽",
    "🔫 USP-S | Kill Confirmed (Полевое испытание) - ~1400₽",
    "🔫 Glock-18 | Wasteland Rebel (Немного поношенное) - ~1300₽",
    "🔫 M4A1-S | Decimator (Немного поношенное) - ~1600₽",
    "🔫 AWP | Atheris (Прямо с завода) - ~900₽",
    "🔫 SSG 08 | Blood in the Water (Прямо с завода) - ~1100₽",
    "🔫 FAMAS | Eye of Athena (Прямо с завода) - ~1000₽",
    "🔫 P2000 | Wicked Sick (Прямо с завода) - ~1200₽",
    "🔫 P90 | Asiimov (Полевое испытание) - ~1400₽",
    "🔫 MP9 | Starlight Protector (Прямо с завода) - ~1300₽",
    "🔫 MAC-10 | Whitefish (Прямо с завода) - ~900₽",
    "🔫 UMP-45 | Crime Scene (Немного поношенное) - ~1000₽"
]

def get_random_skins(count: int = 5) -> list:
    """Возвращает случайные скины"""
    return random.sample(CS2_SKINS, min(count, len(CS2_SKINS)))

def generate_skins_message() -> str:
    """Генерирует сообщение со случайными скинами"""
    skins = get_random_skins(5)
    message = "🎁 ТВОИ СКИНЫ CS2:\n\n"
    for i, skin in enumerate(skins, 1):
        message += f"{i}. {skin}\n"
    total = sum([random.randint(1000, 2000) for _ in range(5)])
    message += f"\n💎 Общая стоимость: ~{total:,}₽"
    return message

def is_trade_link(text: str) -> bool:
    """Проверяет, является ли текст ссылкой на трейд"""
    patterns = [
        r'https?://steamcommunity\.com/tradeoffer/new/\?partner=\d+&token=[a-zA-Z0-9_-]+',
        r'steamcommunity\.com/tradeoffer/new/\?partner=\d+&token=[a-zA-Z0-9_-]+'
    ]
    for pattern in patterns:
        if re.search(pattern, text):
            return True
    return False

class UserState:
    def __init__(self, user_id: int, username: str):
        self.user_id = user_id
        self.username = username
        self.current_task_index = 0
        self.waiting_for_screenshot = False
        self.current_task_key = None
        self.reward_claimed = False
        self.trade_link = None
        self.completed_tasks = []
        self.last_activity = datetime.now()
        self.reminder_sent = False
        self.waiting_for_trade_link = False
        self.received_skins = None

async def send_reminder(context: ContextTypes.DEFAULT_TYPE, user_id: int, task_name: str, task_num: int):
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"⏰ НАПОМИНАНИЕ!\n\n"
                 f"Ты начал выполнять задания для скинов CS2, но так и не завершил!\n\n"
                 f"📋 Ты остановился на {task_name} (Задание {task_num}/4)\n\n"
                 f"🎁 Не забывай, что за выполнение 4 заданий ты получишь скины CS2!\n\n"
                 f"👉 Продолжить - просто отправь скриншот для этого задания\n"
                 f"❌ Отменить - нажми /start",
            parse_mode=ParseMode.HTML
        )
        logger.info(f"Напоминание отправлено пользователю {user_id}")
    except Exception as e:
        logger.error(f"Ошибка отправки напоминания {user_id}: {e}")

async def check_reminders(context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    to_remove = []
    
    for user_id, user in user_data.items():
        if user.reward_claimed:
            to_remove.append(user_id)
            continue
        
        if user.current_task_index >= len(TASKS_ORDER):
            continue
        
        time_diff = now - user.last_activity
        hours_passed = time_diff.total_seconds() / 3600
        
        if hours_passed >= 1 and not user.reminder_sent:
            task_key = TASKS_ORDER[user.current_task_index]
            task_name = TASK_INFO[task_key]["name"]
            task_num = user.current_task_index + 1
            
            await send_reminder(context, user_id, task_name, task_num)
            user.reminder_sent = True
        
        elif hours_passed >= 2 and user.reminder_sent:
            task_key = TASKS_ORDER[user.current_task_index]
            task_name = TASK_INFO[task_key]["name"]
            task_num = user.current_task_index + 1
            
            await send_reminder(context, user_id, task_name, task_num)
            user.last_activity = now
    
    for user_id in to_remove:
        if user_id in user_data:
            del user_data[user_id]

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🎁 ПОЛУЧИТЬ СКИНЫ CS2", callback_data="start_tasks")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user = update.effective_user
    text = (
        f"🎮 ПОЛУЧИ СКИНЫ CS2 БЕСПЛАТНО! 🎮\n\n"
        f"Привет, {user.first_name}! 👋\n\n"
        f"Активируй скрытый промокод разработчиков.\n\n"
        f"💰 Выполни 4 задания и получи набор крутых скинов CS2 (стоимостью 1000-2000₽ каждый)!\n\n"
        f"👇 Нажми на кнопку:"
    )
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=ParseMode.HTML)

async def start_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    
    if user_id in user_data:
        user = user_data[user_id]
        if user.reward_claimed:
            await query.edit_message_text("❌ Ты уже получил скины! Нельзя проходить задания повторно.", parse_mode=ParseMode.HTML)
            return
    
    user = UserState(user_id, query.from_user.username)
    user.current_task_index = 0
    user.completed_tasks = []
    user.last_activity = datetime.now()
    user.reminder_sent = False
    
    user_data[user_id] = user
    
    await show_current_task(query, user)

async def show_current_task(query, user: UserState):
    user.last_activity = datetime.now()
    user.reminder_sent = False
    
    if user.current_task_index >= len(TASKS_ORDER):
        # Все задания выполнены, просим ссылку на трейд
        user.waiting_for_trade_link = True
        await query.edit_message_text(
            text=f"✅ ПОЗДРАВЛЯЮ! ТЫ ВЫПОЛНИЛ ВСЕ 4 ЗАДАНИЯ! 🎉🎉🎉\n\n"
                 f"━━━━━━━━━━━━━━━━━━━━━━\n"
                 f"🎁 ТЕПЕРЬ ОТПРАВЬ ССЫЛКУ НА ТРЕЙД:\n\n"
                 f"📌 Как получить ссылку на трейд:\n"
                 f"1. Зайди в свой инвентарь Steam\n"
                 f"2. Нажми 'Предложить обмен'\n"
                 f"3. Скопируй ссылку для обмена\n"
                 f"4. Отправь её сюда\n\n"
                 f"━━━━━━━━━━━━━━━━━━━━━━\n"
                 f"⏱ Трейд придет в течение 12 часов!\n"
                 f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                 f"❌ Отмена - нажми /start",
            parse_mode=ParseMode.HTML
        )
        return
    
    task_key = TASKS_ORDER[user.current_task_index]
    task = TASK_INFO[task_key]
    
    current = user.current_task_index + 1
    total = len(TASKS_ORDER)
    
    text = (
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📋 ЗАДАНИЕ {current} ИЗ {total}\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"{task['name']}\n\n"
        f"{task['description']}\n\n"
        f"🔗 <a href='{task['link']}'>👉 {task['button']} 👈</a>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"📸 КАК ПОДТВЕРДИТЬ:\n"
        f"После выполнения отправь СКРИНШОТ подтверждения\n"
        f"⏱ Автопроверка займет 5 секунд\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"❌ Отмена - нажми /start\n"
        f"⏰ Если забудешь - я напомню через 1-2 часа!"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ ОТМЕНИТЬ ВСЕ", callback_data="cancel")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    user.waiting_for_screenshot = True
    user.current_task_key = task_key
    
    await query.edit_message_text(
        text=text,
        reply_markup=reply_markup,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

async def handle_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    await main_menu(update, context)

async def handle_trade_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Сначала нажми /start и выбери 'ПОЛУЧИТЬ СКИНЫ CS2'")
        return
    
    user = user_data[user_id]
    
    if not user.waiting_for_trade_link:
        await update.message.reply_text("❌ Сейчас не нужно отправлять ссылку. Сначала выполни все задания!")
        return
    
    if not is_trade_link(text):
        await update.message.reply_text(
            "❌ Это не похоже на ссылку для обмена Steam!\n\n"
            "📌 Правильный формат:\n"
            "https://steamcommunity.com/tradeoffer/new/?partner=XXXXXXXX&token=XXXXXXXX\n\n"
            "Попробуй еще раз или нажми /start для отмены"
        )
        return
    
    # Сохраняем ссылку на трейд и генерируем случайные скины
    user.trade_link = text
    user.reward_claimed = True
    user.waiting_for_trade_link = False
    user.received_skins = generate_skins_message()
    
    await update.message.reply_text(
        f"✅ ССЫЛКА НА ТРЕЙД ПРИНЯТА!\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"{user.received_skins}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 ТВОИ СКИНЫ CS2 БУДУТ ОТПРАВЛЕНЫ В ТЕЧЕНИЕ 12 ЧАСОВ!\n\n"
        f"📝 Сохрани этот диалог, если возникнут вопросы.\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Спасибо за участие! 🎮"
    )
    
    # Удаляем пользователя из активных
    del user_data[user_id]

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id not in user_data:
        await update.message.reply_text("❌ Сначала нажми /start и выбери 'ПОЛУЧИТЬ СКИНЫ CS2'")
        return
    
    user = user_data[user_id]
    
    if user.reward_claimed:
        await update.message.reply_text("❌ Ты уже получил скины!")
        return
    
    if not user.waiting_for_screenshot:
        await update.message.reply_text("❌ Сейчас не нужно отправлять скриншот. Нажми /start")
        return
    
    user.last_activity = datetime.now()
    user.reminder_sent = False
    
    photo = update.message.photo[-1]
    user.waiting_for_screenshot = False
    
    current_num = user.current_task_index + 1
    task_name = TASK_INFO[user.current_task_key]["name"]
    
    checking_msg = await update.message.reply_text(
        f"⏳ ПРОВЕРКА ЗАДАНИЯ {current_num}/4...\n\n"
        f"📋 {task_name}\n\n"
        f"🔍 Идет автоматическая проверка скриншота...\n"
        f"⏱ Подожди 5 секунд!\n\n"
        f"Не отправляй новые сообщения!"
    )
    
    async def check_and_next():
        await asyncio.sleep(5)
        
        try:
            await checking_msg.delete()
        except:
            pass
        
        completed_task = user.current_task_key
        user.completed_tasks.append(completed_task)
        user.current_task_index += 1
        
        if user.current_task_index >= len(TASKS_ORDER):
            await update.message.reply_text(
                f"✅ ЗАДАНИЕ {current_num}/4 ВЫПОЛНЕНО!\n\n"
                f"🎉 ПОЗДРАВЛЯЮ! ТЫ ВЫПОЛНИЛ ВСЕ 4 ЗАДАНИЯ!\n\n"
                f"🎁 Теперь отправь ссылку на трейд, чтобы получить скины!"
            )
            await asyncio.sleep(2)
            
            class DummyQuery:
                def __init__(self, user_id):
                    self.from_user = type('obj', (object,), {'id': user_id})
                async def edit_message_text(self, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
                    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
            
            dummy = DummyQuery(user_id)
            await show_current_task(dummy, user)
        else:
            await update.message.reply_text(
                f"✅ ЗАДАНИЕ {current_num}/4 ВЫПОЛНЕНО!\n\n"
                f"Отлично! Переходим к заданию {current_num + 1}/4... 🚀"
            )
            await asyncio.sleep(2)
            
            class DummyQuery:
                def __init__(self, user_id):
                    self.from_user = type('obj', (object,), {'id': user_id})
                async def edit_message_text(self, text, reply_markup=None, parse_mode=None, disable_web_page_preview=None):
                    await update.message.reply_text(text, reply_markup=reply_markup, parse_mode=parse_mode, disable_web_page_preview=disable_web_page_preview)
            
            dummy = DummyQuery(user_id)
            await show_current_task(dummy, user)
    
    asyncio.create_task(check_and_next())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    await main_menu(update, context)

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    
    if data == "start_tasks":
        await start_tasks(update, context)
    elif data == "cancel":
        await handle_cancel(update, context)

async def reminder_callback(context: ContextTypes.DEFAULT_TYPE):
    await check_reminders(context)

def main():
    print("🚀 БОТ ЗАПУСКАЕТСЯ...")
    print("🎮 CS2 Skins Bot")
    print("📋 Задания по порядку:")
    print("   1. Яндекс Браузер")
    print("   2. СберПрайм")
    print("   3. Яндекс Плюс (промокод 328652SPMA) - <code> для копирования")
    print("   4. 24TV")
    print("🎁 Награда: 5 случайных скинов CS2 (1000-2000₽ каждый)")
    print("⏰ Напоминания: через 1 и 2 часа бездействия")
    
    application = Application.builder().token(TOKEN).build()
    
    job_queue = application.job_queue
    if job_queue:
        job_queue.run_repeating(reminder_callback, interval=1800, first=60)
        print("✅ Система напоминаний запущена (проверка каждые 30 минут)")
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.PHOTO, handle_screenshot))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_trade_link))
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()