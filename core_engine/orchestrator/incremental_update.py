"""
Инкрементальное обновление переводов.

Отслеживает изменения в исходном PDF и перепереводит только измененные блоки.
"""

from __future__ import annotations

from typing import List, Dict, Any, Set
from pathlib import Path
import hashlib
import json


def compute_page_hash(page_data: Dict[str, Any]) -> str:
    """
    Вычисляет хеш страницы для отслеживания изменений.
    """
    # Используем текст и структуру блоков для хеша
    text_parts = []
    for block in page_data.get("blocks", []):
        text = block.get("text") or block.get("normalized_text", "") or ""
        text_parts.append(text)
    
    content = "|".join(text_parts)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def load_translation_state(book_id: str, state_dir: Path) -> Dict[str, Any]:
    """
    Загружает состояние перевода из файла.
    """
    state_file = state_dir / f"{book_id}.state.json"
    if state_file.exists():
        try:
            return json.loads(state_file.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_translation_state(book_id: str, state_dir: Path, state: Dict[str, Any]) -> None:
    """
    Сохраняет состояние перевода в файл.
    """
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{book_id}.state.json"
    state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def detect_changed_blocks(
    current_blocks: List[Dict[str, Any]],
    previous_state: Dict[str, Any]
) -> Set[str]:
    """
    Определяет, какие блоки изменились по сравнению с предыдущей версией.
    
    Returns:
        Множество ID измененных блоков
    """
    changed_ids: Set[str] = set()
    page_hashes = previous_state.get("page_hashes", {})
    
    # Группируем блоки по страницам
    blocks_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for block in current_blocks:
        page = block.get("page", 0)
        blocks_by_page.setdefault(page, []).append(block)
    
    # Проверяем хеши страниц
    for page_num, page_blocks in blocks_by_page.items():
        page_data = {"blocks": page_blocks}
        current_hash = compute_page_hash(page_data)
        previous_hash = page_hashes.get(str(page_num), "")
        
        if current_hash != previous_hash:
            # Страница изменилась - помечаем все блоки как измененные
            for block in page_blocks:
                block_id = block.get("id", "")
                if block_id:
                    changed_ids.add(block_id)
    
    return changed_ids


def merge_translations(
    current_blocks: List[Dict[str, Any]],
    previous_blocks: List[Dict[str, Any]],
    changed_ids: Set[str]
) -> List[Dict[str, Any]]:
    """
    Объединяет старые переводы с новыми для измененных блоков.
    
    Для неизмененных блоков использует старый перевод,
    для измененных - требует нового перевода.
    """
    # Создаем map старых переводов
    old_translations = {}
    for block in previous_blocks:
        block_id = block.get("id", "")
        if block_id and block.get("translated_text"):
            old_translations[block_id] = block.get("translated_text")
    
    # Применяем старые переводы к неизмененным блокам
    result = []
    for block in current_blocks:
        block_id = block.get("id", "")
        if block_id and block_id not in changed_ids and block_id in old_translations:
            # Блок не изменился - используем старый перевод
            block["translated_text"] = old_translations[block_id]
            block["metadata"] = block.get("metadata", {})
            block["metadata"]["from_cache"] = True
        else:
            # Блок изменился или новый - требует перевода
            block["metadata"] = block.get("metadata", {})
            block["metadata"]["needs_translation"] = True
        
        result.append(block)
    
    return result


def update_translation_state(
    book_id: str,
    blocks: List[Dict[str, Any]],
    state_dir: Path
) -> Dict[str, Any]:
    """
    Обновляет состояние перевода после обработки.
    """
    # Группируем блоки по страницам
    blocks_by_page: Dict[int, List[Dict[str, Any]]] = {}
    for block in blocks:
        page = block.get("page", 0)
        blocks_by_page.setdefault(page, []).append(block)
    
    # Вычисляем хеши страниц
    page_hashes = {}
    for page_num, page_blocks in blocks_by_page.items():
        page_data = {"blocks": page_blocks}
        page_hashes[str(page_num)] = compute_page_hash(page_data)
    
    state = {
        "book_id": book_id,
        "page_hashes": page_hashes,
        "total_blocks": len(blocks),
    }
    
    save_translation_state(book_id, state_dir, state)
    return state

