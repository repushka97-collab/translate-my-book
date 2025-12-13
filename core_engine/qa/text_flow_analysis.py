# core_engine/qa/text_flow_analysis.py
"""
[QUALITY VERIFICATION MODE] PyMuPDF Text Flow Analysis.
Проверка соответствия текстового потока оригиналу.
"""

import os
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import fitz  # PyMuPDF


def analyze_text_flow(
    original_pdf: str,
    translated_pdf: str
) -> Dict[str, Any]:
    """
    Анализирует текстовый поток и проверяет его соответствие оригиналу.
    
    Args:
        original_pdf: путь к оригинальному PDF
        translated_pdf: путь к переведенному PDF
    
    Returns:
        Словарь с метриками:
        {
            "flow_score": float (0.0-1.0),
            "hyphenation_errors": int,
            "text_overflow_count": int,
            "reading_order_preserved": bool,
            "flow_issues": List[Dict]
        }
    """
    try:
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        max_pages = min(len(doc_orig), len(doc_trans))
        
        total_blocks = 0
        hyphenation_errors = 0
        overflow_count = 0
        flow_issues = []
        reading_order_ok = True
        
        for page_num in range(max_pages):
            page_orig = doc_orig[page_num]
            page_trans = doc_trans[page_num]
            
            blocks_orig = page_orig.get_text("dict").get("blocks", [])
            blocks_trans = page_trans.get_text("dict").get("blocks", [])
            
            # Проверяем порядок чтения (LTR)
            orig_order = _get_reading_order(blocks_orig)
            trans_order = _get_reading_order(blocks_trans)
            
            if len(orig_order) != len(trans_order):
                reading_order_ok = False
                flow_issues.append({
                    "page": page_num + 1,
                    "issue": "block_count_mismatch",
                    "original_count": len(orig_order),
                    "translated_count": len(trans_order)
                })
            
            # Проверяем каждый блок
            for i, (orig_block, trans_block) in enumerate(zip(blocks_orig[:len(blocks_trans)], blocks_trans)):
                if orig_block.get("type") != 0 or trans_block.get("type") != 0:
                    continue
                
                total_blocks += 1
                
                # Проверка переносов в середине слов
                orig_text = _extract_text_from_block(orig_block)
                trans_text = _extract_text_from_block(trans_block)
                
                if _has_hyphenation_error(trans_text):
                    hyphenation_errors += 1
                    flow_issues.append({
                        "page": page_num + 1,
                        "block_index": i,
                        "issue": "hyphenation_error",
                        "text": trans_text[:50]
                    })
                
                    # Проверка переполнения текста
                    # Для flow layout ширина может быть другой (блоки занимают всю колонку)
                    # Проверяем переполнение по высоте и объему текста
                    orig_bbox = orig_block.get("bbox", [0, 0, 0, 0])
                    trans_bbox = trans_block.get("bbox", [0, 0, 0, 0])
                    
                    orig_width = orig_bbox[2] - orig_bbox[0]
                    orig_height = orig_bbox[3] - orig_bbox[1]
                    trans_width = trans_bbox[2] - trans_bbox[0]
                    trans_height = trans_bbox[3] - trans_bbox[1]
                    
                    orig_area = orig_width * orig_height
                    trans_area = trans_width * trans_height
                    
                    # Проверяем переполнение: если площадь увеличилась более чем в 2 раза
                    # ИЛИ высота увеличилась более чем в 2 раза (при условии что оригинал не был очень маленьким)
                    if (trans_area > orig_area * 2.0 and orig_area > 100) or \
                       (trans_height > orig_height * 2.0 and orig_height > 10):
                        overflow_count += 1
                        flow_issues.append({
                            "page": page_num + 1,
                            "block_index": i,
                            "issue": "text_overflow",
                            "original_width": orig_width,
                            "original_height": orig_height,
                            "translated_width": trans_width,
                            "translated_height": trans_height,
                            "area_ratio": trans_area / orig_area if orig_area > 0 else 0
                        })
        
        # Вычисляем общий score
        flow_score = 1.0
        if total_blocks > 0:
            error_rate = (hyphenation_errors + overflow_count) / total_blocks
            flow_score = max(0.0, 1.0 - error_rate)
        
        if not reading_order_ok:
            flow_score *= 0.9  # Штраф за нарушение порядка
        
        doc_orig.close()
        doc_trans.close()
        
        return {
            "flow_score": max(0.0, min(1.0, flow_score)),
            "hyphenation_errors": hyphenation_errors,
            "text_overflow_count": overflow_count,
            "reading_order_preserved": reading_order_ok,
            "flow_issues": flow_issues[:50],  # Первые 50 для отчета
            "total_blocks_checked": total_blocks
        }
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[TextFlow] Error: {e}\n")
        return {
            "flow_score": 0.0,
            "hyphenation_errors": 0,
            "text_overflow_count": 0,
            "reading_order_preserved": False,
            "flow_issues": [],
            "total_blocks_checked": 0,
            "error": str(e)
        }


def _get_reading_order(blocks: List[Dict]) -> List[int]:
    """Определяет порядок чтения блоков (сверху вниз, слева направо)."""
    block_positions = []
    for i, block in enumerate(blocks):
        if block.get("type") == 0:  # текстовый блок
            bbox = block.get("bbox", [0, 0, 0, 0])
            # Используем верхний левый угол для сортировки
            block_positions.append((bbox[1], bbox[0], i))  # y, x, index
    
    # Сортируем по Y (сверху вниз), затем по X (слева направо)
    block_positions.sort()
    return [idx for _, _, idx in block_positions]


def _has_hyphenation_error(text: str) -> bool:
    """Проверяет наличие ошибок переноса."""
    if not text:
        return False
    
    # Ищем подозрительные паттерны переноса
    # Перенос в середине слова (не на дефис)
    lines = text.split("\n")
    for line in lines:
        # Проверяем, не заканчивается ли строка на середине слова
        if line and not line[-1] in ".,;:!?—–- ":
            # Если следующая строка начинается с маленькой буквы, возможно это перенос
            # (упрощенная эвристика)
            pass
    
    # Ищем дефисы в конце строк (кроме нормальных дефисов)
    for i, line in enumerate(lines[:-1]):
        if line.endswith("-") and len(line) > 3:
            next_line = lines[i + 1] if i + 1 < len(lines) else ""
            if next_line and next_line[0].islower():
                # Возможно, это перенос слова
                return True
    
    return False


def _extract_text_from_block(block: Dict[str, Any]) -> str:
    """Извлекает текст из блока."""
    text = ""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text += span.get("text", "")
    return text.strip()

