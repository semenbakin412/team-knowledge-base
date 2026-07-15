"""Тест Блока 6: Тестовые данные"""
import sys
import os
import json
sys.path.insert(0, '.')

print("=== БЛОК 6: Тестовые данные ===")

# 1. Проверка kb_documents.jsonl
print("1. Проверка kb_documents.jsonl...")
with open('tests_data/inputs/kb_documents.jsonl', 'r', encoding='utf-8') as f:
    docs = [json.loads(line) for line in f if line.strip()]
assert len(docs) == 5, f"Ожидалось 5 документов, получено {len(docs)}"
for i, doc in enumerate(docs, 1):
    assert 'title' in doc, f"Документ {i}: нет title"
    assert 'text' in doc, f"Документ {i}: нет text"
    assert len(doc['text']) > 0, f"Документ {i}: пустой text"
    print(f"   Док {i}: {doc['title'][:40]}... ({len(doc['text'])} символов)")
print(f"   OK - {len(docs)} документов валидны")

# 2. Проверка kb_questions.jsonl
print("2. Проверка kb_questions.jsonl...")
with open('tests_data/inputs/kb_questions.jsonl', 'r', encoding='utf-8') as f:
    questions = [json.loads(line) for line in f if line.strip()]
assert len(questions) == 10, f"Ожидалось 10 вопросов, получено {len(questions)}"

review_true = 0
review_false = 0
for i, q in enumerate(questions, 1):
    assert 'question' in q, f"Вопрос {i}: нет question"
    assert 'expected_needs_review' in q, f"Вопрос {i}: нет expected_needs_review"
    if q['expected_needs_review']:
        review_true += 1
    else:
        review_false += 1
    print(f"   Вопрос {i}: review={q['expected_needs_review']} - {q['question'][:50]}...")

assert review_true == 3, f"Ожидалось 3 вопроса с needs_review=True, получено {review_true}"
assert review_false == 7, f"Ожидалось 7 вопросов с needs_review=False, получено {review_false}"
print(f"   OK - {len(questions)} вопросов (7 false + 3 true)")

# 3. Загрузка документов через API
print("3. Загрузка документов через API...")
os.environ.setdefault('OPENAI_API_KEY', 'test-key')
from app.main import app
client = app.test_client()

for i, doc in enumerate(docs, 1):
    response = client.post('/kb/documents', json=doc)
    assert response.status_code == 201, f"Документ {i}: статус {response.status_code}"
    print(f"   Док {i}: загружен (ID: {response.get_json()['document_id']})")
print(f"   OK - все 5 документов загружены")

print("\n=== БЛОК 6: ПРОЙДЕН ===")
