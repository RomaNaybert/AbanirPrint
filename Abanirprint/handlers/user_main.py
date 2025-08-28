from aiogram import Router, F
from aiogram.types import Message
from aiogram.enums.parse_mode import ParseMode
import asyncio
from aiogram.filters import CommandStart
from keyboards import get_main_reply_keyboard, copy_selector, back_to_menu_button, confirm_keyboard
from config import UPLOAD_DIR, MAX_PHOTOS, MAX_PDF_MB, ALLOWED_IMAGE_TYPES
from services.price_calc import calculate_price
from services.print_manager import print_and_wait
import os
from PyPDF2 import PdfReader
from aiogram.types import CallbackQuery
from aiogram.types import FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter
from keyboards import get_main_reply_keyboard

class PrintStates(StatesGroup):
    await_copies = State()

router = Router()
welcome_message_id = {}  # для хранения id сообщения на удаление
user_print_queue = {}

@router.callback_query(F.data == "back_to_menu")
async def return_to_main(callback: CallbackQuery):
    # Удаляем предыдущее меню (если есть)
    data = welcome_message_id.get(callback.from_user.id)
    if data:
        try:
            if isinstance(data, dict):
                if data.get("menu_msg_id"):
                    await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=data["menu_msg_id"])
                if data.get("user_msg_id"):
                    await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=data["user_msg_id"])
                if data.get("user_file_msg_id"):
                    await callback.bot.delete_message(chat_id=callback.message.chat.id,
                                                      message_id=data["user_file_msg_id"])
            elif isinstance(data, int):
                await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=data)
        except Exception as e:
            print("[DEBUG] Не удалось удалить сообщение:", e)

    # Удаляем само callback-сообщение
    try:
        await callback.message.delete()
    except:
        pass

    # Удаляем файл, если он есть
    data = welcome_message_id.get(callback.from_user.id)

    if data and isinstance(data, dict):
        for mid in data.get("photo_message_ids", []):
            try:
                await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=mid)
            except Exception as e:
                print("[back_to_menu] Не удалось удалить фото:", e)

    if data and isinstance(data, dict):
        file_msg_id = data.get("user_file_msg_id")
        if file_msg_id:
            try:
                await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=file_msg_id)
            except Exception as e:
                print("[DEBUG] Не удалось удалить сообщение с файлом:", e)

    # Показываем новое меню
    msg = await callback.message.answer(
        "👇 Выберите действие:",
        reply_markup=get_main_reply_keyboard(callback.from_user.id)
    )
    welcome_message_id[callback.from_user.id] = {
        "menu_msg_id": msg.message_id
    }

    await callback.answer()

@router.message(CommandStart())
async def cmd_start(message: Message):
    photo = FSInputFile("C:\\Program Files\\JetBrains\\AbanirPrint\\images\\WelcomeImage.png")

    msg1 = await message.answer_photo(
        photo=photo,
        caption=(
            "👋 *Добро пожаловать в Abanir\\.Print\\!*\n\n"
            "Я — ваш цифровой помощник для ✨ *печати* и *сканирования* прямо в Telegram\\.\n\n"
            "📄 Что я умею:\n"
            "• *Печатать* PDF\\-документы и изображения\n"
            "• *Сканировать* бумажные документы и отправлять их вам\n"
            "• *Рассчитывать стоимость* и принимать оплату через СБП\n\n"
            "_Быстро\\. Удобно\\. Качественно\\._"
        ),
        parse_mode=ParseMode.MARKDOWN_V2
    )

    msg2 = await message.answer(
        "👇 *Выберите действие ниже:*",
        reply_markup=get_main_reply_keyboard(message.from_user.id),
        parse_mode=ParseMode.MARKDOWN_V2
    )

    welcome_message_id[message.from_user.id] = {
        "menu_msg_id": msg2.message_id,
        "user_msg_id": message.message_id
    }

from aiogram.types import FSInputFile

