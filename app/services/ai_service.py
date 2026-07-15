import os
import json
import re
from openai import OpenAI

# Константы
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.proxyapi.ru/openai/v1")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")

# Ленивая инициализация клиента
client = None

def get_client():
    global client
    if client is None:
        client = OpenAI(
            base_url=OPENAI_BASE_URL,
            api_key=OPENAI_API_KEY
        )
    return client

MODEL = "gpt-4o-mini"


def generate_answer(question, context, max_retries=3):
    """
    Формирует ответ через LLM.
    Возвращает словарь: {answer, sources, confidence, needs_review}
    """
    # Формируем промпт
    system_prompt = """Ты - помощник по базе знаний команды. Твоя задача - отвечать на вопросы ТОЛЬКО на основе предоставленного контекста.

Правила:
1. Отвечай строго на основе контекста. НЕ додумывай и НЕ придумывай информацию.
2. Если в контексте есть ответ - сформулируй его и укажи источники (цитаты).
3. Если в контексте НЕТ достаточной информации - напиши "Данных недостаточно для формирования ответа." и установи needs_review=true.
4. Всегда возвращай ответ в формате JSON со следующими полями:
   - "answer": строка с ответом
   - "sources": массив объектов с полем "quote" (цитата из контекста)
   - "confidence": "high" | "medium" | "low"
   - "needs_review": true | false

КРИТИЧЕСКИ ВАЖНО:
- Если контекст содержит ответ на вопрос, ОБЯЗАТЕЛЬНО установи needs_review=false и confidence="high"
- Если контекст пустой или не содержит ответа - установи needs_review=true
- Цитаты в sources должны быть точными фрагментами из контекста

Пример ответа когда информация ЕСТЬ:
{"answer": "Ответ на вопрос...", "sources": [{"quote": "Цитата из документа"}], "confidence": "high", "needs_review": false}

Пример ответа когда информации НЕТ:
{"answer": "Данных недостаточно для формирования ответа.", "sources": [], "confidence": "low", "needs_review": true}"""

    user_prompt = f"""Контекст (найденные фрагменты документов):
{context if context else "(нет найденных фрагментов)"}

Вопрос: {question}

Верни ТОЛЬКО JSON, без дополнительных комментариев."""

    for attempt in range(max_retries):
        try:
            response = get_client().chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,  # Низкая температура для строгости
                max_tokens=1000
            )
            
            ai_text = response.choices[0].message.content
            if ai_text is None:
                print(f"LLM вернул пустой ответ, попытка {attempt + 1}")
                continue
            ai_text = ai_text.strip()
            
            # Парсим JSON - убираем markdown-обёртку если есть
            ai_text = re.sub(r'^```json\s*', '', ai_text)
            ai_text = re.sub(r'\s*```$', '', ai_text)
            
            result = json.loads(ai_text)
            
            # Валидируем структуру
            is_valid, error = validate_json_response(result)
            if is_valid:
                return result
            else:
                print(f"Валидация не прошла: {error}, попытка {attempt + 1}")
                
        except json.JSONDecodeError as e:
            print(f"JSON parse error (попытка {attempt + 1}): {e}")
        except Exception as e:
            print(f"Ошибка LLM (попытка {attempt + 1}): {e}")
    
    # Если все попытки не удались - возвращаем безопасный ответ
    return {
        "answer": "Данных недостаточно для формирования ответа.",
        "sources": [],
        "confidence": "low",
        "needs_review": True
    }


def validate_json_response(data):
    """
    Проверяет структуру JSON-ответа.
    Возвращает (is_valid, error_message).
    """
    if not isinstance(data, dict):
        return False, "Ответ не является объектом"
    
    required_fields = ['answer', 'sources', 'confidence', 'needs_review']
    for field in required_fields:
        if field not in data:
            return False, f"Отсутствует поле: {field}"
    
    if not isinstance(data['answer'], str):
        return False, "answer должен быть строкой"
    
    if not isinstance(data['sources'], list):
        return False, "sources должен быть массивом"
    
    if data['confidence'] not in ['high', 'medium', 'low']:
        return False, f"confidence должен быть high/medium/low, получено: {data['confidence']}"
    
    if not isinstance(data['needs_review'], bool):
        return False, "needs_review должен быть boolean"
    
    return True, None
