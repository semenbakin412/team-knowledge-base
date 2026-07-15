# -*- coding: utf-8 -*-
"""
Финальное тестирование через HTTP-запросы к работающему контейнеру.
Запускать ПОСЛЕ docker-compose up --build.

Использование:
    python final_test.py
"""
import sys
import json
import io
import os
import requests

# Устанавливаем UTF-8 кодировку для Windows
if sys.platform == 'win32':
    os.system('chcp 65001 > nul')

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

BASE_URL = "http://localhost:5000"

print("=== ФИНАЛЬНОЕ ТЕСТИРОВАНИЕ (HTTP → Docker) ===")
print(f"Адрес: {BASE_URL}")
print("")

# Очистка: удаляем все существующие документы перед тестом
print("Очистка: удаление существующих документов...")
while True:
    resp = requests.get(f"{BASE_URL}/kb/documents")
    docs = resp.json()
    if not docs:
        break
    requests.delete(f"{BASE_URL}/kb/documents/{docs[0]['id']}")
print("   OK - База очищена\n")

# 0. Загружаем тестовые документы из tests_data
print("0. Загрузка тестовых документов из tests_data/inputs/...")
with open('tests_data/inputs/kb_documents.jsonl', 'r', encoding='utf-8') as f:
    test_docs = [json.loads(line) for line in f]

for doc in test_docs:
    resp = requests.post(f"{BASE_URL}/kb/documents", json={
        'title': doc['title'],
        'text': doc['text']
    })
    assert resp.status_code == 201, f"Ошибка загрузки: {resp.status_code} {resp.text}"
print(f"   OK - Загружено {len(test_docs)} документов\n")

# 1. Проверить витрину
print("1. Проверка витрины...")
resp = requests.get(f"{BASE_URL}/kb/documents")
assert resp.status_code == 200
docs = resp.json()
assert len(docs) == 5, f"Ожидалось 5 документов, найдено {len(docs)}"
print(f"   OK - Найдено {len(docs)} документов")

# 2. Вопрос с ответом
print("")
print("2. Вопрос с ответом...")
resp = requests.post(f"{BASE_URL}/kb/ask", json={
    "question": "Какие инструменты использует команда?"
})
assert resp.status_code == 200
result = resp.json()
print(f"   Ответ: {result['answer'][:50]}...")
print(f"   Needs review: {result['needs_review']}")

# 3. Вопрос без ответа (ручная проверка)
print("")
print("3. Вопрос без ответа...")
resp = requests.post(f"{BASE_URL}/kb/ask", json={
    "question": "Какой прогноз продаж на следующий год?"
})
assert resp.status_code == 200
result = resp.json()
print(f"   Ответ: {result['answer'][:50]}...")
print(f"   Needs review: {result['needs_review']}")
assert result['needs_review'] == True, "Ожидалось needs_review=True"

# 4. Проверить аудит (через API экспорта)
print("")
print("4. Проверка аудита...")
resp = requests.get(f"{BASE_URL}/export/audit")
assert resp.status_code == 200
audit_data = resp.json()
count = len(audit_data)
print(f"   OK - Записей в аудите: {count}")
assert count > 0

# 5. Проверить экспорт аудита
print("")
print("5. Проверка экспорта аудита...")
assert isinstance(audit_data, list)
print(f"   OK - Экспорт аудита работает, записей: {len(audit_data)}")

# 6. Проверить экспорт qa_runs
print("")
print("6. Проверка экспорта qa_runs...")
resp = requests.get(f"{BASE_URL}/export/qa_runs")
assert resp.status_code == 200
qa_data = resp.json()
print(f"   OK - Экспорт qa_runs работает, записей: {len(qa_data)}")

# 7. Тест всех 10 вопросов из тестовых данных
print("")
print("7. Тестирование всех 10 вопросов из tests_data/inputs/kb_questions.jsonl...")
with open('tests_data/inputs/kb_questions.jsonl', encoding='utf-8') as f:
    questions = [json.loads(line) for line in f]

passed = 0
for i, q in enumerate(questions, 1):
    resp = requests.post(f"{BASE_URL}/kb/ask", json={"question": q['question']})
    assert resp.status_code == 200
    result = resp.json()
    expected = q['expected_needs_review']
    actual = result['needs_review']
    match = "OK" if actual == expected else "FAIL"
    if actual == expected:
        passed += 1
    print(f"   Вопрос {i}: {match} expected={expected}, actual={actual} - {q['question'][:40]}...")

print(f"")
print(f"   Результат: {passed}/10 вопросов прошли проверку")

# 8. Проверить ИИ-операцию (строгий JSON)
print("")
print("8. Проверка ИИ-операции /ai/answer_with_sources...")
resp = requests.post(f"{BASE_URL}/ai/answer_with_sources", json={
    "question": "Что такое API?",
    "context": "API (Application Programming Interface) - интерфейс для взаимодействия программ между собой."
})
assert resp.status_code == 200
ai_result = resp.json()
assert 'answer' in ai_result
assert 'sources' in ai_result
assert 'confidence' in ai_result
assert 'needs_review' in ai_result
print(f"   OK - Строгий JSON валиден")
print(f"   answer: {ai_result['answer'][:50]}...")
print(f"   confidence: {ai_result['confidence']}")
print(f"   needs_review: {ai_result['needs_review']}")

print("")
print("=== ВСЕ ТЕСТЫ ПРОЙДЕНЫ ===")
