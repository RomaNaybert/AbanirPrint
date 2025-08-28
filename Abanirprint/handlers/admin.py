from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from config import ADMINS
from services.statistics import load_stats
from datetime import datetime
# utils/admin_only.py
from functools import wraps
from aiogram.types import Message, CallbackQuery
from config import ADMINS

router = Router()
admin_message_cache = {}

async def cleanup_admin_messages(user_id: int, bot, chat_id: int):
    msgs = admin_message_cache.get(user_id, {})
    for msg_id in msgs.get("user_msgs", []):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass
    for msg_id in msgs.get("bot_msgs", []):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=msg_id)
        except:
            pass
    admin_message_cache[user_id] = {"user_msgs": [], "bot_msgs": []}

admin_reply_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 История заказов")],
        [KeyboardButton(text="📈 Статистика"), KeyboardButton(text="📟 Статус аппарата")],
        [KeyboardButton(text="📋 Очередь печати")],
        [KeyboardButton(text="🖨 Выбрать принтер")],
        [KeyboardButton(text="↩️ Выйти из админ-режима")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите раздел"
)

def admin_only(func):
    @wraps(func)
    async def wrapper(event, *args, **kwargs):
        user_id = event.from_user.id
        username = event.from_user.username or "без username"
        full_name = event.from_user.full_name

        # доступ запрещён
        if user_id not in ADMINS:
            if isinstance(event, Message):
                await event.answer("⛔ Доступ запрещён.")
                text_attempt = event.text
            elif isinstance(event, CallbackQuery):
                await event.answer("⛔ Доступ запрещён.", show_alert=True)
                text_attempt = event.data
            else:
                text_attempt = "неизвестный тип запроса"

            # уведомим всех админов (кроме того, кто пытался)
            notify_text = (
                f"🚨 <b>Попытка несанкционированного доступа</b>\n\n"
                f"🧑‍💻 Пользователь: <code>{user_id}</code>\n"
                f"👤 Имя: {full_name}\n"
                f"🔗 Username: @{username}\n"
                f"🗂 Действие: <code>{text_attempt}</code>"
            )

            for admin_id in ADMINS:
                if admin_id != user_id:
                    try:
                        await event.bot.send_message(admin_id, notify_text, parse_mode="HTML")
                    except Exception as e:
                        print(f"[admin_only] ❌ Не удалось уведомить админа {admin_id}: {e}")

            return  # блокируем выполнение
        return await func(event, *args, **kwargs)
    return wrapper

import win32print

def get_all_jobs():
    try:
        p = win32print.OpenPrinter(win32print.GetDefaultPrinter())
        jobs = win32print.EnumJobs(p, 0, 99, 1)
        win32print.ClosePrinter(p)
        return jobs
    except Exception as e:
        print(f"[get_all_jobs] ❌ Ошибка: {e}")
        return []

def cancel_job_by_index(index: int) -> bool:
    try:
        jobs = get_all_jobs()
        if index <= 0 or index > len(jobs):
            return False
        job = jobs[index - 1]
        p = win32print.OpenPrinter(win32print.GetDefaultPrinter())
        win32print.SetJob(p, job["JobId"], 0, None, win32print.JOB_CONTROL_DELETE)
        win32print.ClosePrinter(p)
        return True
    except Exception as e:
        print(f"[cancel_job_by_index] ❌ Ошибка: {e}")
        return False

def restart_job_by_index(index: int) -> bool:
    try:
        jobs = get_all_jobs()
        if index <= 0 or index > len(jobs):
            return False
        job = jobs[index - 1]
        p = win32print.OpenPrinter(win32print.GetDefaultPrinter())
        win32print.SetJob(p, job["JobId"], 0, None, win32print.JOB_CONTROL_RESTART)
        win32print.ClosePrinter(p)
        return True
    except Exception as e:
        print(f"[restart_job_by_index] ❌ Ошибка: {e}")
        return False


from aiogram.types import Message
from services.status_checker import get_printer_status, get_print_queue

