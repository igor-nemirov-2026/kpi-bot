"""Расчёт KPI из Excel и публикация в Telegram. Запускается на GitHub (Actions), на компьютере ничего ставить не нужно.

Переменные окружения (на GitHub — Settings → Secrets and variables → Actions):
  TELEGRAM_BOT_TOKEN   токен бота от @BotFather
  TELEGRAM_CHAT_ID     номер канала или группы (начинается с -100…)

Локальная проверка без отправки:  python run.py --no-telegram
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import sys
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import engine, loader, report, telegram  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="KPI → Telegram")
    ap.add_argument("--excel", default=str(ROOT / "KPI_import_template.xlsx"))
    ap.add_argument("--out", default=str(ROOT / "out"))
    ap.add_argument("--report-date", help="пересчитать на дату ДД.ММ.ГГГГ")
    ap.add_argument("--no-telegram", action="store_true")
    ap.add_argument("--no-images", action="store_true")
    a = ap.parse_args()

    cfg = tomllib.loads((ROOT / "config.toml").read_text(encoding="utf-8"))
    excel = Path(a.excel)
    data = loader.load(excel, excel.parent)          # CSV fact_daily*.csv рядом с Excel тоже читаются
    for w in data["warnings"]:
        print("Внимание:", w)
    rd = dt.datetime.strptime(a.report_date, "%d.%m.%Y").date() if a.report_date else None
    eng = engine.Engine(data, rd)
    company = str(data["settings"].get("Компания") or "Компания")
    generated = f"{dt.datetime.now():%d.%m.%Y %H:%M}"
    meta = eng.meta()
    reports = [eng.role_report(role, rc) for role, rc in cfg.get("roles", {}).items()]
    for r in reports:
        s = r["summary"]
        print(f"{r['role_name']}: зелёных {s['green']}, жёлтых {s['yellow']}, красных {s['red']}")

    out = Path(a.out)
    html = report.build_html(out / f"KPI_{meta['report_date']}.html", company, meta, reports, generated)
    print("Дашборд:", html)
    images = [] if a.no_images else report.screenshots(html, [r["role"] for r in reports], out)
    print("Картинок:", len(images))

    if a.no_telegram:
        return 0
    token, chat = os.environ.get("TELEGRAM_BOT_TOKEN"), os.environ.get("TELEGRAM_CHAT_ID")
    if not token:
        print("ОШИБКА: не задан секрет TELEGRAM_BOT_TOKEN (Settings → Secrets and variables → Actions)")
        return 1
    if not chat:
        # chat_id не задан — ищем канал/группу, куда добавлен бот (по событиям за последние 24 часа)
        chats = [c for c in telegram.find_chats(token) if c["type"] in ("channel", "supergroup", "group")]
        for c in chats:
            print(f"Найден чат: {c['title']}  chat_id = {c['id']}  ({c['type']})")
        if len(chats) != 1:
            print("ОШИБКА: " + ("бот не видит ни одного канала — напишите в канал любое сообщение и запустите снова"
                                if not chats else "бот состоит в нескольких чатах — впишите нужный chat_id из списка выше в секрет TELEGRAM_CHAT_ID"))
            return 1
        chat = str(chats[0]["id"])
        print(f"Публикую в «{chats[0]['title']}». Чтобы закрепить, впишите {chat} в секрет TELEGRAM_CHAT_ID.")
    tg = cfg.get("telegram", {})
    msg = telegram.build_posts(company, meta, reports, "", {}, tg.get("max_alerts", 3))
    for text in msg["posts"]:
        telegram.send(token, chat, text)
    if images:
        telegram.send_photos(token, chat, images, [f"{r['role_name']}" for r in reports])
    telegram.send_document(token, chat, html, "📎 Полный дашборд: откройте файл — вкладки CFO, Собственник, Коммерция, Закупки")
    print("Telegram: отправлено")
    return 0


if __name__ == "__main__":
    sys.exit(main())
