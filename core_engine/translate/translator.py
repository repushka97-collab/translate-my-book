"""
Translation utilities for EWB Core Engine.

Задачи:
- взять нормализованный текст блоков (или raw_text, если нормализации нет);
- прогнать через LLMAdapter;
- сохранить protected tokens, выделенные на этапе normalize;
- заполнить block.translated_text.
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
import re

from core_engine.core.models import BookDocument, Block  # type: ignore


def _looks_like_formula_detection(text: str) -> bool:
    """
    Детектирует математические формулы для пропуска перевода.
    Упрощенная версия для использования в translator.
    """
    t = text.strip()
    if not t or len(t) < 3:
        return False
    
    # Математические символы
    math_symbols = r"[∑∫√≤≥≠≈±×÷∞∈∉⊂⊃∪∩∅→←⇒⇐=]"
    if re.search(math_symbols, t):
        # Проверяем, что это не просто текст с одним символом
        if len(re.findall(math_symbols, t)) >= 2 or ("=" in t and len(t) < 50):
            return True
    
    # Верхние/нижние индексы
    if re.search(r"[¹²³⁴⁵⁶⁷⁸⁹⁰₀₁₂₃₄₅₆₇₈₉]", t):
        return True
    
    # Дроби вида a/b или \frac
    if re.search(r"\b\d+/\d+\b", t) or "\\frac" in t or "\\sqrt" in t:
        return True
    
    # Греческие буквы в математическом контексте (α, β, γ, δ, etc.)
    greek_letters = r"[αβγδεζηθικλμνξοπρστυφχψωΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ]"
    if re.search(greek_letters, t) and len(t) < 100:
        return True
    
    # LaTeX-подобные команды
    if re.search(r"\\[a-zA-Z]+\{", t):
        return True
    
    # Паттерны вида x^2, x_1, etc.
    if re.search(r"\w+[\^_]\d+", t) and len(t) < 50:
        return True
    
    return False


def preserve_tokens(src: str, dst: str, tokens: List[str]) -> str:
    """
    Грубый, но предсказуемый механизм защиты токенов.

    На вход подаём:
      - src: исходный текст (для совместимости, сейчас почти не используем);
      - dst: результат перевода;
      - tokens: список protected_tokens из metadata.

    Логика:
      - если токен не встретился в переведённом тексте, дописываем его в конец
        в квадратных скобках, чтобы он физически не потерялся.
    """
    if not dst:
        dst = ""

    dst_out = dst
    for token in tokens or []:
        # Уже есть — не трогаем.
        if token in dst_out:
            continue
        # Добавляем «хвостом» в [] — чтобы потом QA/человек могли поправить место.
        if dst_out and not dst_out.endswith(" "):
            dst_out += " "
        dst_out += f"[{token}]"

    return dst_out


def _get_block_tokens(block: Block) -> List[str]:
    """Достаёт protected_tokens из metadata блока, если они есть."""
    meta: Dict[str, Any] = getattr(block, "metadata", {}) or {}
    tokens = meta.get("protected_tokens") or []
    if not isinstance(tokens, list):
        return []
    # фильтр по типу на всякий случай
    return [t for t in tokens if isinstance(t, str) and t.strip()]


def translate_block(
    block: Block,
    adapter,
    source_lang: str = "en",
    target_lang: str = "ru",
) -> None:
    """
    Переводит один блок in-place.

    - источник текста: normalized_text > raw_text;
    - переводит через adapter.translate(text, context);
    - сохраняет protected_tokens;
    - НЕ переводит формулы - сохраняет как есть;
    - результат пишет в block.translated_text.
    """
    raw = getattr(block, "raw_text", "") or ""
    normalized = getattr(block, "normalized_text", "") or ""

    text = normalized or raw
    if not text:
        # Нечего переводить — оставляем пустоту.
        block.translated_text = ""  # type: ignore[attr-defined]
        return

    # Проверяем, является ли блок формулой - не переводим
    block_type = getattr(block, "type", None)
    if block_type and hasattr(block_type, "name") and block_type.name == "FORMULA":
        # Формула - сохраняем как есть
        block.translated_text = text  # type: ignore[attr-defined]
        return
    
    # Также проверяем через metadata и текст
    meta: Dict[str, Any] = getattr(block, "metadata", {}) or {}
    if meta.get("role") == "formula" or _looks_like_formula_detection(text):
        block.translated_text = text  # type: ignore[attr-defined]
        return

    tokens = _get_block_tokens(block)

    context = {
        "source_lang": source_lang,
        "target_lang": target_lang,
        "block_id": getattr(block, "id", None),
        "page_number": getattr(block, "page_number", None),
        "block_type": getattr(block, "type", None),
        "protected_tokens": tokens,
    }

    try:
        translated = adapter.translate(text, context)
    except Exception:
        # Fallback: в случае любой ошибки не ломаем пайплайн.
        translated = text

    translated = translated or ""
    translated = preserve_tokens(text, translated, tokens)

    block.translated_text = translated  # type: ignore[attr-defined]


def translate_document(
    doc: BookDocument,
    adapter,
    source_lang: str = "en",
    target_lang: str = "ru",
) -> None:
    """
    Главная точка входа перевода.

    Проходит по всем страницам и блокам и переводит их in-place.
    """
    if doc is None or not getattr(doc, "pages", None):
        return

    for page in doc.pages:
        if not getattr(page, "blocks", None):
            continue

        for block in page.blocks:
            translate_block(block, adapter, source_lang=source_lang, target_lang=target_lang)

