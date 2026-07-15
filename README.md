# Система знаний команды (Team Knowledge Base)

> **Технологии:** Flask, SQLite, gpt-4o-mini, FAISS, sentence-transformers  
> **Время запуска:** ≤ 10 минут

Система для поиска по внутренним документам с ответами на основе источников и честной ручной проверкой. Включает семантический поиск (векторный) для повышения точности.

## Ценность

- **Новичкам** — быстрый доступ к правилам, процессам и терминам команды
- **Менеджерам** — готовые ответы для клиентов с цитатами-источниками
- **Руководителям** — единая точка правды, доказуемость ответов, аудит

## Архитектура

```
Веб-панель (Bootstrap) → Flask API → SQLite (documents, snippets+embedding, qa_runs, audit_runs)
                            ↓
                    FAISS (Векторный поиск) ← sentence-transformers
                            ↓
                    LLM (gpt-4o-mini) → Контроль качества → Аудит
```

**Поток данных:**
1. Пользователь добавляет документ → текст разбивается на чанки (по 1000 символов с перекрытием)
2. Для каждого чанка генерируется векторное представление (эмбеддинг) и сохраняется в FAISS/SQLite
3. Пользователь задаёт вопрос → вопрос векторизируется → поиск по FAISS (топ-5 похожих чанков)
4. Контекст из чанков отправляется в LLM → LLM возвращает ответ с цитатами
5. Результат сохраняется в qa_runs, действие логируется в audit_runs

## Структура проекта

```
team-knowledge-base/
├── app/
│   ├── main.py                    # Flask-приложение, роуты веб-панели, экспорт
│   ├── routes/
│   │   ├── documents.py           # POST/GET /kb/documents, GET/DELETE /kb/documents/<id>
│   │   └── ask.py                 # POST /kb/ask, POST /ai/answer_with_sources, GET /kb/history
│   ├── models/
│   │   └── database.py            # SQLite: init_db, create_snippets, log_audit, эмбеддинги
│   ├── services/
│   │   ├── ai_service.py          # LLM-вызов, строгий JSON, валидация, fallback
│   │   └── search_service.py      # Гибридный поиск (векторный FAISS + текстовый)
│   └── templates/
│       ├── base.html              # Базовый шаблон (Bootstrap 5, навигация)
│       ├── documents.html         # Экран 1: Документы (список + форма + просмотр)
│       ├── ask.html               # Экран 2: Вопросы (вопрос → ответ + источники)
│       └── history.html           # Экран 3: История (фильтр, карточки, экспорт)
├── tests_data/inputs/
│   ├── kb_documents.jsonl         # 5 тестовых документов
│   └── kb_questions.jsonl         # 10 тестовых вопросов (7 false + 3 true)
├── requirements.txt
├── .env.example
├── .gitignore
├── Dockerfile
├── docker-compose.yml
└── README.md
```

## Быстрый старт (≤ 10 минут)

### Локальный запуск

```bash
# 1. Виртуальное окружение
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Linux/Mac

# 2. Установить зависимости (включая FAISS для векторного поиска)
pip install -r requirements.txt

# 3. Настроить переменные окружения
copy .env.example .env         # Windows
# cp .env.example .env         # Linux/Mac
# Откройте .env и вставьте ваш OPENAI_API_KEY

# 4. Запустить
python app/main.py
```

Откройте http://localhost:5000

### Запуск через Docker (рекомендуется)

```bash
# 1. Создайте файл .env с вашим API-ключом
# OPENAI_BASE_URL=https://api.proxyapi.ru/openai/v1
# OPENAI_API_KEY=ваш-ключ

# 2. Запустите через Docker Compose
docker-compose up --build

# 3. Откройте http://localhost:5000
```

База данных сохраняется в Docker volume `db_data` — данные не теряются при перезапуске контейнера.

**Остановка контейнера:**
```bash
docker-compose down          # остановить (данные сохранятся)
docker-compose down -v       # остановить и удалить БД
```

## Переменные окружения (.env)

| Переменная | Описание | Пример |
|---|---|---|
| `OPENAI_BASE_URL` | Базовый URL API | `https://api.proxyapi.ru/openai/v1` |
| `OPENAI_API_KEY` | API-ключ proxyapi.ru | `your-key-here` |