@router.message(F.text == "💰 Прайс")
async def show_price(message: Message):
    from handlers.user_main import _remove_last_menu, welcome_message_id

    # 🧹 Удаляем предыдущее меню "👇 Выберите действие:"
    try:
        msg_id = welcome_message_id.get(message.from_user.id)
        if msg_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
    except:
        pass

    await _remove_last_menu(message)
    await _remove_last_menu(message)
    # Маскируем сообщение пользователя
    try:
        await message.edit_text("‎")  # Невидимый символ
    except:
        try:
            await message.delete()
        except:
            pass

    # Сохраняем ID сообщения пользователя
    welcome_message_id[message.from_user.id] = {
        "menu_msg_id": None,
        "user_msg_id": message.message_id  # 👈 сохраняем сообщение "Прайс"
    }

    image = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\PriceList.png")

    sent_msg = await message.answer_photo(
        photo=image,
        caption=(
            "<b>💰 Стоимость услуг:</b>\n\n"
            "🖨 <b>Печать</b> ч/б, односторонняя — <b>5 ₽</b>/стр.\n"
            "📷 <b>Скан</b> в Telegram — <b>10 ₽</b>/стр.\n"
            "🖨 <b>Скан + печать</b> — <b>15 ₽</b>/стр."
        ),
        reply_markup=back_to_menu_button,
        parse_mode="HTML"
    )

    # Сохраняем сообщение с фото
    welcome_message_id[message.from_user.id]["menu_msg_id"] = sent_msg.message_id

from aiogram.enums import ParseMode

@router.message(F.text == "🖨️ Печать")
async def ask_file(message: Message):
    from handlers.user_main import _remove_last_menu, welcome_message_id

    # 🧹 Удаляем предыдущее меню "👇 Выберите действие:"
    try:
        msg_id = welcome_message_id.get(message.from_user.id)
        if msg_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
    except:
        pass

    await _remove_last_menu(message)
    await _remove_last_menu(message)
    # Маскируем сообщение пользователя
    try:
        await message.edit_text("‎")
    except:
        try:
            await message.delete()
        except:
            pass

    await _remove_last_menu(message)

    photo = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\SendFileImage.png")

    sent = await message.bot.send_photo(
        chat_id=message.chat.id,
        photo=photo,
        caption=(
            "<b>📎 Отправьте файл для печати:</b>\n\n"
            "• <b>PDF</b> до <u><i>20МБ</i></u>\n"
            "• <b>Фото</b> до <u><i>10 изображений</i></u> за раз\n\n"
            "<i>Другие типы файлов пока не поддерживаются</i>"
        ),
        reply_markup=back_to_menu_button,
        parse_mode=ParseMode.HTML
    )

    if not welcome_message_id.get(message.from_user.id):
        welcome_message_id[message.from_user.id] = {}

    welcome_message_id[message.from_user.id]["menu_msg_id"] = sent.message_id

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

@router.message(F.document)
async def handle_file(message: Message, state: FSMContext):
    file: Document = message.document
    file_ext = os.path.splitext(file.file_name)[1].lower()

    # Проверка формата
    if file_ext != ".pdf":
        image = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\UnsupportedErrorImage.png")  # укажи путь к своей картинке
        await message.answer_photo(
            photo=image,
            caption=(
                "❌ <b>Формат не поддерживается</b>\n\n"
                "📎 Можно отправлять только\n"
                " <b>PDF</b> (до 20МБ)\n\n"
                "<i>Попробуйте снова с подходящим форматом</i>"
            ),
            parse_mode=ParseMode.HTML
        )
        return

    # Проверка размера PDF
    if file.file_size > MAX_PDF_MB * 1024 * 1024:
        image = FSInputFile("C:\Program Files\JetBrains\AbanirPrint\images\SizeErrorImage.png")  # укажи путь к файлу изображения
        await message.answer_photo(
            photo=image,
            caption=f"❌ Файл слишком большой.\n\n📄 Максимальный размер PDF:\n<b>{MAX_PDF_MB} МБ</b>\n\n<i>Попробуйте снова с файлом PDF до 20Мб</i>",
            parse_mode=ParseMode.HTML
        )
        return

    # Всё ок — сохраняем файл
    file_path = os.path.join(UPLOAD_DIR, file.file_name)
    await message.bot.download(file, destination=file_path)

    # Определяем количество страниц
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".pdf":
        total_pages = count_pdf_pages(file_path)
    else:
        total_pages = count_image_pages(file_path)

    copies = 1  # пока по умолчанию
    cost_per_page = 5

    await state.update_data(
        file=file_path,
        pages=total_pages,
        copies=copies,
        cost=total_pages * copies * cost_per_page
    )
    user_print_queue[message.from_user.id] = {
        "file": file_path,
        "pages": total_pages,
        "copies": copies,
        "cost": total_pages * copies * cost_per_page
    }

    msg_data = welcome_message_id.get(message.from_user.id)
    if msg_data:
        try:
            if isinstance(msg_data, dict) and msg_data.get("menu_msg_id"):
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_data["menu_msg_id"])
        except Exception as e:
            print("[handle_file] Не удалось удалить сообщение с инструкцией:", e)

    await send_print_parameters(message, state)

    welcome_message_id.setdefault(message.from_user.id, {})["user_file_msg_id"] = message.message_id

