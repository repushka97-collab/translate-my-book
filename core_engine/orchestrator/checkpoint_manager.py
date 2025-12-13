# core_engine/orchestrator/checkpoint_manager.py
"""
[ADVANCED PDF TRANSLATION MODE] Система чекпоинтов для восстановления после сбоев.
"""

import json
import os
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime


class CheckpointManager:
    """Управляет чекпоинтами для восстановления процесса перевода."""
    
    def __init__(self, checkpoint_dir: str = "checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save_checkpoint(
        self,
        book_id: str,
        page_num: int,
        data: Dict[str, Any],
        stage: str = "translate"
    ) -> Path:
        """
        Сохраняет чекпоинт для страницы.
        
        Args:
            book_id: ID книги
            page_num: номер страницы
            data: данные для сохранения
            stage: этап обработки ("translate", "export", etc.)
        
        Returns:
            Путь к сохраненному чекпоинту
        """
        checkpoint_file = self.checkpoint_dir / f"{book_id}_page_{page_num:04d}_{stage}.json"
        
        checkpoint_data = {
            "book_id": book_id,
            "page_num": page_num,
            "stage": stage,
            "timestamp": datetime.now().isoformat(),
            "data": data
        }
        
        checkpoint_file.write_text(
            json.dumps(checkpoint_data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
        
        return checkpoint_file
    
    def load_checkpoint(
        self,
        book_id: str,
        page_num: int,
        stage: str = "translate"
    ) -> Optional[Dict[str, Any]]:
        """
        Загружает чекпоинт для страницы.
        
        Returns:
            Данные чекпоинта или None если не найден
        """
        checkpoint_file = self.checkpoint_dir / f"{book_id}_page_{page_num:04d}_{stage}.json"
        
        if not checkpoint_file.exists():
            return None
        
        try:
            data = json.loads(checkpoint_file.read_text(encoding="utf-8"))
            return data.get("data")
        except Exception:
            return None
    
    def list_checkpoints(self, book_id: str, stage: Optional[str] = None) -> list:
        """
        Список всех чекпоинтов для книги.
        
        Args:
            book_id: ID книги
            stage: фильтр по этапу (опционально)
        
        Returns:
            Список путей к чекпоинтам
        """
        pattern = f"{book_id}_page_*"
        if stage:
            pattern += f"_{stage}.json"
        else:
            pattern += "*.json"
        
        checkpoints = list(self.checkpoint_dir.glob(pattern))
        return sorted(checkpoints)
    
    def clear_checkpoints(self, book_id: str) -> int:
        """
        Удаляет все чекпоинты для книги.
        
        Returns:
            Количество удаленных файлов
        """
        checkpoints = self.list_checkpoints(book_id)
        count = 0
        for cp in checkpoints:
            try:
                cp.unlink()
                count += 1
            except Exception:
                pass
        return count