@router.message(F.text == "📋 Очередь печати")
@admin_only
async def show_print_queue(message: Message):
    from services.status_checker import get_print_queue
    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

    queue = get_print_queue()
    if not queue:
        msg = await message.answer("📭 Очередь пуста.")
        admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}
        return

    text = "<b>📋 Очередь печати:</b>\n\n"
    kb = InlineKeyboardMarkup(inline_keyboard=[])

    for idx, job in enumerate(queue, start=1):
        text += (
            f"📝 Задание #{idx}\n"
            f"• Документ: <code>{job['doc']}</code>\n"
            f"• Отправил: <code>{job['submitted_by']}</code>\n"
            f"• Статус: <b>{job['status']}</b>\n\n"
        )
        kb.inline_keyboard.append([
            InlineKeyboardButton(text=f"❌ Отменить #{idx}", callback_data=f"cancel_job_{idx}"),
            InlineKeyboardButton(text=f"🔄 Повтор #{idx}", callback_data=f"restart_job_{idx}")
        ])

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="↩️ Назад в меню", callback_data="stats_main_menu")
    ])

    msg = await message.answer(text, reply_markup=kb, parse_mode="HTML")
    admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}

@router.callback_query(F.data.startswith("cancel_job_"))
@admin_only
async def cancel_print_job(callback: CallbackQuery):
    job_idx = int(callback.data.replace("cancel_job_", ""))

    success = cancel_job_by_index(job_idx)
    msg_text = f"✅ Задание #{job_idx} отменено." if success else f"❌ Не удалось отменить задание #{job_idx}"
    await callback.answer(msg_text, show_alert=True)

@router.callback_query(F.data.startswith("restart_job_"))
@admin_only
async def restart_print_job(callback: CallbackQuery):
    job_idx = int(callback.data.replace("restart_job_", ""))

    success = restart_job_by_index(job_idx)
    msg_text = f"🔄 Задание #{job_idx} повторно отправлено." if success else f"❌ Не удалось перезапустить задание #{job_idx}"
    await callback.answer(msg_text, show_alert=True)



@router.message(F.text == "📟 Статус аппарата")
@admin_only
async def show_device_status(message: Message):
    await cleanup_admin_messages(message.from_user.id, message.bot, message.chat.id)
    await message.delete()

    try:
        status = get_printer_status()
        # ✅ правильный способ проверить
        if status is None:
            msg = await message.answer("❌ Принтер не найден. Убедись, что он включён и имя указан правильно.")
            admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}
            return

        queue = get_print_queue()
    except Exception as e:
        msg = await message.answer(f"❌ Ошибка получения статуса принтера:\n<code>{e}</code>", parse_mode="HTML")
        admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}
        return

    # 👇 Безопасно продолжаем
    status = get_printer_status()
    if not status:
        msg = await message.answer("❌ Принтер не найден. Убедись, что он включён и имя указан правильно.")
        admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}
        return

    queue = get_print_queue()
    online_status = "🟢 <b>Онлайн</b>" if status["online"] else "🔴 <b>Оффлайн</b>"
    last_activity = datetime.now().strftime("%d.%m.%Y %H:%M")
    error_value = status.get("error", "Неизвестно")
    if error_value not in ["Ошибок нет", "Неизвестно"]:
        error_text = f"⚠️ <b>{error_value}</b>"
    else:
        error_text = "✅ Ошибок нет"

    # Обработка очереди
    queue_count = len(queue)
    queue_text = "\n".join([f"• {j['doc']} ({j['submitted_by']})" for j in queue]) if queue else "Очередь пуста"

    text = (
        f"📟 <b>Статус аппарата</b>\n\n"
        f"📡 Принтер: {status['name']}\n"
        f"🌐 Статус: {online_status}\n"
        f"🕓 Последняя активность: <i>{last_activity}</i>\n\n"
        f"{error_text}\n\n"
        f"📥 <b>Очередь заданий ({queue_count}):</b>\n{queue_text}"
    )

    msg = await message.answer(text, parse_mode="HTML", reply_markup=admin_reply_keyboard)
    admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}

