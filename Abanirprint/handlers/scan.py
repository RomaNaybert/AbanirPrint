# handlers/scan.py

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from services.yookassa_pay import create_payment, check_payment
from services.scan_utils import scan_document, merge_scans_to_pdf, print_file
import asyncio
import os
from aiogram.types import FSInputFile

router = Router()
user_scan_data = {}

class ScanStates(StatesGroup):
    choosing_output = State()
    choosing_pages = State()
    choosing_mode = State()
    waiting_payment = State()
    scanning_manual = State()
    scanning_auto = State()


@router.message(F.text == "📄 Сканирование")
async def start_scan(message: Message, state: FSMContext):
    from handlers.user_main import _remove_last_menu  # 👈 импорт функции (если она в print.py)
    from handlers.user_main import _remove_last_menu, welcome_message_id

    # 🧹 Удаляем предыдущее меню "👇 Выберите действие:"
    try:
        msg_id = welcome_message_id.get(message.from_user.id)
        if msg_id:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
    except:
        pass

    await _remove_last_menu(message)
    await _remove_last_menu(message)  # 👈 добавляем вызов
    # Маскируем или удаляем сообщение пользователя
    try:
        await message.edit_text("‎")
    except:
        try:
            await message.delete()
        except:
            pass

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Понятно", callback_data="scan_confirmed")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back_to_menu")]
    ])

    image = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\ScanInstruction.png")

    text = (
        "<b>📄 Инструкция по сканированию:</b>\n\n"
        "1️⃣ Откройте крышку сканера\n"
        "2️⃣ Положите документ <u>лицевой стороной вниз</u>\n"
        "3️⃣ Закройте крышку\n\n"
        "⬇️ Далее выберите, что делать со сканом"
    )

    await message.answer_photo(photo=image, caption=text, reply_markup=kb, parse_mode="HTML")
    await state.clear()


@router.callback_query(F.data == "scan_confirmed")
async def scan_output_choice(callback: CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()  # 👈 Удаляет сообщение с инструкцией и кнопками
    except:
        pass
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить в Telegram", callback_data="scan_send")],
        [InlineKeyboardButton(text="🖨 Напечатать", callback_data="scan_print")],
        [InlineKeyboardButton(text="↩️ В меню", callback_data="back_to_menu")]
    ])

    text = (
        "<b>📎 Выберите действие:</b>\n\n"
        "• <b>📤 Отправить</b> — бот пришлёт PDF-файл в Telegram\n"
        "• <b>🖨 Напечатать</b> — файл сразу пойдёт на печать"
    )

    try:
        image = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\ScanOption.png")
        await callback.message.answer_photo(image, caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print("[scan_output_choice] Ошибка загрузки изображения:", e)
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")

    await state.set_state(ScanStates.choosing_output)

@router.callback_query(F.data.in_(["scan_send", "scan_print"]))
async def scan_choose_pages(callback: CallbackQuery, state: FSMContext):
    target = "telegram" if callback.data == "scan_send" else "print"
    await state.update_data(output=target)

    # 🧠 Сохраняем ID сообщения с кнопками "📤 Отправить" / "🖨 Напечатать"
    await state.update_data(scan_action_message_id=callback.message.message_id)

    msg = await callback.message.answer("Введите количество страниц для сканирования (1–20):")
    await state.update_data(pages_prompt_id=msg.message_id)
    await state.set_state(ScanStates.choosing_pages)


@router.message(ScanStates.choosing_pages)
async def scan_pages_input(message: Message, state: FSMContext):
    try:
        await message.delete()
    except Exception as e:
        print("[scan_pages_input] Не удалось удалить сообщение пользователя:", e)

    data = await state.get_data()

    # 🧹 Удаляем сообщение с кнопками "📤 Отправить" / "🖨 Напечатать"
    action_id = data.get("scan_action_message_id")
    if action_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=action_id)
        except Exception as e:
            print("[scan_pages_input] Не удалось удалить сообщение с выбором действия:", e)

    # Удаляем текстовое сообщение "Введите количество страниц..."
    prompt_id = data.get("pages_prompt_id")
    if prompt_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except Exception as e:
            print("[scan_pages_input] Не удалось удалить сообщение с запросом страниц:", e)

    if not message.text.isdigit() or not (1 <= int(message.text) <= 20):
        msg = await message.answer("❌ Введите число от 1 до 20.")
        await state.update_data(pages_prompt_id=msg.message_id)
        return

    pages = int(message.text)
    await state.update_data(pages=pages)

    photo = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\ScanMode.png")  # путь к твоей картинке

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖐 Вручную", callback_data="scan_manual")],
        [InlineKeyboardButton(text="⏱ Авто (каждые 5 сек)", callback_data="scan_auto")]
    ])

    caption = (
        "📷 <b>Режимы сканирования:</b>\n\n"
        "🖐 <b>Вручную</b> — вы нажимаете кнопку перед каждым сканом.\n"
        "⏱ <b>Авто</b> — сканирование выполняется каждые 5 сек.\n\n"
        "Выберите режим:"
    )

    msg = await message.answer_photo(photo=photo, caption=caption, reply_markup=kb, parse_mode="HTML")
    await state.update_data(scan_mode_message_id=msg.message_id)  # 💾 сохранить для удаления
    await state.set_state(ScanStates.choosing_mode)
    await state.set_state(ScanStates.choosing_mode)

