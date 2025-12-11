import os
import json
import hashlib
from datetime import datetime

# Корневая директория кэша переводов
CACHE_ROOT = "cache/translations"

def ensure_dir(path: str):
    """Создаёт директорию, если её нет."""
    os.makedirs(path, exist_ok=True)

def hash_text(text: str) -> str:
    """SHA256 от текста — для определения, изменился ли блок."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()

def cache_path(book_id: str, block_id: str) -> str:
    """Путь к файлу кэша для конкретного блока."""
    return os.path.join(CACHE_ROOT, book_id, f"{block_id}.json")

def load_from_cache(book_id: str, block_id: str, text_hash: str, model_name: str):
    """Пытается достать перевод из кэша. Возвращает строку или None."""
    path = cache_path(book_id, block_id)
    if not os.path.exists(path):
        return None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Проверяем: совпадает ли хэш текста и модель перевода
    if data.get("src_hash") == text_hash and data.get("model") == model_name:
        return data.get("translated")

    return None

def save_to_cache(book_id: str, block_id: str, text_hash: str, model_name: str, translated_text: str):
    """Сохраняет результат перевода в кэш."""
    path = cache_path(book_id, block_id)
    ensure_dir(os.path.dirname(path))

    data = {
        "src_hash": text_hash,
        "model": model_name,
        "translated": translated_text,
        "timestamp": datetime.utcnow().isoformat() + "Z"
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