from keyboards import get_main_reply_keyboard  # если у тебя есть клавиатура пользователя

@router.message(F.text == "↩️ Выйти из админ-режима")
@admin_only
async def exit_admin_mode(message: Message):
    await cleanup_admin_messages(message.from_user.id, message.bot, message.chat.id)
    await message.delete()
    msg = await message.answer(
        "📦 Вы вышли из админ-режима.",
        reply_markup=get_main_reply_keyboard(message.from_user.id)
    )
    admin_message_cache[message.from_user.id]["bot_msgs"].append(msg.message_id)

@router.message(F.text == "👨‍💻 Админ-режим")
@admin_only
async def admin_mode(message: Message):
    await cleanup_admin_messages(message.from_user.id, message.bot, message.chat.id)
    await message.delete()

    if message.from_user.id not in ADMINS:
        msg = await message.answer("⛔ Доступ запрещён.")
        admin_message_cache[message.from_user.id]["bot_msgs"] = [msg.message_id]
        return

    from services.history_logger import safe_load_history
    try:
        stats = load_stats()
        orders = safe_load_history()
    except Exception as e:
        msg = await message.answer(f"⚠ Не удалось загрузить статистику.\nОшибка: {e}")
        admin_message_cache[message.from_user.id]["bot_msgs"] = [msg.message_id]
        return

    total_orders = len(orders)
    total_revenue = sum(order.get("details", {}).get("cost", 0) for order in orders)
    last_activity = stats.get("last_activity")
    last_activity_str = datetime.fromisoformat(last_activity).strftime("%d.%m.%Y %H:%M") if last_activity else "нет данных"

    msg = await message.answer(
        f"👨‍💻 <b>Вы вошли в админ-режим</b>\n\n"
        f"📊 <b>Быстрая статистика:</b>\n"
        f"• Всего заказов: <b>{total_orders}</b>\n"
        f"• Общая выручка: <b>{total_revenue} ₽</b>\n"
        f"• Последняя активность: <i>{last_activity_str}</i>\n\n"
        f"🔽 Выберите раздел ниже:",
        parse_mode="HTML",
        reply_markup=admin_reply_keyboard
    )
    admin_message_cache[message.from_user.id]["bot_msgs"] = [msg.message_id]


from services.history_logger import safe_load_history

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(F.text == "📂 История заказов")
@admin_only
async def show_history_choice(message: Message):
    await cleanup_admin_messages(message.from_user.id, message.bot, message.chat.id)
    await message.delete()

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📄 1 заказ", callback_data="history_1"),
            InlineKeyboardButton(text="📄 3 заказа", callback_data="history_3"),
            InlineKeyboardButton(text="📄 6 заказов", callback_data="history_6"),
        ],
        [InlineKeyboardButton(text="📁 Все заказы (JSON)", callback_data="history_json"),],
        [
            InlineKeyboardButton(text="🔙 Назад в меню", callback_data="stats_main_menu")
        ]
    ])

    msg = await message.answer(
        "📂 Сколько последних заказов показать?",
        reply_markup=kb
    )
    admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}



from aiogram.types import CallbackQuery

@router.callback_query(F.data == "history_json")
@admin_only
async def send_history_json(callback: CallbackQuery):
    from aiogram.types import FSInputFile
    import os

    path = "data/history.json"
    if not os.path.exists(path):
        await callback.message.answer("📭 История пуста.")
        return

    file = FSInputFile(path)
    await callback.message.answer_document(
        file,
        caption="📁 Полная история заказов в JSON-формате"
    )

