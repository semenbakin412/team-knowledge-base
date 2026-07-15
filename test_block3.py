"""Тест Блока 3: API (серверная часть)"""
import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')

from app.main import app

client = app.test_client()

print("=== БЛОК 3: API ===")

# 1. POST /kb/documents
print("1. POST /kb/documents...")
response = client.post('/kb/documents', json={
    "title": "Тестовый документ",
    "text": "Это тестовый текст для проверки API."
})
assert response.status_code == 201, f"Ожидался 201, получен {response.status_code}"
created_doc_id = response.get_json()['document_id']
print(f"   OK - статус {response.status_code}, document_id: {created_doc_id}")

# 2. GET /kb/documents
print("2. GET /kb/documents...")
response = client.get('/kb/documents')
assert response.status_code == 200
docs = response.get_json()
assert len(docs) > 0
print(f"   OK - статус {response.status_code}, документов: {len(docs)}")

# 3. GET /kb/documents/<id>
print("3. GET /kb/documents/<id>...")
response = client.get(f'/kb/documents/{created_doc_id}')
assert response.status_code == 200
assert response.get_json()['title'] == "Тестовый документ"
print(f"   OK - статус {response.status_code}, title: {response.get_json()['title']}")

# 4. Валидация: пустой title
print("4. POST /kb/documents (пустой title)...")
response = client.post('/kb/documents', json={"title": "", "text": "Текст"})
assert response.status_code == 400
print(f"   OK - статус {response.status_code} (валидация)")

# 5. Валидация: пустой text
print("5. POST /kb/documents (пустой text)...")
response = client.post('/kb/documents', json={"title": "Заголовок", "text": ""})
assert response.status_code == 400
print(f"   OK - статус {response.status_code} (валидация)")

# 6. POST /kb/ask
print("6. POST /kb/ask...")
response = client.post('/kb/ask', json={"question": "О чём тестовый документ?"})
assert response.status_code == 200
result = response.get_json()
assert 'answer' in result
assert 'sources' in result
assert 'needs_review' in result
print(f"   OK - статус {response.status_code}, needs_review: {result['needs_review']}")

# 7. POST /kb/ask (пустой вопрос)
print("7. POST /kb/ask (пустой вопрос)...")
response = client.post('/kb/ask', json={"question": ""})
assert response.status_code == 400
print(f"   OK - статус {response.status_code} (валидация)")

# 8. GET /kb/history
print("8. GET /kb/history...")
response = client.get('/kb/history')
assert response.status_code == 200
history = response.get_json()
assert len(history) > 0
print(f"   OK - статус {response.status_code}, записей: {len(history)}")

# 9. POST /ai/answer_with_sources
print("9. POST /ai/answer_with_sources...")
response = client.post('/ai/answer_with_sources', json={
    "question": "Что такое API?",
    "context": "API - интерфейс для взаимодействия программ между собой."
})
assert response.status_code == 200
ai = response.get_json()
assert 'answer' in ai
assert 'sources' in ai
assert 'confidence' in ai
assert 'needs_review' in ai
print(f"   OK - статус {response.status_code}, confidence: {ai.get('confidence')}")

# 10. GET /export/audit
print("10. GET /export/audit...")
response = client.get('/export/audit')
assert response.status_code == 200
assert isinstance(response.get_json(), list)
print(f"   OK - статус {response.status_code}, записей: {len(response.get_json())}")

# 11. GET /export/qa_runs
print("11. GET /export/qa_runs...")
response = client.get('/export/qa_runs')
assert response.status_code == 200
assert isinstance(response.get_json(), list)
print(f"   OK - статус {response.status_code}, записей: {len(response.get_json())}")

# 12. 404
print("12. GET /nonexistent (404)...")
response = client.get('/nonexistent')
assert response.status_code == 404
print(f"   OK - статус {response.status_code}")

print("\n=== БЛОК 3: ПРОЙДЕН ===")
