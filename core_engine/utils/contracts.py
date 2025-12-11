# core_engine/utils/contracts.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Sequence


# =========================
# Базовые структуры
# =========================

@dataclass
class IngestResultContract:
    """
    Минимальный контракт для результата ingest_pdf.

    Мы НЕ требуем, чтобы ingest_pdf возвращал именно этот dataclass.
    Валидация просто проверяет наличие совместимых полей.
    """
    book_id: str
    blocks: List[Dict[str, Any]]
    meta: Dict[str, Any]


# Базовый набор ключей для блока
REQUIRED_BLOCK_KEYS = ("id", "page", "order")
# Текстовые поля по стадиям
TEXT_FIELD_INGEST = "text"
TEXT_FIELD_NORMALIZE = "normalized_text"
TEXT_FIELD_TRANSLATE = "translated_text"


# =========================
# Общие утилиты
# =========================

def _ensure_list_of_dicts(value: Any, what: str) -> List[Dict[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError(f"{what} must be a list, got {type(value)!r}")
    out: List[Dict[str, Any]] = []
    for i, item in enumerate(value):
        if not isinstance(item, dict):
            raise ValueError(f"{what}[{i}] must be dict, got {type(item)!r}")
        out.append(item)
    return out


def _ensure_has_keys(block: Dict[str, Any], keys: Sequence[str], where: str) -> None:
    for k in keys:
        if k not in block:
            raise ValueError(f"Block missing required key '{k}' at {where}")


# =========================
# Валидация по стадиям
# =========================

def validate_ingest_result(result: Any) -> IngestResultContract:
    """
    Проверка минимального контракта результата ingest_pdf.

    Ожидаем:
      - атрибут/ключ book_id: str
      - атрибут/ключ blocks: list[dict]
      - атрибут/ключ meta: dict
    """
    # поддерживаем и obj.attr, и obj["key"]
    book_id = getattr(result, "book_id", None) or getattr(result, "id", None)
    if book_id is None and isinstance(result, dict):
        book_id = result.get("book_id") or result.get("id")

    if not isinstance(book_id, str) or not book_id.strip():
        raise ValueError("ingest_result.book_id must be non-empty string")

    blocks = getattr(result, "blocks", None)
    if blocks is None and isinstance(result, dict):
        blocks = result.get("blocks")
    blocks = _ensure_list_of_dicts(blocks, "ingest_result.blocks")

    meta = getattr(result, "meta", None)
    if meta is None and isinstance(result, dict):
        meta = result.get("meta")
    if not isinstance(meta, dict):
        raise ValueError("ingest_result.meta must be dict")

    # лёгкая проверка блоков
    validate_blocks_structure(blocks, stage="ingest", require_text_field=TEXT_FIELD_INGEST)

    return IngestResultContract(book_id=book_id, blocks=blocks, meta=meta)


def validate_blocks_structure(
    blocks: Any,
    *,
    stage: str,
    require_text_field: str | None = None,
    allow_missing_text: bool = False,
) -> List[Dict[str, Any]]:
    """
    Унифицированная проверка списка блоков на любой стадии.

    - обязателен список словарей,
    - каждый блок имеет id/page/order,
    - опционально проверяем наличие текстового поля (text/normalized_text/translated_text).
    """
    where = f"stage={stage}"
    blocks_list = _ensure_list_of_dicts(blocks, f"blocks at {where}")

    for idx, blk in enumerate(blocks_list):
        pos = f"{where}, index={idx}"
        _ensure_has_keys(blk, REQUIRED_BLOCK_KEYS, pos)

        # типы базовых ключей
        if not isinstance(blk["id"], str):
            raise ValueError(f"Block.id must be str at {pos}")
        try:
            int(blk["page"])
        except Exception:
            raise ValueError(f"Block.page must be int-convertible at {pos}")
        try:
            int(blk["order"])
        except Exception:
            raise ValueError(f"Block.order must be int-convertible at {pos}")

        if require_text_field:
            if require_text_field not in blk:
                if allow_missing_text:
                    continue
                raise ValueError(
                    f"Block missing required text field '{require_text_field}' at {pos}"
                )
            text_val = blk.get(require_text_field)
            if text_val is None or (isinstance(text_val, str) and not text_val.strip()):
                if not allow_missing_text:
                    raise ValueError(
                        f"Block.{require_text_field} is empty/None at {pos}"
                    )

    return blocks_list


def validate_layout_model(layout_model: Any) -> Dict[str, Any]:
    """
    Контракт layout_model, который отдаётся в export_json и дальше по пайплайну.

    Ожидаем структуру вида:
    {
        "book_id": str,
        "pages": [
            {
                "page_num": int,
                "blocks": [ <тот же формат блоков, что после translate> ]
            },
            ...
        ]
    }
    """
    if not isinstance(layout_model, dict):
        raise ValueError(f"layout_model must be dict, got {type(layout_model)!r}")

    book_id = layout_model.get("book_id")
    if not isinstance(book_id, str) or not book_id.strip():
        raise ValueError("layout_model['book_id'] must be non-empty string")

    pages = layout_model.get("pages")
    pages_list = _ensure_list_of_dicts(pages, "layout_model['pages']")

    for i, page in enumerate(pages_list):
        if "page_num" not in page:
            raise ValueError(f"pages[{i}] missing 'page_num'")
        try:
            int(page["page_num"])
        except Exception:
            raise ValueError(f"pages[{i}]['page_num'] must be int-convertible")

        page_blocks = page.get("blocks")
        validate_blocks_structure(
            page_blocks,
            stage=f"layout.page[{i}]",
            require_text_field=None,  # тут уже могут быть и заголовки, и пустые блоки
        )

    return layout_model
