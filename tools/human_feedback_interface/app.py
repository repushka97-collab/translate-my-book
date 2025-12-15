"""
Веб-интерфейс для сбора человеческой обратной связи.
Flask приложение для оценки качества перевода.
"""

from flask import Flask, render_template, request, jsonify
import os
import sys
from pathlib import Path

# Добавляем путь к корню проекта
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from core_engine.learning.human_feedback_collector import HumanFeedbackCollector

app = Flask(__name__)

# Инициализируем коллектор обратной связи
feedback_collector = HumanFeedbackCollector()


@app.route('/')
def index():
    """Главная страница."""
    return render_template('index.html')


@app.route('/feedback')
def feedback_page():
    """Страница для оценки страницы."""
    book_path = request.args.get('book')
    page_num = int(request.args.get('page', 1))
    original_pdf = request.args.get('original', book_path)
    
    if not book_path:
        return "Error: book parameter required", 400
    
    # Нормализуем пути (для Windows)
    book_path = book_path.replace('\\', os.sep)
    if original_pdf:
        original_pdf = original_pdf.replace('\\', os.sep)
    
    # Получаем изображения страниц
    try:
        images = feedback_collector.get_page_images(
            original_pdf or book_path,
            book_path,
            page_num
        )
    except Exception as e:
        return f"Error loading pages: {e}", 500
    
    return render_template(
        'feedback.html',
        original_img=images.get("original", ""),
        translated_img=images.get("translated", ""),
        book=book_path,
        page=page_num,
        original_pdf=original_pdf or book_path
    )


@app.route('/save_feedback', methods=['POST'])
def save_feedback():
    """Сохраняет обратную связь."""
    try:
        data = request.json
        book = data.get('book', '')
        page = data.get('page', 1)
        user_name = data.get('user', 'default')
        visual_score = data.get('quality_score')
        problem_areas = data.get('problem_areas', [])
        semantic_issues = data.get('semantic_issues', [])
        comment = data.get('comment', '')
        
        # Определяем пути к PDF
        original_pdf = data.get('original_pdf', book)
        translated_pdf = book
        
        # Собираем обратную связь
        feedback = feedback_collector.collect_feedback(
            original_pdf=original_pdf,
            translated_pdf=translated_pdf,
            page_num=page,
            user_name=user_name,
            visual_score=visual_score,
            problem_areas=problem_areas,
            semantic_issues=semantic_issues,
            comment=comment
        )
        
        return jsonify({
            "status": "success",
            "feedback": feedback,
            "message": "Оценка сохранена!"
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/api/user_feedback/<user_name>')
def get_user_feedback(user_name):
    """Получает всю обратную связь пользователя."""
    try:
        feedbacks = feedback_collector.load_user_feedback(user_name)
        return jsonify({
            "status": "success",
            "feedbacks": feedbacks,
            "count": len(feedbacks)
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


if __name__ == '__main__':
    # Исправление кодировки для Windows
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except Exception:
            pass
    
    print("Starting Human Feedback Interface...")
    print("Open http://localhost:5000/feedback?book=your_book.pdf&page=1")
    app.run(debug=True, port=5000, host='127.0.0.1')

