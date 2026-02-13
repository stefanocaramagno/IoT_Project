# Immagine base Python minimale.
# - python:3.11-slim riduce la dimensione dell'immagine mantenendo un runtime Python completo,
#   adeguato per l'esecuzione del core MAS e delle sue dipendenze (MQTT client, requests, ecc.).
FROM python:3.11-slim

# Impostazioni runtime Python in ambiente container:
# - PYTHONDONTWRITEBYTECODE=1 evita la generazione di file .pyc (riduce I/O e clutter).
# - PYTHONUNBUFFERED=1 rende stdout/stderr non bufferizzati, utile per log immediati via docker logs.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Directory di lavoro del container.
# Tutte le operazioni successive (COPY/RUN/CMD) sono eseguite relativamente a /app.
WORKDIR /app

# Copia delle dipendenze prima del codice per sfruttare la cache dei layer Docker:
# se requirements.txt non cambia, il layer di installazione può essere riutilizzato.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia del codice applicativo del MAS.
# La cartella `app/` contiene i moduli Python (agent, router, mqtt bridge, ecc.).
COPY app/ ./app

# Avvio del MAS:
# - esegue il modulo app.main (entry point definito in mas/app/main.py),
#   consentendo import relativi corretti e comportamento coerente in esecuzione containerizzata.
CMD ["python", "-m", "app.main"]
