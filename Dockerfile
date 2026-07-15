# ---- Сборка: устанавливаем зависимости ----
FROM python:3.11-slim AS builder

WORKDIR /build

# Шаг 1: CPU-only PyTorch (~190MB вместо ~2.7GB с CUDA).
# Устанавливаем в системные site-packages — pip увидит это на следующем шаге.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

# Шаг 2: остальные зависимости. pip видит torch — не качает CUDA-версию.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && rm -rf /root/.cache/pip

# Шаг 3: предзагрузка модели эмбеддингов (чтобы не качать при запуске).
# Модель ~90MB, кэшируется в /root/.cache/huggingface/
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# ---- Продакшен-образ: только нужное ----
FROM python:3.11-slim

WORKDIR /app

# Копируем установленные пакеты и кэш модели из builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin/gunicorn /usr/local/bin/gunicorn
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface

# Копируем только исходники приложения (без тестов, без мусора)
COPY app/ ./app/
COPY .env.example ./.env.example

ENV PYTHONUNBUFFERED=1
ENV PATH="/usr/local/bin:$PATH"
# Отключаем проверку обновлений модели (уже в образе)
ENV HF_HUB_OFFLINE=1

EXPOSE 5000

CMD ["gunicorn", "app.main:app", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120"]
