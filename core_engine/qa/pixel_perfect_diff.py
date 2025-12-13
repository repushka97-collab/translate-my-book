# core_engine/qa/pixel_perfect_diff.py
"""
[QUALITY VERIFICATION MODE] pdf-diff + Pixel Perfect Comparison.
Пиксельное смещение элементов (точность до 0.1px).
"""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import fitz  # PyMuPDF


def compare_pdfs_pixel_perfect(
    original_pdf: str,
    translated_pdf: str,
    max_shift: float = 1.0,
    max_displacement: float = 2.0
) -> Dict[str, Any]:
    """
    Сравнивает PDF файлы с пиксельной точностью.
    
    Args:
        original_pdf: путь к оригинальному PDF
        translated_pdf: путь к переведенному PDF
        max_shift: допустимое смещение в px
        max_displacement: допустимое смещение блоков в px
    
    Returns:
        Словарь с метриками:
        {
            "shift_score": float (0.0-1.0, идеал = 1.0),
            "element_loss": float (0.0-1.0, потерянных элементов),
            "text_overflow": float (0.0-1.0, процент текста вылезшего за границы),
            "displacements": List[Dict] (список смещенных элементов),
            "overall_score": float (общая оценка 0.0-1.0)
        }
    """
    try:
        doc_orig = fitz.open(original_pdf)
        doc_trans = fitz.open(translated_pdf)
        
        max_pages = min(len(doc_orig), len(doc_trans))
        
        total_elements = 0
        shifted_elements = 0
        lost_elements = 0
        overflow_elements = 0
        displacements = []
        
        for page_num in range(max_pages):
            page_orig = doc_orig[page_num]
            page_trans = doc_trans[page_num]
            
            # Получаем блоки текста
            blocks_orig = page_orig.get_text("dict").get("blocks", [])
            blocks_trans = page_trans.get_text("dict").get("blocks", [])
            
            # Определяем режим сравнения: flow layout или точное позиционирование
            # Если количество блоков сильно отличается - вероятно flow layout
            is_flow_layout = abs(len(blocks_orig) - len(blocks_trans)) > len(blocks_orig) * 0.5
            
            # Создаем маппинг блоков по тексту (не по позиции, т.к. flow layout меняет позиции)
            # Используем текст как основной идентификатор
            orig_map = {}
            for i, block in enumerate(blocks_orig):
                if block.get("type") == 0:  # текстовый блок
                    text = _extract_text_from_block(block)
                    if text and len(text.strip()) > 3:  # Минимум 3 символа
                        # Нормализуем текст для сравнения (убираем пробелы, приводим к нижнему регистру)
                        text_normalized = "".join(text.lower().split())[:50]  # Первые 50 символов
                        if text_normalized:
                            # Используем текст как ключ, но сохраняем все варианты
                            if text_normalized not in orig_map:
                                orig_map[text_normalized] = []
                            orig_map[text_normalized].append({"block": block, "index": i, "text": text})
            
            trans_map = {}
            for i, block in enumerate(blocks_trans):
                if block.get("type") == 0:
                    text = _extract_text_from_block(block)
                    if text and len(text.strip()) > 3:
                        text_normalized = "".join(text.lower().split())[:50]
                        if text_normalized:
                            if text_normalized not in trans_map:
                                trans_map[text_normalized] = []
                            trans_map[text_normalized].append({"block": block, "index": i, "text": text})
            
            # Сравниваем блоки по тексту (flow layout объединяет блоки, поэтому сравниваем по содержимому)
            matched_trans_keys = set()
            
            for orig_key, orig_blocks_list in orig_map.items():
                # Берем первый блок из списка (может быть несколько с похожим текстом)
                if not orig_blocks_list:
                    continue
                
                orig_data = orig_blocks_list[0]  # Берем первый
                orig_block = orig_data["block"]
                orig_bbox = orig_block.get("bbox", [0, 0, 0, 0])
                orig_text = orig_data["text"]
                
                total_elements += 1
                
                # Ищем соответствующий блок в переведенном по тексту
                # В flow layout текст может быть объединен, поэтому ищем частичное совпадение
                best_match = None
                best_match_data = None
                best_text_similarity = 0.0
                
                for trans_key, trans_blocks_list in trans_map.items():
                    if trans_key in matched_trans_keys:
                        continue
                    
                    for trans_data in trans_blocks_list:
                        trans_text = trans_data["text"]
                        
                        # Вычисляем схожесть текста (улучшенная версия)
                        # Используем несколько методов для более точного сопоставления
                        orig_words = set(orig_text.lower().split())
                        trans_words = set(trans_text.lower().split())
                        
                        if orig_words and trans_words:
                            # Метод 1: Jaccard similarity по словам
                            common_words = orig_words & trans_words
                            union_words = orig_words | trans_words
                            jaccard_sim = len(common_words) / len(union_words) if union_words else 0.0
                            
                            # Метод 2: Проверка подстрок (для коротких текстов)
                            substring_sim = 0.0
                            if len(orig_text) > 10 and len(trans_text) > 10:
                                # Проверяем, содержит ли один текст другой
                                if orig_text.lower()[:50] in trans_text.lower() or trans_text.lower()[:50] in orig_text.lower():
                                    substring_sim = 0.8
                            
                            # Метод 3: Сравнение первых символов (для очень коротких текстов)
                            char_sim = 0.0
                            if len(orig_text) < 20 and len(trans_text) < 20:
                                # Для коротких текстов сравниваем первые символы
                                min_len = min(len(orig_text), len(trans_text))
                                if min_len > 0:
                                    matches = sum(1 for i in range(min_len) if orig_text[i].lower() == trans_text[i].lower())
                                    char_sim = matches / min_len
                            
                            # Берем максимальную схожесть
                            similarity = max(jaccard_sim, substring_sim, char_sim)
                            
                            # Для PDF_REBUILD требуем более высокую схожесть (блоки должны точно соответствовать)
                            min_similarity = 0.2 if is_flow_layout else 0.4
                            
                            if similarity > best_text_similarity and similarity > min_similarity:
                                best_text_similarity = similarity
                                best_match = trans_key
                                best_match_data = trans_data
                
                if best_match and best_match_data:
                    matched_trans_keys.add(best_match)
                    trans_block = best_match_data["block"]
                    trans_bbox = trans_block.get("bbox", [0, 0, 0, 0])
                    
                    # Проверяем смещение в зависимости от режима
                    if is_flow_layout:
                        # Для flow layout позиции могут сильно отличаться, проверяем только Y
                        dy = abs(trans_bbox[1] - orig_bbox[1])
                        if dy > max_displacement * 2:  # Удваиваем допуск для flow layout
                            shifted_elements += 1
                            displacements.append({
                                "page": page_num + 1,
                                "element_index": orig_data["index"],
                                "dx": abs(trans_bbox[0] - orig_bbox[0]),
                                "dy": dy,
                                "max_shift": dy,
                                "bbox_orig": orig_bbox,
                                "bbox_trans": trans_bbox,
                                "text_similarity": best_text_similarity,
                                "layout_mode": "flow"
                            })
                        
                        # Для flow layout проверяем переполнение по высоте
                        orig_height = orig_bbox[3] - orig_bbox[1]
                        trans_height = trans_bbox[3] - trans_bbox[1]
                        if trans_height > orig_height * 2.0 and orig_height > 10:
                            overflow_elements += 1
                    else:
                        # Для точного позиционирования проверяем и X и Y
                        dx = abs(trans_bbox[0] - orig_bbox[0])
                        dy = abs(trans_bbox[1] - orig_bbox[1])
                        max_shift_actual = max(dx, dy)
                        
                        if max_shift_actual > max_shift:
                            shifted_elements += 1
                            displacements.append({
                                "page": page_num + 1,
                                "element_index": orig_data["index"],
                                "dx": dx,
                                "dy": dy,
                                "max_shift": max_shift_actual,
                                "bbox_orig": orig_bbox,
                                "bbox_trans": trans_bbox,
                                "text_similarity": best_text_similarity,
                                "layout_mode": "precise"
                            })
                        
                        # Проверяем переполнение по ширине (только для точного позиционирования)
                        # Для PDF_REBUILD блок должен оставаться в тех же границах
                        orig_width = orig_bbox[2] - orig_bbox[0]
                        trans_width = trans_bbox[2] - trans_bbox[0]
                        
                        # Переполнение = если текст вылез за границы исходного блока
                        # Упрощенная проверка: если ширина увеличилась более чем на 5% И исходная ширина была маленькой
                        # И блок не сместился по X (иначе это другой блок)
                        if trans_width > orig_width * 1.05 and orig_width < 200 and dx < 10:
                            overflow_elements += 1
                else:
                    # Блок не найден - возможно объединен в flow layout
                    # Проверяем, не содержится ли его текст в других блоках
                    found_in_merged = False
                    for trans_key, trans_blocks_list in trans_map.items():
                        if trans_key in matched_trans_keys:
                            continue
                        for trans_data in trans_blocks_list:
                            trans_text = trans_data["text"]
                            # Проверяем частичное совпадение
                            if orig_text.lower()[:30] in trans_text.lower() or trans_text.lower()[:30] in orig_text.lower():
                                found_in_merged = True
                                break
                        if found_in_merged:
                            break
                    
                    if not found_in_merged:
                        # Используем более агрессивный поиск по всем блокам
                        best_merge_similarity = 0.0
                        best_merge_key = None
                        
                        for trans_key, trans_blocks_list in trans_map.items():
                            if trans_key in matched_trans_keys:
                                continue
                            for trans_data in trans_blocks_list:
                                trans_text = trans_data["text"]
                                
                                # Множественные методы проверки
                                # 1. Проверка подстрок
                                if len(orig_text) > 5 and len(trans_text) > 5:
                                    if orig_text.lower()[:min(50, len(orig_text))] in trans_text.lower() or \
                                       trans_text.lower()[:min(50, len(trans_text))] in orig_text.lower():
                                        similarity = 0.7
                                        if similarity > best_merge_similarity:
                                            best_merge_similarity = similarity
                                            best_merge_key = trans_key
                                            found_in_merged = True
                                
                                # 2. Проверка по словам (более мягкая)
                                orig_words = set(w.lower().strip(".,!?;:()[]{}") for w in orig_text.split() if len(w) > 2)
                                trans_words = set(w.lower().strip(".,!?;:()[]{}") for w in trans_text.split() if len(w) > 2)
                                
                                if orig_words and trans_words:
                                    common = orig_words & trans_words
                                    if len(common) >= min(2, len(orig_words) // 2):  # Хотя бы 2 слова или половина
                                        similarity = len(common) / max(len(orig_words), len(trans_words))
                                        if similarity > best_merge_similarity:
                                            best_merge_similarity = similarity
                                            best_merge_key = trans_key
                                            found_in_merged = True
                                
                                # 3. Проверка по первым символам (для очень коротких блоков)
                                if len(orig_text) < 15 and len(trans_text) < 15:
                                    min_len = min(len(orig_text), len(trans_text))
                                    if min_len >= 3:
                                        matches = sum(1 for i in range(min_len) 
                                                    if orig_text[i].lower() == trans_text[i].lower())
                                        similarity = matches / min_len
                                        if similarity > 0.5 and similarity > best_merge_similarity:
                                            best_merge_similarity = similarity
                                            best_merge_key = trans_key
                                            found_in_merged = True
                        
                        if found_in_merged and best_merge_key:
                            # Нашли объединенный блок - помечаем как использованный
                            matched_trans_keys.add(best_merge_key)
                            # Не считаем как потерянный
                        else:
                            # Действительно потерянный блок
                            lost_elements += 1
        
        # Вычисляем метрики
        shift_score = 1.0 - (shifted_elements / max(total_elements, 1))
        element_loss = lost_elements / max(total_elements, 1)
        text_overflow = overflow_elements / max(total_elements, 1)
        
        # Общая оценка (взвешенная)
        overall_score = (
            shift_score * 0.4 +  # 40% - точность позиционирования
            (1 - element_loss) * 0.3 +  # 30% - сохранение элементов
            (1 - text_overflow) * 0.3  # 30% - отсутствие переполнений
        )
        
        doc_orig.close()
        doc_trans.close()
        
        return {
            "shift_score": max(0.0, min(1.0, shift_score)),
            "element_loss": max(0.0, min(1.0, element_loss)),
            "text_overflow": max(0.0, min(1.0, text_overflow)),
            "displacements": displacements[:100],  # Первые 100 для отчета
            "overall_score": max(0.0, min(1.0, overall_score)),
            "total_elements": total_elements,
            "shifted_elements": shifted_elements,
            "lost_elements": lost_elements,
            "overflow_elements": overflow_elements
        }
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[PixelPerfect] Error: {e}\n")
        return {
            "shift_score": 0.0,
            "element_loss": 1.0,
            "text_overflow": 1.0,
            "displacements": [],
            "overall_score": 0.0,
            "error": str(e)
        }


def _extract_text_from_block(block: Dict[str, Any]) -> str:
    """Извлекает текст из блока."""
    text = ""
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            text += span.get("text", "")
    return text.strip()

