"""Тест Блока 5: Веб-панель"""
import sys
import os
sys.path.insert(0, '.')
os.environ.setdefault('OPENAI_API_KEY', 'test-key')

from app.main import app

client = app.test_client()

print("=== БЛОК 5: Веб-панель ===")

# 1. Главная страница (редирект)
print("1. GET / (редирект)...")
response = client.get('/')
assert response.status_code in [302, 308], f"Ожидался редирект, получен {response.status_code}"
print(f"   OK - статус {response.status_code} (редирект)")

# 2. Страница документов
print("2. GET /documents...")
response = client.get('/documents')
assert response.status_code == 200
assert b'html' in response.data.lower()
print(f"   OK - статус {response.status_code}, HTML получен")

# 3. Страница вопросов
print("3. GET /ask...")
response = client.get('/ask')
assert response.status_code == 200
assert b'html' in response.data.lower()
print(f"   OK - статус {response.status_code}, HTML получен")

# 4. Страница истории
print("4. GET /history...")
response = client.get('/history')
assert response.status_code == 200
assert b'html' in response.data.lower()
print(f"   OK - статус {response.status_code}, HTML получен")

# 5. Проверка наличия Bootstrap в base.html
print("5. Проверка Bootstrap в шаблонах...")
response = client.get('/documents')
assert b'bootstrap' in response.data.lower()
print(f"   OK - Bootstrap подключен")

# 6. Проверка навигации
print("6. Проверка навигации...")
assert b'/documents' in response.data
assert b'/ask' in response.data
assert b'/history' in response.data
print(f"   OK - Навигация на месте")

# 7. Проверка формы добавления документа
print("7. Проверка формы добавления документа...")
assert b'addDocForm' in response.data or b'docTitle' in response.data
print(f"   OK - Форма добавления найдена")

print("\n=== БЛОК 5: ПРОЙДЕН ===")
