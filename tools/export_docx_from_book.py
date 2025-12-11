import sys
from pathlib import Path
import json

# === FIX: Добавляем корень проекта, чтобы core_engine импортировался ===
ROOT = Path(__file__).resolve().parents[1]
sys.path.append(str(ROOT))

from core_engine.layout.layout_reassemble import reassemble_blocks
from core_engine.export.docx_exporter import export_docx

def _get_latest_book_id(output_dir: Path) -> str:
    """Берём последний по времени book_id из output/."""
    candidates = []
    for p in output_dir.iterdir():
        if p.is_dir() and (p / "book.json").exists():
            candidates.append(p)
    if not candidates:
        raise RuntimeError("Не найдено ни одного output/<book_id>/book.json")

    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    return latest.name


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    output_dir = project_root / "output"

    book_id = _get_latest_book_id(output_dir)
    book_dir = output_dir / book_id
    book_json_path = book_dir / "book.json"

    print(f"[info] Используем book_id={book_id}")
    print(f"[info] Загружаю {book_json_path}")

    with book_json_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    blocks = data.get("blocks", [])
    if not blocks:
        raise RuntimeError("В book.json нет поля 'blocks' или оно пустое")

    paragraphs = reassemble_blocks(blocks)

    docx_path = book_dir / "book_ru.docx"
    export_docx(paragraphs, docx_path)

    print(f"[ok] Экспортирован DOCX: {docx_path}")


if __name__ == "__main__":
    main()
