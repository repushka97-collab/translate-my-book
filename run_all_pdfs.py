#!/usr/bin/env python3
"""
Скрипт для прогона всех PDF файлов через пайплайн перевода.
"""

import sys

# Исправление кодировки для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass  # Если не поддерживается, игнорируем
from pathlib import Path
from core_engine.orchestrator.pipeline import run_book_pipeline
import time
import json
from datetime import datetime

def main():
    # Находим все PDF файлы
    test_dirs = ["For test", "ingest"]
    pdf_files = []
    
    for test_dir in test_dirs:
        test_path = Path(test_dir)
        if test_path.exists():
            pdf_files.extend(list(test_path.glob("*.pdf")))
    
    if not pdf_files:
        print("[ERROR] No PDF files found in test directories")
        return
    
    print(f"[INFO] Found {len(pdf_files)} PDF files")
    print("=" * 60)
    
    results = []
    
    for idx, pdf_path in enumerate(pdf_files, 1):
        print(f"\n[{idx}/{len(pdf_files)}] Processing: {pdf_path.name}")
        print(f"  Path: {pdf_path}")
        print(f"  Size: {pdf_path.stat().st_size / 1024:.1f} KB")
        
        start_time = time.time()
        
        try:
            result = run_book_pipeline(pdf_path, mode="dev")
            
            processing_time = time.time() - start_time
            book_id = result.get("book_id", "unknown")
            
            # Проверяем наличие переведенного PDF
            output_dir = Path("output") / book_id
            pdf_output = output_dir / "book_ru.pdf"
            
            success = pdf_output.exists() if output_dir.exists() else False
            
            result_info = {
                "file": str(pdf_path),
                "name": pdf_path.name,
                "book_id": book_id,
                "success": success,
                "processing_time": round(processing_time, 2),
                "output_path": str(pdf_output) if success else None,
                "timestamp": datetime.now().isoformat()
            }
            
            results.append(result_info)
            
            if success:
                pdf_size = pdf_output.stat().st_size / 1024
                print(f"  [OK] Success! Processing time: {processing_time:.1f}s")
                print(f"  [PDF] Output: {pdf_output} ({pdf_size:.1f} KB)")
            else:
                print(f"  [WARN] Completed but PDF not found")
                
        except Exception as e:
            processing_time = time.time() - start_time
            print(f"  [ERROR] Error: {e}")
            
            result_info = {
                "file": str(pdf_path),
                "name": pdf_path.name,
                "success": False,
                "error": str(e),
                "processing_time": round(processing_time, 2),
                "timestamp": datetime.now().isoformat()
            }
            results.append(result_info)
        
        print("-" * 60)
    
    # Сохраняем результаты
    results_file = Path("batch_translation_results.json")
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    
    # Итоговая статистика
    print("\n" + "=" * 60)
    print("ИТОГОВАЯ СТАТИСТИКА")
    print("=" * 60)
    
    total = len(results)
    successful = sum(1 for r in results if r.get("success", False))
    failed = total - successful
    total_time = sum(r.get("processing_time", 0) for r in results)
    
    print(f"Всего файлов: {total}")
    print(f"Успешно: {successful} [OK]")
    print(f"Ошибок: {failed} [ERROR]")
    print(f"Общее время: {total_time:.1f}s")
    print(f"Среднее время на файл: {total_time/total:.1f}s" if total > 0 else "N/A")
    print(f"\nРезультаты сохранены в: {results_file}")
    
    if failed > 0:
        print("\nФайлы с ошибками:")
        for r in results:
            if not r.get("success", False):
                print(f"  - {r['name']}: {r.get('error', 'Unknown error')}")

if __name__ == "__main__":
    main()