@router.callback_query(F.data == "change_copies")
async def prompt_copy_input(callback: CallbackQuery, state: FSMContext):
    await state.set_state(PrintStates.await_copies)

    # сохраняем старый message_id с параметрами
    await state.update_data(last_message_id=callback.message.message_id)

    # отправляем "введите копии" и сохраняем его ID
    msg = await callback.message.answer("✏️ Введите количество копий (от 1 до 20):")
    await state.update_data(prompt_msg_id=msg.message_id)


@router.message(PrintStates.await_copies)
async def receive_copy_input(message: Message, state: FSMContext):
    data = await state.get_data()
    user_input = message.text.strip()
    edit_mode = data.get("edit_mode", "copies")

    info = user_print_queue.get(message.from_user.id)
    if not info:
        await message.answer("❌ Ошибка: файл не найден.")
        await state.clear()
        return

    if edit_mode == "pages":
        info["page_range"] = user_input
    elif edit_mode == "pages_per_sheet":
        if user_input not in ["1", "2", "4"]:
            await message.answer("❌ Введите только 1, 2 или 4")
            return

        pages_per_sheet = int(user_input)
        info["pages_per_sheet"] = pages_per_sheet

        # Пересчёт стоимости
        # Пересчёт стоимости
        total_pages = info.get("pages", 1)
        page_range_str = info.get("page_range", "")
        pages_per_sheet = info.get("pages_per_sheet", 1)
        copies = info.get("copies", 1)

        selected_pages = parse_page_range(page_range_str, total_pages) if page_range_str else list(
            range(1, total_pages + 1))
        sheets = ceil(len(selected_pages) / pages_per_sheet)
        info["cost"] = sheets * copies * 5

        user_print_queue[message.from_user.id] = info
    else:
        if not user_input.isdigit() or not (1 <= int(user_input) <= 20):
            await message.answer("❌ Введите число от 1 до 20.")
            return
        info["copies"] = int(user_input)

    # Обновляем стоимость с учетом выбранных страниц и страниц на листе
    page_range_str = info.get("page_range", "")
    total_pages = info.get("pages", 1)
    pages_per_sheet = info.get("pages_per_sheet", 1)

    selected_pages = parse_page_range(page_range_str, total_pages) if page_range_str else list(
        range(1, total_pages + 1))
    sheets = ceil(len(selected_pages) / pages_per_sheet)
    info["cost"] = sheets * info.get("copies", 1) * 5
    user_print_queue[message.from_user.id] = info

    try:
        await message.delete()
    except:
        pass

    if "prompt_msg_id" in data:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["prompt_msg_id"])
        except:
            pass

    if "last_message_id" in data:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=data["last_message_id"])
        except:
            pass

    photo = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\PrintParamsImage.png")
    caption = (
        "<b>📄 Параметры печати:</b>\n\n"
        "• <b>Чёрно-белая</b>\n"
        "• <b>Односторонняя</b>\n"
        f"• <b>Кол-во копий:</b> <u>{info.get('copies', 1)}</u>\n"
        f"• <b>Страницы:</b> <u>{info.get('page_range', 'все')}</u>\n"
        f"• <b>Страниц на листе:</b> <u>{info.get('pages_per_sheet', 1)}</u>\n\n"
        f"<b>💵 Стоимость:</b> <i>{info['cost']} ₽</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Рассчитать цену и оплатить", callback_data="pay_and_print")],
        [InlineKeyboardButton(text="✏️ Изменить кол-во копий", callback_data="change_copies")],
        [InlineKeyboardButton(text="📑 Выбрать страницы", callback_data="change_pages")],
        [InlineKeyboardButton(text="🗃 На листе: 1 / 2 / 4", callback_data="change_pages_per_sheet")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])

    # 🧹 Удаляем предыдущее сообщение с параметрами
    state_data = await state.get_data()
    last_msg_id = state_data.get("last_message_id")
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except Exception as e:
            print("[DEBUG] Не удалось удалить старое сообщение с параметрами:", e)

    # 🧹 Удаляем старое сообщение с параметрами (если есть)
    state_data = await state.get_data()
    last_msg_id = state_data.get("last_message_id")
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except Exception as e:
            print("[DEBUG] Не удалось удалить старое сообщение с параметрами:", e)

    sent = await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    await state.clear()
    await state.update_data(last_message_id=sent.message_id)

