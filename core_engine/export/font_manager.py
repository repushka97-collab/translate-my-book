# core_engine/export/font_manager.py
"""
Font Manager для поддержки Unicode шрифтов (кириллица).
Управление загрузкой и использованием TTF/OTF шрифтов в PyMuPDF.
"""

import os
from typing import Dict, Optional, Tuple
from pathlib import Path
import fitz  # PyMuPDF


# Стандартные шрифты с поддержкой кириллицы (если доступны в системе)
CYRILLIC_FONTS = {
    "helv": {
        "fallback": "DejaVuSans",
        "ttf_paths": [
            "C:/Windows/Fonts/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/System/Library/Fonts/Helvetica.ttc",
        ]
    },
    "times": {
        "fallback": "DejaVuSerif",
        "ttf_paths": [
            "C:/Windows/Fonts/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/System/Library/Fonts/Times.ttc",
        ]
    },
    "cour": {
        "fallback": "DejaVuSansMono",
        "ttf_paths": [
            "C:/Windows/Fonts/dejavu/DejaVuSansMono.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
            "/System/Library/Fonts/Courier.ttc",
        ]
    }
}


class FontManager:
    """Менеджер шрифтов для поддержки кириллицы."""
    
    def __init__(self):
        self._font_cache: Dict[str, int] = {}  # font_name -> font_xref
        self._loaded_fonts: Dict[str, str] = {}  # font_name -> ttf_path
    
    def find_cyrillic_font(self, base_font: str) -> Optional[str]:
        """
        Ищет TTF/OTF шрифт с поддержкой кириллицы.
        
        Args:
            base_font: базовое имя шрифта (helv, times, cour)
        
        Returns:
            Путь к TTF файлу или None
        """
        if base_font not in CYRILLIC_FONTS:
            return None
        
        font_info = CYRILLIC_FONTS[base_font]
        
        # Проверяем стандартные пути
        for ttf_path in font_info["ttf_paths"]:
            if Path(ttf_path).exists():
                return ttf_path
        
        # Ищем в системных директориях шрифтов
        system_font_dirs = [
            "C:/Windows/Fonts",
            "/usr/share/fonts",
            "/System/Library/Fonts",
            os.path.expanduser("~/Library/Fonts"),
        ]
        
        fallback_name = font_info["fallback"]
        
        # Список возможных имен файлов для поиска
        search_names = [
            fallback_name,
            "DejaVu",
            "Liberation",
            "Arial",  # Windows часто имеет Arial с кириллицей
            "arial",  # lowercase вариант
            "ARIAL",  # uppercase вариант
            "Times New Roman",  # Windows
            "times",  # lowercase
            "TIMES",  # uppercase
            "Courier New",  # Windows
            "courier",  # lowercase
            "COURIER",  # uppercase
        ]
        
        # Для Windows добавляем специфичные имена
        if os.name == "nt":  # Windows
            if base_font == "helv":
                search_names.extend(["arial", "Arial", "ARIAL", "Calibri", "calibri"])
            elif base_font == "times":
                search_names.extend(["times", "Times", "TIMES", "TimesNewRoman", "timesnewroman"])
            elif base_font == "cour":
                search_names.extend(["courier", "Courier", "COURIER", "CourierNew", "couriernew"])
        
        for font_dir in system_font_dirs:
            font_path = Path(font_dir)
            if not font_path.exists():
                continue
            
            # Ищем шрифты с похожим именем
            try:
                for font_file in font_path.rglob("*.ttf"):
                    font_name_lower = font_file.name.lower()
                    if any(search_name.lower() in font_name_lower for search_name in search_names):
                        # Проверяем, что это не моноширинный для helv
                        if base_font == "helv" and "mono" in font_name_lower:
                            continue
                        # Проверяем, что это не serif для helv
                        if base_font == "helv" and "serif" in font_name_lower:
                            continue
                        return str(font_file)
                
                for font_file in font_path.rglob("*.otf"):
                    font_name_lower = font_file.name.lower()
                    if any(search_name.lower() in font_name_lower for search_name in search_names):
                        if base_font == "helv" and "mono" in font_name_lower:
                            continue
                        if base_font == "helv" and "serif" in font_name_lower:
                            continue
                        return str(font_file)
            except (PermissionError, OSError):
                # Пропускаем директории без доступа
                continue
        
        return None
    
    def load_font_to_doc(self, doc: fitz.Document, font_name: str, ttf_path: str) -> Optional[int]:
        """
        Загружает TTF шрифт в документ.
        
        Args:
            doc: документ PyMuPDF
            font_name: имя шрифта для использования
            ttf_path: путь к TTF файлу
        
        Returns:
            font_xref или None при ошибке
        """
        if font_name in self._font_cache:
            return self._font_cache[font_name]
        
        try:
            # Загружаем шрифт в документ
            font_xref = doc.insert_font(
                fontname=font_name,
                fontfile=ttf_path,
                encoding=0  # Unicode encoding
            )
            self._font_cache[font_name] = font_xref
            self._loaded_fonts[font_name] = ttf_path
            return font_xref
        except Exception as e:
            print(f"[FontManager] Failed to load font {font_name} from {ttf_path}: {e}")
            return None
    
    def get_font_for_text(self, doc: fitz.Document, base_font: str, text: str) -> str:
        """
        Получает подходящий шрифт для текста (с поддержкой кириллицы если нужно).
        
        Args:
            doc: документ PyMuPDF
            base_font: базовое имя шрифта
            text: текст для проверки
        
        Returns:
            Имя шрифта для использования
        """
        # Проверяем, есть ли кириллица в тексте
        has_cyrillic = any(ord(c) > 127 and ord(c) < 1104 for c in text)
        
        if not has_cyrillic:
            # Для не-кириллического текста используем стандартные шрифты
            return base_font
        
        # Для кириллицы ищем TTF шрифт
        ttf_path = self.find_cyrillic_font(base_font)
        if ttf_path:
            font_name = f"{base_font}_cyrillic"
            if self.load_font_to_doc(doc, font_name, ttf_path):
                return font_name
        
        # Fallback: используем базовый шрифт (может не отображать кириллицу правильно)
        return base_font


# Глобальный экземпляр менеджера шрифтов
_font_manager: Optional[FontManager] = None


def get_font_manager() -> FontManager:
    """Получает глобальный экземпляр FontManager."""
    global _font_manager
    if _font_manager is None:
        _font_manager = FontManager()
    return _font_manager
