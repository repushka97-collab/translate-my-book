"""
Модуль для сбора человеческой обратной связи.
Превращает оценки пользователя в обучающие данные.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from datetime import datetime
import fitz  # PyMuPDF


class HumanFeedbackCollector:
    """Собирает и сохраняет человеческую обратную связь."""
    
    def __init__(self, feedback_dir: str = "human_feedback"):
        self.feedback_dir = Path(feedback_dir)
        self.feedback_dir.mkdir(parents=True, exist_ok=True)
    
    def collect_feedback(
        self,
        original_pdf: str,
        translated_pdf: str,
        page_num: int,
        user_name: str = "default",
        visual_score: Optional[int] = None,
        problem_areas: Optional[List[Dict[str, Any]]] = None,
        semantic_issues: Optional[List[str]] = None,
        comment: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Собирает обратную связь от пользователя.
        
        Args:
            original_pdf: путь к оригинальному PDF
            translated_pdf: путь к переведенному PDF
            page_num: номер страницы (1-based)
            user_name: имя пользователя
            visual_score: оценка от 1 до 10
            problem_areas: список проблемных областей с bbox
            semantic_issues: список семантических проблем
            comment: текстовый комментарий
        
        Returns:
            Словарь с собранной обратной связью
        """
        feedback = {
            "timestamp": datetime.now().isoformat(),
            "user": user_name,
            "original_pdf": str(original_pdf),
            "translated_pdf": str(translated_pdf),
            "page": page_num,
            "visual_score": visual_score,
            "problem_areas": problem_areas or [],
            "semantic_issues": semantic_issues or [],
            "comment": comment
        }
        
        # Сохраняем как обучающий пример
        self.save_training_example(feedback, user_name)
        
        return feedback
    
    def save_training_example(self, feedback: Dict[str, Any], user_name: str) -> str:
        """
        Сохраняет обратную связь как обучающий пример.
        
        Args:
            feedback: словарь с обратной связью
            user_name: имя пользователя
        
        Returns:
            Путь к сохраненному файлу
        """
        user_dir = self.feedback_dir / user_name
        user_dir.mkdir(parents=True, exist_ok=True)
        
        # Имя файла: book_page_feedback.json
        book_name = Path(feedback["translated_pdf"]).stem
        feedback_file = user_dir / f"{book_name}_page{feedback['page']}_feedback.json"
        
        with open(feedback_file, "w", encoding="utf-8") as f:
            json.dump(feedback, f, indent=2, ensure_ascii=False)
        
        return str(feedback_file)
    
    def load_user_feedback(self, user_name: str) -> List[Dict[str, Any]]:
        """
        Загружает всю обратную связь пользователя.
        
        Args:
            user_name: имя пользователя
        
        Returns:
            Список всех обратных связей
        """
        user_dir = self.feedback_dir / user_name
        if not user_dir.exists():
            return []
        
        feedbacks = []
        for feedback_file in user_dir.glob("*_feedback.json"):
            try:
                with open(feedback_file, "r", encoding="utf-8") as f:
                    feedback = json.load(f)
                    feedbacks.append(feedback)
            except Exception as e:
                print(f"[WARN] Failed to load {feedback_file}: {e}")
        
        return sorted(feedbacks, key=lambda x: x.get("timestamp", ""))
    
    def get_page_images(
        self,
        original_pdf: str,
        translated_pdf: str,
        page_num: int,
        scale: float = 1.5
    ) -> Dict[str, str]:
        """
        Получает изображения страниц для отображения.
        
        Args:
            original_pdf: путь к оригинальному PDF
            translated_pdf: путь к переведенному PDF
            page_num: номер страницы (1-based)
            scale: масштаб изображения
        
        Returns:
            Словарь с base64 изображениями
        """
        images = {}
        import base64
        
        # Нормализуем пути
        original_pdf = str(Path(original_pdf))
        translated_pdf = str(Path(translated_pdf))
        
        try:
            # Оригинал
            if Path(original_pdf).exists():
                doc_orig = fitz.open(original_pdf)
                if page_num <= len(doc_orig):
                    page_orig = doc_orig[page_num - 1]
                    pix_orig = page_orig.get_pixmap(matrix=fitz.Matrix(scale, scale))
                    img_bytes_orig = pix_orig.tobytes("png")
                    images["original"] = f"data:image/png;base64,{base64.b64encode(img_bytes_orig).decode('utf-8')}"
                doc_orig.close()
            else:
                print(f"[WARN] Original PDF not found: {original_pdf}")
        except Exception as e:
            print(f"[WARN] Failed to extract original page {page_num}: {e}")
        
        try:
            # Перевод
            if Path(translated_pdf).exists():
                doc_trans = fitz.open(translated_pdf)
                if page_num <= len(doc_trans):
                    page_trans = doc_trans[page_num - 1]
                    pix_trans = page_trans.get_pixmap(matrix=fitz.Matrix(scale, scale))
                    img_bytes_trans = pix_trans.tobytes("png")
                    images["translated"] = f"data:image/png;base64,{base64.b64encode(img_bytes_trans).decode('utf-8')}"
                doc_trans.close()
            else:
                print(f"[WARN] Translated PDF not found: {translated_pdf}")
        except Exception as e:
            print(f"[WARN] Failed to extract translated page {page_num}: {e}")
        
        return images

