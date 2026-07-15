import json
import time

from flask import Blueprint, request, jsonify
from app.models.database import get_connection, log_audit
from app.services.search_service import search_documents
from app.services.ai_service import generate_answer

ask_bp = Blueprint('ask', __name__)


@ask_bp.route('/kb/ask', methods=['POST'])
def ask_question():
    """POST /kb/ask — Задать вопрос системе."""
    start_time = time.time()
    try:
        data = request.get_json()
        if not data or not data.get('question', '').strip():
            log_audit('ask_question', data, None, 'error', 'question is empty', (time.time() - start_time) * 1000)
            return jsonify({"error": "question не может быть пустым"}), 400

        question = data['question'].strip()

        # Поиск релевантных фрагментов
        snippets = search_documents(question, limit=8)

        # Формируем контекст из фрагментов
        context_parts = []
        for s in snippets:
            context_parts.append(f"[Документ {s['document_id']}]: {s['snippet_text']}")
        context = '\n\n'.join(context_parts) if context_parts else ""

        # Вызываем ИИ
        ai_result = generate_answer(question, context)

        # Определяем sources для возврата
        sources = []
        if ai_result.get('sources') and snippets:
            # Создаём маппинг: snippet_text -> document_id
            snippet_map = {s['snippet_text']: s['document_id'] for s in snippets}
            
            for src in ai_result['sources']:
                quote = src.get('quote', '')
                if not quote:
                    continue
                
                # Ищем документ по цитате
                best_match = None
                best_score = 0
                
                for snippet_text, doc_id in snippet_map.items():
                    # Счётчик совпадений
                    score = 0
                    
                    # 1. Точное совпадение
                    if quote == snippet_text:
                        score = 100
                    # 2. Цитата содержится в фрагменте
                    elif quote in snippet_text:
                        score = 50
                    # 3. Фрагмент содержится в цитате
                    elif snippet_text in quote:
                        score = 50
                    # 4. Частичное совпадение (первые 20 символов)
                    elif quote[:20] in snippet_text:
                        score = 20
                    # 5. Совпадение по ключевым словам
                    else:
                        quote_words = set(quote.lower().split())
                        snippet_words = set(snippet_text.lower().split())
                        word_overlap = len(quote_words & snippet_words)
                        if word_overlap > 3:  # Минимум 3 общих слова
                            score = word_overlap
                    
                    if score > best_score:
                        best_score = score
                        best_match = doc_id
                
                if best_match:
                    sources.append({
                        "document_id": str(best_match), 
                        "quote": quote
                    })

        # Определяем needs_review с fallback логикой
        # Если LLM дал ответ (не "данных недостаточно") и контекст был найден - means_review = false
        answer_text = ai_result.get('answer', '').strip()
        is_empty_answer = not answer_text or answer_text == "Данных недостаточно для формирования ответа."
        
        if snippets and not is_empty_answer:
            # Контекст есть и LLM ответил - значит данные есть
            needs_review = False
        elif not snippets or is_empty_answer:
            # Контекста нет или LLM сказал "данных нет"
            needs_review = True
        else:
            # Fallback на ответ LLM
            needs_review = ai_result.get('needs_review', False)

        # Сохраняем в qa_runs
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            '''INSERT INTO qa_runs (question, answer, sources_json, needs_review, error)
               VALUES (?, ?, ?, ?, ?)''',
            (question, ai_result.get('answer'),
             json.dumps(sources, ensure_ascii=False),
             needs_review,
             'Данных недостаточно' if needs_review else None)
        )
        conn.commit()
        conn.close()
        
        result = {
            "answer": ai_result.get('answer', ''),
            "sources": sources,
            "needs_review": needs_review
        }
        log_audit('ask_question', {"question": question}, result, 'ok' if not needs_review else 'needs_review',
                  'Данных недостаточно' if needs_review else None,
                  (time.time() - start_time) * 1000)
        return jsonify(result), 200

    except Exception as e:
        log_audit('ask_question', data if 'data' in locals() else None, None, 'error', str(e), (time.time() - start_time) * 1000)
        return jsonify({"error": str(e)}), 500


@ask_bp.route('/ai/answer_with_sources', methods=['POST'])
def answer_with_sources():
    """POST /ai/answer_with_sources — ИИ ответ с источниками (для тестов)."""
    start_time = time.time()
    try:
        data = request.get_json()
        if not data or not data.get('question') or not data.get('context'):
            return jsonify({"error": "question и context обязательны"}), 400

        question = data['question']
        context = data['context']

        ai_result = generate_answer(question, context)

        # Валидация
        from app.services.ai_service import validate_json_response
        is_valid, error = validate_json_response(ai_result)
        if not is_valid:
            ai_result = {
                "answer": "Данных недостаточно для формирования ответа.",
                "sources": [],
                "confidence": "low",
                "needs_review": True
            }

        log_audit('answer_with_sources', {"question": question}, ai_result, 'ok', None, (time.time() - start_time) * 1000)
        return jsonify(ai_result), 200

    except Exception as e:
        log_audit('answer_with_sources', data if 'data' in locals() else None, None, 'error', str(e), (time.time() - start_time) * 1000)
        return jsonify({"error": str(e)}), 500


@ask_bp.route('/kb/history', methods=['GET'])
def history():
    """GET /kb/history — История вопросов для веб-панели."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT id, created_at, question, answer, sources_json, needs_review, error FROM qa_runs ORDER BY created_at DESC LIMIT 100')
        rows = cursor.fetchall()
        conn.close()
        
        items = [{
            "id": row['id'],
            "created_at": row['created_at'],
            "question": row['question'],
            "answer": row['answer'],
            "sources_json": row['sources_json'],
            "needs_review": bool(row['needs_review']),
            "error": row['error']
        } for row in rows]
        
        return jsonify(items), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
