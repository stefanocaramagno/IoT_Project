"""
Modulo di configurazione del servizio LLM Gateway.

Obiettivo
--------
Centralizzare la lettura e validazione della configurazione necessaria a contattare
il backend LLM (es. endpoint HTTP del modello, nome del modello, timeout).

Ruolo nel sistema
-----------------
Questo modulo definisce un modello di configurazione (Pydantic) e istanzia una
configurazione globale `settings`, caricata dalle variabili d'ambiente. In caso
di configurazione non valida, il servizio fallisce in avvio con errore esplicito,
evitando comportamenti indefiniti a runtime.

Variabili d'ambiente
--------------------
- LLM_API_BASE:
    Base URL dell'API del modello LLM (default: "http://host.docker.internal:11434").
    Viene validato come URL HTTP tramite AnyHttpUrl.
- LLM_MODEL_NAME:
    Nome del modello da utilizzare (default: "qwen2.5:0.5b").
- LLM_TIMEOUT_SECONDS:
    Timeout (in secondi) per le chiamate HTTP verso il modello (default: "60").

Note progettuali
----------------
- L'uso di Pydantic consente validazione robusta dei parametri (es. URL ben formato).
- Il fallback su valori di default garantisce che il servizio sia avviabile anche
  in assenza di variabili d'ambiente, mantenendo un comportamento prevedibile.
"""

from __future__ import annotations

import os
from pydantic import BaseModel, AnyHttpUrl, ValidationError


class LLMSettings(BaseModel):
    """
    Modello di configurazione per le chiamate al backend LLM.

    Attributi
    ---------
    api_base:
        Base URL dell'API LLM, validato come URL HTTP.
    model_name:
        Identificativo del modello LLM da utilizzare per le richieste.
    timeout_seconds:
        Timeout (secondi) per le richieste HTTP verso il servizio LLM.
    """

    api_base: AnyHttpUrl
    model_name: str
    timeout_seconds: float = 60.0

    @classmethod
    def from_env(cls) -> "LLMSettings":
        """
        Costruisce un'istanza di configurazione leggendo dalle variabili d'ambiente.

        La funzione applica valori di default in caso di variabili mancanti e
        gestisce in modo conservativo l'eventuale parsing del timeout, evitando
        di interrompere l'avvio del servizio per un formato non numerico.

        Returns:
            LLMSettings: Istanza popolata con i valori letti dall'ambiente.
        """
        # Base URL del backend LLM: default pensato per l'esecuzione in container
        # (host.docker.internal punta all'host dal punto di vista del container).
        api_base = os.getenv("LLM_API_BASE", "http://host.docker.internal:11434")

        # Nome del modello da utilizzare nel backend LLM.
        model_name = os.getenv("LLM_MODEL_NAME", "qwen2.5:0.5b")

        # Timeout espresso come stringa nell'ambiente; viene convertito in float.
        timeout_raw = os.getenv("LLM_TIMEOUT_SECONDS", "60")
        try:
            timeout_seconds = float(timeout_raw)
        except ValueError:
            # Fallback conservativo: in caso di valore non numerico, si usa il default.
            timeout_seconds = 60.0

        return cls(api_base=api_base, model_name=model_name, timeout_seconds=timeout_seconds)


# Istanza di configurazione globale.
# Viene creata all'import del modulo per rendere la configurazione disponibile
# agli altri componenti in modo immediato e consistente.
try:
    settings = LLMSettings.from_env()
except ValidationError as exc:
    # In caso di configurazione invalidabile (es. URL malformato), si preferisce
    # fallire subito in avvio: è un errore di configurazione, non recuperabile a runtime.
    raise RuntimeError(f"Errore nella configurazione LLM: {exc}")