from aiogram.types import FSInputFile

@router.callback_query(F.data == "change_pages_per_sheet")
async def ask_pages_per_sheet(callback: CallbackQuery, state: FSMContext):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1 на листе", callback_data="sheet_1")],
        [InlineKeyboardButton(text="2 на листе", callback_data="sheet_2")],
        [InlineKeyboardButton(text="4 на листе", callback_data="sheet_4")],
    ])
    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer("🗃 Выберите, сколько страниц печатать на одном листе:", reply_markup=keyboard)

@router.callback_query(F.data.startswith("sheet_"))
async def set_pages_per_sheet(callback: CallbackQuery, state: FSMContext):
    value = int(callback.data.split("_")[1])
    info = user_print_queue.get(callback.from_user.id)
    if not info:
        await callback.message.answer("❌ Файл не найден.")
        return

    # 🧹 Удаляем сообщение с кнопками "1 на листе / 2 на листе / 4 на листе"
    try:
        await callback.message.delete()
    except:
        pass

    info["pages_per_sheet"] = value
    await send_print_parameters(callback, state)

class PageSelection(StatesGroup):
    mode = State()
    pages_selected = State()

@router.callback_query(F.data == "change_pages")
async def start_page_toggle(callback: CallbackQuery, state: FSMContext):
    info = user_print_queue.get(callback.from_user.id)
    if not info:
        await callback.message.answer("❌ Файл не найден.")
        return

    total = info.get("pages", 1)
    selected = set(range(1, total + 1))  # по умолчанию всё выбрано

    await state.set_state(PageSelection.pages_selected)
    await state.update_data(selected=selected, total=total)
    await render_page_toggle(callback.message, selected, total)


# Отображение выбора страниц
async def render_page_toggle(message: Message, selected: set[int], total: int):
    lines = [f"{i} {'✅' if i in selected else '❌'}" for i in range(1, total + 1)]
    text = "<b>Выберите страницы для печати:</b>\n\n" + "\n".join(lines)

    # Кнопки: по 5 страниц на строку
    buttons = []
    for i in range(1, total + 1, 5):
        row = [InlineKeyboardButton(text=f"{j}", callback_data=f"toggle_page_{j}") for j in range(i, min(i+5, total+1))]
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="✅ Готово", callback_data="pages_done")])

    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    await message.answer(text, parse_mode="HTML", reply_markup=keyboard)

