#!/usr/bin/env python3
"""
Скрипт для тестирования качества перевода на нескольких PDF.
Собирает статистику по всем PDF и создает сводный отчет.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Добавляем корневую директорию в путь
sys.path.insert(0, str(Path(__file__).parent.parent))

from core_engine.orchestrator.pipeline import run_book_pipeline


def test_pdf(pdf_path: Path, mode: str = "fast") -> Dict[str, Any]:
    """
    Тестирует один PDF и возвращает статистику.
    """
    print(f"\n{'='*60}")
    print(f"Testing: {pdf_path.name}")
    print(f"{'='*60}")
    
    try:
        result = run_book_pipeline(pdf_path, mode=mode)
        book_id = result.get("book_id")
        
        if not book_id:
            return {
                "pdf": pdf_path.name,
                "status": "error",
                "error": "No book_id returned"
            }
        
        # Загружаем QA отчет
        qa_path = Path("output") / book_id / "qa_report.json"
        if not qa_path.exists():
            return {
                "pdf": pdf_path.name,
                "status": "error",
                "error": "QA report not found"
            }
        
        with qa_path.open(encoding="utf-8") as f:
            qa_report = json.load(f)
        
        summary = qa_report.get("summary", {})
        metrics = qa_report.get("translation_metrics", {})
        
        return {
            "pdf": pdf_path.name,
            "book_id": book_id,
            "status": "success",
            "total_blocks": summary.get("total_blocks", 0),
            "issues_total": summary.get("issues_total", 0),
            "potential_break": summary.get("issues_by_type", {}).get("potential_break", 0),
            "repeated_tokens": summary.get("issues_by_type", {}).get("repeated_tokens", 0),
            "length_mismatch": summary.get("issues_by_type", {}).get("length_mismatch", 0),
            "average_length_ratio": metrics.get("average_length_ratio", 0),
            "qa_status": qa_report.get("status", "unknown"),
        }
    except Exception as e:
        return {
            "pdf": pdf_path.name,
            "status": "error",
            "error": str(e)
        }


def main():
    """
    Тестирует все PDF в директории и создает сводный отчет.
    """
    import argparse
    
    parser = argparse.ArgumentParser(description="Test translation quality on multiple PDFs")
    parser.add_argument("--pdf-dir", default="For test", help="Directory with PDF files")
    parser.add_argument("--mode", default="fast", help="Translation mode (fast/full/hybrid)")
    parser.add_argument("--out", default="output/quality_test_report.json", help="Output report path")
    args = parser.parse_args()
    
    pdf_dir = Path(args.pdf_dir)
    if not pdf_dir.exists():
        print(f"Error: Directory {pdf_dir} does not exist")
        return 1
    
    # Находим все PDF файлы
    pdf_files = list(pdf_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: No PDF files found in {pdf_dir}")
        return 1
    
    print(f"Found {len(pdf_files)} PDF files to test")
    
    results = []
    for pdf_path in pdf_files:
        result = test_pdf(pdf_path, mode=args.mode)
        results.append(result)
    
    # Создаем сводный отчет
    successful = [r for r in results if r.get("status") == "success"]
    failed = [r for r in results if r.get("status") == "error"]
    
    # Агрегированная статистика
    if successful:
        total_blocks = sum(r.get("total_blocks", 0) for r in successful)
        total_issues = sum(r.get("issues_total", 0) for r in successful)
        total_potential_break = sum(r.get("potential_break", 0) for r in successful)
        avg_length_ratio = sum(r.get("average_length_ratio", 0) for r in successful) / len(successful)
        
        summary = {
            "total_pdfs": len(pdf_files),
            "successful": len(successful),
            "failed": len(failed),
            "aggregated_stats": {
                "total_blocks": total_blocks,
                "total_issues": total_issues,
                "total_potential_break": total_potential_break,
                "average_potential_break_per_pdf": total_potential_break / len(successful) if successful else 0,
                "average_length_ratio": avg_length_ratio,
            }
        }
    else:
        summary = {
            "total_pdfs": len(pdf_files),
            "successful": 0,
            "failed": len(failed),
        }
    
    report = {
        "summary": summary,
        "results": results,
    }
    
    # Сохраняем отчет
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    
    # Выводим краткую статистику
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total PDFs: {len(pdf_files)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")
    
    if successful:
        print(f"\nAggregated Statistics:")
        print(f"  Total blocks: {total_blocks}")
        print(f"  Total issues: {total_issues}")
        print(f"  Total potential_break: {total_potential_break}")
        print(f"  Average potential_break per PDF: {total_potential_break / len(successful):.1f}")
        print(f"  Average length ratio: {avg_length_ratio:.3f}")
    
    print(f"\nReport saved to: {out_path}")
    
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

