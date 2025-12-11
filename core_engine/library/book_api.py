"""
High-level book API for EWB Core Engine.

Даёт внешний слой поверх файловой библиотеки:

- загрузка манифеста и слоёв;
- получение структуры книги;
- получение страницы;
- получение блока;
- перевод отдельного блока с использованием LLMRouter
  и запись результата обратно в blocks_index.json + кэш.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from core_engine.llm.router import LLMRouter  # type: ignore
from core_engine.translate.translator import preserve_tokens  # type: ignore
from core_engine.cache.translation_cache import (  # type: ignore
    load_from_cache,
    save_to_cache,
    hash_text,
)

logger = logging.getLogger(__name__)


# =============================================================================
# Вспомогательные функции работы с файловой библиотекой
# =============================================================================


def _book_dir(book_id: str, library_root: str = "library") -> Path:
    return Path(library_root) / book_id


def _manifest_path(book_id: str, library_root: str = "library") -> Path:
    return _book_dir(book_id, library_root) / "manifest.json"


def _layers_dir(book_id: str, library_root: str = "library") -> Path:
    return _book_dir(book_id, library_root) / "layers"


def _blocks_index_path(book_id: str, library_root: str = "library") -> Path:
    return _layers_dir(book_id, library_root) / "blocks_index.json"


def _pages_path(book_id: str, library_root: str = "library") -> Path:
    return _layers_dir(book_id, library_root) / "pages.json"


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"JSON file not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _dump_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    tmp_path.replace(path)


# =============================================================================
# Публичный API: чтение структуры
# =============================================================================


def load_manifest(book_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Загружает manifest.json для книги.
    """
    path = _manifest_path(book_id, library_root)
    return _load_json(path)