# Обработка нажатий на номера страниц
@router.callback_query(F.data.startswith("toggle_page_"))
async def toggle_page(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected", set())
    total = data.get("total", 1)
    page = int(callback.data.split("_")[-1])

    if page in selected:
        selected.remove(page)
    else:
        selected.add(page)

    await state.update_data(selected=selected)

    try:
        await callback.message.delete()
    except:
        pass

    await render_page_toggle(callback.message, selected, total)


# Завершение выбора
@router.callback_query(F.data == "pages_done")
async def finalize_page_selection(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = sorted(data.get("selected", set()))
    user_id = callback.from_user.id

    info = user_print_queue.get(user_id)
    if not info:
        await callback.message.answer("❌ Файл не найден.")
        return

    def format_range(pages: list[int]) -> str:
        if not pages:
            return ""
        ranges = []
        start = prev = pages[0]
        for p in pages[1:]:
            if p == prev + 1:
                prev = p
            else:
                if start == prev:
                    ranges.append(str(start))
                else:
                    ranges.append(f"{start}-{prev}")
                start = prev = p
        if start == prev:
            ranges.append(str(start))
        else:
            ranges.append(f"{start}-{prev}")
        return ",".join(ranges)

    info["page_range"] = format_range(selected)
    user_print_queue[user_id] = info

    try:
        await callback.message.delete()
    except:
        pass

    await send_print_parameters(callback, state)
    await state.clear()


@router.callback_query(F.data.startswith("range_"))
async def set_page_range(callback: CallbackQuery, state: FSMContext):
    data = callback.data

    info = user_print_queue.get(callback.from_user.id)
    if not info:
        await callback.message.answer("❌ Файл не найден.")
        return

    if data == "range_all":
        info["page_range"] = ""
    elif data == "range_custom":
        # Переход в ручной ввод
        await state.set_state(PrintStates.await_copies)
        await state.update_data(edit_mode="pages", last_message_id=callback.message.message_id)
        msg = await callback.message.answer("✍ Введите страницы вручную (например: 1-3,5,7):")
        await state.update_data(prompt_msg_id=msg.message_id)
        return
    else:
        # range_2_5
        _, start, end = data.split("_")
        info["page_range"] = f"{start}-{end}"

    await send_print_parameters(callback, state)

from aiogram.types import Message, CallbackQuery

async def send_print_parameters(message_or_callback, state: FSMContext):
    # Получаем объект message из message или callback
    if isinstance(message_or_callback, CallbackQuery):
        message = message_or_callback.message
        user_id = message_or_callback.from_user.id
    elif isinstance(message_or_callback, Message):
        message = message_or_callback
        user_id = message.from_user.id
    else:
        raise ValueError("Unknown type passed to send_print_parameters")

    info = user_print_queue.get(user_id)
    if not info:
        await message.answer("❌ Ошибка: параметры не найдены.")
        return

    copies = info.get("copies", 1)
    pages = info.get("pages", 1)
    page_range_str = info.get("page_range", "")
    pages_per_sheet = info.get("pages_per_sheet", 1)

    pages_to_print = parse_page_range(page_range_str, pages) if page_range_str else pages
    sheets = ceil(pages_to_print / pages_per_sheet)
    info["cost"] = sheets * copies * 5

    photo = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\PrintParamsImage.png")
    caption = (
        "<b>📄 Параметры печати:</b>\n\n"
        "• <b>Чёрно-белая</b>\n"
        "• <b>Односторонняя</b>\n"
        f"• <b>Кол-во копий:</b> <u>{copies}</u>\n"
        f"• <b>Страницы:</b> <u>{info.get('page_range', 'все')}</u>\n"
        f"• <b>Страниц на листе:</b> <u>{info.get('pages_per_sheet', 1)}</u>\n\n"
        f"<b>💵 Стоимость:</b> <i>{info['cost']} ₽</i>"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Рассчитать цену и оплатить", callback_data="pay_and_print")],
        [InlineKeyboardButton(text="✏️ Изменить кол-во копий", callback_data="change_copies")],
        [InlineKeyboardButton(text="📑 Выбрать страницы", callback_data="change_pages")],
        [InlineKeyboardButton(
            text=f"🗃 На листе: {pages_per_sheet} стр",
            callback_data="change_pages_per_sheet"
        )],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])

    # 🧹 Удаляем старое сообщение с параметрами (если есть)
    state_data = await state.get_data()
    last_msg_id = state_data.get("last_message_id")
    if last_msg_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=last_msg_id)
        except Exception as e:
            print("[DEBUG] Не удалось удалить старое сообщение с параметрами:", e)

    sent = await message.answer_photo(photo=photo, caption=caption, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    await state.update_data(last_message_id=sent.message_id)

from services.yookassa_pay import create_payment, check_payment




@router.callback_query(F.data == "pay_and_print")
async def start_payment(callback: CallbackQuery):
    info = user_print_queue.get(callback.from_user.id)
    if not info:
        await callback.message.answer("❌ Файл не найден.")
        return

    total_pages = info.get("pages", 1)
    copies = info.get("copies", 1)
    page_range_str = info.get("page_range", "")
    pages_per_sheet = info.get("pages_per_sheet", 1)

    pages_to_print = parse_page_range(page_range_str, total_pages) if page_range_str else total_pages
    sheets = ceil(pages_to_print / pages_per_sheet)
    cost = sheets * copies * 5
    info["cost"] = cost

    payment = create_payment(cost, callback.from_user.id)
    info["payment_id"] = payment["id"]

    text = (
        f"💵 Стоимость: {cost} ₽\n"
        f"({pages_to_print} стр. ÷ {pages_per_sheet} на листе = {sheets} листов × {copies} коп. × 5₽)"
        "\n\n🔗 Нажмите кнопку ниже для оплаты по СБП"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить через СБП", url=payment["url"])],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_payment")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])

    try:
        await callback.message.delete()
    except:
        pass

    await callback.message.answer(text, reply_markup=keyboard)

