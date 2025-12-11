"""
Text normalization utilities for EWB Core Engine.

Задачи:
- чистка служебных символов (soft hyphen, неразрывные пробелы и т.п.)
- нормализация пробелов и переводов строк
- склейка переносов по дефису: "сло-\nво" -> "слово"
- подготовка normalized_text для перевода
- извлечение protected tokens в block.metadata["protected_tokens"]
"""

from __future__ import annotations

import re
from typing import List, Dict, Any

from core_engine.core.models import BookDocument, Block


# --- базовые паттерны ---------------------------------------------------------

SOFT_HYPHEN = "\u00ad"  # ­
NBSP = "\u00a0"

RE_MULTISPACE = re.compile(r"[ \t]+")
RE_BLANK_LINES = re.compile(r"\n{3,}")

# перенос по дефису: сло-\nво -> слово
RE_HYPHEN_BREAK = re.compile(r"(\w+)-\n(\w+)", re.UNICODE)

# FIG/TABLE, panel letters, ссылки, DOI/URL
RE_FIG_TABLE = re.compile(r"\b(FIG\.?\s*\d+[A-Z]?)\b", re.IGNORECASE)
RE_TABLE = re.compile(r"\b(TABLE\.?\s*\d+[A-Z]?)\b", re.IGNORECASE)
RE_CITATION = re.compile(r"\[(\d+(?:\s*[–-]\s*\d+)?(?:\s*,\s*\d+)*)\]")
RE_DOI = re.compile(r"\b10\.\d{4,9}/\S+\b", re.IGNORECASE)
RE_URL = re.compile(r"https?://\S+")
RE_SUP_INDEX = re.compile(r"[A-Za-z0-9]\s*[\u00B2\u00B3\u00B9\u2070-\u209F]")  # грубый индикатор индексов


# --- утилиты ------------------------------------------------------------------


def _strip_soft_chars(text: str) -> str:
    if not text:
        return ""
    text = text.replace(SOFT_HYPHEN, "")
    text = text.replace(NBSP, " ")
    return text


def _merge_hyphen_breaks(text: str) -> str:
    # несколько проходов, если в тексте их много
    prev = None
    cur = text
    while prev != cur:
        prev = cur
        cur = RE_HYPHEN_BREAK.sub(r"\1\2", cur)
    return cur


def _normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    # нормализуем пробелы внутри строк
    lines = []
    for line in text.splitlines():
        line = RE_MULTISPACE.sub(" ", line).strip()
        lines.append(line)
    text = "\n".join(l for l in lines if l != "")
    # схлопываем тройные/дальше переводы строк в двойные
    text = RE_BLANK_LINES.sub("\n\n", text)
    return text.strip()


def _detect_protected_tokens(text: str) -> List[str]:
    tokens: List[str] = []

    for m in RE_FIG_TABLE.finditer(text):
        tokens.append(m.group(1).strip())

    for m in RE_TABLE.finditer(text):
        t = m.group(1).strip()
        if t not in tokens:
            tokens.append(t)

    for m in RE_CITATION.finditer(text):
        tokens.append(m.group(0))

    for m in RE_DOI.finditer(text):
        tokens.append(m.group(0))

    for m in RE_URL.finditer(text):
        tokens.append(m.group(0))

    # индексы/степени – пока просто флажок, без явного токена
    if RE_SUP_INDEX.search(text):
        tokens.append("__HAS_SUP_INDEX__")

    # уникализируем, сохраняем порядок
    seen = set()
    uniq: List[str] = []
    for t in tokens:
        if t not in seen:
            uniq.append(t)
            seen.add(t)
    return uniq


def _normalize_block_text(raw: str) -> Dict[str, Any]:
    """
    Возвращает:
      {
        "normalized": <str>,
        "protected_tokens": [..]
      }
    """
    if not raw:
        return {"normalized": "", "protected_tokens": []}

    t = raw

    # 1) чистим служебные символы
    t = _strip_soft_chars(t)

    # 2) склейка дефисных переносов
    t = _merge_hyphen_breaks(t)

    # 3) нормализация пробелов/пустых строк
    t = _normalize_whitespace(t)

    # 4) protected tokens
    tokens = _detect_protected_tokens(t)

    return {
        "normalized": t,
        "protected_tokens": tokens,
    }


# --- публичный API ------------------------------------------------------------


def normalize_document(doc: BookDocument) -> None:
    """
    Главная точка входа нормализации.

    - проходит по всем блокам
    - пишет normalized_text
    - добавляет/обновляет metadata["protected_tokens"]
    """
    for page in doc.pages:
        for block in page.blocks:
            if not isinstance(block, Block):
                # на будущее, если появятся другие типы объектов
                continue

            raw = block.raw_text or ""
            norm_info = _normalize_block_text(raw)

            block.normalized_text = norm_info["normalized"]

            # метаданные могут уже содержать что-то своё
            meta = dict(block.metadata or {})
            existing = meta.get("protected_tokens") or []
            # мерджим без дубликатов
            merged: List[str] = []
            seen = set()

            for t in list(existing) + list(norm_info["protected_tokens"]):
                if t not in seen:
                    merged.append(t)
                    seen.add(t)

            meta["protected_tokens"] = merged
            block.metadata = meta
# --- v3 pipeline adapter -------------------------------------------------------

def normalize_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Адаптер для v3-пайплайна.

    Если в блоке уже есть normalized_text / protected_tokens
    (после normalize_document), просто прокидываем их дальше.
    Если нет — считаем по _normalize_block_text().
    """
    normalized: List[Dict[str, Any]] = []

    for blk in blocks:
        new_blk = dict(blk)

        existing_meta = dict(new_blk.get("metadata") or {})
        existing_tokens = existing_meta.get("protected_tokens") or []

        # Если уже есть нормализованный текст — используем его
        if "normalized_text" in new_blk:
            norm_text = new_blk["normalized_text"]
            tokens = existing_tokens
        else:
            raw = new_blk.get("text") or ""
            norm_info = _normalize_block_text(raw)
            norm_text = norm_info["normalized"]
            tokens = existing_tokens + norm_info["protected_tokens"]

        # Пишем нормализованный текст
        new_blk["normalized_text"] = norm_text

        # Мердж protected_tokens без дублей
        merged_tokens: List[str] = []
        seen = set()
        for t in tokens:
            if t not in seen:
                merged_tokens.append(t)
                seen.add(t)

        existing_meta["protected_tokens"] = merged_tokens
        new_blk["metadata"] = existing_meta

        normalized.append(new_blk)

    return normalized


