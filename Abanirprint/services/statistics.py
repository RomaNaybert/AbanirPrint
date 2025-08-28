import json
from datetime import datetime
from pathlib import Path

STAT_PATH = Path("storage/statistics.json")
STAT_PATH.parent.mkdir(exist_ok=True)

def load_stats():
    if not STAT_PATH.exists():
        return {"orders": [], "last_activity": None}
    with open(STAT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def save_stats(stats):
    with open(STAT_PATH, "w", encoding="utf-8") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)

def log_order(order_type, pages, revenue):
    stats = load_stats()
    stats["orders"].append({
        "type": order_type,
        "pages": pages,
        "revenue": revenue,
        "timestamp": datetime.now().isoformat()
    })
    stats["last_activity"] = datetime.now().isoformat()
    save_stats(stats)