# services/decorators.py
# from functools import wraps
# from services.notify_admins import notify_admins_about_print_error
# from datetime import datetime
#
# def notify_on_failure(action: str):
#     """
#     Оборачивает функцию: при ошибке отправит уведомление админам с деталями.
#     Аргументы функции должны включать: user_id, bot и details (dict).
#     """
#     def decorator(func):
#         @wraps(func)
#         async def wrapper(*args, **kwargs):
#             try:
#                 return await func(*args, **kwargs)
#             except Exception as e:
#                 bot = kwargs.get("bot")
#                 user_id = kwargs.get("user_id") or kwargs.get("user") or "неизвестно"
#                 details = kwargs.get("details") or {}
#
#                 if bot:
#                     await notify_admins_about_print_error(
#                         bot=bot,
#                         user_id=user_id,
#                         action=action,
#                         details=details,
#                         error_message=str(e)
#                     )
#                 raise
#         return wrapper
#     return decorator