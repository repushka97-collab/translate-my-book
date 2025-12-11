import json
from pathlib import Path
from typing import Dict, Any

def export_json_bundle(layout_model: Dict[str, Any], book_id: str) -> Dict[str, str]:
    out_dir = Path("output") / book_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / "book.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(layout_model, f, ensure_ascii=False, indent=2)

    return {"json": str(json_path)}

