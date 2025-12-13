"""
[PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

Интеграция pdf2docx для идеального сохранения таблиц.
Основано на: https://github.com/dothinking/pdf2docx
"""

from __future__ import annotations

from typing import Optional
from pathlib import Path
import os


def convert_pdf_to_docx_via_pdf2docx(
    pdf_path: str,
    docx_path: str,
    start_page: int = 1,
    end_page: Optional[int] = None,
    tables_only: bool = False
) -> bool:
    """
    Конвертирует PDF в DOCX через pdf2docx с идеальным сохранением таблиц.
    
    Args:
        pdf_path: путь к PDF
        docx_path: путь для сохранения DOCX
        start_page: начальная страница (1-based)
        end_page: конечная страница (None = до конца)
        tables_only: конвертировать только таблицы
    
    Returns:
        True если успешно, False если pdf2docx не установлен
    """
    try:
        from pdf2docx import Converter  # type: ignore
    except ImportError:
        return False
    
    try:
        cv = Converter(pdf_path)
        
        # Конвертируем с опциями
        cv.convert(
            docx_path,
            start=start_page,
            end=end_page,
            pages=None,  # все страницы если не указан диапазон
        )
        
        cv.close()
        return True
    except Exception as e:
        print(f"[WARN] pdf2docx conversion failed: {e}")
        return False


def extract_tables_via_pdf2docx(pdf_path: str, page_num: int) -> list:
    """
    Извлекает таблицы со страницы через pdf2docx.
    Автоопределение merged cells и сохранение стилей.
    """
    try:
        from pdf2docx import Converter  # type: ignore
    except ImportError:
        return []
    
    try:
        cv = Converter(pdf_path)
        tables = cv.extract_tables(start=page_num, end=page_num)
        cv.close()
        return tables[0] if tables else []
    except Exception:
        return []