@router.callback_query(F.data.startswith("history_"))
@admin_only
async def show_history_by_count(callback: CallbackQuery):
    await cleanup_admin_messages(callback.from_user.id, callback.bot, callback.message.chat.id)
    try:
        await callback.message.delete()
    except:
        pass

    count = int(callback.data.replace("history_", ""))
    history = safe_load_history()
    if not history:
        msg = await callback.message.answer("📭 История пуста.", reply_markup=admin_reply_keyboard)
        admin_message_cache[callback.from_user.id] = {"bot_msgs": [msg.message_id]}
        return

    entries = reversed(history[-count:])
    text = f"<b>📂 Последние {count} заказ(ов):</b>\n\n"
    for entry in entries:
        text += f"🕓 <i>{entry['datetime']}</i>\n"
        text += f"👤 ID: <code>{entry['user_id']}</code>\n"
        text += f"📌 Действие: <b>{entry['action']}</b>\n"
        for key, value in entry["details"].items():
            text += f"  • {key}: {value}\n"
        text += "\n"

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Назад", callback_data="stats_main_menu")
    ]])

    msg = await callback.message.answer(text, parse_mode="HTML", reply_markup=kb)
    admin_message_cache[callback.from_user.id] = {"bot_msgs": [msg.message_id]}


from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(F.text == "📈 Статистика")
@admin_only
async def show_statistics(message: Message):
    await message.delete()
    await show_statistics_core(message.from_user.id, message.bot, message.chat.id)

    history = safe_load_history()
    if not history:
        msg = await message.answer("📭 Нет данных о заказах", reply_markup=admin_reply_keyboard)
        admin_message_cache[message.from_user.id]["bot_msgs"] = [msg.message_id]
        return

    # 🧠 Статистика по категориям
    stats = {
        "print": 0,
        "scan": 0,
        "scan_and_print": 0,
    }
    total_pages_printed = 0
    total_pages_scanned = 0
    total_revenue = 0

    for entry in history:
        action = entry.get("action")
        stats[action] = stats.get(action, 0) + 1

        details = entry.get("details", {})
        total_revenue += details.get("cost", 0)

        if action in ["print"]:
            total_pages_printed += details.get("pages", 0) * details.get("copies", 1)
        if action in ["scan", "scan_and_print"]:
            total_pages_scanned += details.get("pages", 0)

    text = (
        f"<b>📈 Статистика за весь период:</b>\n\n"
        f"<b>📦 Количество заказов:</b>\n"
        f"• Печать: <b>{stats.get('print', 0)}</b>\n"
        f"• Сканирование: <b>{stats.get('scan', 0)}</b>\n"
        f"• Сканирование + печать: <b>{stats.get('scan_and_print', 0)}</b>\n\n"
        f"<b>💰 Общая выручка:</b> <u>{total_revenue} ₽</u>\n\n"
        f"<b>📃 Всего страниц:</b>\n"
        f"• Напечатано: <b>{total_pages_printed}</b>\n"
        f"• Отсканировано: <b>{total_pages_scanned}</b>"
    )

    # ⏱ Кнопки периода
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📅 День", callback_data="stats_day"),
            InlineKeyboardButton(text="📆 Неделя", callback_data="stats_week"),
            InlineKeyboardButton(text="🗓 Месяц", callback_data="stats_month"),
        ],
        [
            InlineKeyboardButton(text="🔙 Назад в меню", callback_data="stats_main_menu")
        ]
    ])

    admin_message_cache[message.from_user.id]["bot_msgs"] = [msg.message_id]

@router.callback_query(F.data == "stats_back")
@admin_only
async def back_to_stats_periods(callback):
    await callback.message.delete()
    await show_statistics_core(callback.from_user.id, callback.bot, callback.message.chat.id)

from datetime import datetime, timedelta

def filter_history_by_period(period: str) -> list:
    history = safe_load_history()
    now = datetime.now()

    def in_range(dt: datetime) -> bool:
        if period == "day":
            return dt.date() == now.date()
        elif period == "week":
            return dt >= now - timedelta(days=7)
        elif period == "month":
            return dt >= now - timedelta(days=30)
        elif period == "all":
            return True
        return False

    filtered = []
    for entry in history:
        try:
            dt = datetime.strptime(entry["datetime"], "%Y-%m-%d %H:%M:%S")
            if in_range(dt):
                filtered.append(entry)
        except:
            continue

    return filtered

