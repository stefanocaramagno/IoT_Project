from __future__ import annotations

import os
from pydantic import BaseModel, AnyHttpUrl, ValidationError


class LLMSettings(BaseModel):
    api_base: AnyHttpUrl
    model_name: str
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "LLMSettings":
        api_base = os.getenv("LLM_API_BASE", "http://host.docker.internal:11434")
        model_name = os.getenv("LLM_MODEL_NAME", "qwen2.5:0.5b")
        timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "60")
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            timeout_seconds = 60.0

        return cls(api_base=api_base, model_name=model_name, timeout_seconds=timeout_seconds)

try:
    settings = LLMSettings.from_env()
except ValidationError as exc:
    raise RuntimeError(f"Errore nella configurazione LLM: {exc}")
