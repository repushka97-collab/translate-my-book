# core_engine/normalize/sentence_merger.py

from __future__ import annotations

from typing import List, Dict, Any
import re


# Союзы и предлоги, которые часто начинают продолжение предложения
CONTINUATION_MARKERS = {
    "and", "or", "but", "however", "also", "besides", "more", "less",
    "which", "that", "what", "when", "where", "how",
    "as", "than", "because", "therefore", "so", "thus",
    "at", "for", "from", "to", "in", "on", "with", "by",
    "this", "that", "these", "those",
    "his", "her", "its", "their",
    # Русские (на случай если уже переведено)
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

# Признаки незавершенного предложения
INCOMPLETE_SENTENCE_PATTERNS = [
    r",\s*$",  # Заканчивается запятой
    r";\s*$",  # Заканчивается точкой с запятой
    r":\s*$",  # Заканчивается двоеточием
    r"\s+and\s*$",  # Заканчивается "and"
    r"\s+or\s*$",  # Заканчивается "or"
    r"\s+but\s*$",  # Заканчивается "but"
    r"\s+that\s*$",  # Заканчивается "that"
    r"\s+which\s*$",  # Заканчивается "which"
    r"\s+to\s*$",  # Заканчивается "to" (инфинитив)
    # Русские
    r"\s+и\s*$",  # Заканчивается "и"
    r"\s+или\s*$",  # Заканчивается "или"
    r"\s+а\s*$",  # Заканчивается "а"
    r"\s+но\s*$",  # Заканчивается "но"
    r"\s+что\s*$",  # Заканчивается "что"
    r"\s+который\s*$",  # Заканчивается "который"
    r"\s+чтобы\s*$",  # Заканчивается "чтобы"
]


def looks_like_sentence_continuation_en(prev_text: str, current_text: str) -> bool:
    """
    Определяет, является ли current_text продолжением prev_text (для английского текста).
    Использует контекстный анализ: пунктуация, регистр, маркеры.
    """
    if not prev_text or not current_text:
        return False
    
    prev = prev_text.strip()
    curr = current_text.strip()
    
    # 1. Предыдущий текст заканчивается на завершенное предложение
    prev_ends_complete = prev and prev[-1] in ".!?"
    if prev_ends_complete:
        return False  # Предложение завершено
    
    # 2. Текущий текст начинается с маленькой буквы - вероятно продолжение
    if curr and curr[0].islower():
        return True
    
    # 3. Предыдущий текст заканчивается на маркер незавершенного предложения
    for pattern in INCOMPLETE_SENTENCE_PATTERNS:
        if re.search(pattern, prev, re.IGNORECASE):
            return True
    
    # 4. Текущий текст начинается с маркера продолжения
    first_word = curr.split()[0].lower() if curr.split() else ""
    if first_word in CONTINUATION_MARKERS:
        return True
    
    # 5. Оба текста короткие - вероятно разорванное предложение
    if len(prev) < 100 and len(curr) < 60:
        if not prev_ends_complete:
            return True
    
    # 6. После запятой короткий фрагмент - продолжение
    if prev and prev[-1] == "," and len(curr) < 80:
        return True
    
    return False


def merge_blocks_sentences(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Объединяет разорванные предложения между блоками на уровне normalize.
    Работает с normalized_text блоков.
    """
    if not blocks:
        return []
    
    merged = []
    
    for i, block in enumerate(blocks):
        # Получаем текст для анализа (normalized_text или text)
        prev_text = None
        if merged:
            prev_block = merged[-1]
            prev_text = (prev_block.get("normalized_text") or prev_block.get("text") or "").strip()
        
        current_text = (block.get("normalized_text") or block.get("text") or "").strip()
        
        # Пропускаем пустые блоки
        if not current_text:
            merged.append(block)
            continue
        
        # Проверяем, нужно ли объединить с предыдущим блоком
        if prev_text and looks_like_sentence_continuation_en(prev_text, current_text):
            # Объединяем normalized_text
            prev_normalized = merged[-1].get("normalized_text") or merged[-1].get("text", "")
            current_normalized = block.get("normalized_text") or block.get("text", "")
            
            # Правильный пробел
            if prev_normalized and prev_normalized[-1] in ",;:":
                merged_normalized = prev_normalized + " " + current_normalized
            else:
                merged_normalized = prev_normalized + " " + current_normalized
            
            # Обновляем предыдущий блок
            merged[-1]["normalized_text"] = merged_normalized
            # Также обновляем text для совместимости
            if "text" in merged[-1]:
                merged[-1]["text"] = merged_normalized
            
            # Объединяем protected_tokens если есть
            prev_tokens = merged[-1].get("metadata", {}).get("protected_tokens", [])
            current_tokens = block.get("metadata", {}).get("protected_tokens", [])
            if current_tokens:
                all_tokens = list(prev_tokens) + list(current_tokens)
                # Убираем дубликаты
                unique_tokens = []
                seen = set()
                for token in all_tokens:
                    if token not in seen:
                        unique_tokens.append(token)
                        seen.add(token)
                
                if "metadata" not in merged[-1]:
                    merged[-1]["metadata"] = {}
                merged[-1]["metadata"]["protected_tokens"] = unique_tokens
            
            continue
        
        # Не объединяем - добавляем как новый блок
        merged.append(block)
    
    return merged

