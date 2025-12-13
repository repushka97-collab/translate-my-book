"""
Выборочное маскирование контента для частичного перевода.

Позволяет пометить определенные блоки как "не переводить" или "перевести с приоритетом".
"""

from __future__ import annotations

from typing import List, Dict, Any, Set
import re


def apply_selective_mask(
    blocks: List[Dict[str, Any]],
    mask_config: Dict[str, Any] = None
) -> List[Dict[str, Any]]:
    """
    Применяет маскирование к блокам на основе конфигурации.
    
    Args:
        blocks: список блоков для обработки
        mask_config: конфигурация маскирования:
            - skip_patterns: список regex паттернов для пропуска перевода
            - skip_types: типы блоков для пропуска (например, ["formula", "code"])
            - skip_roles: роли блоков для пропуска (например, ["footnote", "header"])
            - priority_patterns: список regex паттернов для приоритетного перевода
            - skip_block_ids: конкретные ID блоков для пропуска
    
    Returns:
        Список блоков с добавленными метаданными маскирования
    """
    if not mask_config:
        return blocks
    
    skip_patterns = mask_config.get("skip_patterns", [])
    skip_types = mask_config.get("skip_types", [])
    skip_roles = mask_config.get("skip_roles", [])
    priority_patterns = mask_config.get("priority_patterns", [])
    skip_block_ids = set(mask_config.get("skip_block_ids", []))
    
    result = []
    for block in blocks:
        block_id = block.get("id", "")
        block_type = block.get("type", "")
        metadata = block.get("metadata", {})
        role = metadata.get("role", "")
        text = block.get("text") or block.get("normalized_text", "") or ""
        
        # Проверяем, нужно ли пропустить этот блок
        should_skip = False
        
        # Проверка по ID
        if block_id in skip_block_ids:
            should_skip = True
        
        # Проверка по типу
        if block_type in skip_types or (isinstance(block_type, dict) and block_type.get("name") in skip_types):
            should_skip = True
        
        # Проверка по роли
        if role in skip_roles:
            should_skip = True
        
        # Проверка по паттернам
        if not should_skip and skip_patterns:
            for pattern in skip_patterns:
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        should_skip = True
                        break
                except Exception:
                    continue
        
        # Проверка приоритета
        is_priority = False
        if priority_patterns:
            for pattern in priority_patterns:
                try:
                    if re.search(pattern, text, re.IGNORECASE):
                        is_priority = True
                        break
                except Exception:
                    continue
        
        # Добавляем метаданные маскирования
        if "metadata" not in block:
            block["metadata"] = {}
        
        if should_skip:
            block["metadata"]["skip_translation"] = True
            block["metadata"]["mask_reason"] = "selective_mask"
        elif is_priority:
            block["metadata"]["translation_priority"] = "high"
        
        result.append(block)
    
    return result


def filter_masked_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Фильтрует блоки, помеченные для пропуска перевода.
    """
    return [b for b in blocks if not b.get("metadata", {}).get("skip_translation", False)]


def get_priority_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Возвращает блоки с высоким приоритетом перевода.
    """
    return [b for b in blocks if b.get("metadata", {}).get("translation_priority") == "high"]

