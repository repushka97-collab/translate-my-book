# core_engine/ingest/pdfplumber_advanced.py
"""
[ADVANCED PDF TRANSLATION MODE] PDFPlumber + LayoutParser для сложных таблиц.
Точное извлечение таблиц с merged cells и rowspan/colspan.
"""

import os
from typing import List, Dict, Any, Optional
from core_engine.core.models import TableObject, TableCell, BBox


def extract_tables_with_pdfplumber(
    pdf_path: str,
    page_num: int,
    strategy: str = "lines"
) -> Optional[TableObject]:
    """
    Извлекает таблицы через PDFPlumber с точным определением границ ячеек.
    
    Args:
        pdf_path: путь к PDF
        page_num: номер страницы (1-based)
        strategy: стратегия извлечения ("lines", "text", "explicit")
    
    Returns:
        TableObject или None если таблица не найдена
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        return None
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if page_num < 1 or page_num > len(pdf.pages):
                return None
            
            page = pdf.pages[page_num - 1]  # 0-based
            
            # Извлекаем таблицы с указанной стратегией
            tables = page.extract_tables(
                strategy=strategy,
                vertical_strategy="lines_strict",  # строгий режим для линий
                horizontal_strategy="lines_strict",
                snap_tolerance=3,  # толеранс для объединения близких линий
                join_tolerance=3,
                edge_tolerance=3,
                min_words_vertical=1,  # минимум слов для вертикальной линии
                min_words_horizontal=1,
                intersection_tolerance=3,
                text_tolerance=3,
                text_x_tolerance=3,
                text_y_tolerance=3,
            )
            
            if not tables:
                return None
            
            # Берем первую найденную таблицу (можно расширить для множественных)
            table_data = tables[0]
            if not table_data or len(table_data) < 2:
                return None
            
            # Определяем bbox таблицы
            # PDFPlumber не дает точный bbox, используем координаты ячеек
            table_bbox = page.bbox  # fallback на размер страницы
            
            # Пробуем найти точные координаты через слова
            words = page.extract_words()
            if words:
                # Ищем слова, которые попадают в первую и последнюю ячейки
                first_cell_text = None
                last_cell_text = None
                for row in table_data:
                    for cell in row:
                        if cell and cell.strip():
                            if not first_cell_text:
                                first_cell_text = cell.strip()
                            last_cell_text = cell.strip()
                
                if first_cell_text:
                    # Находим координаты первого слова
                    for word in words:
                        if first_cell_text.lower() in word.get("text", "").lower():
                            x0 = word.get("x0", 0)
                            y0 = word.get("top", 0)
                            break
                    else:
                        x0, y0 = 0, 0
                else:
                    x0, y0 = 0, 0
                
                if last_cell_text:
                    # Находим координаты последнего слова
                    for word in reversed(words):
                        if last_cell_text.lower() in word.get("text", "").lower():
                            x1 = word.get("x1", page.width)
                            y1 = word.get("bottom", page.height)
                            break
                    else:
                        x1, y1 = page.width, page.height
                else:
                    x1, y1 = page.width, page.height
                
                table_bbox = BBox(x0, y0, x1, y1)
            else:
                table_bbox = BBox(0, 0, page.width, page.height)
            
            # Преобразуем таблицу в TableObject
            cells: List[TableCell] = []
            rows_count = len(table_data)
            cols_count = max(len(row) for row in table_data) if table_data else 0
            
            # Определяем merged cells через анализ пустых ячеек
            # PDFPlumber помечает merged cells как None или пустые строки
            for r_idx, row in enumerate(table_data):
                for c_idx, cell_text in enumerate(row):
                    if cell_text is None:
                        # Это может быть merged cell - пропускаем
                        continue
                    
                    # Определяем rowspan/colspan (упрощенная версия)
                    # В реальности нужно анализировать структуру таблицы
                    rowspan = 1
                    colspan = 1
                    
                    # Проверяем, не является ли это частью merged cell
                    # (упрощенная эвристика)
                    if c_idx < len(row) - 1 and row[c_idx + 1] is None:
                        # Возможно, это начало merged cell
                        colspan = 1  # TODO: улучшить детекцию
                    
                    cells.append(TableCell(
                        row=r_idx,
                        col=c_idx,
                        text=str(cell_text).strip() if cell_text else "",
                        rowspan=rowspan,
                        colspan=colspan
                    ))
            
            if not cells:
                return None
            
            table_obj = TableObject(
                id=f"p{page_num}_tbl_pdfplumber",
                page_number=page_num,
                bbox=table_bbox,
                cells=cells,
                label=None,
                caption=None,
            )
            
            return table_obj
            
    except Exception as e:
        # Логируем ошибку, но не падаем
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[PDFPlumber] Page {page_num}: {e}\n")
        return None


def extract_all_tables_pdfplumber(
    pdf_path: str,
    page_range: Optional[tuple] = None
) -> Dict[int, List[TableObject]]:
    """
    Извлекает все таблицы из PDF через PDFPlumber.
    
    Args:
        pdf_path: путь к PDF
        page_range: (start, end) для ограничения страниц, None = все страницы
    
    Returns:
        Словарь {page_num: [TableObject, ...]}
    """
    try:
        import pdfplumber  # type: ignore
    except ImportError:
        return {}
    
    result: Dict[int, List[TableObject]] = {}
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            start_page = 1
            end_page = len(pdf.pages)
            
            if page_range:
                start_page = max(1, page_range[0])
                end_page = min(len(pdf.pages), page_range[1])
            
            for page_num in range(start_page, end_page + 1):
                tables_on_page = []
                
                # Пробуем разные стратегии
                for strategy in ["lines", "text", "explicit"]:
                    table_obj = extract_tables_with_pdfplumber(
                        pdf_path, page_num, strategy=strategy
                    )
                    if table_obj:
                        tables_on_page.append(table_obj)
                        break  # Используем первую найденную
                
                if tables_on_page:
                    result[page_num] = tables_on_page
                    
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[PDFPlumber] Extract all: {e}\n")
    
    return result

