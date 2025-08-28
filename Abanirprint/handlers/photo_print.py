from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
import asyncio, os
from PIL import Image
from aiogram.fsm.state import StatesGroup, State
from config import UPLOAD_DIR, MAX_PHOTOS
from services.print_manager import print_and_wait
from services.yookassa_pay import create_payment, check_payment

router = Router()
user_print_queue = {}
photo_groups = {}
pending_tasks = {}


class PhotoPrintStates(StatesGroup):
    await_copies_photo = State()

def estimate_pages_for_image(path: str) -> int:
    with Image.open(path) as img:
        width, height = img.size
        ratio = width / height
        return 1 if 0.6 < ratio < 1.7 else 2

@router.message(F.photo & ~F.media_group_id)
async def handle_single_photo(message: Message, state: FSMContext):
    user_id = message.from_user.id

    file = message.photo[-1]
    path = os.path.join(UPLOAD_DIR, f"{user_id}_single.jpg")
    await message.bot.download(file.file_id, destination=path)
    pages = estimate_pages_for_image(path)

    user_print_queue[user_id] = {
        "file": [path],
        "pages": pages,
        "copies": 1
    }

    await state.set_data({
        "file": [path],
        "pages": pages,
        "copies": 1
    })

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="photo_done")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])

    # 🧹 Удалить сообщение "📎 Отправьте файл для печати"
    from handlers.user_main import welcome_message_id

    msg_data = welcome_message_id.get(user_id)
    if msg_data and isinstance(msg_data, dict):
        msg_id = msg_data.get("menu_msg_id")
        if msg_id:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=msg_id)
            except Exception as e:
                print("[handle_single_photo] Не удалось удалить меню:", e)

    from handlers.user_main import welcome_message_id

    # Удаляем прошлые фото и "Фото добавлено", если были
    old = welcome_message_id.get(user_id, {})
    old_photo_ids = old.get("photo_message_ids", [])
    for mid in old_photo_ids:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
        except:
            pass

    # Добавляем новое
    photo_msg = await message.answer(f"✅ Фото добавлено (1/{MAX_PHOTOS})", reply_markup=kb)

    welcome_message_id.setdefault(user_id, {})["photo_message_ids"] = [message.message_id, photo_msg.message_id]

@router.message(F.photo & F.media_group_id)
async def collect_group_photo(message: Message, state: FSMContext):
    key = (message.chat.id, message.media_group_id)
    photo_groups.setdefault(key, []).append(message)

    if key not in pending_tasks:
        pending_tasks[key] = asyncio.create_task(process_group(key, state))

async def process_group(key, state: FSMContext):
    await asyncio.sleep(2.0)

    messages = photo_groups.pop(key, [])
    pending_tasks.pop(key, None)

    if not messages:
        return

    user_id = messages[0].from_user.id
    chat_id = messages[0].chat.id

    if len(messages) > MAX_PHOTOS:
        msg = await messages[0].answer(f"❌ Можно загрузить не более {MAX_PHOTOS} фото.")
        await state.update_data(status_msg_id=msg.message_id)
        return

    paths = []
    total_pages = 0
    for i, msg in enumerate(messages):
        file = msg.photo[-1]
        path = os.path.join(UPLOAD_DIR, f"{msg.media_group_id}_{i}.jpg")
        await msg.bot.download(file.file_id, destination=path)
        paths.append(path)
        total_pages += estimate_pages_for_image(path)

    user_print_queue[user_id] = {
        "file": paths,
        "pages": total_pages,
        "copies": 1
    }

    await state.set_data({
        "file": paths,
        "pages": total_pages,
        "copies": 1
    })

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Готово", callback_data="photo_done")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])

    # 🧹 Удалить сообщение "📎 Отправьте файл для печати"
    from handlers.user_main import welcome_message_id

    msg_data = welcome_message_id.get(user_id)
    if msg_data and isinstance(msg_data, dict):
        msg_id = msg_data.get("menu_msg_id")
        if msg_id:
            try:
                await messages[0].bot.delete_message(chat_id=chat_id, message_id=msg_id)
            except Exception as e:
                print("[process_group] Не удалось удалить меню:", e)

    from handlers.user_main import welcome_message_id

    # Удаляем старые фото и сообщение "Фото добавлено"
    old = welcome_message_id.get(user_id, {})
    old_photo_ids = old.get("photo_message_ids", [])
    for mid in old_photo_ids:
        try:
            await messages[0].bot.delete_message(chat_id=chat_id, message_id=mid)
        except:
            pass

    # Собираем message_id текущей группы
    msg_ids = [m.message_id for m in messages]
    status_msg = await messages[0].answer(f"✅ Фото добавлено ({len(paths)}/{MAX_PHOTOS})", reply_markup=kb)
    msg_ids.append(status_msg.message_id)

    # Сохраняем новые
    welcome_message_id.setdefault(user_id, {})["photo_message_ids"] = msg_ids

