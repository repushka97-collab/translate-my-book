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
    Улучшенная версия: более агрессивное слияние для уменьшения potential_break.
    """
    if not prev_text or not current_text:
        return False
    
    prev = prev_text.strip()
    curr = current_text.strip()
    
    if not prev or not curr:
        return False
    
    # 1. Предыдущий текст заканчивается на завершенное предложение
    prev_ends_complete = prev[-1] in ".!?"
    if prev_ends_complete:
        # Но если следующий блок начинается с маленькой буквы - может быть продолжение
        # (например, "Dr. Smith" или "U.S.A.")
        if curr[0].islower() and len(prev) < 10:
            # Очень короткий блок с точкой - может быть аббревиатура
            return True
        return False  # Предложение завершено
    
    # 2. Текущий текст начинается с маленькой буквы - вероятно продолжение
    if curr[0].islower():
        return True
    
    # 3. Предыдущий текст заканчивается на маркер незавершенного предложения
    for pattern in INCOMPLETE_SENTENCE_PATTERNS:
        if re.search(pattern, prev, re.IGNORECASE):
            return True
    
    # 4. Текущий текст начинается с маркера продолжения
    first_word = curr.split()[0].lower() if curr.split() else ""
    if first_word in CONTINUATION_MARKERS:
        return True
    
    # 5. УЛУЧШЕННОЕ: Если предыдущий блок длинный (>80) и не заканчивается на точку,
    # а текущий не начинается с заглавной буквы - скорее всего продолжение
    if len(prev) > 80 and not prev_ends_complete:
        # Проверяем что текущий не начинается с заглавной (кроме начала предложения)
        if not curr[0].isupper() or (curr[0].isupper() and len(curr.split()) == 1):
            # Одно слово с заглавной - может быть имя собственное, но если короткий блок - продолжение
            if len(curr) < 50:
                return True
    
    # 6. Оба текста короткие - вероятно разорванное предложение
    if len(prev) < 150 and len(curr) < 80:
        if not prev_ends_complete:
            return True
    
    # 7. После запятой/точки с запятой/двоеточия - продолжение
    if prev[-1] in ",;:":
        return True
    
    # 8. НОВОЕ: Если предыдущий блок длинный (>100) и заканчивается на пробел/дефис,
    # а текущий короткий (<100) - вероятно продолжение
    if len(prev) > 100 and len(curr) < 100:
        # Проверяем последние символы предыдущего блока
        prev_end = prev[-20:].strip() if len(prev) > 20 else prev
        if not prev_end[-1] in ".!?":
            # Не заканчивается на завершающую пунктуацию
            return True
    
    # 9. БОЛЕЕ АГРЕССИВНОЕ: Если предыдущий блок длинный (>60) без точки,
    # а текущий начинается с маленькой буквы или короткий - продолжение
    if len(prev) > 60 and not prev_ends_complete:
        if curr[0].islower() or len(curr) < 100:
            return True
    
    # 12. ЕЩЕ БОЛЕЕ АГРЕССИВНОЕ: Если предыдущий блок очень длинный (>200) без точки,
    # а текущий не начинается с заглавной буквы - почти наверняка продолжение
    if len(prev) > 200 and not prev_ends_complete:
        if not curr[0].isupper() or (curr[0].isupper() and len(curr.split()) <= 2):
            return True
    
    # 13. ЕЩЕ БОЛЕЕ АГРЕССИВНОЕ: Если предыдущий блок длинный (>100) и заканчивается на пробел/дефис,
    # а текущий не слишком длинный (<200) - вероятно продолжение
    if len(prev) > 100 and len(curr) < 200 and not prev_ends_complete:
        # Проверяем последние слова предыдущего блока
        prev_words = prev.split()
        if prev_words:
            last_word = prev_words[-1].lower()
            # Если последнее слово - предлог/союз, точно продолжение
            if last_word in {"and", "or", "but", "that", "which", "to", "for", "with", "in", "on", "at", "from", "by", "of", "as", "the", "a", "an"}:
                return True
            # Если последнее слово не заканчивается на пунктуацию - вероятно продолжение
            if not last_word[-1] in ".!?;:,":
                return True
    
    # 10. БОЛЕЕ АГРЕССИВНОЕ: Если предыдущий блок заканчивается на предлог/союз
    # (and, or, but, that, which, to, for, with, in, on, at, from, by)
    prev_last_word = prev.split()[-1].lower() if prev.split() else ""
    if prev_last_word in {"and", "or", "but", "that", "which", "to", "for", "with", "in", "on", "at", "from", "by", "of", "as"}:
        return True
    
    # 11. БОЛЕЕ АГРЕССИВНОЕ: Если текущий блок очень короткий (<40) и предыдущий не заканчивается на точку
    if len(curr) < 40 and not prev_ends_complete:
        return True
    
    return False


def merge_blocks_sentences(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Объединяет разорванные предложения между блоками на уровне normalize.
    Работает с normalized_text блоков.
    Улучшенная версия: более агрессивное слияние.
    """
    if not blocks:
        return []
    
    merged = []
    
    for i, block in enumerate(blocks):
        # Получаем текст для анализа (normalized_text или text)
        prev_text = None
        prev_block = None
        if merged:
            prev_block = merged[-1]
            prev_text = (prev_block.get("normalized_text") or prev_block.get("text") or "").strip()
        
        current_text = (block.get("normalized_text") or block.get("text") or "").strip()
        
        # Пропускаем пустые блоки
        if not current_text:
            merged.append(block)
            continue
        
        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Если блоки на одной странице и близко по order
        # и предыдущий не заканчивается на точку - более агрессивное слияние
        same_page = False
        close_order = False
        if prev_block:
            prev_page = prev_block.get("page", 0)
            prev_order = prev_block.get("order", 0)
            curr_page = block.get("page", 0)
            curr_order = block.get("order", 0)
            
            same_page = (prev_page == curr_page)
            close_order = (curr_order - prev_order <= 2)  # В пределах 2 блоков
        
        # Проверяем, нужно ли объединить с предыдущим блоком
        should_merge = False
        if prev_text:
            should_merge = looks_like_sentence_continuation_en(prev_text, current_text)
            
            # ДОПОЛНИТЕЛЬНО: Если блоки на одной странице и близко, и предыдущий длинный
            # без точки - более агрессивное слияние
            if not should_merge and same_page and close_order:
                prev_ends_punct = prev_text and prev_text[-1] in ".!?"
                if not prev_ends_punct and len(prev_text) > 60:  # Снижен порог с 80 до 60
                    # Длинный блок без точки на той же странице - вероятно продолжение
                    should_merge = True
            
            # ЕЩЕ БОЛЕЕ АГРЕССИВНОЕ: Если блоки на одной странице и предыдущий >50 без точки
            if not should_merge and same_page:
                prev_ends_punct = prev_text and prev_text[-1] in ".!?"
                if not prev_ends_punct and len(prev_text) > 50 and len(current_text) < 150:
                    # Средний блок без точки, следующий не слишком длинный - вероятно продолжение
                    should_merge = True
        
        if should_merge:
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

