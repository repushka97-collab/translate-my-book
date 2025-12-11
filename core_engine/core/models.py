from __future__ import annotations

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import List, Optional, Dict, Any


class BlockType(str, Enum):
    TEXT = "text"
    HEADING = "heading"
    TABLE = "table"
    IMAGE = "image"
    CAPTION = "caption"
    FORMULA = "formula"
    FOOTNOTE = "footnote"
    REFERENCE = "reference"


@dataclass
class BBox:
    x0: float
    y0: float
    x1: float
    y1: float


@dataclass
class TextSpan:
    text: str
    font: Optional[str] = None
    size: Optional[float] = None
    bold: bool = False
    italic: bool = False
    language: Optional[str] = None


@dataclass
class Block:
    id: str
    page_number: int
    type: BlockType
    bbox: BBox
    spans: List[TextSpan] = field(default_factory=list)
    raw_text: str = ""
    normalized_text: Optional[str] = None
    translated_text: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ImageObject:
    id: str
    page_number: int
    bbox: BBox
    image_bytes: bytes
    mime_type: str
    alt_text: Optional[str] = None
    label: Optional[str] = None  # FIG.1A, FIG.1B и т.п.

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # image_bytes в JSON не сериализуем — выкидываем
        d["image_bytes"] = None
        return d


@dataclass
class TableCell:
    row: int
    col: int
    text: str
    rowspan: int = 1
    colspan: int = 1


@dataclass
class TableObject:
    id: str
    page_number: int
    bbox: BBox
    cells: List[TableCell]
    label: Optional[str] = None  # TABLE 1 и т.п.
    caption: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Page:
    number: int
    width: float
    height: float
    blocks: List[Block] = field(default_factory=list)
    images: List[ImageObject] = field(default_factory=list)
    tables: List[TableObject] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BookDocument:
    source_path: str
    pages: List[Page]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_json_dict(self) -> Dict[str, Any]:
        """
        Безопасная JSON-представление:
        - image_bytes выбрасываем
        - остальное — чистый текст/метаданные
        """
        pages_data: List[Dict[str, Any]] = []

        for p in self.pages:
            page_dict: Dict[str, Any] = {
                "number": p.number,
                "width": p.width,
                "height": p.height,
                "metadata": p.metadata,
                "blocks": [],
                "images": [],
                "tables": [],
            }

            # Блоки
            for b in p.blocks:
                page_dict["blocks"].append(b.to_dict())

            # Изображения (без image_bytes)
            for img in p.images:
                page_dict["images"].append(img.to_dict())

            # Таблицы
            for tbl in p.tables:
                page_dict["tables"].append(tbl.to_dict())

            pages_data.append(page_dict)

        return {
            "source_path": self.source_path,
            "metadata": self.metadata,
            "pages": pages_data,
        }

