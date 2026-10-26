"""Один HTML-файл с дашбордами всех ролей (данные встроены) и картинки PNG для Telegram."""
from __future__ import annotations

import json
from pathlib import Path

TEMPLATE = Path(__file__).resolve().parent


def build_html(out_file: Path, company: str, meta: dict, reports: list[dict], generated_at: str) -> Path:
    html = (TEMPLATE / "dashboard.html").read_text(encoding="utf-8")
    css = (TEMPLATE / "style.css").read_text(encoding="utf-8")
    js = (TEMPLATE / "app.js").read_text(encoding="utf-8")
    data = json.dumps({"company": company, "generated_at": generated_at, "meta": meta, "reports": reports},
                      ensure_ascii=False).replace("</", "<\\/")
    html = html.replace("/*STYLE*/", css).replace("/*DATA*/", data).replace("/*APP*/", js)
    out_file = Path(out_file)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(html, encoding="utf-8")
    return out_file


def screenshots(html_file: Path, roles: list[str], out_dir: Path) -> list[Path]:
    """PNG-картинка дашборда каждой роли (компактная таблица). Нужен playwright; без него — пустой список."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return []
    out = []
    url = Path(html_file).resolve().as_uri()
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        for role in roles:
            page.goto(f"{url}?role={role}&view=compact&shot=1")
            page.wait_for_timeout(500)
            png = Path(out_dir) / f"{role}.png"
            page.screenshot(path=str(png), full_page=True)
            out.append(png)
        browser.close()
    return out
