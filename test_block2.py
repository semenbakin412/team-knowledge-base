"""Тест Блока 2: База данных"""
import sys
import os
sys.path.insert(0, '.')

from app.models.database import init_db, get_connection, create_snippets, log_audit

print("=== БЛОК 2: База данных ===")

# 1. init_db
init_db()
print("OK - init_db() выполнен")

# 2. Проверка таблиц
conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [t[0] for t in cursor.fetchall() if t[0] != 'sqlite_sequence']
print(f"Таблицы: {tables}")
assert 'documents' in tables, "Нет таблицы documents"
assert 'snippets' in tables, "Нет таблицы snippets"
assert 'qa_runs' in tables, "Нет таблицы qa_runs"
assert 'audit_runs' in tables, "Нет таблицы audit_runs"
print("OK - Все 4 таблицы на месте")

# 3. Проверка create_snippets
cursor.execute("DELETE FROM snippets")
cursor.execute("DELETE FROM documents")
conn.commit()
cursor.execute("INSERT INTO documents (title, text) VALUES (?, ?)", ("Тест", "Абзац 1\n\nАбзац 2\n\nАбзац 3"))
doc_id = cursor.lastrowid
conn.commit()
conn.close()

create_snippets(doc_id, "Абзац 1\n\nАбзац 2\n\nАбзац 3")

conn = get_connection()
cursor = conn.cursor()
cursor.execute("SELECT COUNT(*) FROM snippets WHERE document_id=?", (doc_id,))
count = cursor.fetchone()[0]
print(f"OK - create_snippets: {count} фрагмента создано")
assert count == 3, f"Ожидалось 3 фрагмента, получено {count}"

# 4. Проверка log_audit
log_audit("test_action", {"input": "test"}, {"output": "ok"}, "ok")
cursor.execute("SELECT COUNT(*) FROM audit_runs")
count = cursor.fetchone()[0]
print(f"OK - log_audit: {count} записей в аудите")
assert count > 0

# 5. Проверка структуры таблиц
for table in ['documents', 'snippets', 'qa_runs', 'audit_runs']:
    cursor.execute(f"PRAGMA table_info({table})")
    cols = [col[1] for col in cursor.fetchall()]
    print(f"  {table}: {cols}")

conn.close()
print("\n=== БЛОК 2: ПРОЙДЕН ===")