@router.callback_query(F.data == "check_payment")
async def check_payment_status(callback: CallbackQuery):
    info = user_print_queue.get(callback.from_user.id)
    if not info or "payment_id" not in info:
        await callback.message.answer("❌ Платёж не найден.")
        return

    status = check_payment(info["payment_id"])
    print(f"[DEBUG] Payment status for {info['payment_id']}: {status}")

    if status == "succeeded":
        try:
            await callback.message.delete()
        except:
            pass

        await simulate_print_progress(callback.message, info["file"], info["copies"], info=info)
    else:
        await callback.answer("⏳ Оплата не подтверждена. Попробуйте позже.", show_alert=True)

@router.callback_query(F.data == "start_print")
async def start_actual_print(callback: CallbackQuery):
    info = user_print_queue.get(callback.from_user.id)
    if not info:
        await callback.message.answer("❌ Ошибка: файл не найден.")
        return

    # Удаляем сообщение с кнопками (если нужно)
    try:
        await callback.message.delete()
    except:
        pass

    # Анимация + печать
    await simulate_print_progress(callback.message, info["file"], info["copies"], info=info)

from collections import defaultdict
from aiogram.utils.markdown import hbold, hitalic

from PIL import Image

def estimate_pages_for_image(path: str) -> int:
    with Image.open(path) as img:
        width, height = img.size
        aspect_ratio = width / height

        # Оцениваем, помещается ли на один лист (A4 ~ 1.41)
        return 1 if 0.6 < aspect_ratio < 1.7 else 2  # примерная логика

@router.callback_query(F.data.startswith("copies_"))
async def calc_price(callback):
    copies = int(callback.data.split("_")[1])
    total_pages = 3  # эмуляция
    cost = calculate_price(total_pages, copies)
    await callback.message.answer(f"💸 Всего: {total_pages} стр. × {copies} коп. = {cost} ₽\n\nОплата имитирована ✅\n\n🖨 Документ отправлен в очередь на печать.")
    await callback.answer()

async def _remove_last_menu(message: Message):
    data = welcome_message_id.get(message.from_user.id)
    if not data:
        return

    bot = message.bot
    try:
        if isinstance(data, dict):
            if data.get("menu_msg_id"):
                await bot.delete_message(chat_id=message.chat.id, message_id=data["menu_msg_id"])
            if data.get("user_msg_id"):
                await bot.delete_message(chat_id=message.chat.id, message_id=data["user_msg_id"])
        elif isinstance(data, int):  # старый формат
            await bot.delete_message(chat_id=message.chat.id, message_id=data)
    except Exception as e:
        print("[DEBUG] Не удалось удалить сообщение:", e)

    welcome_message_id[message.from_user.id] = None

