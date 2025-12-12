# core_engine/translate/quality_pass.py

from __future__ import annotations

from typing import List, Dict, Any
import re


Block = Dict[str, Any]


def _cleanup_long_text(text: str) -> str:
    """
    Улучшенная эвристическая чистка:
    - схлопываем повторные пробелы;
    - убираем мусорные пробелы перед знаками препинания;
    - выправляем тройные точки и многоточия;
    - убираем странные непечатаемые пробелы;
    - исправляем артефакты NLLB;
    - нормализуем кавычки.
    """
    if not text:
        return text

    s = text

    # убираем неразрывные/странные пробелы и другие невидимые символы
    s = s.replace("\u00A0", " ").replace("\u200B", "").replace("\u2009", " ")
    s = s.replace("\u2008", " ").replace("\u2007", " ").replace("\u2006", " ")

    # схлопываем повторные пробелы
    s = re.sub(r"\s+", " ", s)

    # пробел перед знаками препинания → убираем
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)

    # пробел после открывающих скобок/кавычек
    s = re.sub(r"([\(\[\{«])\s+", r"\1", s)
    
    # пробел перед закрывающими скобками/кавычками
    s = re.sub(r"\s+([\)\]\}»])", r"\1", s)

    # нормализуем многоточие
    s = re.sub(r"\.{3,}", "…", s)

    # нормализуем кавычки (английские → русские где уместно)
    # Но только если текст в основном на кириллице
    cyr_ratio = sum(1 for c in s if "а" <= c.lower() <= "я" or c.lower() == "ё") / max(len([c for c in s if c.isalpha()]), 1)
    if cyr_ratio > 0.5:
        # В основном русский текст - нормализуем кавычки
        s = s.replace('"', '"').replace('"', '"')
        s = s.replace("'", "'").replace("'", "'")

    # исправляем артефакты типа "а а" (дублирование одиночных букв)
    s = re.sub(r"\b([а-яё])\s+\1\b", r"\1", s, flags=re.IGNORECASE)

    # обрезаем по краям
    return s.strip()


def run_quality_pass(
    blocks: List[Block],
    min_chars: int = 400,
) -> List[Block]:
    """
    Quality-pass v1: лёгкая постобработка ТОЛЬКО длинных блоков.
    Никакой магии, только чистка артефактов.

    В будущем сюда можно подвесить мощную LLM для реальной редактуры.
    """
    processed: List[Block] = []

    for b in blocks:
        text = b.get("translated_text")
        if not isinstance(text, str):
            processed.append(b)
            continue

        if len(text) < min_chars:
            # короткие блоки не трогаем
            processed.append(b)
            continue

        cleaned = _cleanup_long_text(text)

        new_b = dict(b)
        new_meta = dict(new_b.get("metadata") or {})
        new_meta["quality_pass"] = "heuristic_v1"
        new_b["metadata"] = new_meta
        new_b["translated_text"] = cleaned

        processed.append(new_b)

    return processed
