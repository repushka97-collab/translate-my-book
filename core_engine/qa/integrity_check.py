from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Optional
import re

Block = Dict[str, Any]
QAReport = Dict[str, Any]

# Управляющие символы, которых не должно быть в тексте
_SUSPICIOUS_CONTROL_CHARS = {
    chr(i)
    for i in range(0x00, 0x20)
    if chr(i) not in {"\n", "\r", "\t"}
}

# Ключевые термины, которые часто "торчат" по-английски в русском тексте
_SUSPECT_EN_TERMS = {
    "acupuncture",
    "meridian",
    "meridians",
    "chi",
    "qi",
    "yin",
    "yang",
    "channel",
    "channels",
    "fascia",
    "fascias",
}


def _block_key(block: Block) -> str:
    """Человеко-читаемый идентификатор блока для отчёта."""
    bid = block.get("id")
    if bid:
        return str(bid)
    page = block.get("page", "?")
    order = block.get("order", "?")
    return f"page={page},order={order}"


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _detect_suspicious_chars(text: str):
    chars = set()
    for ch in text:
        if ch in _SUSPICIOUS_CONTROL_CHARS or ch in {"\ufffd", "Ã", "Â"}:
            chars.add(ch)
    return sorted(chars)


def _count_alphabets(text: str) -> Dict[str, int]:
    latin = sum(1 for ch in text if "a" <= ch.lower() <= "z")
    cyr = sum(1 for ch in text if "а" <= ch.lower() <= "я" or ch.lower() == "ё")
    other = len(text) - latin - cyr
    return {"latin": latin, "cyr": cyr, "other": other}


def _detect_mixed_alphabet_issue(text: str) -> Dict[str, Any] | None:
    """
    Ищем странные смеси латиницы/кириллицы в одном блоке.
    Игнорируем латиницу в скобках (аббревиатуры, термины) и URL/DOI.
    """
    # Исключаем латиницу в скобках и URL/DOI из подсчета
    text_for_check = text
    # Убираем содержимое скобок
    text_for_check = re.sub(r"\([^)]*\)", "", text_for_check)
    # Убираем URL и DOI
    text_for_check = re.sub(r"https?://\S+", "", text_for_check, flags=re.IGNORECASE)
    text_for_check = re.sub(r"doi\.org/\S+", "", text_for_check, flags=re.IGNORECASE)
    
    stats = _count_alphabets(text_for_check)
    latin = stats["latin"]
    cyr = stats["cyr"]
    total_letters = latin + cyr
    if total_letters == 0:
        return None

    latin_ratio = latin / total_letters
    cyr_ratio = cyr / total_letters

    # Сценарий: текст в основном русский, но заметный кусок латиницы (не в скобках)
    # Более строгий порог: латиница должна быть >= 30% чтобы это было проблемой
    if cyr_ratio >= 0.5 and latin_ratio >= 0.3:
        return {
            "latin": latin,
            "cyr": cyr,
            "latin_ratio": round(latin_ratio, 3),
            "cyr_ratio": round(cyr_ratio, 3),
        }

    return None


def _detect_concatenated_scripts(text: str) -> List[str]:
    """
    Ищем слова, где латиница и кириллица склеены без пробела:
    типа 'meridiansвсе', 'Yangи'.
    Игнорируем случаи где латиница в конце после цифр (например "MSK", "TCM").
    """
    tokens = re.findall(r"\S+", text)
    bad: List[str] = []
    for t in tokens:
        has_latin = any("a" <= ch.lower() <= "z" for ch in t)
        has_cyr = any("а" <= ch.lower() <= "я" or ch.lower() == "ё" for ch in t)
        if has_latin and has_cyr:
            # Игнорируем если это выглядит как аббревиатура в конце (например "MSK", "TCM")
            # или если латиница только в начале короткого слова (например "Qi" в "Qi-терапия")
            if len(t) <= 5 and (t[0].isupper() or t.lower() in ["msk", "tcm", "dn", "qi", "yin", "yang"]):
                continue
            bad.append(t)
    return bad