from services.pdf_preprocess import extract_pages, duplicate_pdf, parse_page_range
from services.pdf_preprocess import generate_n_up_pdf
from services.pdf_preprocess import render_pages_to_images, generate_n_up_pdf
from services.pdf_preprocess import extract_pages, render_pages_to_images, generate_n_up_pdf, duplicate_pdf
from services.pdf_preprocess import get_page_numbers_from_range

import win32evtlog

def check_printer_errors_from_event_log(printer_name: str, minutes_back: int = 2) -> str | None:
    server = 'localhost'
    logtype = 'System'
    hand = win32evtlog.OpenEventLog(server, logtype)

    import datetime
    import time
    now = datetime.datetime.now()
    flags = win32evtlog.EVENTLOG_BACKWARDS_READ | win32evtlog.EVENTLOG_SEQUENTIAL_READ
    events = win32evtlog.ReadEventLog(hand, flags, 0)

    if not events:
        return None

    for ev_obj in events:
        if ev_obj.TimeGenerated < now - datetime.timedelta(minutes=minutes_back):
            break  # слишком старое событие

        if ev_obj.EventID in [13, 6161, 6163, 6170] and printer_name in ev_obj.StringInserts[0]:
            msg = " ".join(ev_obj.StringInserts)
            if "бумага" in msg.lower() or "paper" in msg.lower():
                return f"🧾 {msg}"

    return None

import cv2
import os
import time
import cv2

import subprocess
import time

import subprocess
import os
import signal
import time

def record_video_during_print_safe(output_path: str, final_pdf: str) -> bool:
    ffmpeg_path = r"C:\Program Files\JetBrains\AbanirPrint\ffmpeg.exe"
    output_path = os.path.abspath(output_path)

    command = [
        ffmpeg_path,
        "-f", "dshow",
        "-i", "video=Webcam C170",
        "-vcodec", "libx264",
        "-preset", "ultrafast",
        "-crf", "25",
        "-y", output_path
    ]

    print(f"[ffmpeg] ▶️ Запускаем ffmpeg в {output_path}")
    try:
        # 1. Стартуем запись ffmpeg через shell, чтобы он получил CTRL+C корректно
        process = subprocess.Popen(command, creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)

        # 2. ДАЁМ ВРЕМЯ камере
        print("[ffmpeg] ⏳ Подождите, камера прогревается...")
        time.sleep(2)

        # 3. Печатаем
        print("[ffmpeg] ✅ Камера готова. Печать пошла...")
        print_and_wait(final_pdf)

        # 4. Завершаем ffmpeg красиво — посылаем CTRL+C
        print("[ffmpeg] 🛑 Завершение записи...")
        process.send_signal(signal.CTRL_BREAK_EVENT)  # Windows: посылаем Ctrl+Break
        process.wait(timeout=10)

        # 5. Проверяем файл
        exists = os.path.exists(output_path)
        size_ok = os.path.getsize(output_path) > 1000 if exists else False

        return exists and size_ok

    except Exception as e:
        print(f"[ffmpeg] ❌ Ошибка: {e}")
        return False


