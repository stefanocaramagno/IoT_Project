# Base image Python minimale.
# - python:3.11-slim riduce dimensione dell'immagine rispetto alla variante full
#   mantenendo un runtime Python completo e adeguato per FastAPI/uvicorn.
FROM python:3.11-slim

# Impostazioni runtime Python per ambiente container:
# - PYTHONDONTWRITEBYTECODE=1 evita la creazione di file .pyc, riducendo I/O e clutter.
# - PYTHONUNBUFFERED=1 rende l'output non bufferizzato (stdout/stderr immediato),
#   utile per logging e osservabilità tramite docker logs.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directory di lavoro all'interno del container.
# Tutti i comandi successivi (COPY/RUN/CMD) lavorano in /app.
WORKDIR /app

# Copia del file delle dipendenze prima del codice applicativo per sfruttare la cache
# dei layer Docker: se requirements.txt non cambia, il layer di installazione resta cacheable.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia del codice sorgente del servizio.
# La struttura è mantenuta con package `app/` come root applicativa.
COPY app/ ./app

# Avvio del microservizio:
# - uvicorn esegue l'app FastAPI definita in app.main:app
# - host 0.0.0.0 per rendere il servizio accessibile dall'esterno del container
# - port 8000 come porta standard del servizio nel docker-compose.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