def load_blocks_index(book_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Загружает layers/blocks_index.json.
    """
    path = _blocks_index_path(book_id, library_root)
    return _load_json(path)


def load_pages_layer(book_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Загружает layers/pages.json.
    """
    path = _pages_path(book_id, library_root)
    return _load_json(path)


def get_book_structure(book_id: str, library_root: str = "library") -> Dict[str, Any]:
    """
    Высокоуровневая структура книги для внешних систем (бот, n8n).

    Контракт (пример):

    {
      "book_id": "...",
      "pages": 564,
      "metadata": {...},
      "blocks": [
        {
          "id": "p1_b0",
          "page": 1,
          "type": "text",
          "raw": "...",
          "normalized": "...",
          "translated": "...",
          "protected_tokens": [...],
          "bbox": [...]
        },
        ...
      ]
    }
    """
    manifest = load_manifest(book_id, library_root)
    blocks_data = load_blocks_index(book_id, library_root)

    raw_blocks: List[Dict[str, Any]] = blocks_data.get("blocks", []) or []
    blocks_out: List[Dict[str, Any]] = []

    for b in raw_blocks:
        meta: Dict[str, Any] = b.get("metadata") or {}
        tokens = meta.get("protected_tokens") or []

        block_out: Dict[str, Any] = {
            "id": b.get("id"),
            "page": b.get("page_number"),
            "type": b.get("type"),
            "raw": b.get("raw_text"),
            "normalized": b.get("normalized_text"),
            "translated": b.get("translated_text"),
            "protected_tokens": tokens,
        }

        bbox = b.get("bbox")
        if isinstance(bbox, dict):
            block_out["bbox"] = [
                bbox.get("x0"),
                bbox.get("y0"),
                bbox.get("x1"),
                bbox.get("y1"),
            ]
        else:
            block_out["bbox"] = bbox

        blocks_out.append(block_out)

    result: Dict[str, Any] = {
        "book_id": manifest.get("book_id", book_id),
        "pages": manifest.get("pages"),
        "metadata": manifest.get("metadata", {}),
        "blocks": blocks_out,
    }

    return result


def get_page(
    book_id: str,
    page_number: int,
    library_root: str = "library",
) -> Dict[str, Any]:
    """
    Возвращает структуру одной страницы:

    {
      "book_id": "...",
      "page": 7,
      "blocks": [ {block}, ... ]
    }
    """
    pages_layer = load_pages_layer(book_id, library_root)
    blocks_index = load_blocks_index(book_id, library_root)

    blocks_by_id: Dict[str, Dict[str, Any]] = {
        b.get("id"): b for b in (blocks_index.get("blocks") or [])
    }

    page_entry = None
    for p in pages_layer.get("pages", []):
        if int(p.get("number")) == int(page_number):
            page_entry = p
            break

    if page_entry is None:
        raise ValueError(f"Page {page_number} not found for book {book_id}")

    block_ids: List[str] = page_entry.get("blocks", []) or []
    blocks_out: List[Dict[str, Any]] = []

    for bid in block_ids:
        b = blocks_by_id.get(bid)
        if not b:
            continue
        meta: Dict[str, Any] = b.get("metadata") or {}
        tokens = meta.get("protected_tokens") or []

        block_out: Dict[str, Any] = {
            "id": b.get("id"),
            "page": b.get("page_number"),
            "type": b.get("type"),
            "raw": b.get("raw_text"),
            "normalized": b.get("normalized_text"),
            "translated": b.get("translated_text"),
            "protected_tokens": tokens,
        }
        blocks_out.append(block_out)

    return {
        "book_id": book_id,
        "page": page_number,
        "blocks": blocks_out,
    }


def get_block(
    book_id: str,
    block_id: str,
    library_root: str = "library",
) -> Dict[str, Any]:
    """
    Возвращает структуру одного блока:

    {
      "id": "p7_b3",
      "page": 7,
      "type": "text",
      "raw": "...",
      "normalized": "...",
      "translated": "...",
      "protected_tokens": [...],
      "bbox": [...]
    }
    """
    blocks_index = load_blocks_index(book_id, library_root)
    for b in blocks_index.get("blocks", []) or []:
        if b.get("id") == block_id:
            meta: Dict[str, Any] = b.get("metadata") or {}
            tokens = meta.get("protected_tokens") or []

            bbox = b.get("bbox")
            if isinstance(bbox, dict):
                bbox_out = [
                    bbox.get("x0"),
                    bbox.get("y0"),
                    bbox.get("x1"),
                    bbox.get("y1"),
                ]
            else:
                bbox_out = bbox

            return {
                "id": b.get("id"),
                "page": b.get("page_number"),
                "type": b.get("type"),
                "raw": b.get("raw_text"),
                "normalized": b.get("normalized_text"),
                "translated": b.get("translated_text"),
                "protected_tokens": tokens,
                "bbox": bbox_out,
            }

    raise ValueError(f"Block {block_id} not found for book {book_id}")


# =============================================================================
# Публичный API: перевод блока + кэш
# =============================================================================


def translate_block_in_library(
    book_id: str,
    block_id: str,
    library_root: str = "library",
    llm_config_path: Optional[str] = None,
    source_lang: str = "en",
    target_lang: str = "ru",
) -> Dict[str, Any]:
    """
    Переводит один блок книги:

    - читает структуру,
    - ищет блок,
    - берёт normalized_text/raw_text,
    - достаёт protected_tokens,
    - сначала пытается взять из кэша,
    - если кэша нет → вызывает adapter.translate(),
    - сохраняет перевод в blocks_index.json + кэш.

    Возвращает dict с обновлённым блоком и флагом cache_hit.
    """

    # === ЗАГРУЗКА СЛОЯ БЛОКОВ ===
    blocks_data = load_blocks_index(book_id, library_root)
    blocks: List[Dict[str, Any]] = blocks_data.get("blocks", []) or []

    target_block: Optional[Dict[str, Any]] = None
    for b in blocks:
        if b.get("id") == block_id:
            target_block = b
            break

    if target_block is None:
        raise ValueError(f"Block {block_id} not found for book {book_id}")

    raw = target_block.get("raw_text") or ""
    normalized = target_block.get("normalized_text") or ""
    text = normalized or raw

    if not text:
        target_block["translated_text"] = ""
        _dump_json(_blocks_index_path(book_id, library_root), blocks_data)
        result = get_block(book_id, block_id, library_root)
        result["cache_hit"] = False
        return result

    meta = target_block.get("metadata") or {}
    tokens = meta.get("protected_tokens") or []
    if not isinstance(tokens, list):
        tokens = []

    # === ПОДГОТОВКА LLM ===
    router = LLMRouter(config_path=llm_config_path)
    adapter = router.get_translation_adapter()
    model_name = getattr(adapter, "model_name", adapter.__class__.__name__)

    # === КЭШ ===
    text_hash = hash_text(text)
    cached = load_from_cache(book_id, block_id, text_hash, model_name)

    if cached is not None:
        target_block["translated_text"] = cached
        _dump_json(_blocks_index_path(book_id, library_root), blocks_data)

        result = get_block(book_id, block_id, library_root)
        result["cache_hit"] = True
        return result

    # === ВЫЗОВ LLM ===
    context = {
        "book_id": book_id,
        "block_id": block_id,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "page_number": target_block.get("page_number"),
        "block_type": target_block.get("type"),
        "protected_tokens": tokens,
    }

    try:
        translated = adapter.translate(text, context)
    except Exception as exc:
        logger.error("LLM translate error: %s", exc)
        translated = text

    translated = translated or ""
    translated = preserve_tokens(text, translated, tokens)

    # === СОХРАНЕНИЕ В blocks_index.json ===
    target_block["translated_text"] = translated
    _dump_json(_blocks_index_path(book_id, library_root), blocks_data)

    # === СОХРАНЕНИЕ В КЭШ ===
    save_to_cache(book_id, block_id, text_hash, model_name, translated)

    result = get_block(book_id, block_id, library_root)
    result["cache_hit"] = False
    return result

# =============================================================================
# Публичный API: перевод страницы / книги
# =============================================================================


def translate_page_in_library(
    book_id: str,
    page_number: int,
    library_root: str = "library",
    llm_config_path: Optional[str] = None,
    source_lang: str = "en",
    target_lang: str = "ru",
) -> Dict[str, Any]:
    """
    Переводит ВСЕ блоки одной страницы.

    Возвращает:
    {
      "book_id": "...",
      "page": 1,
      "blocks": [ <результаты translate_block_in_library>, ... ]
    }
    """
    pages_layer = load_pages_layer(book_id, library_root)

    page_entry: Optional[Dict[str, Any]] = None
    for p in pages_layer.get("pages", []) or []:
        if int(p.get("number")) == int(page_number):
            page_entry = p
            break

    if page_entry is None:
        raise ValueError(f"Page {page_number} not found for book {book_id}")

    block_ids: List[str] = page_entry.get("blocks", []) or []
    blocks_out: List[Dict[str, Any]] = []

    for bid in block_ids:
        res = translate_block_in_library(
            book_id=book_id,
            block_id=bid,
            library_root=library_root,
            llm_config_path=llm_config_path,
            source_lang=source_lang,
            target_lang=target_lang,
        )
        blocks_out.append(res)

    return {
        "book_id": book_id,
        "page": page_number,
        "blocks": blocks_out,
    }


def translate_book_in_library(
    book_id: str,
    library_root: str = "library",
    llm_config_path: Optional[str] = None,
    source_lang: str = "en",
    target_lang: str = "ru",
) -> Dict[str, Any]:
    """
    Переводит ВСЮ книгу (все страницы, все блоки).

    Чтобы не вываливать гигантский текст, возвращаем сводку по страницам:

    {
      "book_id": "...",
      "pages": [
        {
          "page": 1,
          "blocks": 10,
          "cache_hits": 8,
          "translated": 10
        },
        ...
      ]
    }
    """
    pages_layer = load_pages_layer(book_id, library_root)
    pages_info: List[Dict[str, Any]] = []

    for p in pages_layer.get("pages", []) or []:
        page_num = int(p.get("number"))
        page_result = translate_page_in_library(
            book_id=book_id,
            page_number=page_num,
            library_root=library_root,
            llm_config_path=llm_config_path,
            source_lang=source_lang,
            target_lang=target_lang,
        )

        blocks = page_result.get("blocks", []) or []
        total_blocks = len(blocks)
        cache_hits = sum(1 for b in blocks if b.get("cache_hit"))
        pages_info.append(
            {
                "page": page_num,
                "blocks": total_blocks,
                "cache_hits": cache_hits,
                "translated": total_blocks,
            }
        )

    return {
        "book_id": book_id,
        "pages": pages_info,
    }

