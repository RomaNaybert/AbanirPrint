import win32print
import datetime

import wmi
import win32print

# Расшифровка статусов WMI
DETECTED_ERROR_STATES = {
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

PRINTER_STATUSES = {
    1: "Другое",
    2: "Неизвестно",
    3: "Идёт печать",
    4: "Ожидание",
    5: "Завершено",
    6: "Ошибка",
    7: "Вне сети",
    8: "Пауза",
    9: "Блокировка бумаги",
    10: "Удаление",
    11: "Нет ответа",
    12: "Невозможно подключиться",
    13: "Неисправность",
    14: "Предупреждение",
    15: "Проверка",
    16: "ОК"
}

from config import PRINTER_NAME

from services.printer_config import get_saved_printer_name

import subprocess

def get_error_state_via_wmic(printer_name: str) -> int | None:
    try:
        result = subprocess.run(
            ["wmic", "printer", "where", f"Name='{printer_name}'", "get", "DetectedErrorState"],
            capture_output=True,
            text=True,
            timeout=5
        )
        for line in result.stdout.splitlines():
            line = line.strip()
            if line.isdigit():
                return int(line)
    except Exception as e:
        print(f"[get_error_state_via_wmic] Ошибка: {e}")
    return None
import win32print

PRINTER_STATUS_FLAGS = {
    0x00000002: "Ошибка",
    0x00000004: "Требует внимания",
    0x00000008: "Бумага загружена",
    0x00000010: "Нет бумаги",
    0x00000020: "Нет тонера",
    0x00000200: "Печать приостановлена",
    0x00080000: "Занят",
    0x00200000: "Нет подключения",
    0x00000100: "Открыта крышка",
    0x00000040: "Бумага замята",
    0x00000080: "Печать завершена",
}

def get_printer_real_status(printer_name: str = None) -> list[str]:
    if not printer_name:
        printer_name = win32print.GetDefaultPrinter()
    hPrinter = win32print.OpenPrinter(printer_name)
    info = win32print.GetPrinter(hPrinter, 2)  # level 2 contains Status
    status_flags = info["Status"]
    win32print.ClosePrinter(hPrinter)

    statuses = []
    for flag, description in PRINTER_STATUS_FLAGS.items():
        if status_flags & flag:
            statuses.append(description)

    return statuses or ["Статус неизвестен"]
def get_printer_status():
    try:
        printer_name = get_saved_printer_name()
        if not printer_name:
            return None

        hPrinter = win32print.OpenPrinter(printer_name)
        info = win32print.GetPrinter(hPrinter, 2)
        status_flags = info["Status"]
        win32print.ClosePrinter(hPrinter)

        real_statuses = []
        for flag, desc in PRINTER_STATUS_FLAGS.items():
            if status_flags & flag:
                real_statuses.append(desc)

        return {
            "name": printer_name,
            "status_flags": real_statuses or ["Статус неизвестен"],
            "online": "Нет подключения" not in real_statuses,
            "error": ", ".join(real_statuses) if real_statuses else "Ошибок нет"
        }

    except Exception as e:
        return {
            "name": "Неизвестно",
            "status_flags": ["Ошибка получения статуса"],
            "online": False,
            "error": str(e)
        }

def get_print_queue():
    try:
        printer_name = get_saved_printer_name()
        if not printer_name:
            return []
        p = win32print.OpenPrinter(printer_name)
        jobs = win32print.EnumJobs(p, 0, 99, 1)
        return [
            {
                "doc": job["pDocument"],
                "status": job["Status"],
                "submitted_by": job["pUserName"]
            } for job in jobs
        ]
    except:
        return []

