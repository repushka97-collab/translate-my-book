"""
[PDF TRANSLATION EXPERT MODE — ИСПОЛЬЗОВАТЬ ДЛЯ ФИНАЛЬНОЙ СТАДИИ]

OCR для картинок с текстом.
Основано на: https://github.com/tesseract-ocr/tessdoc/blob/main/ImproveQuality.md
"""

from __future__ import annotations

from typing import List, Dict, Any, Optional
from pathlib import Path
import fitz  # PyMuPDF


def ocr_image_with_tesseract(
    image_bytes: bytes,
    languages: str = "eng+rus",
    psm: int = 6,
    oem: int = 1
) -> Optional[str]:
    """
    Распознает текст на изображении через Tesseract OCR.
    
    Args:
        image_bytes: байты изображения (PNG/JPEG)
        languages: языки для OCR (например, "eng+rus")
        psm: Page Segmentation Mode (6 = единый блок текста)
        oem: OCR Engine Mode (1 = LSTM только)
    
    Returns:
        Распознанный текст или None
    """
    try:
        import pytesseract  # type: ignore
        from PIL import Image  # type: ignore
        import io
    except ImportError:
        return None
    
    try:
        # Загружаем изображение из bytes
        img = Image.open(io.BytesIO(image_bytes))
        
        # Распознаем текст
        custom_config = f"--oem {oem} --psm {psm} -l {languages}"
        text = pytesseract.image_to_string(img, config=custom_config)
        
        return text.strip() if text else None
    except Exception as e:
        print(f"[WARN] Tesseract OCR failed: {e}")
        return None


def extract_and_ocr_images_from_pdf(
    pdf_path: str,
    page_num: int,
    languages: str = "eng+rus"
) -> List[Dict[str, Any]]:
    """
    Извлекает изображения со страницы и распознает текст на них.
    
    Алгоритм:
    1. Извлечь все изображения из PDF
    2. Отправить в Tesseract с русской моделью
    3. Вернуть результаты с координатами для замены текста
    
    Returns:
        Список словарей:
        {
            "bbox": {"x0": float, "y0": float, "x1": float, "y1": float},
            "image_bytes": bytes,
            "ocr_text": str,
            "confidence": float (optional)
        }
    """
    results: List[Dict[str, Any]] = []
    
    try:
        doc = fitz.open(pdf_path)
        if page_num >= len(doc):
            return results
        
        page = doc[page_num]
        
        # Получаем изображения с bbox
        image_list = page.get_images(full=True)
        text_dict = page.get_text("dict")
        
        # Маппинг xref -> bbox
        xref_to_bbox = {}
        for block in text_dict.get("blocks", []):
            if block.get("type") == 1 and "image" in block:
                xref = block.get("image")
                bbox = block.get("bbox", [0, 0, 0, 0])
                if len(bbox) == 4:
                    xref_to_bbox[xref] = bbox
        
        # Обрабатываем каждое изображение
        for img_idx, img_info in enumerate(image_list):
            xref = img_info[0]
            try:
                # Извлекаем изображение
                pix = fitz.Pixmap(doc, xref)
                if pix.alpha:
                    pix = fitz.Pixmap(pix, 0)  # убираем alpha
                if pix.colorspace is None or pix.n not in (1, 3):
                    pix = fitz.Pixmap(fitz.csRGB, pix)
                
                image_bytes = pix.tobytes("png")
                
                # Получаем bbox
                bbox_list = xref_to_bbox.get(xref, [0, 0, 0, 0])
                bbox = {
                    "x0": bbox_list[0],
                    "y0": bbox_list[1],
                    "x1": bbox_list[2],
                    "y1": bbox_list[3],
                }
                
                # OCR
                ocr_text = ocr_image_with_tesseract(image_bytes, languages=languages)
                
                if ocr_text:
                    results.append({
                        "bbox": bbox,
                        "image_bytes": image_bytes,
                        "ocr_text": ocr_text,
                        "xref": xref,
                    })
                
                del pix
            except Exception as e:
                print(f"[WARN] Failed to process image {img_idx}: {e}")
                continue
        
        doc.close()
    except Exception as e:
        print(f"[WARN] Failed to extract images from page {page_num}: {e}")
    
    return results

