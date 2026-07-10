FROM python:3.13-slim

WORKDIR /app

# Dépendances d'abord pour profiter du cache de layers
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

EXPOSE 8000

# --proxy-headers : derrière le reverse proxy Caddy (X-Forwarded-*)
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]
