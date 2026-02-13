# Immagine base Python minimale.
# - python:3.11-slim riduce dimensione dell'immagine rispetto alla variante full
#   mantenendo un runtime adeguato per il simulatore MQTT.
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

# Avvio del simulatore:
# - esegue il modulo app.main (entry point in sims/app/main.py),
#   preservando import corretti in esecuzione containerizzata.
CMD ["python", "-m", "app.main"]
