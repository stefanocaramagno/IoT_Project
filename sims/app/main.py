import os
import time
import json
import random
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
PUBLISH_INTERVAL_SECONDS = float(os.getenv("PUBLISH_INTERVAL_SECONDS", "5"))

DISTRICTS = ["quartiere1", "quartiere2"]
SENSOR_TYPES = ["traffic", "pollution"]


def classify_severity(sensor_type: str, value: float) -> str:
    if sensor_type == "traffic":
        # valore indicativo: veicoli/minuto su un asse principale
        if value < 40:
            return "low"
        elif value < 100:
            return "medium"
        else:
            return "high"
    elif sensor_type == "pollution":
        # valore indicativo: µg/m3 di PM2.5
        if value < 50:
            return "low"
        elif value < 100:
            return "medium"
        else:
            return "high"
    return "unknown"


def build_payload(district: str, sensor_type: str) -> dict:
    if sensor_type == "traffic":
        value = random.randint(0, 160)  # veicoli/minuto
        unit = "veh/min"
    elif sensor_type == "pollution":
        value = round(random.uniform(10, 180), 1)  # µg/m3
        unit = "µg/m3"
    else:
        value = 0
        unit = "unknown"

    severity = classify_severity(sensor_type, value)
    now = datetime.now(timezone.utc).isoformat()

    return {
        "district": district,
        "type": sensor_type,
        "value": value,
        "unit": unit,
        "severity": severity,
        "timestamp": now,
    }


def main():
    client_id = f"sim-sensors-{random.randint(0, 9999)}"
    client = mqtt.Client(client_id=client_id, clean_session=True)

    print(f"[sim-sensors] Connessione al broker MQTT {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT} ...")
    client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, keepalive=60)
    client.loop_start()

    try:
        while True:
            for district in DISTRICTS:
                for sensor_type in SENSOR_TYPES:
                    topic = f"city/{district}/{sensor_type}"
                    payload = build_payload(district, sensor_type)
                    payload_str = json.dumps(payload)
                    result = client.publish(topic, payload_str, qos=0)
                    if result.rc == mqtt.MQTT_ERR_SUCCESS:
                        print(f"[sim-sensors] Pubblicato su {topic}: {payload_str}")
                    else:
                        print(f"[sim-sensors] ERRORE pubblicazione su {topic}: rc={result.rc}")
            time.sleep(PUBLISH_INTERVAL_SECONDS)
    except KeyboardInterrupt:
        print("[sim-sensors] Terminazione richiesta, chiusura client MQTT...")
    finally:
        client.loop_stop()
        client.disconnect()
        print("[sim-sensors] Disconnesso dal broker.")


if __name__ == "__main__":
    main()
