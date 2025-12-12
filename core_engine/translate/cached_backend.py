# core_engine/translate/cached_backend.py

from __future__ import annotations

from typing import List, Dict, Any
import hashlib
import json
from pathlib import Path

from core_engine.translate.llm_adapter import LLMBackend


class CachedBackend(LLMBackend):
    """
    Обертка над другим backend с кэшированием переводов.
    
    Кэш сохраняется в cache/translations/<hash>/<text_hash>.json
    и содержит переведенный текст.
    
    Параметры в profile:
      - wrapped_backend: имя backend для обертки (nllb, hybrid, etc.)
      - cache_enabled: включить ли кэширование (default: True)
      - cache_dir: директория для кэша (default: cache/translations)
    """

    def __init__(self, profile: Dict[str, Any]):
        super().__init__(profile)
        self.cache_enabled = profile.get("cache_enabled", True)
        self.cache_dir = Path(profile.get("cache_dir", "cache/translations"))
        self.wrapped_backend_name = profile.get("wrapped_backend", "nllb")
        
        # Создаем wrapped backend
        wrapped_profile = {k: v for k, v in profile.items() if not k.startswith("cache_") and k != "wrapped_backend"}
        wrapped_profile["backend"] = self.wrapped_backend_name
        
        from core_engine.translate.llm_adapter import make_backend
        self.wrapped_backend = make_backend(wrapped_profile)

    def _get_cache_key(self, text: str, source_lang: str, target_lang: str) -> str:
        """
        Генерирует ключ кэша на основе текста и языков.
        """
        key_data = f"{source_lang}:{target_lang}:{text}"
        return hashlib.sha256(key_data.encode("utf-8")).hexdigest()

    def _get_cache_path(self, cache_key: str) -> Path:
        """
        Возвращает путь к файлу кэша.
        """
        # Используем первые 2 символа хеша для организации директорий
        subdir = cache_key[:2]
        cache_subdir = self.cache_dir / subdir
        cache_subdir.mkdir(parents=True, exist_ok=True)
        return cache_subdir / f"{cache_key}.json"

    def _load_from_cache(self, cache_key: str) -> str | None:
        """
        Загружает перевод из кэша.
        """
        if not self.cache_enabled:
            return None
        
        cache_path = self._get_cache_path(cache_key)
        if not cache_path.exists():
            return None
        
        try:
            with cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("translated_text", None)
        except Exception as e:
            print(f"[CACHE][WARN] Failed to load cache for {cache_key[:8]}: {e}")
            return None

    def _save_to_cache(self, cache_key: str, original_text: str, translated_text: str, source_lang: str, target_lang: str) -> None:
        """
        Сохраняет перевод в кэш.
        """
        if not self.cache_enabled:
            return
        
        cache_path = self._get_cache_path(cache_key)
        try:
            data = {
                "original_text": original_text,
                "translated_text": translated_text,
                "source_lang": source_lang,
                "target_lang": target_lang,
            }
            with cache_path.open("w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"[CACHE][WARN] Failed to save cache for {cache_key[:8]}: {e}")

    def translate(self, blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Переводит блоки с использованием кэша.
        """
        source_lang = self.profile.get("source_lang", "en")
        target_lang = self.profile.get("target_lang", "ru")
        
        # Разделяем блоки на кэшированные и некэшированные
        cached_blocks: List[Dict[str, Any]] = []
        uncached_blocks: List[Dict[str, Any]] = []
        cache_map: Dict[int, str] = {}  # Индекс блока -> cache_key
        
        for i, block in enumerate(blocks):
            text = block.get("text") or block.get("normalized_text", "")
            if not text.strip():
                cached_blocks.append(block)
                continue
            
            cache_key = self._get_cache_key(text, source_lang, target_lang)
            cached_text = self._load_from_cache(cache_key)
            
            if cached_text is not None:
                # Используем кэшированный перевод
                new_block = dict(block)
                new_block["translated_text"] = cached_text
                new_block["metadata"] = new_block.get("metadata", {})
                new_block["metadata"]["cache_hit"] = True
                cached_blocks.append(new_block)
            else:
                # Нужен перевод
                uncached_blocks.append(block)
                cache_map[len(uncached_blocks) - 1] = cache_key
        
        cache_hits = len(cached_blocks)
        if cache_hits > 0:
            print(f"[CACHE] Cache hits: {cache_hits}/{len(blocks)} blocks")
        
        if not uncached_blocks:
            return cached_blocks
        
        # Переводим некэшированные блоки
        print(f"[CACHE] Translating {len(uncached_blocks)} uncached blocks...")
        translated_blocks = self.wrapped_backend.translate(uncached_blocks)
        
        # Сохраняем в кэш и объединяем результаты
        for i, block in enumerate(translated_blocks):
            original_text = uncached_blocks[i].get("text") or uncached_blocks[i].get("normalized_text", "")
            translated_text = block.get("translated_text", "")
            cache_key = cache_map[i]
            
            if translated_text.strip():
                self._save_to_cache(cache_key, original_text, translated_text, source_lang, target_lang)
        
        # Объединяем кэшированные и переведенные блоки
        # Восстанавливаем исходный порядок
        result: List[Dict[str, Any]] = []
        
        # Создаем маппинг: cache_key -> переведенный блок
        cached_map = {self._get_cache_key(b.get("text") or b.get("normalized_text", ""), source_lang, target_lang): b 
                     for b in cached_blocks if (b.get("text") or b.get("normalized_text", "")).strip()}
        translated_map = {}
        for i, block in enumerate(uncached_blocks):
            text = block.get("text") or block.get("normalized_text", "")
            if text.strip():
                cache_key = self._get_cache_key(text, source_lang, target_lang)
                translated_map[cache_key] = translated_blocks[i]
        
        # Восстанавливаем порядок
        for block in blocks:
            text = block.get("text") or block.get("normalized_text", "")
            if not text.strip():
                result.append(block)
                continue
            
            cache_key = self._get_cache_key(text, source_lang, target_lang)
            
            if cache_key in cached_map:
                # Берем из кэшированных
                result.append(cached_map[cache_key])
            elif cache_key in translated_map:
                # Берем из переведенных
                result.append(translated_map[cache_key])
            else:
                # Fallback: оригинальный блок
                result.append(block)
        
        return result

