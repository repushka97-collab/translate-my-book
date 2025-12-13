# core_engine/export/doctr_images.py
"""
[ADVANCED PDF TRANSLATION MODE] DocTR + PyMuPDF для текста в изображениях.
Текст внутри диаграмм, скриншотов, логотипов.
"""

import os
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
import io


def extract_text_from_image_doctr(
    image_bytes: bytes,
    languages: List[str] = ["eng"]
) -> List[Dict[str, Any]]:
    """
    Извлекает текст из изображения через DocTR.
    
    Args:
        image_bytes: байты изображения
        languages: список языков для OCR (например, ["eng", "rus"])
    
    Returns:
        Список словарей с текстовыми областями:
        [{"text": str, "bbox": [x0, y0, x1, y1], "confidence": float}, ...]
    """
    try:
        from doctr.io import DocumentFile  # type: ignore
        from doctr.models import ocr_predictor  # type: ignore
    except ImportError:
        # Fallback на Tesseract если DocTR недоступен
        return _extract_text_tesseract_fallback(image_bytes, languages)
    
    try:
        # Загружаем изображение
        image = Image.open(io.BytesIO(image_bytes))
        
        # Инициализируем DocTR модель
        model = ocr_predictor(pretrained=True)
        
        # Конвертируем в формат DocTR
        doc = DocumentFile.from_images([image])
        
        # Распознаем текст
        result = model(doc)
        
        # Извлекаем текстовые области
        text_regions = []
        for page_result in result.pages:
            for block in page_result.blocks:
                for line in block.lines:
                    for word in line.words:
                        # Получаем bbox слова
                        geometry = word.geometry
                        bbox = [
                            geometry[0][0],  # x0
                            geometry[0][1],  # y0
                            geometry[1][0],  # x1
                            geometry[1][1],  # y1
                        ]
                        
                        text_regions.append({
                            "text": word.value,
                            "bbox": bbox,
                            "confidence": word.confidence if hasattr(word, "confidence") else 1.0
                        })
        
        return text_regions
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[DocTR] Error: {e}\n")
        
        # Fallback на Tesseract
        return _extract_text_tesseract_fallback(image_bytes, languages)


def _extract_text_tesseract_fallback(
    image_bytes: bytes,
    languages: List[str]
) -> List[Dict[str, Any]]:
    """Fallback на Tesseract если DocTR недоступен."""
    try:
        import pytesseract  # type: ignore
        from PIL import Image
        import io
    except ImportError:
        return []
    
    try:
        image = Image.open(io.BytesIO(image_bytes))
        
        # Конвертируем языки в формат Tesseract
        lang_str = "+".join(languages)
        
        # Получаем данные с bbox
        data = pytesseract.image_to_data(image, lang=lang_str, output_type=pytesseract.Output.DICT)
        
        text_regions = []
        n_boxes = len(data['text'])
        for i in range(n_boxes):
            text = data['text'][i].strip()
            if text and int(data['conf'][i]) > 30:  # минимум 30% уверенности
                text_regions.append({
                    "text": text,
                    "bbox": [
                        data['left'][i],
                        data['top'][i],
                        data['left'][i] + data['width'][i],
                        data['top'][i] + data['height'][i]
                    ],
                    "confidence": float(data['conf'][i]) / 100.0
                })
        
        return text_regions
        
    except Exception:
        return []


def translate_image_text(
    image_bytes: bytes,
    translate_fn,
    source_lang: str = "en",
    target_lang: str = "ru",
    preserve_aspect_ratio: bool = True
) -> Optional[bytes]:
    """
    Переводит текст в изображении и генерирует новое изображение.
    
    Args:
        image_bytes: байты исходного изображения
        translate_fn: функция перевода (text, source_lang, target_lang) -> translated_text
        source_lang: исходный язык
        target_lang: целевой язык
        preserve_aspect_ratio: сохранять ли пропорции
    
    Returns:
        Байты нового изображения с переведенным текстом или None при ошибке
    """
    try:
        # Извлекаем текст
        text_regions = extract_text_from_image_doctr(image_bytes, languages=[source_lang])
        
        if not text_regions:
            return None
        
        # Загружаем изображение
        image = Image.open(io.BytesIO(image_bytes))
        draw = ImageDraw.Draw(image)
        
        # Пробуем загрузить шрифт
        try:
            # Используем системный шрифт для кириллицы
            font_size = 12
            try:
                font = ImageFont.truetype("arial.ttf", font_size)
            except:
                try:
                    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
                except:
                    font = ImageFont.load_default()
        except:
            font = ImageFont.load_default()
        
        # Переводим и рисуем текст
        for region in text_regions:
            original_text = region["text"]
            bbox = region["bbox"]
            
            # Переводим
            translated_text = translate_fn(original_text, source_lang, target_lang)
            
            # Закрашиваем оригинальный текст (белый прямоугольник)
            x0, y0, x1, y1 = bbox
            draw.rectangle([x0, y0, x1, y1], fill="white")
            
            # Рисуем переведенный текст
            draw.text((x0, y0), translated_text, fill="black", font=font)
        
        # Сохраняем в байты
        output = io.BytesIO()
        image.save(output, format="PNG")
        return output.getvalue()
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[DocTR] Translate image error: {e}\n")
        return None


def replace_images_in_pdf_with_translated_text(
    pdf_path: str,
    output_path: str,
    translate_fn,
    page_range: Optional[Tuple[int, int]] = None
) -> bool:
    """
    Заменяет изображения в PDF на версии с переведенным текстом.
    
    Args:
        pdf_path: путь к исходному PDF
        output_path: путь для сохранения нового PDF
        translate_fn: функция перевода
        page_range: (start_page, end_page) или None для всех страниц
    
    Returns:
        True при успехе
    """
    try:
        doc = fitz.open(pdf_path)
        
        start_page = 0
        end_page = len(doc) - 1
        
        if page_range:
            start_page = max(0, page_range[0] - 1)
            end_page = min(len(doc) - 1, page_range[1] - 1)
        
        for page_num in range(start_page, end_page + 1):
            page = doc[page_num]
            
            # Получаем изображения на странице
            image_list = page.get_images()
            
            for img_idx, img_info in enumerate(image_list):
                xref = img_info[0]
                
                # Извлекаем изображение
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                
                # Переводим текст в изображении
                translated_image_bytes = translate_image_text(
                    image_bytes,
                    translate_fn,
                    preserve_aspect_ratio=True
                )
                
                if translated_image_bytes:
                    # Находим bbox изображения
                    image_rects = page.get_image_rects(xref)
                    if image_rects:
                        rect = image_rects[0]
                        
                        # Удаляем старое изображение и вставляем новое
                        page.delete_image(xref)
                        page.insert_image(rect, stream=translated_image_bytes)
        
        doc.save(output_path)
        doc.close()
        return True
        
    except Exception as e:
        error_log_path = os.getenv("ERROR_LOG_PATH", "errors.log")
        with open(error_log_path, "a", encoding="utf-8") as f:
            f.write(f"[DocTR] Replace images error: {e}\n")
        return False