@router.callback_query(F.data == "photo_done")
async def photo_done(callback: CallbackQuery, state: FSMContext):
    info = user_print_queue.get(callback.from_user.id)
    if not info:
        await callback.answer("❌ Фото не найдены", show_alert=True)
        return
    await callback.message.delete()
    await send_print_parameters(callback.message, state, info)
    await callback.answer()

@router.callback_query(F.data == "pay_and_print_photo")
async def photo_payment(callback: CallbackQuery, state: FSMContext):
    info = user_print_queue.get(callback.from_user.id)

    # Если не найдено — fallback к FSMContext
    if not info:
        state_data = await state.get_data()
        if "file" in state_data:
            info = {
                "file": state_data["file"],
                "pages": state_data["pages"],
                "copies": state_data.get("copies", 1)
            }
            user_print_queue[callback.from_user.id] = info
        else:
            await callback.message.answer("❌ Фото не найдены.")
            return

    cost = info["pages"] * info["copies"] * 5
    payment = create_payment(cost, callback.from_user.id)
    info["payment_id"] = payment["id"]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Оплатить через СБП", url=payment["url"])],
        [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data="check_payment_photo")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])

    try:
        await callback.message.delete()
    except: pass

    extra_note = ""
    if info["pages"] > len(info["file"]):
        extra_note = (
            "\n\n⚠️ Некоторые фото не поместились на один лист, поэтому общее число страниц больше, чем число фото."
        )

    await callback.message.answer(
        f"💵 Стоимость: {cost} ₽ ({info['pages']} стр. × {info['copies']} коп. × 5₽)"
        f"{extra_note}\n\n🔗 Нажмите кнопку ниже для оплаты по СБП",
        reply_markup=keyboard
    )

@router.callback_query(F.data == "check_payment_photo")
async def photo_check_payment(callback: CallbackQuery):
    info = user_print_queue.get(callback.from_user.id)
    if not info or "payment_id" not in info:
        await callback.message.answer("❌ Платёж не найден.")
        return

    status = check_payment(info["payment_id"])
    if status == "succeeded":
        await callback.message.delete()
        await simulate_print_progress(callback.message, info["file"], info["copies"], info=info)
    else:
        await callback.answer("⏳ Оплата не подтверждена", show_alert=True)

from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
from PIL import Image
from services.print_manager import print_and_wait

def estimate_pages_for_image(path: str) -> int:
    with Image.open(path) as img:
        width, height = img.size
        ratio = width / height
        return 1 if 0.6 < ratio < 1.7 else 2


