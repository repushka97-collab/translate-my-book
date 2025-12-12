# core_engine/normalize/heading_preprocessor.py

from __future__ import annotations

from typing import List, Dict, Any
import re

from core_engine.translate.heading_translator import (
    HEADING_DICTIONARY,
    translate_heading_with_dictionary,
)


def preprocess_headings_in_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Pre-processing заголовков ДО перевода.
    Применяет словарь заголовков к normalized_text, если блок является заголовком.
    """
    processed = []
    
    for block in blocks:
        metadata = block.get("metadata", {})
        role = metadata.get("role", "")
        
        normalized_text = (block.get("normalized_text") or block.get("text") or "").strip()
        
        # Определяем, является ли блок заголовком:
        # 1. По role (если установлен detect_headings)
        # 2. По исходному тексту (если весь капс и короткий)
        is_heading = role in ("heading1", "heading2", "heading3")
        
        if not is_heading and normalized_text:
            # Проверяем по тексту: если весь капс и короткий - вероятно заголовок
            if normalized_text.isupper() and len(normalized_text.split()) <= 6:
                is_heading = True
        
        # Если это заголовок, пробуем применить словарь
        if is_heading and normalized_text:
            dict_translation = translate_heading_with_dictionary(normalized_text)
            if dict_translation:
                # Заменяем normalized_text на перевод из словаря
                # Это будет использовано при переводе
                new_block = dict(block)
                new_block["normalized_text"] = dict_translation
                # Помечаем что это уже переведено через словарь
                if "metadata" not in new_block:
                    new_block["metadata"] = {}
                new_block["metadata"]["heading_preprocessed"] = True
                processed.append(new_block)
                continue
        
        # Не заголовок или словарь не помог - оставляем как есть
        processed.append(block)
    
    return processed

