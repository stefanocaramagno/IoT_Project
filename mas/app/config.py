import os

MQTT_BROKER_HOST: str = os.getenv("MQTT_BROKER_HOST", "mqtt-broker")
MQTT_BROKER_PORT: int = int(os.getenv("MQTT_BROKER_PORT", "1883"))

MQTT_TOPIC_FILTER: str = "city/+/+"

DISTRICTS = ["quartiere1", "quartiere2"]

WEB_BACKEND_URL: str = os.getenv("WEB_BACKEND_URL", "http://web-backend:8000")
LLM_GATEWAY_URL: str = os.getenv("LLM_GATEWAY_URL", "http://llm-gateway:8000")