def _detect_suspect_english_terms(text: str) -> List[str]:
    """
    Ищем ключевые английские термины в русском блоке.
    Игнорируем если термин уже нормализован (в скобках или с русским эквивалентом).
    """
    lowered = text.lower()
    found = []
    for term in _SUSPECT_EN_TERMS:
        if term in lowered:
            # Проверяем контекст: если термин в скобках или рядом с русским эквивалентом - это нормально
            pattern = re.escape(term)
            # Игнорируем если термин в скобках: (meridian) или ци (Qi)
            if re.search(rf"\([^)]*{pattern}[^)]*\)", lowered) or re.search(rf"[а-яё]+\s*\({pattern}\)", lowered):
                continue
            # Игнорируем если это часть нормализованного термина: "меридиан (meridian)"
            if re.search(rf"[а-яё]+\s*\({pattern}\)", lowered):
                continue
            found.append(term)
    return found


def _detect_repeated_fragments(text: str) -> List[str]:
    """
    Грубый поиск 'дребезга':
    - удвоенные слова подряд (по русски и по английски)
    """
    tokens = re.findall(r"\w+", text.lower())
    if len(tokens) < 2:
        return []

    bad: List[str] = []
    for prev, cur in zip(tokens, tokens[1:]):
        if prev == cur and prev not in bad:
            bad.append(prev)

    return bad


