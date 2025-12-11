# core_engine/translate/editor_pass.py

from __future__ import annotations

from typing import List, Dict, Any
import re


Block = Dict[str, Any]


def _script_of_char(ch: str) -> str:
    """Определяем, к какому алфавиту относится символ."""
    code = ord(ch)
    # латиница
    if 0x0041 <= code <= 0x005A or 0x0061 <= code <= 0x007A:
        return "latin"
    # кириллица
    if 0x0400 <= code <= 0x04FF or ch.lower() == "ё":
        return "cyr"
    return "other"


def _split_mixed_token(token: str) -> str:
    """
    Разбиваем токен типа 'meridiansвсе' или 'Yangи' на части
    по границе смены алфавита (латиница/кириллица).
    """
    if not token or len(token) < 2:
        return token

    scripts = [_script_of_char(ch) for ch in token]
    has_latin = any(s == "latin" for s in scripts)
    has_cyr = any(s == "cyr" for s in scripts)

    # если не обе системы — не трогаем
    if not (has_latin and has_cyr):
        return token

    parts = []
    current = token[0]
    current_script = scripts[0]

    for ch, sc in zip(token[1:], scripts[1:]):
        if sc == current_script or sc == "other" or current_script == "other":
            current += ch
            if current_script == "other":
                current_script = sc
        else:
            parts.append(current)
            current = ch
            current_script = sc

    if current:
        parts.append(current)

    # склеиваем с пробелами
    return " ".join(p for p in parts if p)


def _fix_mixed_scripts_in_text(text: str) -> str:
    tokens = re.findall(r"\S+", text)
    if not tokens:
        return text

    new_tokens: List[str] = []
    changed = False

    for t in tokens:
        fixed = _split_mixed_token(t)
        if fixed != t:
            changed = True
        new_tokens.append(fixed)

    if not changed:
        return text

    # сохраняем исходные разделители максимально просто
    return re.sub(
        r"\S+",
        lambda _: new_tokens.pop(0),
        text,
    )


def _apply_custom_fixes(text: str) -> str:
    """
    Адресные фиксы под самые частые артефакты.
    Здесь можно наращивать словарь по мере появления багов.
    """
    s = text

    # Конкретный артефакт от NLLB: "НТакупунктура" → "Акупунктура"
    s = re.sub(r"\bНТакупунктура\b", "Акупунктура", s)

    # Иногда слипается 'NТакупунктура' → "Акупунктура" (грубый фикс)
    s = re.sub(r"\bNТакупунктура\b", "Акупунктура", s)

    return s


def run_editor_pass(blocks: List[Block], min_chars: int = 200) -> List[Block]:
    """
    Editor-pass v1: работаем поверх перевода, только на длинных блоках.

    Сейчас:
    - режем склейки латиница+кириллица в одном токене (meridiansвсе → meridians все);
    - правим несколько жёстко захардкоженных артефактов (НТакупунктура и т.п.).

    В будущем сюда можно будет подвесить настоящую LLM-редактуру.
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

        original = text

        # 1) Адресные правки
        text = _apply_custom_fixes(text)

        # 2) Исправление склеенных токенов с разными алфавитами
        text = _fix_mixed_scripts_in_text(text)

        if text == original:
            processed.append(b)
            continue

        new_b = dict(b)
        new_meta = dict(new_b.get("metadata") or {})
        new_meta["editor_pass"] = "heuristic_v1"
        new_b["metadata"] = new_meta
        new_b["translated_text"] = text

        processed.append(new_b)

    return processed
