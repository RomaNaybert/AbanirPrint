import json
import os
from datetime import datetime

HISTORY_FILE = "data/history.json"

def safe_save_action(user_id: int, action: str, details: dict):
    os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)

    entry = {
        "user_id": user_id,
        "action": action,
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "details": details
    }

    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                history = json.load(f)

        history.append(entry)

        with open(HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2, ensure_ascii=False)

        print("[history_logger] Записано OK")
    except Exception as e:
        print(f"[history_logger] Ошибка записи: {e}")

def safe_load_history() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []

    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"[history_logger] Ошибка чтения истории: {e}")
        return []