@router.callback_query(F.data.in_(["scan_manual", "scan_auto"]))
async def scan_prepare_payment(callback: CallbackQuery, state: FSMContext):
    # Перед созданием кнопок оплаты
    mode = "manual" if callback.data == "scan_manual" else "auto"
    data = await state.get_data()

    # 🧹 Удаляем сообщение с выбором режима
    scan_mode_msg_id = data.get("scan_mode_message_id")
    if scan_mode_msg_id:
        try:
            await callback.bot.delete_message(chat_id=callback.message.chat.id, message_id=scan_mode_msg_id)
        except Exception as e:
            print("[scan_prepare_payment] Не удалось удалить сообщение с выбором режима:", e)
    pages = data["pages"]
    output = data["output"]

    price_per_page = 10 if output == "telegram" else 15
    cost = pages * price_per_page  # цена за 1 скан
    payment = create_payment(cost, callback.from_user.id)
    await state.update_data(
        mode=mode,
        payment_id=payment["id"],
        cost=cost  # 👈 ДОБАВЬ ЭТО
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить через СБП", url=payment["url"])],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="scan_check_payment")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])

    await callback.message.answer(
        f"💵 Стоимость: {cost} ₽ ({pages} стр. × {price_per_page}₽)\n\n🔗 Нажмите кнопку ниже для оплаты по СБП",
        reply_markup=kb
    )
    await state.set_state(ScanStates.waiting_payment)

@router.callback_query(F.data == "scan_check_payment")
async def scan_check_payment(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if check_payment(data["payment_id"]) != "succeeded":
        await callback.answer("⏳ Оплата не подтверждена", show_alert=True)
        return

    await callback.message.delete()
    pages = data["pages"]
    mode = data["mode"]
    output = data["output"]
    user_id = callback.from_user.id

    folder = f"scans/{user_id}"
    os.makedirs(folder, exist_ok=True)

    if mode == "manual":
        await state.set_state(ScanStates.scanning_manual)
        progress_msg = await callback.message.answer(
            f"📷 Готово к сканированию\n\n"
            f"🗂 Всего страниц: {pages}\n"
            f"✅ Отсканировано: 0\n"
            f"⌛ Осталось: {pages}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📷 Отсканировать", callback_data="scan_once")]
            ])
        )
        await state.update_data(current_page=0, folder=folder, scan_prompt_id=progress_msg.message_id)
    else:
        await state.set_state(ScanStates.scanning_auto)

        progress_msg = await callback.message.answer(
            f"📷 Подготовка к авто-сканированию\n\n"
            f"🗂 Всего страниц: {pages}\n"
            f"✅ Отсканировано: 0\n"
            f"⌛ Осталось: {pages}\n\n"
            f"<code>{get_progress_bar(0)}</code>\n\n"
            f"<i>Подготовьте листы и положите первую страницу в сканер.\n"
            f"Скан начнётся после нажатия кнопки ниже.\n"
            f"После каждой страницы у вас будет 5 секунд на замену.</i>",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="▶️ Начать авто-скан", callback_data="start_auto_scan")
            ]]),
            parse_mode="HTML"
        )

        await state.update_data(current_page=0, folder=folder, scan_prompt_id=progress_msg.message_id)

