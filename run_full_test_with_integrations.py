#!/usr/bin/env python3
"""
Полный прогон всех тестовых PDF с применением последних интеграций.
Включает Human Feedback, Quality Metrics, Auto-Correction и Production модули.
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Исправление кодировки для Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent))

from core_engine.orchestrator.pipeline import run_book_pipeline


def find_test_pdfs():
    """Находит все тестовые PDF в проекте."""
    pdfs = []
    
    # Ищем в разных местах
    search_dirs = [
        Path("For test"),
        Path("ingest"),
    ]
    
    for search_dir in search_dirs:
        if search_dir.exists():
            for pdf_file in search_dir.glob("*.pdf"):
                # Пропускаем переведенные PDF
                if "book_ru.pdf" in str(pdf_file) or "output" in str(pdf_file):
                    continue
                # Пропускаем временные файлы и системные файлы
                if pdf_file.name.startswith("._") or pdf_file.name.startswith("~"):
                    continue
                if "temp" in str(pdf_file).lower() or "tmp" in str(pdf_file).lower():
                    continue
                # Пропускаем уже переведенные из library
                if "library" in str(pdf_file):
                    continue
                pdfs.append(pdf_file)
    
    # Убираем дубликаты
    unique_pdfs = []
    seen = set()
    for pdf in pdfs:
        if str(pdf) not in seen:
            seen.add(str(pdf))
            unique_pdfs.append(pdf)
    
    return sorted(unique_pdfs)


def main():
    print("=" * 80)
    print("🚀 ПОЛНЫЙ ПРОГОН ВСЕХ ТЕСТОВЫХ PDF С ПОСЛЕДНИМИ ИНТЕГРАЦИЯМИ")
    print("=" * 80)
    print()
    
    # Включаем все последние интеграции
    os.environ["USE_HUMAN_LIKE_EVALUATION"] = "1"
    os.environ["HUMAN_MODEL_USER"] = "default"  # Будет использоваться базовая модель
    os.environ["QUALITY_CHECK"] = "1"
    os.environ["HEATMAP_DIFF"] = "1"
    os.environ["PDF_DIFF_CHECK"] = "1"
    os.environ["LAYOUT_FIXER"] = "1"
    os.environ["OVERFLOW_PREDICTOR"] = "1"
    os.environ["FONT_COMPENSATOR"] = "1"
    os.environ["VECTOR_REPAIR"] = "1"
    # КРИТИЧНО: Используем HTML экспорт с абсолютным позиционированием для лучшего качества
    # HTML экспорт лучше сохраняет layout и предотвращает наезд текста
    os.environ["PDF_REBUILD"] = "0"  # Отключаем PDF_REBUILD (проблемы с наездом текста)
    os.environ["HTML_TO_PDF_PLAYWRIGHT"] = "1"  # Используем HTML→PDF через Playwright
    os.environ["HTML_ABSOLUTE"] = "1"  # Абсолютное позиционирование для точности
    os.environ["GHOSTSCRIPT_COMPRESS"] = "1"
    
    print("📋 Включенные модули:")
    print("   ✅ Human Like Evaluation")
    print("   ✅ Quality Metrics")
    print("   ✅ Heatmap Diff")
    print("   ✅ PDF Diff Check")
    print("   ✅ Layout Fixer")
    print("   ✅ Overflow Predictor")
    print("   ✅ Font Compensator")
    print("   ✅ Vector Repair")
    print("   ✅ HTML to PDF (Playwright) - ПРИОРИТЕТ")
    print("   ✅ HTML_ABSOLUTE=1 - точное позиционирование")
    print("   ✅ Ghostscript Compression")
    print()
    
    # Находим все тестовые PDF
    test_pdfs = find_test_pdfs()
    
    if not test_pdfs:
        print("❌ Не найдено тестовых PDF")
        print()
        print("💡 Разместите PDF файлы в одной из директорий:")
        print("   - test_pdfs/")
        print("   - For test/")
        print("   - input/")
        print("   - корень проекта")
        return 1
    
    print(f"✅ Найдено {len(test_pdfs)} тестовых PDF:")
    for i, pdf in enumerate(test_pdfs, 1):
        print(f"   {i}. {pdf}")
    print()
    
    # Создаем директорию для результатов
    results_dir = Path("full_test_results")
    results_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results_file = results_dir / f"full_test_{timestamp}.txt"
    
    results = []
    successful = 0
    failed = 0
    
    print("=" * 80)
    print("🔄 НАЧАЛО ОБРАБОТКИ")
    print("=" * 80)
    print()
    
    with open(results_file, "w", encoding="utf-8") as log_file:
        for i, pdf_path in enumerate(test_pdfs, 1):
            print(f"[{i}/{len(test_pdfs)}] Обработка: {pdf_path.name}")
            print("-" * 80)
            
            try:
                start_time = datetime.now()
                
                # Запускаем пайплайн
                result = run_book_pipeline(
                    source_path=str(pdf_path),
                    mode="fast"  # Используем fast для быстрого теста
                )
                
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                
                # Проверяем успех по наличию PDF
                pdf_output = result.get("export_paths", {}).get("pdf") if result else None
                if not pdf_output and result:
                    pdf_output = result.get("pdf_path")
                
                # PDF создан = успех
                success = pdf_output and Path(pdf_output).exists()
                
                if success:
                    successful += 1
                    status = "✅ УСПЕХ"
                    
                    # Извлекаем информацию о результатах
                    quality_score = result.get("qa_report", {}).get("overall_score", "N/A") if result else "N/A"
                    human_score = result.get("human_quality_score", "N/A") if result else "N/A"
                    
                    print(f"   {status}")
                    print(f"   Время: {duration:.1f} сек")
                    print(f"   PDF: {pdf_output}")
                    if quality_score != "N/A":
                        print(f"   Quality Score: {quality_score:.1f}/100")
                    if human_score != "N/A":
                        print(f"   Human Score: {human_score:.1f}/10")
                    
                    results.append({
                        "pdf": str(pdf_path),
                        "status": "success",
                        "duration": duration,
                        "output": pdf_output,
                        "quality_score": quality_score,
                        "human_score": human_score
                    })
                    
                    log_file.write(f"[{i}/{len(test_pdfs)}] {pdf_path.name}: SUCCESS ({duration:.1f}s)\n")
                    log_file.write(f"  Output: {pdf_output}\n")
                    if quality_score != "N/A":
                        log_file.write(f"  Quality: {quality_score:.1f}/100\n")
                    if human_score != "N/A":
                        log_file.write(f"  Human: {human_score:.1f}/10\n")
                    log_file.write("\n")
                else:
                    failed += 1
                    status = "❌ ОШИБКА"
                    error_msg = result.get("error", "PDF not created") if result else "No result"
                    
                    print(f"   {status}")
                    print(f"   Ошибка: {error_msg}")
                    if pdf_output:
                        print(f"   Ожидаемый PDF: {pdf_output}")
                    
                    results.append({
                        "pdf": str(pdf_path),
                        "status": "failed",
                        "error": error_msg,
                        "expected_pdf": str(pdf_output) if pdf_output else None
                    })
                    
                    log_file.write(f"[{i}/{len(test_pdfs)}] {pdf_path.name}: FAILED\n")
                    log_file.write(f"  Error: {error_msg}\n")
                    if pdf_output:
                        log_file.write(f"  Expected PDF: {pdf_output}\n")
                    log_file.write("\n")
                
            except Exception as e:
                failed += 1
                status = "❌ ИСКЛЮЧЕНИЕ"
                
                print(f"   {status}")
                print(f"   {type(e).__name__}: {e}")
                
                results.append({
                    "pdf": str(pdf_path),
                    "status": "exception",
                    "error": str(e)
                })
                
                log_file.write(f"[{i}/{len(test_pdfs)}] {pdf_path.name}: EXCEPTION\n")
                log_file.write(f"  {type(e).__name__}: {e}\n\n")
            
            print()
            log_file.flush()
    
    # Итоговый отчет
    print("=" * 80)
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 80)
    print()
    print(f"✅ Успешно: {successful}/{len(test_pdfs)}")
    print(f"❌ Ошибок: {failed}/{len(test_pdfs)}")
    print()
    
    if successful > 0:
        print("📁 Результаты сохранены в:")
        for result in results:
            if result["status"] == "success":
                print(f"   {result['output']}")
    print()
    print(f"📝 Полный лог: {results_file}")
    print()
    
    # Сохраняем итоговый отчет в JSON
    summary_file = results_dir / f"summary_{timestamp}.json"
    import json
    summary = {
        "timestamp": timestamp,
        "total": len(test_pdfs),
        "successful": successful,
        "failed": failed,
        "results": results
    }
    with open(summary_file, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    
    print(f"📊 Сводка: {summary_file}")
    print()
    print("=" * 80)
    print("✅ ПРОГОН ЗАВЕРШЕН")
    print("=" * 80)
    print()
    print("💡 Теперь вы можете оценить результаты своими глазами:")
    print("   1. Откройте переведенные PDF в output/")
    print("   2. Запустите веб-интерфейс для оценки:")
    print("      cd tools/human_feedback_interface")
    print("      python app.py")
    print("   3. Оцените качество перевода")
    print()
    
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

