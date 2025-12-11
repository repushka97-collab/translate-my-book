# core_engine/translate/term_normalizer.py

from __future__ import annotations

from typing import List, Dict, Any
import re


Block = Dict[str, Any]


def _normalize_terms(text: str) -> str:
    """
    Терминологический нормализатор v1 (без look-behind).
    Стабильная версия, не создаёт дублей и не падает на regex.
    """

    s = text

    # ============================
    #  СТАШИРОВАНИЕ УЖЕ НОРМАЛИЗОВАННЫХ ФРАГМЕНТОВ
    # ============================

    placeholders = {}

    def stash(pattern: str, key_prefix: str):
        # Находим совпадения и заменяем на временные ключи
        nonlocal s
        matches = list(re.finditer(pattern, s, flags=re.IGNORECASE))
        for idx, m in enumerate(matches):
            orig = m.group(0)
            key = f"__TERM_{key_prefix}_{idx}__"
            placeholders[key] = orig
            s = s.replace(orig, key)

    # Скрываем уже нормализованные формы, чтобы не испортить их
    stash(r"Инь\s+и\s+Ян\s*\(Yin\s*&\s*Yang\)", "YIN_YANG_RU")
    stash(r"ци\s*\(Qi\)", "QI_RU")
    stash(r"меридиан[а-я]*", "MERIDIAN_RU")  # меридиан / меридианы — оставляем как есть
    stash(r"опорно-двигательн[а-я]+\s*\(MSK\)", "MSK_RU")
    stash(r"сухое\s+иглоукалывание\s*\(DN\)", "DN_RU")
    stash(r"традиционная китайская медицина\s*\(ТКМ\)", "TCM_RU")

    # ============================
    #  АНГЛИЙСКИЕ ТЕРМИНЫ → РУССКИЕ НОРМАЛИЗОВАННЫЕ
    # ============================

    # Yin & Yang
    s = re.sub(
        r"\bYin\s*&\s*Yang\b",
        "Инь и Ян (Yin & Yang)",
        s,
        flags=re.IGNORECASE,
    )

    # Qi / Chi → ци (Qi)
    s = re.sub(
        r"\bQi\b",
        "ци (Qi)",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bChi\b",
        "ци (Qi)",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bQi\b",
        "ци (Qi)",
        s,
        flags=re.IGNORECASE,
    )

    # Yin → Инь (Yin)
    s = re.sub(
        r"\bYin\b",
        "Инь (Yin)",
        s,
        flags=re.IGNORECASE,
    )

    # Yang → Ян (Yang)
    s = re.sub(
        r"\bYang\b",
        "Ян (Yang)",
        s,
        flags=re.IGNORECASE,
    )

    # meridian(s)
    s = re.sub(
        r"\bmeridians\b",
        "меридианы",
        s,
        flags=re.IGNORECASE,
    )
    s = re.sub(
        r"\bmeridian\b",
        "меридиан",
        s,
        flags=re.IGNORECASE,
    )

    # MSK — делаем аккуратно: только если русского варианта ещё нет
    s = re.sub(
        r"\bMSK\b",
        "опорно-двигательный аппарат (MSK)",
        s,
        flags=re.IGNORECASE,
    )

    # DN
    s = re.sub(
        r"\bDN\b",
        "сухое иглоукалывание (DN)",
        s,
        flags=re.IGNORECASE,
    )

    # TCM
    s = re.sub(
        r"\bTCM\b",
        "традиционная китайская медицина (ТКМ)",
        s,
        flags=re.IGNORECASE,
    )

    # ============================
    #  ВОССТАНОВЛЕНИЕ ПЛЕЙСХОЛДЕРОВ
    # ============================

    for key, orig in placeholders.items():
        s = s.replace(key, orig)

    return s


def run_term_normalizer(blocks: List[Block], min_chars: int = 0) -> List[Block]:
    """
    Терминологический проход v1: нормализуем ключевые термины
    по умолчанию во всех блоках (min_chars=0).
    """
    out = []

    for b in blocks:
        text = b.get("translated_text")
        if not isinstance(text, str):
            out.append(b)
            continue

        if len(text) < min_chars:
            out.append(b)
            continue

        norm = _normalize_terms(text)

        if norm == text:
            out.append(b)
            continue

        bb = dict(b)
        meta = dict(bb.get("metadata") or {})
        meta["term_pass"] = "v1"
        bb["metadata"] = meta
        bb["translated_text"] = norm
        out.append(bb)

    return out
