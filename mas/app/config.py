import os

MQTT_BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))

# Sottoscrizione a tutti i sensori di tutti i quartieri: city/<district>/<type>
MQTT_TOPIC_FILTER: str = "city/+/+"

# Quartieri noti (devono essere coerenti con il simulatore)
DISTRICTS = ["quartiere1", "quartiere2"]