@router.callback_query(F.data == "start_auto_scan")
async def scan_auto_start(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    pages = data["pages"]
    folder = data["folder"]
    scan_prompt_id = data["scan_prompt_id"]

    loop = asyncio.get_running_loop()

    for i in range(pages):
        progress = 0
        # Скан начинается сразу
        scan_task = loop.run_in_executor(None, scan_document, os.path.join(folder, f"scan_{i+1}.jpg"))

        # 1. Прогресс до 80% (примерно за 15 секунд)
        for step in range(1, 9):
            progress = step / 10
            text = (
                f"<b>📡 Авто-скан страницы {i + 1}</b>\n\n"
                f"🗂 Всего: {pages}\n"
                f"✅ Отсканировано: {i}\n"
                f"⌛ Осталось: {pages - i}\n\n"
                f"<code>{get_progress_bar(progress)}</code>\n\n"
                f"<i>Подготовьте страницу. Сканирование закончится через {8 - step + 1} сек</i>"
            )
            try:
                await callback.bot.edit_message_text(
                    chat_id=callback.message.chat.id,
                    message_id=scan_prompt_id,
                    text=text,
                    parse_mode="HTML"
                )
            except:
                pass
            await asyncio.sleep(1.9)

        # 2. Дождись завершения сканирования
        await scan_task

        # 3. 100% и статус
        text = (
            f"<b>✅ Страница {i + 1} отсканирована</b>\n\n"
            f"🗂 Всего: {pages}\n"
            f"✅ Отсканировано: {i + 1}\n"
            f"⌛ Осталось: {pages - (i + 1)}\n\n"
            f"<code>{get_progress_bar(1.0)}</code>\n\n"
            f"<i>Замените страницу. Скан начнётся через 5 секунд</i>"
        )
        try:
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=scan_prompt_id,
                text=text,
                parse_mode="HTML"
            )
        except:
            pass

        await state.update_data(current_page=i + 1)
        if i + 1 < pages:
            for countdown in range(5, 0, -1):
                countdown_text = (
                    f"<b>✅ Страница {i + 1} отсканирована</b>\n\n"
                    f"🗂 Всего: {pages}\n"
                    f"✅ Отсканировано: {i + 1}\n"
                    f"⌛ Осталось: {pages - (i + 1)}\n\n"
                    f"<code>{get_progress_bar(1.0)}</code>\n\n"
                    f"<i>Замените страницу. Скан начнётся через {countdown} секунд</i>"
                )
                try:
                    await callback.bot.edit_message_text(
                        chat_id=callback.message.chat.id,
                        message_id=scan_prompt_id,
                        text=countdown_text,
                        parse_mode="HTML"
                    )
                except:
                    pass
                await asyncio.sleep(1)  # малый интервал перед следующим циклом

    # Всё готово — завершаем
    await finish_scanning(callback.message, state)

from aiogram.utils.chat_action import ChatActionSender
from aiogram.types import CallbackQuery

@router.callback_query(F.data == "scan_once")
async def manual_scan_once(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    page = data.get("current_page", 0)
    total = data["pages"]
    folder = data["folder"]
    scan_prompt_id = data.get("scan_prompt_id")

    path = os.path.join(folder, f"scan_{page + 1}.jpg")
    await callback.answer("📷 Сканирование началось...")

    # Эмуляция прогресс-бара
    # 1. запускаем реальное сканирование сразу
    loop = asyncio.get_running_loop()
    scan_task = loop.run_in_executor(None, scan_document, path)

    # 2. параллельно показываем прогресс до 80%
    for i in range(1, 9):  # 8 шагов (до 80%)
        progress_bar = get_progress_bar(i / 9)
        text = (
            f"<b>📡 Сканирование страницы {page + 1}...</b>\n\n"
            f"🗂 Всего: {total}\n"
            f"✅ Отсканировано: {page}\n\n"
            f"⌛ Осталось: {total - page}\n\n"
            f"<code>{progress_bar}</code>"
        )
        try:
            await callback.bot.edit_message_text(
                chat_id=callback.message.chat.id,
                message_id=scan_prompt_id,
                text=text,
                reply_markup=None,
                parse_mode="HTML"
            )
        except:
            pass
        await asyncio.sleep(1.9)  # ~15 сек

    # 3. дожидаемся завершения реального сканирования
    await scan_task

    page += 1
    await state.update_data(current_page=page)

    # обновлённый прогресс (100%)
    progress_bar = get_progress_bar(1.0)
    final_text = (
        f"<b>✅ Страница {page} отсканирована!</b>\n\n"
        f"🗂 Всего: {total}\n"
        f"✅ Отсканировано: {page}\n"
        f"⌛ Осталось: {total - page}\n\n"
        f"<code>{progress_bar}</code>\n\n"
        f"<i>Сканер готов к следующей странице.</i>"
    )

    try:
        await callback.bot.edit_message_text(
            chat_id=callback.message.chat.id,
            message_id=scan_prompt_id,
            text=final_text,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="📷 Отсканировать", callback_data="scan_once")]
            ]),
            parse_mode="HTML"
        )
    except Exception as e:
        print("[manual_scan_once] Ошибка обновления финального сообщения:", e)

    if page >= total:
        await finish_scanning(callback.message, state)

