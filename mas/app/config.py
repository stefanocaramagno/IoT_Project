"""
Modulo di configurazione del servizio MAS (Multi-Agent System) per il monitoraggio urbano.

Obiettivo
---------
Centralizzare i parametri di configurazione utilizzati dai componenti del MAS,
rendendo il sistema facilmente configurabile tramite variabili d'ambiente e
valori di default ragionevoli per l'esecuzione in Docker Compose.

Ruolo nel sistema
-----------------
Questo modulo definisce:
- Parametri di connessione al broker MQTT (host, porta) e topic filter per la sottoscrizione.
- Elenco dei distretti/quartieri gestiti dal sistema (creazione agenti e routing eventi).
- Endpoint dei servizi esterni dipendenti:
    - web-backend per persistenza/consultazione eventi e azioni
    - llm-gateway per decisioni assistite (escalation e coordinamento)

Variabili d'ambiente
--------------------
- MQTT_BROKER_HOST:
    Hostname del broker MQTT (default: "mqtt-broker" in rete Docker).
- MQTT_BROKER_PORT:
    Porta del broker MQTT (default: 1883).
- WEB_BACKEND_URL:
    Base URL del backend web per persistenza e API (default: "http://web-backend:8000").
- LLM_GATEWAY_URL:
    Base URL del gateway LLM (default: "http://llm-gateway:8000").

Note progettuali
----------------
- I valori di default sono coerenti con i nomi dei servizi definiti in docker-compose,
  facilitando l'esecuzione out-of-the-box.
- Il topic filter MQTT usa wildcard per ricevere eventi da qualunque distretto e tipo sensore.
"""

import os

# --- Configurazione MQTT -------------------------------------------------------
# Host del broker MQTT (nome servizio in Docker Compose oppure hostname reale).
MQTT_BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")

# Porta del broker MQTT (default standard MQTT: 1883).
MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))

# Topic filter MQTT per la sottoscrizione:
# "city/+/+" significa: tutti i distretti (1° '+') e tutti i tipi sensore (2° '+').
MQTT_TOPIC_FILTER: str = "city/+/+"

# --- Modellazione distretti ----------------------------------------------------
# Elenco dei distretti monitorati dal MAS: guida la creazione degli agenti locali.
DISTRICTS = ["quartiere1", "quartiere2"]

# --- Endpoint servizi esterni -------------------------------------------------
# Backend web responsabile di persistenza e API per dashboard/consultazione.
WEB_BACKEND_URL: str = os.getenv("WEB_BACKEND_URL", "http://web-backend:8000")

# Gateway LLM utilizzato per decisioni assistite (escalation, coordination planning).
LLM_GATEWAY_URL: str = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8000")
