import os
from flask import Flask, redirect, render_template, jsonify
from dotenv import load_dotenv

# Загружаем переменные из .env файла
load_dotenv()

from app.routes.documents import documents_bp
from app.routes.ask import ask_bp
from app.models.database import init_db

def create_app():
    # template_folder='templates' -> ищет в app/templates/ (относительно __name__)
    app = Flask(__name__, template_folder='templates')
    
    # Регистрация Blueprint'ов
    # documents_bp: /kb/documents, /kb/documents/<id>
    app.register_blueprint(documents_bp, url_prefix='/kb/documents')
    # ask_bp: /kb/ask, /kb/history, /ai/answer_with_sources (полные пути в роутах)
    app.register_blueprint(ask_bp)
    
    # Инициализация базы данных
    init_db()
    
    # Корневая страница -> редирект на документы
    @app.route('/')
    def index():
        return redirect('/documents')
    
    # Веб-панель: страницы
    @app.route('/documents')
    def documents_page():
        return render_template('documents.html')
    
    @app.route('/ask')
    def ask_page():
        return render_template('ask.html')
    
    @app.route('/history')
    def history_page():
        return render_template('history.html')
    
    # Экспорт аудита в JSON (требование lesson.txt: экспорт JSON или CSV)
    @app.route('/export/audit')
    def export_audit():
        from app.models.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM audit_runs ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        items = [dict(row) for row in rows]
        return jsonify(items), 200
    
    # Экспорт истории вопросов в JSON
    @app.route('/export/qa_runs')
    def export_qa_runs():
        from app.models.database import get_connection
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM qa_runs ORDER BY created_at DESC')
        rows = cursor.fetchall()
        conn.close()
        items = [dict(row) for row in rows]
        return jsonify(items), 200
    
    # Обработка ошибок
    @app.errorhandler(404)
    def not_found(e):
        return {'error': 'Not found'}, 404
    
    @app.errorhandler(500)
    def internal_error(e):
        return {'error': 'Internal server error'}, 500
    
    return app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