def qa_check_blocks(normalized_blocks: List[Block], translated_blocks: List[Block]) -> QAReport:
    """
    QA-контур v2.

    БАЗОВЫЕ ПРОВЕРКИ:
    - пустые / None переводы;
    - пустые source-тексты;
    - длина строк и translation drift;
    - подозрительные символы;
    - потерянные / лишние блоки;
    - статистика по ролям layout (по normalized-блокам).

    ДОПОЛНИТЕЛЬНО (v2):
    - смешение алфавитов (латиница/кириллица);
    - склейка латиница+кириллица в одном токене;
    - "торчащие" английские термины в русском переводе;
    - повторяющиеся подряд слова.
    """
    issues: List[Dict[str, Any]] = []

    # --- 1. Индексация по id ---
    src_by_id = {
        str(b.get("id")): b
        for b in normalized_blocks
        if b.get("id") is not None
    }
    tgt_by_id = {
        str(b.get("id")): b
        for b in translated_blocks
        if b.get("id") is not None
    }

    src_ids = set(src_by_id.keys())
    tgt_ids = set(tgt_by_id.keys())

    # Потерянные блоки (есть в source, нет в translate)
    for bid in sorted(src_ids - tgt_ids):
        block = src_by_id[bid]
        issues.append(
            {
                "block_id": bid,
                "page": block.get("page"),
                "order": block.get("order"),
                "type": "lost_block",
                "severity": "high",
                "message": "Block present in normalized_blocks but missing in translated_blocks.",
                "meta": {},
            }
        )

    # Лишние блоки (есть в translate, нет в source)
    for bid in sorted(tgt_ids - src_ids):
        block = tgt_by_id[bid]
        issues.append(
            {
                "block_id": bid,
                "page": block.get("page"),
                "order": block.get("order"),
                "type": "extra_block",
                "severity": "high",
                "message": "Block present in translated_blocks but not in normalized_blocks.",
                "meta": {},
            }
        )

    # Общие id
    common_ids = sorted(src_ids & tgt_ids)

    # Блоки без id: сопоставляем по позиции
    src_no_id = [b for b in normalized_blocks if b.get("id") is None]
    tgt_no_id = [b for b in translated_blocks if b.get("id") is None]
    pair_without_id_count = min(len(src_no_id), len(tgt_no_id))

    paired_blocks: List[tuple[Block, Block]] = []

    for bid in common_ids:
        paired_blocks.append((src_by_id[bid], tgt_by_id[bid]))

    for idx in range(pair_without_id_count):
        paired_blocks.append((src_no_id[idx], tgt_no_id[idx]))

    # --- 2. Проверки по парам блоков ---
    for src_block, tgt_block in paired_blocks:
        block_id = _block_key(src_block)
        src_text = _safe_text(src_block.get("text"))
        tgt_text = _safe_text(tgt_block.get("translated_text"))

        src_len = len(src_text.strip())
        tgt_len = len(tgt_text.strip())

        # 2.1. Пустой или None перевод
        if tgt_len == 0 and src_len > 0:
            severity = "high" if src_len > 20 else "medium"
            issues.append(
                {
                    "block_id": block_id,
                    "page": src_block.get("page"),
                    "order": src_block.get("order"),
                    "type": "empty_translation",
                    "severity": severity,
                    "message": "Translated text is empty while source has content.",
                    "meta": {"src_len": src_len, "tgt_len": tgt_len},
                }
            )

        # 2.2. Пустой source при непустом переводе
        if src_len == 0 and tgt_len > 0:
            issues.append(
                {
                    "block_id": block_id,
                    "page": src_block.get("page"),
                    "order": src_block.get("order"),
                    "type": "empty_source",
                    "severity": "medium",
                    "message": "Source text is empty or missing while translation is non-empty.",
                    "meta": {"src_len": src_len, "tgt_len": tgt_len},
                }
            )

        # 2.3. Translation drift по длине
        if src_len > 0 and tgt_len > 0:
            ratio = tgt_len / max(src_len, 1)
            # Мягкие пороги: <0.3 или >3.0 — подозрительно
            # Жёсткие: <0.15 или >5.0 — ошибка
            if ratio < 0.3 or ratio > 3.0:
                severity = "medium"
                if ratio < 0.15 or ratio > 5.0:
                    severity = "high"
                issues.append(
                    {
                        "block_id": block_id,
                        "page": src_block.get("page"),
                        "order": src_block.get("order"),
                        "type": "length_mismatch",
                        "severity": severity,
                        "message": "Translated text length is suspicious compared to source (translation drift).",
                        "meta": {
                            "src_len": src_len,
                            "tgt_len": tgt_len,
                            "ratio": ratio,
                        },
                    }
                )

        # 2.4. Подозрительные символы
        suspicious = _detect_suspicious_chars(tgt_text)
        if suspicious:
            issues.append(
                {
                    "block_id": block_id,
                    "page": src_block.get("page"),
                    "order": src_block.get("order"),
                    "type": "suspicious_chars",
                    "severity": "medium",
                    "message": "Translated text contains suspicious control or mojibake characters.",
                    "meta": {"chars": suspicious},
                }
            )

        # 2.5. Потенциальные разрывы текста (улучшенная эвристика)
        if src_len > 80:
            stripped = src_text.rstrip()
            if not stripped:
                continue
            # Игнорируем если заканчивается на пунктуацию, закрывающие скобки, или URL/DOI
            if stripped[-1] in ".!?;:,)]}":
                continue
            if stripped.endswith(("-", "–", "—")):
                continue
            # Игнорируем если это URL или DOI
            if re.search(r"\b(https?://|doi\.org/)\S+$", stripped, re.IGNORECASE):
                continue
            # Игнорируем если это список или перечисление
            if re.search(r"[,;]\s*$", stripped):
                continue
            issues.append(
                {
                    "block_id": block_id,
                    "page": src_block.get("page"),
                    "order": src_block.get("order"),
                    "type": "potential_break",
                    "severity": "low",
                    "message": "Source block looks like it may be cut in the middle of a sentence (no terminal punctuation).",
                    "meta": {"src_len": src_len},
                }
            )

        # === QA v2 ДОПОЛНИТЕЛЬНЫЕ ПРОВЕРКИ ПО ПЕРЕВОДУ ===

        # 2.6. Смешение алфавитов
        if tgt_len > 0:
            mix_info = _detect_mixed_alphabet_issue(tgt_text)
            if mix_info:
                issues.append(
                    {
                        "block_id": block_id,
                        "page": src_block.get("page"),
                        "order": src_block.get("order"),
                        "type": "mixed_alphabet",
                        "severity": "medium",
                        "message": "Translated text contains a suspicious mixture of Latin and Cyrillic characters.",
                        "meta": mix_info,
                    }
                )

            # 2.7. Склейка латиница+кириллица в одном токене
            concatenated = _detect_concatenated_scripts(tgt_text)
            if concatenated:
                issues.append(
                    {
                        "block_id": block_id,
                        "page": src_block.get("page"),
                        "order": src_block.get("order"),
                        "type": "concatenated_scripts",
                        "severity": "medium",
                        "message": "Tokens contain both Latin and Cyrillic characters without separation.",
                        "meta": {"tokens": concatenated},
                    }
                )

            # 2.8. Подозрительные английские термины в русском тексте
            suspect_terms = _detect_suspect_english_terms(tgt_text)
            if suspect_terms:
                issues.append(
                    {
                        "block_id": block_id,
                        "page": src_block.get("page"),
                        "order": src_block.get("order"),
                        "type": "suspect_terms_en_in_ru",
                        "severity": "low",
                        "message": "English acupuncture-related terms found in Russian translation.",
                        "meta": {"terms": suspect_terms},
                    }
                )

            # 2.9. Повторяющиеся слова подряд
            reps = _detect_repeated_fragments(tgt_text)
            if reps:
                issues.append(
                    {
                        "block_id": block_id,
                        "page": src_block.get("page"),
                        "order": src_block.get("order"),
                        "type": "repeated_tokens",
                        "severity": "low",
                        "message": "Repeated tokens detected in translated text.",
                        "meta": {"tokens": reps},
                    }
                )

    # --- 3. Диагностика ролей layout (heading/body/...) ---
    role_counter = Counter()
    for block in normalized_blocks:
        meta = block.get("metadata") or {}
        role = meta.get("role", "unknown")
        role_counter[str(role)] += 1

    # --- 4. Метрики качества перевода ---
    translation_metrics = {}
    try:
        from core_engine.qa.translation_metrics import (
            analyze_translation_quality,
            calculate_length_ratio,
        )
        
        # Собираем метрики по всем блокам
        length_ratios = []
        for src_block, tgt_block in paired_blocks:
            src_text = _safe_text(src_block.get("normalized_text") or src_block.get("text"))
            tgt_text = _safe_text(tgt_block.get("translated_text"))
            if src_text and tgt_text:
                ratio = calculate_length_ratio(src_text, tgt_text)
                length_ratios.append(ratio)
        
        if length_ratios:
            translation_metrics = {
                "average_length_ratio": sum(length_ratios) / len(length_ratios),
                "min_length_ratio": min(length_ratios),
                "max_length_ratio": max(length_ratios),
                "blocks_analyzed": len(length_ratios),
            }
    except Exception as e:
        # Если метрики не доступны - пропускаем
        translation_metrics = {"error": str(e)}

    # --- 5. Итоговый статус ---
    severity_counts = Counter(issue["severity"] for issue in issues)
    if severity_counts.get("high", 0) > 0:
        status = "error"
    elif issues:
        status = "warn"
    else:
        status = "ok"

    issues_by_type = Counter(issue["type"] for issue in issues)

    report: QAReport = {
        "status": status,
        "issues": issues,
        "summary": {
            "total_blocks": len(normalized_blocks),
            "checked": len(paired_blocks),
            "issues_total": len(issues),
            "issues_by_type": dict(issues_by_type),
            "issues_by_severity": dict(severity_counts),
            "roles_count": dict(role_counter),
        },
        "translation_metrics": translation_metrics,
    }

    return report
