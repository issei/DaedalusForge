FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# system deps mínimos
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -U pip && pip install --no-cache-dir -r requirements.txt

# copie apenas o necessário (ajuste conforme seu layout)
COPY . /app

CMD ["python", "main.py", "--process", "process_config.yaml"]
