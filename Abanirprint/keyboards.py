from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

back_to_menu_button = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🔙 Вернуться в главное меню", callback_data="back_to_menu")]
])

# Меню-клавиатура (ReplyKeyboard)
from config import ADMINS
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_reply_keyboard(user_id: int):
    buttons = [
        [KeyboardButton(text="🖨️ Печать")],
        [KeyboardButton(text="📄 Сканирование")],
        [KeyboardButton(text="💰 Прайс")]
    ]
    if user_id in ADMINS:
        buttons.append([KeyboardButton(text="👨‍💻 Админ-режим")])
    return ReplyKeyboardMarkup(
        keyboard=buttons,
        resize_keyboard=True,
        input_field_placeholder="Выберите действие ниже"
    )

# Инлайн-клавиатура для выбора количества копий
def copy_selector(max_copies=5):
    kb = InlineKeyboardBuilder()
    for i in range(1, max_copies + 1):
        kb.button(text=f"{i} коп.", callback_data=f"copies_{i}")
    return kb.as_markup()

def confirm_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Начать печать", callback_data="start_print")],
        [InlineKeyboardButton(text="🔙 В главное меню", callback_data="back_to_menu")]
    ])