import time

from flask import Blueprint, request, jsonify
from app.models.database import get_connection, create_snippets, log_audit
import time

documents_bp = Blueprint('documents', __name__)


@documents_bp.route('', methods=['POST'])
def add_document():
    """POST /kb/documents — Добавить документ."""
    start_time = time.time()
    try:
        data = request.get_json()
        if not data:
            log_audit('add_document', None, None, 'error', 'No JSON data', (time.time() - start_time) * 1000)
            return jsonify({"error": "Отсутствует JSON-данные"}), 400

        title = data.get('title', '').strip()
        text = data.get('text', '').strip()

        if not title:
            log_audit('add_document', data, None, 'error', 'title is empty', (time.time() - start_time) * 1000)
            return jsonify({"error": "title не может быть пустым"}), 400
        if not text:
            log_audit('add_document', data, None, 'error', 'text is empty', (time.time() - start_time) * 1000)
            return jsonify({"error": "text не может быть пустым"}), 400
        if len(title) > 200:
            return jsonify({"error": "title слишком длинный (макс 200 символов)"}), 400
        if len(text) > 500000:  # Увеличили лимит до 500К символов
            return jsonify({"error": "text слишком длинный (макс 500000 символов)"}), 400

        conn = get_connection()
        cursor = conn.cursor()
        
        # Получаем максимальный ID и увеличиваем его на 1
        cursor.execute('SELECT MAX(id) FROM documents')
        max_id = cursor.fetchone()[0]
        new_id = (max_id or 0) + 1
        
        # Вставляем документ с определённым ID
        cursor.execute('INSERT INTO documents (id, title, text) VALUES (?, ?, ?)', (new_id, title, text))
        conn.commit()
        conn.close()

        # Создаём фрагменты
        create_snippets(new_id, text)

        result = {"status": "ok", "document_id": str(new_id)}
        log_audit('add_document', {"title": title}, result, 'ok', None, (time.time() - start_time) * 1000)
        return jsonify(result), 201

    except Exception as e:
        log_audit('add_document', data if 'data' in locals() else None, None, 'error', str(e), (time.time() - start_time) * 1000)
        return jsonify({"error": str(e)}), 500


@documents_bp.route('', methods=['GET'])
def list_documents():
    """GET /kb/documents — Витрина документов."""
    start_time = time.time()
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, created_at FROM documents ORDER BY created_at ASC')
        rows = cursor.fetchall()
        conn.close()

        docs = [{"id": row['id'], "title": row['title'], "created_at": row['created_at']} for row in rows]
        log_audit('list_documents', None, docs, 'ok', None, (time.time() - start_time) * 1000)
        return jsonify(docs), 200

    except Exception as e:
        log_audit('list_documents', None, None, 'error', str(e), (time.time() - start_time) * 1000)
        return jsonify({"error": str(e)}), 500


@documents_bp.route('/<int:document_id>', methods=['GET'])
def get_document(document_id):
    """GET /kb/documents/<id> — Получить документ по ID."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, title, text, created_at FROM documents WHERE id = ?', (document_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return jsonify({"error": "Документ не найден"}), 404

        return jsonify({
            "id": row['id'],
            "title": row['title'],
            "text": row['text'],
            "created_at": row['created_at']
        }), 200

    except Exception as e:
        return jsonify({"error": str(e)}), 500


@documents_bp.route('/<int:document_id>', methods=['DELETE'])
def delete_document(document_id):
    """DELETE /kb/documents/<id> — Удалить документ и сдвинуть все последующие."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        
        # 1. Удаляем фрагменты удаляемого документа
        cursor.execute('DELETE FROM snippets WHERE document_id = ?', (document_id,))
        
        # 2. Удаляем сам документ (освобождаем ID)
        cursor.execute('DELETE FROM documents WHERE id = ?', (document_id,))
        
        # 3. Массово сдвигаем все remaining документы на -1
        # Сначала snippets, потом documents
        cursor.execute('UPDATE snippets SET document_id = document_id - 1 WHERE document_id > ?', (document_id,))
        cursor.execute('UPDATE documents SET id = id - 1 WHERE id > ?', (document_id,))
        
        conn.commit()
        conn.close()
        
        return jsonify({"status": "ok"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
