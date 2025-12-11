# core_engine/translate/quality_pass.py

from __future__ import annotations

from typing import List, Dict, Any
import re


Block = Dict[str, Any]


def _cleanup_long_text(text: str) -> str:
    """
    Небольшая эвристическая чистка:
    - схлопываем повторные пробелы;
    - убираем мусорные пробелы перед знаками препинания;
    - выправляем тройные точки и многоточия;
    - убираем странные непечатаемые пробелы.
    """
    if not text:
        return text

    s = text

    # убираем неразрывные/странные пробелы
    s = s.replace("\u00A0", " ").replace("\u200B", "")

    # схлопываем повторные пробелы
    s = re.sub(r"\s+", " ", s)

    # пробел перед знаками препинания → убираем
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)

    # нормализуем многоточие
    s = re.sub(r"\.{3,}", "…", s)

    # иногда модель даёт " ,", " .", " ?"
    s = re.sub(r"\s+([,.!?])", r"\1", s)

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
