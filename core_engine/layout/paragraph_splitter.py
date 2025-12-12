# core_engine/layout/paragraph_splitter.py

from __future__ import annotations

from typing import List, Dict, Any
import re


def split_mixed_paragraph(text: str) -> List[Dict[str, Any]]:
    """
    Разделяет смешанные параграфы, содержащие заголовки и текст.
    
    Примеры:
    - "упражнения: Основные понятия С H А Р Т Е R 1 Терапевтические упражнения..."
    - "1 I Р А R Т Общие понятия Терапевтические"
    
    Возвращает список параграфов с правильными типами.
    """
    if not text or len(text) < 10:
        return [{"type": "paragraph", "text": text}]
    
    result = []
    text_clean = text.strip()
    
    # Паттерны для разорванных заголовков
    # "С H А Р Т Е R 1" или "С H А П Т Е R 1"
    chapter_pattern = re.compile(r"С\s+H\s+А\s+[РP]\s+Т\s+Е\s+R\s+(\d+)", re.IGNORECASE)
    # "1 I Р А R Т" или "1 I Р А R Т Общие понятия"
    part_pattern = re.compile(r"(\d+)\s+([I1])\s+([РP]\s+[АA]\s+[RР]\s+[ТT])(?:\s+(.+))?", re.IGNORECASE)
    
    # Ищем разорванные заголовки в тексте
    chapter_match = chapter_pattern.search(text_clean)
    part_match = part_pattern.search(text_clean)
    
    if chapter_match:
        # Нашли "С H А Р Т Е R 1" - разделяем
        start_pos = chapter_match.start()
        end_pos = chapter_match.end()
        
        # Текст до заголовка
        before = text_clean[:start_pos].strip()
        if before:
            result.append({"type": "paragraph", "text": before})
        
        # Заголовок
        chapter_num = chapter_match.group(1)
        result.append({"type": "heading1", "text": f"ГЛАВА {chapter_num}"})
        
        # Текст после заголовка
        after = text_clean[end_pos:].strip()
        if after:
            result.append({"type": "paragraph", "text": after})
        
        return result if result else [{"type": "paragraph", "text": text}]
    
    if part_match:
        # Нашли "1 I Р А R Т" - разделяем
        start_pos = part_match.start()
        end_pos = part_match.end()
        
        # Текст до заголовка
        before = text_clean[:start_pos].strip()
        if before:
            result.append({"type": "paragraph", "text": before})
        
        # Заголовок
        part_num = part_match.group(2).upper()
        result.append({"type": "heading1", "text": f"ЧАСТЬ {part_num}"})
        
        # Текст после заголовка (если есть)
        after = text_clean[end_pos:].strip()
        if after:
            result.append({"type": "paragraph", "text": after})
        
        return result if result else [{"type": "paragraph", "text": text}]
    
    # Если не нашли разорванные заголовки, проверяем на смешанный контент
    # (заголовки в капсе + обычный текст)
    # Разделяем по паттерну: КАПС ТЕКСТ → заголовок + параграф
    caps_section = re.search(r"([А-ЯЁA-Z\s]{10,})\s+([а-яёА-ЯЁ][а-яёА-ЯЁ\s]{20,})", text_clean)
    if caps_section:
        caps_text = caps_section.group(1).strip()
        normal_text = caps_section.group(2).strip()
        
        # Если капс короткий - это заголовок
        if len(caps_text.split()) <= 6:
            result.append({"type": "heading2", "text": caps_text})
            if normal_text:
                result.append({"type": "paragraph", "text": normal_text})
            return result
    
    # Не нашли смешанный контент - возвращаем как есть
    return [{"type": "paragraph", "text": text}]


def split_paragraphs_with_headings(paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Проходит по параграфам и разделяет те, которые содержат смешанный контент.
    """
    result = []
    
    for para in paragraphs:
        if para.get("type") != "paragraph":
            result.append(para)
            continue
        
        text = para.get("text", "").strip()
        if not text:
            result.append(para)
            continue
        
        # Пробуем разделить смешанный параграф
        split = split_mixed_paragraph(text)
        result.extend(split)
    
    return result

