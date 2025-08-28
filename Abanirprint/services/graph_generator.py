import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
from collections import Counter
from services.history_logger import safe_load_history
import matplotlib.ticker as ticker


import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
from datetime import datetime, timedelta
from collections import Counter
from services.history_logger import safe_load_history


def generate_stats_chart(period: str, output_path: str = "chart.png"):
    history = safe_load_history()
    now = datetime.now()

    def in_range(dt: datetime) -> bool:
        if period == "day":
            return dt.date() == now.date()
        elif period == "week":
            return dt >= now - timedelta(days=7)
        elif period == "month":
            return dt >= now - timedelta(days=30)
        return False

    filtered = []
    for entry in history:
        try:
            dt = datetime.strptime(entry["datetime"], "%Y-%m-%d %H:%M:%S")
            if in_range(dt):
                filtered.append((dt, entry.get("action")))
        except:
            continue

    # Группировка
    buckets = {}
    if period == "day":
        for hour in range(24):
            buckets[f"{hour}:00"] = Counter()
        for dt, action in filtered:
            buckets[f"{dt.hour}:00"][action] += 1
    elif period == "week":
        weekdays_rus = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
        for i in range(7):
            day_obj = now - timedelta(days=6 - i)
            buckets[weekdays_rus[day_obj.weekday()]] = Counter()
        for dt, action in filtered:
            buckets[weekdays_rus[dt.weekday()]][action] += 1
    elif period == "month":
        for i in range(1, 32):
            buckets[str(i)] = Counter()
        for dt, action in filtered:
            buckets[str(dt.day)][action] += 1

    labels = list(buckets.keys())
    prints = np.array([buckets[k].get("print", 0) for k in labels])
    scans = np.array([buckets[k].get("scan", 0) for k in labels])
    combos = np.array([buckets[k].get("scan_and_print", 0) for k in labels])

    x = np.arange(len(labels))
    width = 0.6
    bottom = np.zeros(len(labels))

    fig, ax = plt.subplots(figsize=(12, 6))

    # Пастельные цвета
    color_print = "#A0C4FF"      # светло-синий
    color_scan = "#B9FBC0"       # светло-зелёный
    color_combo = "#FFD6A5"      # светло-оранжевый

    p1 = ax.bar(x, prints, width, label="Печать", color=color_print, bottom=bottom)
    bottom += prints
    p2 = ax.bar(x, scans, width, label="Скан", color=color_scan, bottom=bottom)
    bottom += scans
    p3 = ax.bar(x, combos, width, label="Скан + Печать", color=color_combo, bottom=bottom)

    # Подписи на каждом отрезке
    def add_labels(bars, heights):
        for bar, height in zip(bars, heights):
            if height > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_y() + height / 2,
                    str(int(height)),
                    ha='center',
                    va='center',
                    fontsize=8,
                    color='black'
                )

    add_labels(p1, prints)
    add_labels(p2, scans)
    add_labels(p3, combos)

    # Текст и стиль
    ax.set_xlabel("Период")
    ax.set_ylabel("Кол-во заказов")

    period_titles = {
        "day": "сегодня",
        "week": "неделю",
        "month": "месяц"
    }
    ax.set_title(f"Статистика за {period_titles.get(period, 'период')}")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=45, ha="right")

    # Целые значения по оси Y
    ax.yaxis.set_major_locator(ticker.MultipleLocator(1))

    # Сетка
    ax.yaxis.grid(True, linestyle='--', alpha=0.6)

    ax.legend()
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()

import matplotlib.pyplot as plt
from collections import Counter
import numpy as np
from services.history_logger import safe_load_history


def generate_pie_chart_for_all_time(output_path: str = "chart_all_time_pie.png"):
    history = safe_load_history()
    stats = Counter(entry["action"] for entry in history)

    # Цвета как в bar chart
    color_print = "#A0C4FF"      # светло-синий
    color_scan = "#B9FBC0"       # светло-зелёный
    color_combo = "#FFD6A5"      # светло-оранжевый

    labels = []
    sizes = []
    colors = []

    if stats.get("print", 0):
        labels.append("Печать")
        sizes.append(stats["print"])
        colors.append(color_print)

    if stats.get("scan", 0):
        labels.append("Скан")
        sizes.append(stats["scan"])
        colors.append(color_scan)

    if stats.get("scan_and_print", 0):
        labels.append("Скан + Печать")
        sizes.append(stats["scan_and_print"])
        colors.append(color_combo)

    # Построение круга
    fig, ax = plt.subplots()
    ax.pie(sizes, labels=labels, autopct="%1.1f%%", colors=colors, startangle=140)
    ax.axis("equal")
    plt.title("Распределение заказов за всё время")
    plt.tight_layout()
    plt.savefig(output_path)
    plt.close()