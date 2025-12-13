# core_engine/translate/hybrid_backend.py

from __future__ import annotations

from typing import List, Dict, Any
import requests

from core_engine.translate.nllb_backend import translate_with_nllb

# Импортируем LLMBackend из llm_adapter, но только для типизации
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from core_engine.translate.llm_adapter import LLMBackend
else:
    # В runtime используем прямое наследование через импорт
    import sys
    from core_engine.translate import llm_adapter
    LLMBackend = llm_adapter.LLMBackend


class HybridBackend(LLMBackend):
    """
    Гибридный backend: NLLB baseline + LLM refine.
    
    Стратегия:
    1. Все блоки переводим через NLLB (быстро)
    2. Длинные/важные блоки улучшаем через LLM (Ollama/Qwen)
    
    Параметры в profile:
      - nllb_*: параметры для NLLB (model_name, device, batch_size, etc.)
      - refine_enabled: включить ли улучшение через LLM (default: True)
      - refine_min_length: минимальная длина блока для улучшения (default: 200)
      - refine_important_types: типы блоков для обязательного улучшения (heading, caption)
      - ollama_endpoint: URL Ollama сервера (default: http://127.0.0.1:11434)
      - ollama_model: модель Ollama (default: qwen2.5:7b)
    """

    def __init__(self, profile: Dict[str, Any]):
        super().__init__(profile)
        self.refine_enabled = profile.get("refine_enabled", True)
        self.refine_min_length = profile.get("refine_min_length", 200)
        self.refine_important_types = profile.get("refine_important_types", ["heading1", "heading2", "caption"])
        self.ollama_endpoint = profile.get("ollama_endpoint", "http://127.0.0.1:11434")
        self.ollama_model = profile.get("ollama_model", "qwen2.5:7b")

    def _call_ollama_refine(self, en_text: str, nllb_translation: str, prev_context: str = "", next_context: str = "") -> str:
        """
        Улучшает перевод через Ollama с учетом контекста.
        """
        context_part = ""
        if prev_context or next_context:
            context_part = "\n\nКонтекст для лучшего понимания:\n"
            if prev_context:
                context_part += f"Предыдущий текст (уже переведен): {prev_context[:200]}...\n"
            if next_context:
                context_part += f"Следующий текст (оригинал): {next_context[:200]}...\n"
        
        prompt = f"""Ты профессиональный переводчик с английского на русский. Улучши следующий перевод, сделав его более естественным и точным, сохраняя все термины и технические детали. Учитывай контекст для лучшей связности текста.{context_part}

Оригинал (английский):
{en_text}

Текущий перевод (нужно улучшить):
{nllb_translation}

Улучшенный перевод (только текст, без пояснений):"""

        url = f"{self.ollama_endpoint.rstrip('/')}/api/generate"
        payload = {
            "model": self.ollama_model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,  # Низкая температура для более точного перевода
                "top_p": 0.9,
            }
        }

        try:
            resp = requests.post(url, json=payload, timeout=120)
            resp.raise_for_status()
            data = resp.json()
            refined = data.get("response", "").strip()
            
            # Очищаем ответ от возможных пояснений
            if "\n" in refined:
                refined = refined.split("\n")[0]
            refined = refined.strip('"').strip("'").strip()
            
            return refined if refined else nllb_translation
        except Exception as e:
            print(f"[HYBRID][WARN] Ollama refine failed: {e}, using NLLB translation")
            return nllb_translation

    def _should_refine(self, block: Dict[str, Any], nllb_text: str) -> bool:
        """
        Определяет, нужно ли улучшать блок через LLM.
        Расширенная версия: учитывает больше типов и сниженный порог длины.
        """
        if not self.refine_enabled:
            return False
        
        # Проверяем важные типы (расширенный список)
        metadata = block.get("metadata", {})
        role = metadata.get("role", "")
        block_type = block.get("type", "")
        
        important_roles = self.refine_important_types + ["heading3", "abstract", "introduction", "conclusion"]
        if role in important_roles or block_type in ["heading1", "heading2", "heading3"]:
            return True
        
        # Проверяем длину (сниженный порог для лучшего качества)
        min_len = max(100, self.refine_min_length // 2)  # Снижаем порог вдвое
        if len(nllb_text) >= min_len:
            return True
        
        # Также улучшаем блоки с техническими терминами или сложными конструкциями
        src_text = block.get("text") or block.get("normalized_text", "")
        if src_text:
            # Если есть много заглавных букв (акронимы) или технические термины
            if sum(1 for c in src_text if c.isupper()) > len(src_text) * 0.3:
                return True
        
        return False
    
    def _get_context(self, blocks: List[Dict[str, Any]], current_idx: int, context_window: int = 2) -> tuple[str, str]:
        """
        Получает контекст из предыдущих и следующих блоков для улучшения перевода.
        Возвращает (previous_context, next_context).
        """
        prev_texts = []
        next_texts = []
        
        # Предыдущие блоки
        for i in range(max(0, current_idx - context_window), current_idx):
            txt = blocks[i].get("translated_text", "").strip()
            if txt:
                prev_texts.append(txt)
        
        # Следующие блоки (оригинал, не переведенный)
        for i in range(current_idx + 1, min(len(blocks), current_idx + 1 + context_window)):
            txt = blocks[i].get("text") or blocks[i].get("normalized_text", "").strip()
            if txt:
                next_texts.append(txt)
        
        prev_context = " ".join(prev_texts[-2:])  # Последние 2 блока
        next_context = " ".join(next_texts[:2])   # Первые 2 блока
        
        return prev_context, next_context

    def translate(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Гибридный перевод: NLLB baseline + LLM refine для важных блоков.
        """
        # Шаг 1: Переводим все блоки через NLLB
        nllb_profile = {
            "source_lang": self.profile.get("source_lang", "en"),
            "target_lang": self.profile.get("target_lang", "ru"),
            "batch_size": self.profile.get("nllb_batch_size", self.profile.get("batch_size", 16)),
            "max_length": self.profile.get("nllb_max_length", self.profile.get("max_length", 640)),
            "model_name": self.profile.get("nllb_model_name", "facebook/nllb-200-distilled-600M"),
            "device": self.profile.get("nllb_device", self.profile.get("device", "cuda")),
        }
        
        print(f"[HYBRID] Step 1: Translating {len(blocks)} blocks with NLLB...")
        translated = translate_with_nllb(
            blocks,
            source_lang=nllb_profile["source_lang"],
            target_lang=nllb_profile["target_lang"],
            batch_size=nllb_profile["batch_size"],
            max_length=nllb_profile["max_length"],
            model_name=nllb_profile["model_name"],
            device=nllb_profile["device"],
        )

        # Шаг 2: Улучшаем важные блоки через LLM с контекстом
        if self.refine_enabled:
            refined_count = 0
            for i, block in enumerate(translated):
                nllb_text = block.get("translated_text", "").strip()
                if not nllb_text:
                    continue
                
                if self._should_refine(block, nllb_text):
                    src_text = block.get("text") or block.get("normalized_text", "")
                    if src_text.strip():
                        # Получаем контекст из соседних блоков
                        prev_ctx, next_ctx = self._get_context(translated, i, context_window=2)
                        
                        refined = self._call_ollama_refine(src_text, nllb_text, prev_ctx, next_ctx)
                        if refined and refined != nllb_text:
                            block["translated_text"] = refined
                            block["metadata"] = block.get("metadata", {})
                            block["metadata"]["refined"] = True
                            refined_count += 1
                            if refined_count % 5 == 0:
                                print(f"[HYBRID] Refined {refined_count} blocks...")
            
            if refined_count > 0:
                print(f"[HYBRID] Step 2: Refined {refined_count}/{len(blocks)} blocks with LLM (context-aware)")

        return translated