@router.callback_query(F.data == "stats_main_menu")
@admin_only
async def stats_main_menu(callback):
    try:
        await callback.message.delete()
    except Exception as e:
        print(f"[stats_main_menu] ❌ Не удалось удалить сообщение: {e}")

    msg = await callback.message.answer(
        "🔧 Вернулись в админ-меню:",
        reply_markup=admin_reply_keyboard
    )
    admin_message_cache[callback.from_user.id] = {"bot_msgs": [msg.message_id]}

async def show_statistics_core(user_id: int, bot, chat_id: int):
    await cleanup_admin_messages(user_id, bot, chat_id)

    history = safe_load_history()
    if not history:
        msg = await bot.send_message(chat_id, "📭 Нет данных о заказах", reply_markup=admin_reply_keyboard)
        admin_message_cache[user_id] = {"bot_msgs": [msg.message_id]}
        return

    stats = {"print": 0, "scan": 0, "scan_and_print": 0}
    total_pages_printed = 0
    total_pages_scanned = 0
    total_revenue = 0

    for entry in history:
        action = entry.get("action")
        stats[action] = stats.get(action, 0) + 1
        details = entry.get("details", {})
        total_revenue += details.get("cost", 0)
        if action == "print":
            total_pages_printed += details.get("pages", 0) * details.get("copies", 1)
        elif action in ("scan", "scan_and_print"):
            total_pages_scanned += details.get("pages", 0)

    text = (
        f"<b>📈 Статистика за весь период:</b>\n\n"
        f"<b>📦 Количество заказов:</b>\n"
        f"• Печать: <b>{stats.get('print', 0)}</b>\n"
        f"• Сканирование: <b>{stats.get('scan', 0)}</b>\n"
        f"• Сканирование + печать: <b>{stats.get('scan_and_print', 0)}</b>\n\n"
        f"<b>💰 Общая выручка:</b> <u>{total_revenue} ₽</u>\n\n"
        f"<b>📃 Всего страниц:</b>\n"
        f"• Напечатано: <b>{total_pages_printed}</b>\n"
        f"• Отсканировано: <b>{total_pages_scanned}</b>"
    )

    # 🎨 Построим круговую диаграмму
    import matplotlib.pyplot as plt

    labels = ["Печать", "Скан", "Скан + Печать"]
    values = [
        stats.get("print", 0),
        stats.get("scan", 0),
        stats.get("scan_and_print", 0)
    ]
    colors = ["#A0C4FF", "#B9FBC0", "#FFD6A5"]

    if sum(values) > 0:
        fig, ax = plt.subplots()
        ax.pie(values, labels=labels, colors=colors, autopct="%1.1f%%", startangle=90)
        ax.axis("equal")
        plt.title("Распределение заказов за всё время")
        plt.tight_layout()
        plt.savefig("stats_pie_all.png")
        plt.close()

        from aiogram.types import FSInputFile
        image = FSInputFile("stats_pie_all.png")

        msg = await bot.send_photo(
            chat_id,
            photo=image,
            caption=text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="📅 День", callback_data="stats_day"),
                    InlineKeyboardButton(text="📆 Неделя", callback_data="stats_week"),
                    InlineKeyboardButton(text="🗓 Месяц", callback_data="stats_month"),
                ],
                [InlineKeyboardButton(text="🔙 Назад в меню", callback_data="stats_main_menu")]
            ])
        )
    else:
        # если заказов нет, просто текст
        msg = await bot.send_message(chat_id, text, reply_markup=admin_reply_keyboard, parse_mode="HTML")

    admin_message_cache[user_id] = {"bot_msgs": [msg.message_id]}