async def simulate_print_progress(message: Message, original_path: str, copies: int = 1, info=None):
    user_id = message.chat.id if hasattr(message, "chat") else message.from_user.id
    info = user_print_queue.get(user_id)

    if not info:
        await message.answer("❌ Ошибка: параметры не найдены.")
        return

    page_range_str = info.get("page_range", "")
    total_pages = info.get("pages", 1)
    pages_per_sheet = info.get("pages_per_sheet", 1)

    selected_pages = get_page_numbers_from_range(page_range_str, total_pages) if page_range_str else list(range(1, total_pages + 1))
    if isinstance(selected_pages, int):  # защита
        selected_pages = [selected_pages]

    print(f"[DEBUG] selected_pages = {selected_pages}, type = {type(selected_pages)}")

    # ⬇️ ВЫРЕЗАЕМ ТОЛЬКО НУЖНЫЕ СТРАНИЦЫ
    trimmed_pdf = extract_pages(original_path, selected_pages)

    # ⬇️ ПРЕОБРАЗУЕМ В ИЗОБРАЖЕНИЯ
    new_total = count_pdf_pages(trimmed_pdf)
    images = render_pages_to_images(trimmed_pdf, list(range(1, new_total + 1)))

    # ⬇️ ФОРМИРУЕМ N-UP PDF
    n_up_pdf = generate_n_up_pdf(images, pages_per_sheet)

    # ⬇️ ДУБЛИРУЕМ НА КОПИИ
    final_pdf = duplicate_pdf(n_up_pdf, copies)

    print("[DEBUG] Путь к финальному PDF:", final_pdf)
    os.system(f'start {final_pdf}')  # предварительный просмотр

    # ⬇️ АНИМАЦИЯ ПОДГОТОВКИ
    progress_msg = await message.answer("📤 Подготовка к печати...")
    for i in range(0, 101, 20):
        bar = "🟩" * (i // 20) + "⬜" * (5 - (i // 20))
        try:
            await progress_msg.edit_text(f"📤 Подготовка к печати...\n{i}%\n{bar}")
        except:
            pass
        await asyncio.sleep(0.6)

    # await check_and_notify_printer_errors(
    #     bot=message.bot,
    #     user_id=message.from_user.id,
    #     action="печать",
    #     details={
    #         "file": original_path,
    #         "copies": copies
    #     }
    # )

    from aiogram.types import FSInputFile

    # 🎥 Записываем видео (10 сек)
    import cv2

    import cv2

    # 🎥 Записываем видео (10 сек)
    video_path = f"print_videos/print_demo_{message.from_user.id}.mp4"
    recorded = await asyncio.to_thread(record_video_during_print_safe, video_path, final_pdf)

    if recorded:
        video_file = FSInputFile(video_path)
        await message.answer_video(
            video=video_file,
            caption="🎥 Это пример, как будет выглядеть печать.\nMVP-версия в действии!"
        )
    else:
        await message.answer("⚠️ Видео не удалось записать. Камера не отвечает.")

    # ⬇️ ПЕЧАТЬ


    try:
        await progress_msg.delete()
    except:
        pass

    # Удаляем сообщение пользователя с файлом
    msg_data = welcome_message_id.get(user_id)
    if msg_data and isinstance(msg_data, dict):
        file_msg_id = msg_data.get("user_file_msg_id")
        if file_msg_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=file_msg_id)
            except Exception as e:
                print("[DEBUG] Не удалось удалить сообщение с файлом после печати:", e)

    # Отправляем сообщение об окончании печати
    await message.answer("🖨 Печать завершена. Заберите ваш документ!")

    from services.history_logger import safe_save_action

    # ...
    safe_save_action(
        user_id=user_id,
        action="print",
        details={
            "pages": len(selected_pages),
            "copies": copies,
            "pages_per_sheet": pages_per_sheet,
            "page_range": info.get("page_range", "все"),
            "cost": info["cost"],
            "error": None
        }
    )

    # Показываем главное меню
    msg = await message.answer("👇 Выберите действие:",
                               reply_markup=get_main_reply_keyboard(user_id))
    welcome_message_id[user_id] = {
        "menu_msg_id": msg.message_id
    }


from PyPDF2 import PdfReader

def count_pdf_pages(path: str) -> int:
    try:
        reader = PdfReader(path)
        return len(reader.pages)
    except:
        return 1  # fallback

from aiogram.utils.media_group import MediaGroupBuilder

import re
from math import ceil

def parse_page_range(page_range_str: str, total_pages: int) -> int:
    """
    Возвращает количество страниц по введённому диапазону, например: "1-3,5,7"
    """
    pages = set()
    for part in page_range_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-")
            if start.isdigit() and end.isdigit():
                pages.update(range(int(start), int(end)+1))
        elif part.isdigit():
            pages.add(int(part))

    # фильтруем выход за пределы
    pages = {p for p in pages if 1 <= p <= total_pages}
    return len(pages) if pages else total_pages