async def simulate_print_progress(message: Message, file_path: str | list[str], copies: int = 1, info=None):
    progress_msg = None
    for i in range(0, 101, 20):
        bar = "🟩" * (i // 20) + "⬜" * (5 - (i // 20))
        text = f"📤 Отправка файла на печать...\n{i}%\n{bar}"
        if progress_msg is None:
            progress_msg = await message.answer(text)
        else:
            await progress_msg.edit_text(text)
        await asyncio.sleep(0.6)


    loop = asyncio.get_running_loop()
    if isinstance(file_path, list):
        for path in file_path:
            await loop.run_in_executor(
                None,
                print_and_wait,
                file_path,
                copies,
                120,  # timeout
                message.from_user.id,  # user_id
                message.bot  # bot
            )
    else:
        from services.notify_admins import try_notify_print_error
        try:
            await loop.run_in_executor(None, print_and_wait, file_path, copies)
        except Exception as e:
            await try_notify_print_error(
                bot=message.bot,
                user_id=message.from_user.id,
                action="печать",
                details={
                    "file": file_path,
                    "copies": copies
                },
                exception=e
            )
            await message.answer("❌ Ошибка при печати. Администратор уведомлён.")
            return

    await progress_msg.delete()

    from services.history_logger import safe_save_action

    if info:
        total_pages = info.get("pages", 1)
        copies = info.get("copies", 1)
        total_cost = total_pages * copies * 5
        user_id = info.get("user_id", message.from_user.id)

        safe_save_action(
            user_id=user_id,
            action="print",
            details={
                "pages": total_pages,
                "copies": copies,
                "cost": total_cost,
                "error": None
            }
        )


    # 🧹 Удаляем сообщения с фото и "Фото добавлено"
    from handlers.user_main import welcome_message_id

    user_id = message.chat.id if hasattr(message, "chat") else message.from_user.id
    msg_data = welcome_message_id.get(user_id)

    if msg_data and isinstance(msg_data, dict):
        photo_ids = msg_data.get("photo_message_ids", [])
        for mid in photo_ids:
            try:
                await message.bot.delete_message(chat_id=message.chat.id, message_id=mid)
            except Exception as e:
                print("[simulate_print_progress] Не удалось удалить фото:", e)

        # Очищаем
        msg_data["photo_message_ids"] = []


    await message.answer("🖨 Печать завершена. Заберите ваш документ!")

@router.callback_query(F.data == "change_copies_photo")
async def change_copies_photo(callback: CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await state.set_state(PhotoPrintStates.await_copies_photo)
    msg = await callback.message.answer("✏️ Введите количество копий (от 1 до 20):")
    await state.update_data(prompt_msg_id=msg.message_id)

@router.message(PhotoPrintStates.await_copies_photo)
async def receive_copies_input(message: Message, state: FSMContext):
    if not message.text.isdigit() or not (1 <= int(message.text) <= 20):
        await message.answer("❌ Введите число от 1 до 20.")
        return

    new_copies = int(message.text)
    data = await state.get_data()
    file = data.get("file")
    pages = data.get("pages")
    old_prompt_id = data.get("prompt_msg_id")
    last_msg_id = data.get("last_message_id")

    if old_prompt_id:
        try:
            await message.bot.delete_message(message.chat.id, old_prompt_id)
        except: pass
    try:
        await message.bot.delete_message(message.chat.id, message.message_id)
    except: pass
    if last_msg_id:
        try:
            await message.bot.delete_message(message.chat.id, last_msg_id)
        except: pass

    info = {
        "file": file,
        "pages": pages,
        "copies": new_copies
    }
    user_print_queue[message.from_user.id] = info
    await send_print_parameters(message, state, info)
    await state.clear()

async def send_print_parameters(message: Message, state, info: dict):
    photo = FSInputFile(r"C:\Program Files\JetBrains\AbanirPrint\images\PrintParamsImage.png")
    caption = (
        "<b>📄 Параметры печати:</b>\n\n"
        "• <b>Чёрно-белая</b>\n"
        "• <b>Односторонняя</b>\n"
        f"• <b>Кол-во копий:</b> <u>{info['copies']}</u>\n\n"
        f"<b>💵 Стоимость:</b> <i>5 ₽ за страницу</i>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💸 Рассчитать цену и оплатить", callback_data="pay_and_print_photo")],
        [InlineKeyboardButton(text="✏️ Изменить кол-во копий", callback_data="change_copies_photo")],
        [InlineKeyboardButton(text="↩️ В главное меню", callback_data="back_to_menu")]
    ])
    sent = await message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode="HTML")
    await state.update_data(last_message_id=sent.message_id)

