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


async def _convert_async(html_path: str, pdf_path: str) -> None:
    from playwright.async_api import async_playwright

    html_abs = Path(html_path).resolve().as_uri()
    pdf_out = str(Path(pdf_path).resolve())

    async with async_playwright() as p:
        # chromium is default; requires that browsers are installed
        browser = await p.chromium.launch(args=["--no-sandbox"])
        page = await browser.new_page()
        await page.goto(html_abs)
        await page.pdf(path=pdf_out, print_background=True)
        await browser.close()


def convert_html_to_pdf(html_path: str, pdf_path: str) -> bool:
    """
    Best-effort конвертация HTML → PDF через Playwright (если установлен и есть браузер).
    Возвращает True при успехе, False при любой ошибке.
    """
    if not _is_playwright_available():
        return False
    try:
        asyncio.run(_convert_async(html_path, pdf_path))
        return True
    except Exception:
        return False

