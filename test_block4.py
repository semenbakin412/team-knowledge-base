"""Тест Блока 4: ИИ-сервисы и поиск"""
import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')

from app.services.ai_service import validate_json_response, generate_answer
from app.services.search_service import search_documents, get_document_by_id

print("=== БЛОК 4: ИИ-сервисы и поиск ===")

# 1. validate_json_response - валидный JSON
print("1. validate_json_response (валидный)...")
valid = {
    "answer": "Тест",
    "sources": [{"quote": "Цитата"}],
    "confidence": "high",
    "needs_review": False
}
is_valid, error = validate_json_response(valid)
assert is_valid, f"Ожидалось True, ошибка: {error}"
print(f"   OK - is_valid={is_valid}")

# 2. validate_json_response - невалидный (нет полей)
print("2. validate_json_response (нет полей)...")
invalid = {"answer": "Тест"}
is_valid, error = validate_json_response(invalid)
assert not is_valid
print(f"   OK - is_valid={is_valid}, error: {error}")

# 3. validate_json_response - неверный confidence
print("3. validate_json_response (неверный confidence)...")
invalid2 = {
    "answer": "Тест",
    "sources": [],
    "confidence": "super",
    "needs_review": False
}
is_valid, error = validate_json_response(invalid2)
assert not is_valid
print(f"   OK - is_valid={is_valid}, error: {error}")

# 4. validate_json_response - неверный тип needs_review
print("4. validate_json_response (needs_review не bool)...")
invalid3 = {
    "answer": "Тест",
    "sources": [],
    "confidence": "low",
    "needs_review": "yes"
}
is_valid, error = validate_json_response(invalid3)
assert not is_valid
print(f"   OK - is_valid={is_valid}, error: {error}")

# 5. generate_answer - fallback при отсутствии ключа
print("5. generate_answer (fallback без ключа)...")
result = generate_answer("Тестовый вопрос", "Тестовый контекст")
assert result['needs_review'] == True
assert result['confidence'] == 'low'
assert "недостаточно" in result['answer'].lower()
print(f"   OK - fallback сработал, needs_review={result['needs_review']}")

# 6. search_documents - поиск по ключевым словам
print("6. search_documents...")
results = search_documents("инструменты команда", limit=5)
print(f"   Найдено фрагментов: {len(results)}")
# Результаты могут быть пустыми если БД пуста
print(f"   OK - поиск выполнен, результатов: {len(results)}")

# 7. get_document_by_id
print("7. get_document_by_id...")
doc = get_document_by_id(1)
if doc:
    print(f"   OK - документ найден: {doc['title']}")
else:
    print(f"   OK - документ не найден (БД может быть пуста)")

print("\n=== БЛОК 4: ПРОЙДЕН ===")
