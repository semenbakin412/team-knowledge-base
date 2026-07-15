# -*- coding: utf-8 -*-
import struct
import faiss
import numpy as np
import re

from app.models.database import get_connection, get_embedding_model


def clean_text(text):
    """Удаляет лишние пробелы и нормализует текст."""
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def search_documents(question, limit=5):
    """
    Гибридный поиск: объединяет векторный и текстовый поиск для максимальной точности.
    """
    # Получаем все фрагменты из БД
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, document_id, snippet_text, embedding FROM snippets')
    rows = cursor.fetchall()
    conn.close()
    
    if not rows:
        return []
    
    # 1. ВЕКТОРНЫЙ ПОИСК
    vector_results = _vector_search(question, rows, limit=10)
    
    # 2. ТЕКСТОВЫЙ ПОИСК (fallback)
    text_results = _keyword_search(question, rows, limit=10)
    
    # 3. ОБЪЕДИНЯЕМ РЕЗУЛЬТАТЫ
    combined = _combine_results(vector_results, text_results, limit=limit)
    
    return combined


def _vector_search(question, rows, limit=10):
    """Векторный поиск через FAISS."""
    model = get_embedding_model()
    question_embedding = model.encode([question], normalize_embeddings=True)
    
    # Преобразуем в numpy
    if hasattr(question_embedding, 'numpy'):
        question_embedding = question_embedding.numpy()
    elif hasattr(question_embedding, 'tolist'):
        question_embedding = np.array(question_embedding.tolist(), dtype='float32')
    else:
        question_embedding = np.array(question_embedding, dtype='float32')
    
    if question_embedding.ndim > 1:
        question_embedding = question_embedding.flatten()
    
    question_embedding_np = question_embedding.astype('float32')
    
    # Декодируем эмбеддинги
    embeddings = []
    snippets_data = []
    
    for row in rows:
        emb_blob = row['embedding']
        if emb_blob and len(emb_blob) >= 4:
            try:
                num_floats = len(emb_blob) // 4
                embedding_list = list(struct.unpack(f'{num_floats}f', emb_blob[:num_floats*4]))
                embeddings.append(embedding_list)
                snippets_data.append({
                    "document_id": row['document_id'],
                    "snippet_text": row['snippet_text']
                })
            except:
                pass
    
    if not embeddings:
        return []
    
    embeddings_np = np.array(embeddings, dtype='float32')
    dimension = embeddings_np.shape[1]
    
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_np)
    
    search_limit = min(limit, len(snippets_data))
    if search_limit <= 0:
        return []
    
    distances, indices = index.search(question_embedding_np.reshape(1, -1), search_limit)
    
    results = []
    for i, idx in enumerate(indices[0]):
        if idx != -1:
            results.append({
                "document_id": snippets_data[idx]['document_id'],
                "snippet_text": snippets_data[idx]['snippet_text'],
                "score": float(distances[0][i]),
                "type": "vector"
            })
    
    results.sort(key=lambda x: x['score'])
    return results
    

def _keyword_search(question, rows, limit=10):
    """Текстовый поиск по ключевым словам с поддержкой русских словоформ."""
    stop_words = {
        'что', 'как', 'где', 'когда', 'почему', 'зачем', 'кто', 'какой', 'какая',
        'какие', 'какое', 'ли', 'же', 'бы', 'для', 'при', 'это', 'этом', 'эта',
        'этот', 'был', 'была', 'только', 'также', 'ещё', 'еще', 'уже', 'всех',
        'всего', 'может', 'можно', 'нужно', 'надо', 'если', 'то', 'так', 'там',
        'тут', 'чем', 'простыми', 'словами', 'просто',
        'the', 'is', 'at', 'which', 'on', 'a', 'an', 'and', 'or', 'to', 'of',
        'for', 'in', 'with', 'by', 'from', 'as', 'be', 'this', 'that', 'it',
        'про', 'над', 'под', 'из', 'от', 'до', 'к', 'у', 'на', 'за', 'о', 'об',
        'по', 'не', 'ни', 'или', 'и', 'а', 'но', 'бы',
    }
    
    question_lower = question.lower()
    words = re.findall(r'[а-яёa-z]{3,}', question_lower)
    keywords = [w for w in words if w not in stop_words]
    
    if not keywords:
        keywords = words
    
    # Создаём основы слов (первые 4-5 символов) для частичного совпадения
    stems = set()
    for kw in keywords:
        if len(kw) >= 5:
            stems.add(kw[:4])
        if len(kw) >= 6:
            stems.add(kw[:5])
    
    scored_snippets = []
    for row in rows:
        score = 0
        text = row['snippet_text'].lower()
        
        for kw in keywords:
            # Полное совпадение
            if kw in text:
                score += len(kw) * 10
            else:
                # Совпадение по основе слова (первые 4-5 символов)
                for stem_len in [5, 4]:
                    if len(kw) >= stem_len + 1:
                        stem = kw[:stem_len]
                        if stem in text:
                            score += stem_len * 2
                            break
        
        if score > 0:
            scored_snippets.append({
                "document_id": row['document_id'],
                "snippet_text": row['snippet_text'],
                "score": -score,
                "type": "text"
            })
    
    scored_snippets.sort(key=lambda x: x['score'])
    return scored_snippets[:limit]


def _combine_results(vector_results, text_results, limit=5):
    """Объединяет результаты: текстовый поиск приоритетнее векторного."""
    seen = set()
    combined = []
    
    # Сначала добавляем результаты текстового поиска (точные совпадения ключевых слов)
    for result in text_results:
        snippet_text = result['snippet_text']
        if snippet_text not in seen:
            seen.add(snippet_text)
            combined.append(result)
    
    # Затем добавляем векторные результаты (семантическое сходство)
    for result in vector_results:
        snippet_text = result['snippet_text']
        if snippet_text not in seen:
            seen.add(snippet_text)
            combined.append(result)
    
    return combined[:limit]


def get_document_by_id(document_id):
    """Возвращает документ из БД по ID."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT id, title, text, created_at FROM documents WHERE id = ?', (document_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return None
    return {
        "id": row['id'],
        "title": row['title'],
        "text": row['text'],
        "created_at": row['created_at']
    }
