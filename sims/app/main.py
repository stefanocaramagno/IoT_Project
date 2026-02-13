"""
Simulatore di sensori MQTT per il progetto "Urban Monitoring Multi-Agent System".

Obiettivo
---------
Generare eventi sensoriali sintetici (es. traffico e inquinamento) e pubblicarli
periodicamente su un broker MQTT, in modo da:
- alimentare il Multi-Agent System (MAS) con dati realistici e continui;
- testare end-to-end il flusso: simulatori -> broker -> listener/router -> agenti -> persistenza/LLM.

Ruolo nel sistema
-----------------
Questo script agisce come producer di messaggi MQTT:
- pubblica su topic del formato: "city/<district>/<sensor_type>"
- invia payload JSON con campi standardizzati (district, type, value, unit, severity, timestamp)

Variabili d'ambiente
---------------------------------------
- MQTT_BROKER_HOST:
    Hostname/IP del broker MQTT (default: "localhost").
- MQTT_BROKER_PORT:
    Porta del broker MQTT (default: 1883).
- PUBLISH_INTERVAL_SECONDS:
    Intervallo tra i cicli di pubblicazione (default: 5 secondi).

Note progettuali
----------------
- Il simulatore usa valori random per riprodurre condizioni dinamiche.
- La severità è derivata deterministicamente dal valore numerico e dal tipo di sensore,
  così da produrre eventi low/medium/high utili per testare:
    - regole deterministiche di escalation,
    - decisioni assistite dal gateway LLM (per medium/high).
- I timestamp sono emessi in formato ISO 8601 in UTC per coerenza e correlazione temporale.
"""

import os
import time
import json
import random
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

# --- Configurazione runtime (env + default) -----------------------------------
# Host e porta del broker MQTT: in Docker Compose spesso è il nome del servizio (es. "mqtt-broker").
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))

# Intervallo (secondi) tra i cicli di pubblicazione (tutti i distretti e sensori).
PUBLISH_INTERVAL_SECONDS = float(os.getenv("PUBLISH_INTERVAL_SECONDS", "5"))

# Distretti e tipologie sensore simulate: devono essere coerenti con la configurazione del MAS.
DISTRICTS = ["quartiere1", "quartiere2"]
SENSOR_TYPES = ["traffic", "pollution"]


def classify_severity(sensor_type: str, value: float) -> str:
    """
    Classifica la severità (low/medium/high) in modo deterministico.

    Motivazione
    -----------
    Assegnare una severità derivata dal valore consente di:
    - generare eventi etichettati coerentemente (utile per test funzionali),
    - controllare indirettamente la frequenza di eventi critici o medi.

    Args:
        sensor_type: Tipo di sensore ("traffic" o "pollution").
        value: Valore misurato/simulato.

    Returns:
        str: "low", "medium", "high" oppure "unknown" se il tipo non è riconosciuto.
    """
    if sensor_type == "traffic":
        # Soglie scelte per simulare: traffico basso <40, medio 40-99, alto >=100 (unità: veh/min).
        if value < 40:
            return "low"
        elif value < 100:
            return "medium"
        else:
            return "high"
    elif sensor_type == "pollution":
        # Soglie scelte per simulare: inquinamento basso <50, medio 50-99, alto >=100 (unità: µg/m3).
        if value < 50:
            return "low"
        elif value < 100:
            return "medium"
        else:
            return "high"
    return "unknown"


def build_payload(district: str, sensor_type: str) -> dict:
    """
    Costruisce il payload JSON da pubblicare per una coppia (distretto, tipo sensore).

    Flusso
    ------
    - Genera un valore random in un range plausibile per il tipo sensore.
    - Imposta l'unità di misura coerente.
    - Determina la severità con classify_severity().
    - Genera timestamp ISO 8601 in UTC.

    Args:
        district: Nome del distretto sorgente.
        sensor_type: Tipo di sensore (es. "traffic", "pollution").

    Returns:
        dict: Payload conforme allo schema atteso dal MAS (router/agent).
    """
    if sensor_type == "traffic":
        # Traffico simulato come intero (es. veicoli/minuto) con range ampio per produrre anche "high".
        value = random.randint(0, 160)
        unit = "veh/min"
    elif sensor_type == "pollution":
        # Inquinamento simulato come float con una cifra decimale.
        value = round(random.uniform(10, 180), 1)
        unit = "µg/m3"
    else:
        # Caso non previsto: payload comunque costruito con valori safe.
        value = 0
        unit = "unknown"

    severity = classify_severity(sensor_type, value)
    now = datetime.now(timezone.utc).isoformat()

    # Nota: il campo "type" è usato dal MAS per mappare sensor_type (compatibile con SensorEvent.from_raw()).
    return {
        "district": district,
        "type": sensor_type,
        "value": value,
        "unit": unit,
        "severity": severity,
        "timestamp": now,
    }


def main():
    """
    Avvio del simulatore e pubblicazione ciclica dei messaggi MQTT.

    Flusso
    ------
    - Crea un client MQTT con client_id casuale (riduce collisioni tra più simulatori).
    - Connette al broker e avvia il loop MQTT (thread interno paho-mqtt).
    - In loop infinito:
        - per ogni distretto e sensore: pubblica su topic city/<district>/<sensor_type>
        - attende PUBLISH_INTERVAL_SECONDS
    - Gestisce KeyboardInterrupt per terminazione pulita.
    """
    # Client ID casuale: utile per esecuzioni parallele senza conflitti.
    client_id = f"sim-sensors-{random.randint(0, 9999)}"
    client = mqtt.Client(client_id=client_id, clean_session=True)

    print(f"[sim-sensors] Connessione al broker MQTT {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} ...")
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()

    try:
        while True:
            for district in DISTRICTS:
                for sensor_type in SENSOR_TYPES:
                    # Topic standard del progetto: city/<district>/<sensor_type>
                    topic = f"city/{district}/{sensor_type}"
                    payload = build_payload(district, sensor_type)

                    # Serializzazione JSON del payload: formato atteso dal listener del MAS.
                    payload_str = json.dumps(payload)

                    # Pubblicazione QoS 0 (fire-and-forget), adeguata per un simulatore e test.
                    result = client.publish(topic, payload_str, qos=0)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        print(f"[sim-sensors] Pubblicato su {topic}: {payload_str}")
                    else:
                        print(f"[sim-sensors] ERRORE pubblicazione su {topic}: rc={result.rc}")

            time.sleep(PUBLISH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("[sim-sensors] Terminazione richiesta, chiusura client MQTT...")
    finally:
        # Chiusura pulita del loop e disconnessione dal broker.
        client.loop_stop()
        client.disconnect()
        print("[sim-sensors] Disconnesso dal broker.")


if __name__ == "__main__":
    # Esecuzione standalone (python sims/app/main.py o via container).
    main()
