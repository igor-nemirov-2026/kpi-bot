"""Публикация сводки KPI в Telegram-канал или группу."""
from __future__ import annotations

import html
import time
from pathlib import Path

import requests

API = "https://api.telegram.org/bot{token}/{method}"
DOT = {"green": "🟢", "yellow": "🟡", "red": "🔴", "na": "⚪"}
ICON = {"cfo": "💼", "owner": "👑", "sales": "🛒", "purchase": "📦"}


def _fmt(v, d=1):
    if v is None:
        return "—"
    return f"{v:,.{d}f}".replace(",", " ").replace(".", ",")


def _pct(v):
    return "—" if v is None else _fmt(v * 100, 1) + "%"


def build_posts(company: str, meta: dict, reports: list[dict], site_url: str, ai: dict | None = None,
                max_alerts: int = 3) -> dict:
    """Тексты постов: head — шапка с ключевыми цифрами, roles — блок по каждой роли,
    posts — готовые посты для канала (склеены, каждый до 4000 символов)."""
    e = html.escape
    d = meta["report_date"]
    date_ru = f"{d[8:10]}.{d[5:7]}.{d[0:4]}"
    head = (f"📊 <b>KPI {e(company)} на {date_ru}</b>\n"
            f"{e(meta['month_name'])}: прошло {meta['wd_elapsed']} из {meta['wd_month']} рабочих дней\n")
    # ключевые цифры — из первой роли, где есть выручка
    key_lines = []
    seen = set()
    for rep in reports:
        for r in rep["kpis"]:
            if r["id"] in ("rev", "gm", "ebitda") and r["id"] not in seen:
                seen.add(r["id"])
                unit = "" if r["unit"] == "%" else " " + r["unit"]
                val = _fmt(r["mtd"], 2 if r["unit"] == "%" else 1) + ("%" if r["unit"] == "%" else "")
                key_lines.append(f"{DOT[r['light_month']]} {e(r['kpi'])}: <b>{val}{e(unit)}</b> "
                                 f"· прогноз месяца {_pct(r['fc_month_pct'])} плана")
    posts_all = [head + "\n" + "\n".join(key_lines)]
    per_role = []
    for rep in reports:
        s = rep["summary"]
        lines = [f"\n{ICON.get(rep['role'], '•')} <b>{e(rep['role_name'])}</b>  "
                 f"🟢 {s['green']} · 🟡 {s['yellow']} · 🔴 {s['red']}"]
        for a in rep["alerts"][:max_alerts]:
            lines.append(f"{DOT[a['light']]} <b>{e(a['kpi'])}</b>: {e(a['text'])}")
        if ai and ai.get(rep["role"]):
            lines.append(f"🤖 <i>{e(ai[rep['role']])}</i>")
        if site_url:
            lines.append(f'<a href="{e(site_url.rstrip("/"))}/{rep["role"]}/">Открыть дашборд {e(rep["role_name"])} →</a>')
        block = "\n".join(lines)
        per_role.append((rep["role"], block))
    # склейка в посты до 4000 символов (лимит Telegram 4096)
    posts: list[tuple[str, str]] = []
    cur = posts_all[0]
    for _, block in per_role:
        if len(cur) + len(block) > 3900:
            posts.append(("all", cur))
            cur = block.lstrip("\n")
        else:
            cur += "\n" + block
    posts.append(("all", cur))
    return {"head": posts_all[0], "roles": per_role, "posts": [t for _, t in posts]}


def send(token: str, chat_id: str, text: str, thread_id: int | None = None, retries: int = 3) -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
    if thread_id:
        payload["message_thread_id"] = thread_id
    last = None
    for attempt in range(retries):
        try:
            r = requests.post(API.format(token=token, method="sendMessage"), json=payload, timeout=30)
            data = r.json()
            if data.get("ok"):
                return
            if r.status_code == 429:
                time.sleep(int(data.get("parameters", {}).get("retry_after", 5)))
                continue
            last = data.get("description", r.text)
            break
        except requests.RequestException as ex:  # нет интернета — подождать и повторить
            last = str(ex)
            time.sleep(10 * (attempt + 1))
    raise RuntimeError(f"Telegram не принял сообщение: {last}")


def find_chats(token: str) -> list[dict]:
    """Список чатов и каналов, где бот видел сообщения (для поиска chat_id)."""
    r = requests.get(API.format(token=token, method="getUpdates"), timeout=30).json()
    if not r.get("ok"):
        raise RuntimeError(r.get("description"))
    chats = {}
    for u in r["result"]:
        for key in ("message", "channel_post", "my_chat_member", "edited_message"):
            msg = u.get(key)
            if msg and "chat" in msg:
                c = msg["chat"]
                chats[c["id"]] = {"id": c["id"], "type": c.get("type"), "title": c.get("title") or c.get("username"),
                                  "thread_id": msg.get("message_thread_id")}
    return list(chats.values())


def _post(token, method, data, files=None):
    r = requests.post(API.format(token=token, method=method), data=data, files=files, timeout=120)
    js = r.json()
    if not js.get("ok"):
        raise RuntimeError(f"Telegram ({method}): {js.get('description', r.text)}")
    return js


def send_document(token: str, chat_id: str, path, caption: str = "") -> None:
    with open(path, "rb") as f:
        _post(token, "sendDocument", {"chat_id": chat_id, "caption": caption}, {"document": (Path(path).name, f)})


def send_photos(token: str, chat_id: str, paths, captions) -> None:
    """Альбом картинок (до 10). Длинные картинки Telegram может не принять как фото — тогда шлём файлами."""
    import json as _json
    files, media = {}, []
    for i, (p, c) in enumerate(zip(paths, captions)):
        files[f"f{i}"] = open(p, "rb")
        media.append({"type": "photo", "media": f"attach://f{i}", "caption": c})
    try:
        _post(token, "sendMediaGroup", {"chat_id": chat_id, "media": _json.dumps(media, ensure_ascii=False)}, files)
    except RuntimeError:
        for f in files.values():
            f.seek(0)
        for i, m in enumerate(media):
            m["type"] = "document"
        _post(token, "sendMediaGroup", {"chat_id": chat_id, "media": _json.dumps(media, ensure_ascii=False)}, files)
    finally:
        for f in files.values():
            f.close()
