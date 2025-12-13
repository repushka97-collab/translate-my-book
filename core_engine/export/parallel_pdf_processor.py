"""
[PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

Пакетная обработка с чекпоинтами для больших PDF (300+ страниц).
Основано на: https://github.com/pymupdf/PyMuPDF-Utilities/blob/master/examples/parallel-processing.py
"""

from __future__ import annotations

from typing import List, Dict, Any, Callable, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import time


class CheckpointManager:
    """
    Управление чекпоинтами для восстановления после падения.
    """
    
    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    
    def save_checkpoint(self, book_id: str, page_num: int, data: Dict[str, Any]) -> None:
        """Сохраняет чекпоинт для страницы."""
        checkpoint_file = self.checkpoint_dir / f"{book_id}_p{page_num}.json"
        checkpoint_file.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    
    def load_checkpoint(self, book_id: str, page_num: int) -> Optional[Dict[str, Any]]:
        """Загружает чекпоинт для страницы."""
        checkpoint_file = self.checkpoint_dir / f"{book_id}_p{page_num}.json"
        if checkpoint_file.exists():
            try:
                return json.loads(checkpoint_file.read_text(encoding="utf-8"))
            except Exception:
                return None
        return None
    
    def get_processed_pages(self, book_id: str) -> set:
        """Возвращает множество обработанных страниц."""
        processed = set()
        for checkpoint_file in self.checkpoint_dir.glob(f"{book_id}_p*.json"):
            try:
                page_num = int(checkpoint_file.stem.split("_p")[1])
                processed.add(page_num)
            except Exception:
                continue
        return processed


def process_pages_parallel(
    total_pages: int,
    process_page_fn: Callable[[int], Dict[str, Any]],
    book_id: str,
    checkpoint_dir: Path,
    max_workers: int = 4,
    checkpoint_interval: int = 10
) -> List[Dict[str, Any]]:
    """
    Параллельная обработка страниц с чекпоинтами.
    
    Args:
        total_pages: общее количество страниц
        process_page_fn: функция обработки страницы (page_num) -> result_dict
        book_id: ID книги для чекпоинтов
        checkpoint_dir: директория для чекпоинтов
        max_workers: количество потоков
        checkpoint_interval: сохранять чекпоинт каждые N страниц
    
    Returns:
        Список результатов обработки страниц
    """
    checkpoint_mgr = CheckpointManager(checkpoint_dir)
    processed_pages = checkpoint_mgr.get_processed_pages(book_id)
    
    results: List[Dict[str, Any]] = []
    results_lock = {}  # простой словарь для результатов
    
    def process_with_checkpoint(page_num: int) -> Dict[str, Any]:
        """Обрабатывает страницу с проверкой чекпоинта."""
        # Проверяем чекпоинт
        checkpoint = checkpoint_mgr.load_checkpoint(book_id, page_num)
        if checkpoint:
            return checkpoint
        
        # Обрабатываем страницу
        try:
            result = process_page_fn(page_num)
            result["page"] = page_num
            result["processed_at"] = time.time()
            
            # Сохраняем чекпоинт
            checkpoint_mgr.save_checkpoint(book_id, page_num, result)
            
            return result
        except Exception as e:
            return {
                "page": page_num,
                "error": str(e),
                "processed_at": time.time()
            }
    
    # Запускаем параллельную обработку
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Пропускаем уже обработанные страницы
        pages_to_process = [p for p in range(total_pages) if p not in processed_pages]
        
        if not pages_to_process:
            print(f"[PARALLEL] All {total_pages} pages already processed")
            # Загружаем все результаты из чекпоинтов
            for page_num in range(total_pages):
                checkpoint = checkpoint_mgr.load_checkpoint(book_id, page_num)
                if checkpoint:
                    results.append(checkpoint)
            return results
        
        print(f"[PARALLEL] Processing {len(pages_to_process)} pages with {max_workers} workers...")
        
        # Отправляем задачи
        future_to_page = {
            executor.submit(process_with_checkpoint, page_num): page_num
            for page_num in pages_to_process
        }
        
        # Собираем результаты
        completed = 0
        for future in as_completed(future_to_page):
            page_num = future_to_page[future]
            try:
                result = future.result()
                results.append(result)
                completed += 1
                
                if completed % checkpoint_interval == 0:
                    print(f"[PARALLEL] Completed {completed}/{len(pages_to_process)} pages...")
            except Exception as e:
                print(f"[PARALLEL] Error processing page {page_num}: {e}")
                results.append({
                    "page": page_num,
                    "error": str(e)
                })
    
    # Сортируем результаты по номеру страницы
    results.sort(key=lambda x: x.get("page", 0))
    
    return results

