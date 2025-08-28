# utils/print_utils.py

from aiogram.types import Message, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from services.print_manager import print_and_wait
from PIL import Image
import asyncio

def estimate_pages_for_image(path: str) -> int:
    with Image.open(path) as img:
        width, height = img.size
        ratio = width / height
        return 1 if 0.6 < ratio < 1.7 else 2

async def simulate_print_progress(message: Message, file_path: str | list[str], copies: int = 1):
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
            await loop.run_in_executor(None, print_and_wait, path, copies)
    else:
        await loop.run_in_executor(None, print_and_wait, file_path, copies)

    await progress_msg.delete()
    await message.answer("🖨 Печать завершена. Заберите ваш документ!")

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
        [InlineKeyboardButton("💸 Рассчитать цену и оплатить", callback_data="pay_and_print")],
        [InlineKeyboardButton("✏️ Изменить кол-во копий", callback_data="change_copies")],
        [InlineKeyboardButton("↩️ В главное меню", callback_data="back_to_menu")]
    ])
    sent = await message.answer_photo(photo, caption=caption, reply_markup=kb, parse_mode="HTML")
    await state.update_data(last_message_id=sent.message_id)