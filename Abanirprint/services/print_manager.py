import os
import time
import subprocess
import win32print
import win32api

SUPPORTED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp'}

import os
import time
import subprocess
import win32print
import win32api
import wmi
from datetime import datetime

from services.notify_admins import notify_admins_about_print_error
from services.printer_config import get_saved_printer_name

SUPPORTED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp'}

import pythoncom  # Добавь этот импорт
import os, time, subprocess, win32print, win32api, wmi
from datetime import datetime
from services.notify_admins import notify_admins_about_print_error
from services.printer_config import get_saved_printer_name

SUPPORTED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.bmp'}

def print_and_wait(filepaths, copies: int = 1, timeout: int = 120, user_id=None, bot=None):
    # 👇 ИНИЦИАЛИЗАЦИЯ COM ДЛЯ ПОТОКА
    pythoncom.CoInitialize()

    try:
        if isinstance(filepaths, str):
            filepaths = [filepaths]

        printer = get_saved_printer_name() or win32print.GetDefaultPrinter()
        seen_jobs = set()

        for _ in range(copies):
            for filepath in filepaths:
                filepath = os.path.abspath(filepath)
                ext = os.path.splitext(filepath)[1].lower()

                if ext == ".pdf":
                    win32api.ShellExecute(
                        0, "printto", filepath, f'"{printer}"',
                        os.path.dirname(filepath), 0
                    )
                elif ext in SUPPORTED_EXTENSIONS:
                    subprocess.Popen(
                        ["mspaint", "/pt", filepath, printer], shell=False
                    )
                else:
                    _notify_print_error(bot, user_id, "печать", {"файл": filepath}, f"Формат {ext} не поддерживается")
                    raise ValueError(f"Формат {ext} не поддерживается")

                time.sleep(1)

        wait_for_queue(printer, timeout, user_id=user_id, bot=bot, filepaths=filepaths)

    finally:
        # 👇 Освобождаем COM
        pythoncom.CoUninitialize()

from services.notify_admins import notify_admins_about_print_error
def wait_for_queue(printer: str, timeout: int, user_id=None, bot=None, filepaths=None):
    start = time.time()
    seen_jobs = set()
    c = wmi.WMI()

    while True:
        h = win32print.OpenPrinter(printer)
        jobs = win32print.EnumJobs(h, 0, -1, 1)
        win32print.ClosePrinter(h)

        current_ids = {job["JobId"] for job in jobs}
        seen_jobs |= current_ids

        # 🟢 Печать завершилась
        if seen_jobs and not (seen_jobs & current_ids):
            return

        # ⏱ Печать затянулась
        if time.time() - start > timeout:
            _notify_print_error(bot, user_id, "печать", {"файл": filepaths}, "Печать заняла слишком много времени")
            raise TimeoutError("Печать заняла слишком много времени")

        # ⚠️ Проверка состояния принтера на ошибки
        try:
            for printer_obj in c.Win32_Printer(Name=printer):
                error_code = printer_obj.DetectedErrorState
                if error_code not in (2, None):  # 2 — "Ошибок нет"
                    error_text = _decode_error(error_code)
                    _notify_print_error(bot, user_id, "печать", {"файл": filepaths}, error_text)
                    raise RuntimeError(f"Ошибка печати: {error_text}")
        except Exception as e:
            print("[wait_for_queue] Ошибка проверки статуса:", e)

        time.sleep(1)


def _decode_error(code):
    ERRORS = {
        0: "Неизвестно",
        1: "Другое",
        2: "Ошибок нет",
        3: "Мало бумаги",
        4: "Нет бумаги",
        5: "Мало тонера",
        6: "Нет тонера",
        7: "Заправка",
        8: "Ошибка в печати",
        9: "Внимание",
        10: "Неизвестная ошибка"
    }
    return ERRORS.get(code, f"Неизвестная ошибка ({code})")


def _notify_print_error(bot, user_id, action, details, error_message):
    if bot and user_id:
        try:
            from asyncio import run_coroutine_threadsafe
            coro = notify_admins_about_print_error(
                bot=bot,
                user_id=user_id,
                action=action,
                details=details,
                error_message=error_message
            )
            loop = bot.get_running_loop()
            run_coroutine_threadsafe(coro, loop)
        except Exception as e:
            print("[notify_admins] Ошибка отправки уведомления:", e)