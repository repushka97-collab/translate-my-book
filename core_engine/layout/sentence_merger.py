# core_engine/layout/sentence_merger.py

from __future__ import annotations

from typing import List, Dict, Any
import re


# Союзы и предлоги, которые часто начинают продолжение предложения
CONTINUATION_MARKERS = {
    "и", "а", "но", "однако", "также", "кроме", "более", "менее",
    "который", "которая", "которое", "которые",
    "что", "чтобы", "когда", "где", "куда", "откуда",
    "как", "чем", "потому", "поэтому", "так", "таким",
    "при", "для", "от", "до", "из", "на", "в", "с", "по", "к",
    "это", "этот", "эта", "это", "эти",
    "тот", "та", "то", "те",
    "его", "её", "их",
    "или", "либо",
}

# Слова, которые обычно начинают новое предложение
NEW_SENTENCE_MARKERS = {
    "кроме", "однако", "но", "а", "и",  # Могут быть и в начале
    "таким", "таким образом", "в результате", "следовательно",
    "во-первых", "во-вторых", "в-третьих",
    "кроме того", "более того", "к тому же",
}

# Признаки незавершенного предложения
INCOMPLETE_SENTENCE_PATTERNS = [
    r",\s*$",  # Заканчивается запятой
    r";\s*$",  # Заканчивается точкой с запятой
    r":\s*$",  # Заканчивается двоеточием
    r"\s+и\s*$",  # Заканчивается "и"
    r"\s+или\s*$",  # Заканчивается "или"
    r"\s+а\s*$",  # Заканчивается "а"
    r"\s+но\s*$",  # Заканчивается "но"
    r"\s+что\s*$",  # Заканчивается "что"
    r"\s+который\s*$",  # Заканчивается "который"
    r"\s+чтобы\s*$",  # Заканчивается "чтобы"
]


def looks_like_sentence_continuation(prev_text: str, current_text: str) -> bool:
    """
    Определяет, является ли current_text продолжением prev_text.
    Использует контекстный анализ: пунктуация, регистр, маркеры.
    """
    if not prev_text or not current_text:
        return False
    
    prev = prev_text.strip()
    curr = current_text.strip()
    
    # 1. Предыдущий текст заканчивается на незавершенное предложение
    prev_ends_complete = prev and prev[-1] in ".!?"
    if prev_ends_complete:
        return False  # Предложение завершено
    
    # 2. Текущий текст начинается с маленькой буквы - вероятно продолжение
    if curr and curr[0].islower():
        # Но проверяем маркеры нового предложения
        first_word = curr.split()[0].lower() if curr.split() else ""
        if first_word in NEW_SENTENCE_MARKERS and len(curr) > 30:
            return False  # Это новое предложение
        return True
    
    # 3. Предыдущий текст заканчивается на маркер незавершенного предложения
    for pattern in INCOMPLETE_SENTENCE_PATTERNS:
        if re.search(pattern, prev):
            return True
    
    # 4. Текущий текст начинается с маркера продолжения
    first_word = curr.split()[0].lower() if curr.split() else ""
    if first_word in CONTINUATION_MARKERS:
        return True
    
    # 5. Оба текста короткие - вероятно разорванное предложение
    if len(prev) < 100 and len(curr) < 60:
        # Проверяем что предыдущий не заканчивается на точку
        if not prev_ends_complete:
            return True
    
    # 6. После запятой короткий фрагмент - продолжение
    if prev and prev[-1] == "," and len(curr) < 80:
        return True
    
    return False


def merge_paragraphs(paragraphs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Улучшенное слияние разорванных предложений в параграфах.
    """
    if not paragraphs:
        return []
    
    merged = []
    
    for i, para in enumerate(paragraphs):
        if para.get("type") != "paragraph":
            merged.append(para)
            continue
        
        text = (para.get("text") or "").strip()
        if not text:
            continue
        
        # Проверяем, нужно ли объединить с предыдущим параграфом
        if merged and merged[-1].get("type") == "paragraph":
            prev_text = (merged[-1].get("text") or "").strip()
            
            if looks_like_sentence_continuation(prev_text, text):
                # Объединяем
                # Правильный пробел: если предыдущий заканчивается на знак препинания, пробел уже есть
                if prev_text and prev_text[-1] in ",;:":
                    merged[-1]["text"] = prev_text + " " + text
                else:
                    merged[-1]["text"] = prev_text + " " + text
                continue
        
        # Не объединяем - добавляем как новый параграф
        merged.append(para)
    
    return merged


def merge_paragraphs_in_stream(paragraph_stream: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Применяет слияние предложений к paragraph_stream.
    Обрабатывает только параграфы, сохраняя структуру (заголовки, списки, etc.).
    """
    result = []
    paragraph_buffer = []
    
    for para in paragraph_stream:
        if para.get("type") == "paragraph":
            paragraph_buffer.append(para)
        else:
            # Не параграф - сначала обрабатываем накопленные параграфы
            if paragraph_buffer:
                merged = merge_paragraphs(paragraph_buffer)
                result.extend(merged)
                paragraph_buffer = []
            result.append(para)
    
    # Обрабатываем оставшиеся параграфы
    if paragraph_buffer:
        merged = merge_paragraphs(paragraph_buffer)
        result.extend(merged)
    
    return result

