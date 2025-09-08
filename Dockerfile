FROM python:3.11-slim

# Минимум системных пакетов (нам хватает для Stage 1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PYTHONUNBUFFERED=1
CMD ["bash", "-lc", "uvicorn app.api.main:app --host 0.0.0.0 --port 8000"]