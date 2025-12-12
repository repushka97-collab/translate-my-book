# core_engine/translate/editor_pass.py

from __future__ import annotations

from typing import List, Dict, Any
import re
from collections import Counter


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
    Адресные фиксы под самые частые артефакты NLLB.
    Здесь можно наращивать словарь по мере появления багов.
    """
    s = text

    # Конкретный артефакт от NLLB: "НТакупунктура" → "Акупунктура"
    s = re.sub(r"\bНТакупунктура\b", "Акупунктура", s)
    s = re.sub(r"\bNТакупунктура\b", "Акупунктура", s)
    
    # Другие частые артефакты NLLB
    # "НТерапия" → "Терапия"
    s = re.sub(r"\bНТерапия\b", "Терапия", s, flags=re.IGNORECASE)
    s = re.sub(r"\bNТерапия\b", "Терапия", s, flags=re.IGNORECASE)
    
    # "НТренировка" → "Тренировка"
    s = re.sub(r"\bНТренировка\b", "Тренировка", s, flags=re.IGNORECASE)
    s = re.sub(r"\bNТренировка\b", "Тренировка", s, flags=re.IGNORECASE)
    
    # Исправляем двойные пробелы после знаков препинания
    s = re.sub(r"([,.!?;:])\s{2,}", r"\1 ", s)
    
    # Исправляем пробелы перед знаками препинания
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)
    
    # Исправляем множественные пробелы
    s = re.sub(r" {2,}", " ", s)
    
    # Исправляем артефакты типа "а а" → "а" (одиночные буквы дублируются)
    s = re.sub(r"\b([а-яё])\s+\1\b", r"\1", s, flags=re.IGNORECASE)
    
    # Исправляем кириллическую "а" в английских словах (часто артефакт NLLB)
    # "а therapist" → "a therapist", но только если перед ней пробел или начало строки
    s = re.sub(r"\bа\s+([a-z])", r"a \1", s, flags=re.IGNORECASE)
    s = re.sub(r"([a-z])\s+а\s+", r"\1 a ", s, flags=re.IGNORECASE)
    
    # Исправляем "а " в начале предложения (если это английский текст)
    # Но только если следующее слово на латинице
    s = re.sub(r"^а\s+([a-z])", r"a \1", s, flags=re.IGNORECASE | re.MULTILINE)
    
    # ============================
    # УНИВЕРСАЛЬНЫЕ ПОСТ-ФИКСЫ ПЕРЕВОДА (без хардкодов под одну книгу)
    # ============================
    
    # 1) Убираем разрывы между буквами в КАПС-заголовках (CHAPTER / PART / ГЛАВА)
    def _collapse_spaced_caps(match: re.Match) -> str:
        return match.group(0).replace(" ", "")
    s = re.sub(r"\b(?:[A-ZА-ЯЁ]\s+){2,}[A-ZА-ЯЁ]\b", _collapse_spaced_caps, s)
    
    # 2) Убираем артефактные одиночные латинские префиксы (d/N) перед словами
    s = re.sub(r"\b[dnDN]\s+(?=[A-Za-zА-Яа-яЁё])", "", s)
    
    # 3) Исправляем пробелы после пунктуации: "методов.Техники" → "методов. Техники"
    s = re.sub(r"([.!?])([А-ЯЁA-Z])", r"\1 \2", s)
    s = re.sub(r"([,;:])([А-ЯЁа-яёA-Za-z])", r"\1 \2", s)
    
    # 4) Исправляем пробелы перед пунктуацией
    s = re.sub(r"\s+([,.!?;:])", r"\1", s)

    return s


def _dedupe_repeated_tokens(text: str) -> str:
    """
    Убираем подряд идущие дублирующиеся токены (регистр нечувствителен).
    Улучшенная версия: лучше обрабатывает числа и знаки препинания.
    """
    # Разбиваем на слова и знаки препинания
    parts = re.findall(r"\S+", text)
    if len(parts) < 2:
        return text

    out = []
    prev = None
    for t in parts:
        # Нормализуем: убираем знаки препинания для сравнения
        norm = re.sub(r"^[\W_]+|[\W_]+$", "", t).lower()
        prev_norm = re.sub(r"^[\W_]+|[\W_]+$", "", prev).lower() if prev else None

        # Пропускаем повтор, но только если это не число и не очень короткое слово
        if prev is not None and norm and prev_norm and norm == prev_norm:
            # Исключения: не удаляем если это число или очень короткое слово (может быть частью структуры)
            if len(norm) > 1 and not norm.isdigit():
                continue
        out.append(t)
        prev = t

    if not out or len(out) == len(parts):
        return text

    # Восстанавливаем текст из отфильтрованных токенов
    # Сохраняем пробелы между токенами
    result = []
    out_idx = 0
    for part in parts:
        if out_idx < len(out) and part == out[out_idx]:
            result.append(part)
            out_idx += 1
        elif out_idx < len(out):
            # Пропущенный токен - не добавляем
            pass
    
    return " ".join(result) if result else text


def _normalize_acu_terms(text: str) -> str:
    """
    Лёгкая нормализация часто встречающихся терминов (yin/yang/qi/chi),
    чтобы убрать лишнюю латиницу.
    """
    repls = [
        (r"\bYin[\-\u2013\u2014/\\&]*Yang\b", "Инь и Ян (Yin & Yang)"),
        (r"\bYin\b", "Инь (Yin)"),
        (r"\bYang\b", "Ян (Yang)"),
        (r"\bQi\b", "ци (Qi)"),
        (r"\bChi\b", "ци (Qi)"),
    ]
    s = text
    for pattern, replacement in repls:
        s = re.sub(pattern, replacement, s, flags=re.IGNORECASE)
    return s


def _replace_mixed_one_letter_tokens(text: str) -> str:
    """
    Если токен состоит из одной латинской буквы между русскими словами (часто артефакт),
    заменяем на кириллический аналог, если есть.
    """
    mapping = {
        "a": "а",
        "e": "е",
        "o": "о",
        "p": "р",
        "c": "с",
        "x": "х",
        "y": "у",
        "k": "к",
        "b": "в",
        "m": "м",
        "t": "т",
    }

    def repl(match):
        token = match.group(0)
        low = token.lower()
        if low in mapping:
            repl_char = mapping[low]
            return repl_char.upper() if token[0].isupper() else repl_char
        return token

    return re.sub(r"\b[A-Za-z]\b", repl, text)

def run_editor_pass(blocks: List[Block], min_chars: int = 0) -> List[Block]:
    """
    Editor-pass v1: работаем поверх перевода, только на длинных блоках.

    Сейчас:
    - режем склейки латиница+кириллица в одном токене (meridiansвсе → meridians все);
    - правим несколько жёстко захардкоженных артефактов (НТакупунктура и т.п.);
    - убираем подряд идущие дубликаты токенов;
    - заменяем одиночные латинские буквы в русских предложениях на кириллические аналоги;
    - нормализуем yin/yang/qi/chi.

    В будущем сюда можно будет подвесить настоящую LLM-редактуру.
    """
    processed: List[Block] = []

    for b in blocks:
        text = b.get("translated_text")
        if not isinstance(text, str):
            processed.append(b)
            continue

        original = text

        # 1) Адресные правки
        text = _apply_custom_fixes(text)

        # 2) Терминологические фиксы (yin/yang/qi/chi)
        text = _normalize_acu_terms(text)

        # 3) Исправление склеенных токенов с разными алфавитами
        text = _fix_mixed_scripts_in_text(text)

        # 4) Удаляем подряд идущие дубликаты
        text = _dedupe_repeated_tokens(text)

        # 5) Одиночные латинские буквы → кириллические аналоги (грубый фикс)
        text = _replace_mixed_one_letter_tokens(text)

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