@router.callback_query(F.data.startswith("stats_"))
@admin_only
async def show_stats_for_period(callback, state=None):
    await cleanup_admin_messages(callback.from_user.id, callback.bot, callback.message.chat.id)
    try:
        await callback.message.delete()
    except Exception as e:
        print(f"[show_stats_for_period] ❌ Не удалось удалить сообщение: {e}")

    period_key = callback.data.replace("stats_", "")
    period_titles = {
        "day": "сегодня",
        "week": "неделю",
        "month": "месяц",
        "all": "всё время"
    }
    title = period_titles.get(period_key, "период")

    history = filter_history_by_period(period_key)

    if not history:
        msg = await callback.message.answer(f"📭 Нет заказов за {title}", reply_markup=admin_reply_keyboard)
        admin_message_cache[callback.from_user.id] = {"bot_msgs": [msg.message_id]}
        return

    from collections import Counter

    stats = Counter(entry.get("action") for entry in history)
    total_revenue = sum(entry.get("details", {}).get("cost", 0) for entry in history)
    printed_pages = sum(entry.get("details", {}).get("pages", 0) * entry.get("details", {}).get("copies", 1)
                        for entry in history if entry["action"] == "print")
    scanned_pages = sum(entry.get("details", {}).get("pages", 0)
                        for entry in history if entry["action"] in ("scan", "scan_and_print"))
    unique_users = len(set(entry["user_id"] for entry in history))

    text = (
        f"<b>📊 Заказы за {title}:</b>\n\n"
        f"👤 Уникальных пользователей: <b>{unique_users}</b>\n"
        f"🧾 Всего заказов: <b>{len(history)}</b>\n"
        f"• Печать: <b>{stats.get('print', 0)}</b>\n"
        f"• Скан: <b>{stats.get('scan', 0)}</b>\n"
        f"• Скан + печать: <b>{stats.get('scan_and_print', 0)}</b>\n\n"
        f"📃 Страниц:\n"
        f"• Напечатано: <b>{printed_pages}</b>\n"
        f"• Отсканировано: <b>{scanned_pages}</b>\n\n"
        f"💰 Выручка: <b>{total_revenue} ₽</b>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="↩️ Назад к периодам", callback_data="stats_back")
    ]])

    from services.graph_generator import generate_stats_chart  # если вынесешь код в отдельный файл
    from aiogram.types import FSInputFile

    # если период — не "all", строим график


    if period_key in ("day", "week", "month"):
        chart_path = f"chart_{period_key}.png"
        generate_stats_chart(period_key, output_path=chart_path)
        image = FSInputFile(chart_path)

        msg = await callback.message.answer_photo(
            photo=image,
            caption=text,
            parse_mode="HTML",
            reply_markup=kb
        )
    else:
        msg = await callback.message.answer(
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

    admin_message_cache[callback.from_user.id] = {"bot_msgs": [msg.message_id]}

from aiogram.types import FSInputFile

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import wmi
from services.printer_config import save_printer_name

@router.message(F.text == "🖨 Выбрать принтер")
@admin_only
async def choose_printer(message: Message):
    c = wmi.WMI()
    printers = [p.Name for p in c.Win32_Printer()]
    if not printers:
        msg = await message.answer("❌ Принтеры не найдены.")
        admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"set_printer:{name}")]
            for name in printers
        ] + [[InlineKeyboardButton(text="↩️ Назад", callback_data="stats_main_menu")]]
    )

    msg = await message.answer("📋 Выберите принтер:", reply_markup=kb)
    admin_message_cache[message.from_user.id] = {"bot_msgs": [msg.message_id]}

@router.callback_query(F.data.startswith("set_printer:"))
@admin_only
async def set_selected_printer(callback: CallbackQuery):
    printer_name = callback.data.replace("set_printer:", "")
    save_printer_name(printer_name)

    await callback.message.delete()
    msg = await callback.message.answer(
        f"✅ Принтер <b>{printer_name}</b> выбран.",
        parse_mode="HTML",
        reply_markup=admin_reply_keyboard
    )
    admin_message_cache[callback.from_user.id] = {"bot_msgs": [msg.message_id]}

from functools import wraps
from aiogram.types import Message, CallbackQuery
from config import ADMINS