Без валидного ключа система работает в режиме fallback: все ответы получают `needs_review=true`.

## API — Точки доступа

### Точка 1: Добавить документ

```bash
curl -X POST http://localhost:5000/kb/documents \
  -H "Content-Type: application/json" \
  -d '{"title":"Правила команды","text":"Рабочие часы: 9-18. Каналы: Slack, Email."}'
```

Ответ:
```json
{"status": "ok", "document_id": "1"}
```

Ошибки: 400 — пустой title/text, title > 200 символов, text > 500000 символов.

> **Примечание:** Документы автоматически разбиваются на чанки по 1000 символов с перекрытием 200 символов для более точного поиска.

### Точка 2: Витрина документов

```bash
curl http://localhost:5000/kb/documents
```

Ответ:
```json
[{"id": 1, "title": "Правила команды", "created_at": "2024-01-01 12:00:00"}]
```

Получить документ по ID:
```bash
curl http://localhost:5000/kb/documents/1
```

### Точка 3: Задать вопрос системе

```bash
curl -X POST http://localhost:5000/kb/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Какие инструменты использует команда?"}'
```

Ответ (данные найдены):
```json
{
  "answer": "Команда использует GitLab, Jira, Confluence, Slack и Figma.",
  "sources": [{"document_id": "1", "quote": "GitLab - репозиторий кода..."}],
  "needs_review": false
}
```

Ответ (данных недостаточно):
```json
{
  "answer": "Данных недостаточно для формирования ответа.",
  "sources": [],
  "needs_review": true
}
```

### Точка 4: ИИ-ответ с источниками (строгий JSON)

```bash
curl -X POST http://localhost:5000/ai/answer_with_sources \
  -H "Content-Type: application/json" \
  -d '{"question":"Что такое API?","context":"API - интерфейс для взаимодействия программ."}'
```

Ответ:
```json
{
  "answer": "API — интерфейс для взаимодействия программ между собой.",
  "sources": [{"quote": "API - интерфейс для взаимодействия программ."}],
  "confidence": "high",
  "needs_review": false
}
```

### История вопросов

```bash
curl http://localhost:5000/kb/history
```

## Веб-панель (3 экрана)

| Экран | URL | Назначение |
|---|---|---|
| Документы | `/documents` | Список, добавление, просмотр документов |
| Вопросы | `/ask` | Задать вопрос, получить ответ с источниками |
| История | `/history` | Таблица вопросов, фильтр "требует проверки", карточки, экспорт |

## 3 сценария пользователя

### Сценарий 1: Загрузка документов
Пользователь открывает вкладку «Документы» → заполняет форму (название + текст) → нажимает «Добавить» → документ появляется в таблице.

### Сценарий 2: Вопрос с ответом
Пользователь открывает вкладку «Вопросы» → вводит вопрос → нажимает «Спросить» → получает ответ и список источников (цитаты с номерами документов).

### Сценарий 3: Ручная проверка
Пользователь задаёт вопрос, на который нет данных → система отвечает «Данных недостаточно» → выставляет `needs_review=true` → в истории вопрос помечается красным значком «Требует проверки» → в карточке видна причина.

## База данных

SQLite-файл: `knowledge_base.db` (создаётся автоматически при первом запуске)

| Таблица | Поля | Назначение |
|---|---|---|
| documents | id, created_at, title, text | Документы базы знаний |
| snippets | id, created_at, document_id, snippet_text, **embedding** | Фрагменты (чанки) для поиска + векторные представления |
| qa_runs | id, created_at, question, answer, sources_json, needs_review, error | История вопросов и ответов |
| audit_runs | id, created_at, action, input, output, status, error, duration_ms | Аудит всех действий |

Посмотреть данные:
```bash
sqlite3 knowledge_base.db "SELECT * FROM audit_runs ORDER BY created_at DESC LIMIT 10;"
sqlite3 knowledge_base.db "SELECT * FROM qa_runs WHERE needs_review=1;"
sqlite3 knowledge_base.db "SELECT COUNT(*) FROM documents;"
```

