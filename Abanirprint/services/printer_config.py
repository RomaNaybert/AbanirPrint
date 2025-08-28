import json
import os

CONFIG_PATH = "data/printer_config.json"

def get_saved_printer_name() -> str:
    if not os.path.exists(CONFIG_PATH):
        return ""
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data.get("printer_name", "")
    except:
        return ""

def save_printer_name(name: str):
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump({"printer_name": name}, f, indent=2, ensure_ascii=False)