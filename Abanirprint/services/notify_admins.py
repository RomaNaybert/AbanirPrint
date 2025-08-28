# services/notify_admins.py
# services/notify_admins.py

from config import ADMINS
from datetime import datetime

async def notify_admins_about_print_error(bot, user_id, action, details, error_message):
    text = (
        f"🚨 <b>Ошибка во время обработки заказа</b>\n\n"
        f"🧑‍💻 Пользователь: <code>{user_id}</code>\n"
        f"📌 Действие: <b>{action}</b>\n"
        f"🕓 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"🧾 Детали:\n"
    )
    for key, value in details.items():
        text += f"  • <b>{key}</b>: {value}\n"

    text += f"\n❌ <b>Ошибка:</b> <code>{error_message}</code>"

    for admin_id in ADMINS:
        try:
            await bot.send_message(admin_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"[notify_admins] Не удалось отправить сообщение админу {admin_id}: {e}")

# # utils/notifier.py
# from config import ADMINS
# from aiogram.types import Message
#
# async def notify_admins_about_print_error(bot, user_id, action, details, error_message: str):
#     from datetime import datetime
#
#     text = (
#         f"🚨 <b>Ошибка во время обработки заказа</b>\n\n"
#         f"🧑‍💻 Пользователь: <code>{user_id}</code>\n"
#         f"📌 Действие: <b>{action}</b>\n"
#         f"🕓 Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
#         f"🧾 Детали:\n"
#     )
#
#     for key, value in details.items():
#         text += f"  • <b>{key}</b>: {value}\n"
#
#     text += f"\n❌ <b>Ошибка:</b> <code>{error_message}</code>"
#
#     for admin_id in ADMINS:
#         try:
#             await bot.send_message(admin_id, text, parse_mode="HTML")
#         except Exception as e:
#             print(f"[notifier] ❌ Не удалось отправить сообщение админу {admin_id}: {e}")
#
# # services/decorators.py
# from functools import wraps
# from services.notify_admins import notify_admins_about_print_error
#
# def notify_on_failure(action: str):
#     """
#     Оборачивает функцию, чтобы при ошибке отправить уведомление админам.
#     """
#     def decorator(func):
#         @wraps(func)
#         async def wrapper(*args, **kwargs):
#             try:
#                 return await func(*args, **kwargs)
#             except Exception as e:
#                 bot = kwargs.get("bot") or args[0]
#                 user_id = kwargs.get("user_id") or kwargs.get("user") or "неизвестно"
#                 details = kwargs.get("details", {})
#                 await notify_admins_about_print_error(
#                     bot=bot,
#                     user_id=user_id,
#                     action=action,
#                     details=details,
#                     error_message=str(e)
#                 )
#                 raise
#         return wrapper
#     return decorator
#
# async def try_notify_print_error(bot, user_id, action, details, exception):
#     """
#     Уведомляет админов об ошибке при печати/скане.
#     """
#     try:
#         await notify_admins_about_print_error(
#             bot=bot,
#             user_id=user_id,
#             action=action,
#             details=details,
#             error_message=str(exception)
#         )
#     except Exception as e:
#         print(f"[try_notify_print_error] Ошибка при уведомлении админов: {e}")