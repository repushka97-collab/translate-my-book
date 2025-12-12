# core_engine/layout/chapter_detector.py

from __future__ import annotations

from typing import List, Dict, Any, Optional
import re

Block = Dict[str, Any]


def detect_chapter_structure(blocks: List[Block]) -> List[Block]:
    """
    Определяет иерархическую структуру книги:
    - Part (Часть)
    - Chapter (Глава)
    - Section (Раздел)
    
    Добавляет в metadata:
      - chapter_level: "part", "chapter", "section", или None
      - chapter_number: номер (если есть)
      - chapter_title: название (если есть)
    """
    new_blocks: List[Block] = []
    current_part: Optional[str] = None
    current_chapter: Optional[str] = None
    current_section: Optional[str] = None
    
    # Паттерны для определения структуры
    PART_PATTERNS = [
        re.compile(r"^PART\s+[IVX]+", re.IGNORECASE),
        re.compile(r"^ЧАСТЬ\s+[IVX]+", re.IGNORECASE),
        re.compile(r"^PART\s+\d+", re.IGNORECASE),
        re.compile(r"^ЧАСТЬ\s+\d+", re.IGNORECASE),
    ]
    
    CHAPTER_PATTERNS = [
        re.compile(r"^CHAPTER\s+\d+", re.IGNORECASE),
        re.compile(r"^ГЛАВА\s+\d+", re.IGNORECASE),
        re.compile(r"^CHAPTER\s+[IVX]+", re.IGNORECASE),
        re.compile(r"^ГЛАВА\s+[IVX]+", re.IGNORECASE),
    ]
    
    SECTION_PATTERNS = [
        re.compile(r"^\d+\.\d+",),  # "1.1", "2.3"
        re.compile(r"^\d+\.\d+\.\d+",),  # "1.1.1"
    ]
    
    for block in blocks:
        text = (block.get("translated_text") or block.get("text") or "").strip()
        metadata = block.get("metadata", {})
        role = metadata.get("role", "")
        
        # Проверяем только заголовки
        if role not in ("heading1", "heading2"):
            new_blocks.append(block)
            continue
        
        # Определяем уровень структуры
        chapter_level = None
        chapter_number = None
        chapter_title = None
        
        # Part
        for pattern in PART_PATTERNS:
            match = pattern.match(text)
            if match:
                chapter_level = "part"
                chapter_number = match.group(0)
                chapter_title = text[len(match.group(0)):].strip()
                current_part = chapter_number
                current_chapter = None  # Сбрасываем главу при новой части
                break
        
        # Chapter
        if not chapter_level:
            for pattern in CHAPTER_PATTERNS:
                match = pattern.match(text)
                if match:
                    chapter_level = "chapter"
                    chapter_number = match.group(0)
                    chapter_title = text[len(match.group(0)):].strip()
                    current_chapter = chapter_number
                    current_section = None  # Сбрасываем раздел при новой главе
                    break
        
        # Section (подраздел)
        if not chapter_level and SECTION_PATTERNS:
            for pattern in SECTION_PATTERNS:
                match = pattern.match(text)
                if match:
                    chapter_level = "section"
                    chapter_number = match.group(0)
                    chapter_title = text[len(match.group(0)):].strip()
                    current_section = chapter_number
                    break
        
        # Обновляем metadata
        if chapter_level:
            metadata = dict(metadata)
            metadata["chapter_level"] = chapter_level
            if chapter_number:
                metadata["chapter_number"] = chapter_number
            if chapter_title:
                metadata["chapter_title"] = chapter_title
            if current_part:
                metadata["part"] = current_part
            if current_chapter:
                metadata["chapter"] = current_chapter
            if current_section:
                metadata["section"] = current_section
        
        new_block = dict(block)
        new_block["metadata"] = metadata
        new_blocks.append(new_block)
    
    return new_blocks

