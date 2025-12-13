# core_engine/translate/llm_adapter.py

from __future__ import annotations

from typing import List, Dict, Any
from dataclasses import dataclass

import requests  # для экспериментального Ollama-backend

from core_engine.config.llm_config import get_llm_profile
from core_engine.translate.nllb_backend import translate_with_nllb
from core_engine.translate.quality_pass import run_quality_pass
from core_engine.translate.editor_pass import run_editor_pass
from core_engine.translate.term_normalizer import run_term_normalizer
from core_engine.translate.heading_translator import process_headings_in_blocks


# =========================
#   БАЗОВЫЙ ИНТЕРФЕЙС BACKEND'ОВ
# =========================

@dataclass
class LLMBackend:
    """Базовый интерфейс backend-модели."""
    profile: Dict[str, Any]

    def translate(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        raise NotImplementedError


# =========================
#   NLLB BACKEND (GPU/CPU)
# =========================

class NLLBBackend(LLMBackend):
    """
    Обёртка над translate_with_nllb.

    Ожидает в profile:
      - model_name
      - device ("cuda" / "cpu")
      - batch_size
      - max_length
      - source_lang
      - target_lang
    """

    def translate(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return translate_with_nllb(
            blocks,
            source_lang=self.profile.get("source_lang", "en"),
            target_lang=self.profile.get("target_lang", "ru"),
            batch_size=self.profile.get("batch_size", 8),
            max_length=self.profile.get("max_length", 512),
            model_name=self.profile.get(
                "model_name", "facebook/nllb-200-distilled-1.3B"
            ),
            device=self.profile.get("device", "cuda"),
        )


# =========================
#   OLLAMA BACKEND (ЭКСПЕРИМЕНТАЛЬНЫЙ)
# =========================

class OllamaBackend(LLMBackend):
    """
    Экспериментальный backend для Ollama.
    Включается ТОЛЬКО если в llm.yaml явно указан backend: ollama.
    """

    def _call_ollama(self, prompt: str) -> str:
        endpoint = self.profile.get("ollama_endpoint", "http://127.0.0.1:11434")
        model = self.profile.get("ollama_model", "llama3")

        url = f"{endpoint.rstrip('/')}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        try:
            resp = requests.post(url, json=payload, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            text = data.get("response", "")
            return text or ""
        except Exception as e:
            # Если Ollama умерла — не валим весь пайп, возвращаем исходный текст.
            print(f"[LLM][OLLAMA] ERROR: {e}")
            return ""

    def translate(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        translated: List[Dict[str, Any]] = []

        for b in blocks:
            src_text = b.get("text") or b.get("normalized_text") or ""
            if not src_text.strip():
                out_text = src_text
            else:
                out_text = self._call_ollama(src_text)
                if not out_text:
                    # Fallback: если модель ничего не дала — оставляем исходник
                    out_text = src_text

            new_b = dict(b)
            new_b["translated_text"] = out_text
            translated.append(new_b)

        return translated


# =========================
#   PLACEHOLDER BACKEND (DEV-РЕЖИМ)
# =========================

class PlaceholderBackend(LLMBackend):
    """
    DEV-режим — быстрые прогоны без реального перевода.
    Берёт исходный текст и чистит его от XML-недопустимых символов,
    чтобы python-docx не падал.
    """

    @staticmethod
    def _sanitize_for_xml(text: str) -> str:
        if not isinstance(text, str):
            text = str(text)
        # Разрешаем таб, перевод строки и возврат каретки, остальное < 0x20 выкидываем
        return "".join(
            ch
            for ch in text
            if ch in ("\t", "\n", "\r") or ord(ch) >= 0x20
        )

    def translate(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        translated: List[Dict[str, Any]] = []
        for b in blocks:
            src = (
                b.get("translated_text")
                or b.get("normalized_text")
                or b.get("text")
                or ""
            )
            clean = self._sanitize_for_xml(src)
            new_b = dict(b)
            new_b["translated_text"] = clean
            translated.append(new_b)
        return translated



# =========================
#   ФАБРИКА BACKEND'ОВ
# =========================

def make_backend(profile: Dict[str, Any]) -> LLMBackend:
    backend = str(profile.get("backend", "nllb")).lower()

    # Проверяем, нужен ли кэш
    if profile.get("cache_enabled", False):
        from core_engine.translate.cached_backend import CachedBackend
        return CachedBackend(profile)

    if backend == "hybrid":
        # Ленивый импорт для избежания циклических зависимостей
        from core_engine.translate.hybrid_backend import HybridBackend
        return HybridBackend(profile)
    if backend == "nllb":
        return NLLBBackend(profile)
    if backend == "ollama":
        return OllamaBackend(profile)
    if backend == "placeholder":
        return PlaceholderBackend(profile)

    # Fallback на placeholder, чтобы пайп не падал
    return PlaceholderBackend(profile)


# =========================
#   ПУБЛИЧНЫЙ API ЯДРА
# =========================

def translate_blocks(
    blocks: List[Dict[str, Any]],
    source_lang: str = "en",
    target_lang: str = "ru",
    mode: str | None = None,
) -> List[Dict[str, Any]]:
    """
    Главная точка входа ядра для перевода блоков.

    mode ожидается такой же, как имя профиля в configs/llm.yaml:
      - "dev"  → backend: placeholder (мгновенный прогон, без перевода)
      - "fast" → обычно NLLB-600M на CUDA
      - "full" → NLLB-1.3B (CPU или CUDA, как задашь в профиле)

    get_llm_profile(mode) возвращает профиль, в котором уже прописаны:
      - backend
      - model_name / device / batch_size / max_length
      - при необходимости source_lang / target_lang
    """

    # Загружаем профиль для нужного режима
    profile = get_llm_profile(mode)

    # Синхронизируем языки с параметрами пайплайна
    profile["source_lang"] = profile.get("source_lang", source_lang) or source_lang
    profile["target_lang"] = profile.get("target_lang", target_lang) or target_lang

    # Строим backend
    backend = make_backend(profile)

    # Пропускаем формулы - не переводим их
    import re
    def _is_formula_block(block: Dict[str, Any]) -> bool:
        """Проверяет, является ли блок формулой."""
        block_type = block.get("type")
        if isinstance(block_type, str) and block_type.lower() == "formula":
            return True
        if isinstance(block_type, dict) and block_type.get("name") == "FORMULA":
            return True
        metadata = block.get("metadata", {})
        if metadata.get("role") == "formula":
            return True
        text = (block.get("normalized_text") or block.get("text") or "").strip()
        if not text or len(text) < 3:
            return False
        # Математические символы
        if re.search(r"[∑∫√≤≥≠≈±×÷∞∈∉⊂⊃∪∩∅→←⇒⇐=]", text):
            if len(re.findall(r"[∑∫√≤≥≠≈±×÷∞∈∉⊂⊃∪∩∅→←⇒⇐=]", text)) >= 2 or ("=" in text and len(text) < 50):
                return True
        # LaTeX команды
        if re.search(r"\\[a-zA-Z]+\{", text) or "\\frac" in text or "\\sqrt" in text:
            return True
        # Индексы/степени
        if re.search(r"[¹²³⁴⁵⁶⁷⁸⁹⁰₀₁₂₃₄₅₆₇₈₉]", text):
            return True
        # Паттерны x^2, x_1
        if re.search(r"\w+[\^_]\d+", text) and len(text) < 50:
            return True
        return False

    # Обрабатываем формулы отдельно - сохраняем как есть
    for block in blocks:
        if _is_formula_block(block):
            text = block.get("normalized_text") or block.get("text") or ""
            block["translated_text"] = text
            block["metadata"] = block.get("metadata", {})
            block["metadata"]["formula_preserved"] = True

    # Перевод (или подстановка текста) - формулы уже обработаны
    translated = backend.translate(blocks)

    # Quality-pass v1: лёгкая чистка
    translated = run_quality_pass(translated)

    # Editor-pass v1: исправление артефактов
    translated = run_editor_pass(translated)

    # Term-normalizer v1: приведение терминов
    translated = run_term_normalizer(translated)
    
    # Heading-translator: специальная обработка заголовков
    translated = process_headings_in_blocks(translated)

    return translated