## Векторный поиск (Semantic Search)


1. **Чанкирование:** Документы разбиваются на фрагменты по 1000 символов с перекрытием 200 символов
2. **Векторизация:** Каждый фрагмент преобразуется в числовой вектор (эмбеддинг) с помощью модели `all-MiniLM-L6-v2`
3. **Поиск:** При задании вопроса система ищет наиболее похожие фрагменты через FAISS (топ-8) + текстовый поиск по ключевым словам
4. **Контекст:** Найденные фрагменты отправляются в LLM для формирования ответа

**Преимущества:**
- Поиск по смыслу, а не только по ключевым словам
- Лучше понимает синонимы и контекст
- Работает локально, без облачных сервисов

## Ручная проверка (needs_review)

Ручная проверка включается когда:
- Не найдено подходящих фрагментов (пустой контекст)
- `confidence = "low"`
- LLM не вернул валидный JSON после 3 попыток
- Источники пусты

Как воспроизвести:
```bash
curl -X POST http://localhost:5000/kb/ask \
  -H "Content-Type: application/json" \
  -d '{"question":"Какой прогноз продаж на следующий квартал?"}'
```

Ожидаемый результат: `needs_review: true`, `sources: []`, причина в `qa_runs.error`.

## Экспорт данных

```bash
# Экспорт аудита (JSON)
curl http://localhost:5000/export/audit

# Экспорт истории вопросов (JSON)
curl http://localhost:5000/export/qa_runs
```

Также доступно из веб-панели: вкладка «История» → кнопки «Экспорт QA» и «Экспорт аудита».

## Тестовые данные

Папка `tests_data/inputs/`:
- `kb_documents.jsonl` — 5 документов (Правила, FAQ, Шаблоны, Словарь, Процесс)
- `kb_questions.jsonl` — 10 вопросов (7 с ответом + 3 без ответа)

### Мини-таблица тестовых вопросов

| № | Вопрос | expected_needs_review | Почему | Документ-источник |
|---|--------|----------------------|--------|-------------------|
| 1 | Какие инструменты использует команда для работы? | false | Ответ есть в документе | Правила работы команды |
| 2 | Как оформить заказ на сайте? | false | Ответ есть в документе | Частые вопросы клиентов |
| 3 | Что делать если клиент недоволен качеством товара? | false | Ответ есть в документе | Шаблоны ответов |
| 4 | Что такое API простыми словами? | false | Ответ есть в документе | Словарь терминов |
| 5 | Какой график работы команды? | false | Ответ есть в документе | Правила работы команды |
| 6 | Сколько длится доставка по России? | false | Ответ есть в документе | Частые вопросы клиентов |
| 7 | Какие шаги для запуска задачи? | false | Ответ есть в документе | Процесс запуска задачи |
| 8 | Какой прогноз продаж на следующий квартал? | true | Нет информации в документах | — |
| 9 | Какая зарплата у сотрудников? | true | Нет информации в документах | — |
| 10 | Кто генеральный директор компании? | true | Нет информации в документах | — |

### Запуск тестов

```bash
# Сквозной тест всех блоков
python final_test.py

# Тесты по блокам
python test_block2.py   # База данных
python test_block3.py   # API
python test_block4.py   # ИИ-сервисы и поиск
python test_block5.py   # Веб-панель
python test_block6.py   # Тестовые данные
```

## Контроль качества

- **Вход:** проверка title/text на пустоту и длину, проверка question на пустоту
- **LLM:** строгий JSON с валидацией структуры (answer, sources, confidence, needs_review)
- **Выход:** если sources пуст → needs_review=true; если LLM не ответил → безопасный fallback
- **Аудит:** каждое действие логируется с duration_ms, status и error

## Docker

```bash
# Сборка и запуск
docker-compose up --build

# Остановка (данные сохранятся в volume)
docker-compose down

# Остановка с удалением БД
docker-compose down -v
```

Образ: `python:3.11-slim`, multi-stage build, CPU-only PyTorch (~2.2GB).
БД: Docker volume `db_data` → `/app/data/knowledge_base.db`.
Модель эмбеддингов `all-MiniLM-L6-v2` предзагружена в образ.
