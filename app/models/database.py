import sqlite3
import os
import json
import struct
from datetime import datetime

DB_PATH = os.environ.get('DB_PATH', os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'knowledge_base.db'))

# Ленивая загрузка модели эмбеддингов
_embedding_model = None

def get_embedding_model():
    """Загружает модель для генерации эмбеддингов."""
    global _embedding_model
    if _embedding_model is None:
        from sentence_transformers import SentenceTransformer
        # Используем легковесную модель
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def serialize_embedding(embedding):
    """Конвертирует список float в байты для сохранения в SQLite."""
    return struct.pack(f'{len(embedding)}f', *embedding)


def get_connection():
    """Возвращает подключение к SQLite-базе."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Создаёт 4 таблицы если они не существуют."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            title TEXT NOT NULL,
            text TEXT NOT NULL
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS snippets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            document_id INTEGER REFERENCES documents(id),
            snippet_text TEXT NOT NULL,
            embedding BLOB
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS qa_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            question TEXT NOT NULL,
            answer TEXT,
            sources_json TEXT,
            needs_review BOOLEAN DEFAULT 0,
            error TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS audit_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            action TEXT NOT NULL,
            input TEXT,
            output TEXT,
            status TEXT,
            error TEXT,
            duration_ms INTEGER
        )
    ''')

    conn.commit()
    conn.close()


def create_snippets(document_id, text):
    """
    Разбивает текст на чанки и сохраняет с эмбеддингами.
    Использует рекурсивное разделение для лучшего качества поиска.
    """
    CHUNK_SIZE = 1000
    CHUNK_OVERLAP = 200
    
    # Генерируем эмбеддинги
    model = get_embedding_model()
    
    # Рекурсивное разделение текста
    chunks = []
    
    # Сначала пробуем разбить по заголовкам (если есть)
    if '\n#' in text:
        sections = text.split('\n# ')
        for section in sections:
            chunks.extend(_split_chunk(section.strip(), CHUNK_SIZE, CHUNK_OVERLAP))
    else:
        # Разбиваем по абзацам
        paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        if not paragraphs:
            paragraphs = [p.strip() for p in text.split('\n') if p.strip()]
        
        for para in paragraphs:
            chunks.extend(_split_chunk(para, CHUNK_SIZE, CHUNK_OVERLAP))
    
    # Генерируем эмбеддинги для всех чанков
    if chunks:
        embeddings = model.encode(chunks, show_progress_bar=False, normalize_embeddings=True)
    else:
        embeddings = []
    
    # Сохраняем в БД
    conn = get_connection()
    cursor = conn.cursor()
    for i, chunk in enumerate(chunks):
        embedding_blob = None
        if i < len(embeddings):
            emb = embeddings[i]
            # Конвертируем в список float корректно
            if hasattr(emb, 'numpy'):
                emb_list = emb.numpy().tolist()
            elif hasattr(emb, 'tolist'):
                emb_list = emb.tolist()
            else:
                emb_list = emb if isinstance(emb, list) else [float(emb)]
            embedding_blob = serialize_embedding(emb_list)
        
        cursor.execute(
            'INSERT INTO snippets (document_id, snippet_text, embedding) VALUES (?, ?, ?)',
            (document_id, chunk, embedding_blob)
        )
    conn.commit()
    conn.close()


def _split_chunk(text, chunk_size, overlap):
    """Рекурсивно разбивает текст на чанки указанного размера."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunk = text[start:end]
        
        # Пытаемся разрезать по предложению или пробелу
        if end < len(text):
            last_space = chunk.rfind(' ')
            last_period = max(chunk.rfind('. '), chunk.rfind('! '), chunk.rfind('? '))
            split_pos = max(last_space, last_period)
            
            if split_pos > chunk_size * 0.5:  # Не режем слишком рано
                chunk = chunk[:split_pos + 1]
                end = start + split_pos + 1
        
        chunks.append(chunk)
        start = end - overlap
    
    return chunks


def log_audit(action, input_data, output_data, status, error=None, duration_ms=None):
    """Записывает запись в audit_runs."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        '''INSERT INTO audit_runs (action, input, output, status, error, duration_ms)
           VALUES (?, ?, ?, ?, ?, ?)''',
        (action,
         json.dumps(input_data, ensure_ascii=False) if input_data else None,
         json.dumps(output_data, ensure_ascii=False) if output_data else None,
         status,
         error,
         duration_ms)
    )
    conn.commit()
    conn.close()
