from __future__ import annotations

import asyncio
import os
from pathlib import Path


def _is_playwright_available() -> bool:
    try:
        import playwright  # noqa: F401
        return True
    except Exception:
        return False


async def _convert_async(html_path: str, pdf_path: str, page_width: float = None, page_height: float = None) -> None:
    from playwright.async_api import async_playwright

    html_abs = Path(html_path).resolve().as_uri()
    pdf_out = str(Path(pdf_path).resolve())

    async with async_playwright() as p:
        # chromium is default; requires that browsers are installed
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        await page.goto(html_abs, wait_until="networkidle")
        
        # Улучшенные параметры PDF для сохранения layout
        pdf_options = {
            "path": pdf_out,
            "print_background": True,  # Сохраняем фон и цвета
            "prefer_css_page_size": False,  # Используем явные размеры
            "margin": {
                "top": "0",
                "right": "0",
                "bottom": "0",
                "left": "0",
            },
        }
        
        # Если указаны размеры страницы, используем их
        if page_width and page_height:
            # Конвертируем из точек (pt) в дюймы для Playwright
            # 1 pt = 1/72 дюйма
            width_inches = page_width / 72.0
            height_inches = page_height / 72.0
            pdf_options["width"] = f"{width_inches}in"
            pdf_options["height"] = f"{height_inches}in"
        else:
            # Дефолтные размеры A4
            pdf_options["format"] = "A4"
        
        await page.pdf(**pdf_options)
        await browser.close()


def convert_html_to_pdf(html_path: str, pdf_path: str, page_width: float = None, page_height: float = None) -> bool:
    """
    Best-effort конвертация HTML → PDF через Playwright (если установлен и есть браузер).
    Сохраняет layout, фон, и размеры страниц.
    Возвращает True при успехе, False при любой ошибке.
    
    Args:
        html_path: путь к HTML файлу
        pdf_path: путь для сохранения PDF
        page_width: ширина страницы в точках (pt), опционально
        page_height: высота страницы в точках (pt), опционально
    """
    if not _is_playwright_available():
        return False
    try:
        asyncio.run(_convert_async(html_path, pdf_path, page_width, page_height))
        return True
    except Exception as e:
        print(f"[WARN] HTML to PDF conversion failed: {e}")
        return False