async def auto_scan(callback: CallbackQuery, state: FSMContext, folder: str):
    data = await state.get_data()
    total = data["pages"]
    loop = asyncio.get_running_loop()

    for i in range(total):
        path = os.path.join(folder, f"scan_{i+1}.jpg")

        # ⚙️ В фоновом потоке:
        await loop.run_in_executor(None, scan_document, path)

        await callback.message.answer(f"📸 Отсканирована страница {i+1}")
        await asyncio.sleep(5)

    await finish_scanning(callback.message, state)

from keyboards import get_main_reply_keyboard
from handlers.user_main import return_to_main

from handlers.user_main import welcome_message_id

async def show_main_menu(message):
    try:
        # Удалить старое меню, если оно есть
        old = welcome_message_id.get(message.from_user.id)
        if isinstance(old, dict) and old.get("menu_msg_id"):
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old["menu_msg_id"])
        elif isinstance(old, int):
            await message.bot.delete_message(chat_id=message.chat.id, message_id=old)
    except:
        pass

    # Показать новое меню
    # msg = await message.answer(text = " f", reply_markup=main_reply_keyboard)
    welcome_message_id[message.from_user.id] = {"menu_msg_id": msg.message_id}

async def finish_scanning(message: Message, state: FSMContext):
    print("[finish_scanning] Вызван")
    data = await state.get_data()
    user_id = message.chat.id
    folder = data["folder"]
    output = data["output"]
    paths = [os.path.join(folder, f"scan_{i+1}.jpg") for i in range(data["pages"])]
    pdf_path = os.path.join(folder, "result.pdf")
    merge_scans_to_pdf(paths, pdf_path)

    # 🧹 Удалить сообщение с прогрессом
    prompt_id = data.get("scan_prompt_id")
    if prompt_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=prompt_id)
        except:
            pass

    if output == "telegram":
        await message.answer_document(
            FSInputFile(pdf_path),
            caption="📎 Ваш отсканированный документ",
            reply_markup=get_main_reply_keyboard(user_id)
        )
    else:
        # 1. Показываем "Файл отправлен на печать..."
        printing_msg = await message.answer("🖨 Файл отправлен на печать...")

        # 2. Печатаем в фоне
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, print_file, pdf_path)

        try:
            await printing_msg.delete()
        except:
            pass

        # 3. Через паузу — финальное сообщение
        await message.answer(
            "✅ Сканирование и печать завершены! Заберите ваш документ.",
            reply_markup=get_main_reply_keyboard(user_id)
        )

        await asyncio.sleep(1)

    from services.history_logger import safe_save_action

    print(f"[finish_scanning] Сохраняем: output={output}")
    safe_save_action(
        user_id=user_id,
        action="scan" if output == "telegram" else "scan_and_print",
        details={
            "pages": data["pages"],
            "mode": data["mode"],
            "output": output,
            "cost": data.get("cost", 0),
            "error": None
        }
    )

    await state.clear()


def get_progress_bar(progress: float, total: int = 10) -> str:
    filled = round(progress * total)
    empty = total - filled
    return "▰" * filled + "▱" * empty