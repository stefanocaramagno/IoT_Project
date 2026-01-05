# Urban Monitoring Multi-Agent System

Questo repository contiene un sistema di **monitoraggio urbano** basato su un **Multi‑Agent System (MAS)**, con integrazione di sensori simulati via MQTT, un backend web per la persistenza e la visualizzazione dei dati, e un **LLM Gateway** che incapsula un modello linguistico per supportare le decisioni di escalation e il coordinamento tra quartieri.

Il documento è focalizzato sugli aspetti di **build & deploy**, ma fornisce anche una breve panoramica dell’architettura e della struttura della repository per facilitare l’onboarding e l’utilizzo del progetto.

## 1. Architettura ad alto livello

L’architettura è composta dai seguenti servizi, orchestrati tramite **Docker Compose**:

* **mqtt-broker**
  Broker MQTT basato su *Eclipse Mosquitto*, responsabile della ricezione dei messaggi pubblicati dai simulatori di sensori e della loro consegna al MAS.

* **sim-sensors**
  Servizio Python che simula sensori distribuiti su più quartieri. Pubblica periodicamente misure (ad esempio traffico e inquinamento) su topic MQTT del tipo `city/<district>/<sensor_type>`.

* **mas-core**
  Core del sistema multi‑agente.

  * Ascolta i topic MQTT e converte i messaggi in eventi strutturati.
  * Instrada gli eventi ai **DistrictMonitoringAgent** responsabili dei singoli quartieri.
  * Gestisce un **CityCoordinatorAgent** per le decisioni globali e il coordinamento multi‑quartiere.
  * Interagisce con:

    * il backend web per la persistenza di eventi e azioni;
    * il LLM Gateway per il supporto decisionale.

* **web-backend**
  Backend web basato su **FastAPI**, con:

  * persistenza su **SQLite** (`data/urban_monitoring.db`);
  * API per la registrazione e consultazione di **Event** e **Action**;
  * dashboard HTML/Jinja2 per la visualizzazione interattiva dello stato urbano e delle azioni intraprese.

* **llm-gateway**
  Micro‑servizio FastAPI che incapsula l’accesso a un **LLM Engine** esterno (ad es. *Ollama*), fornendo:

  * un endpoint per la **decisione di escalation** a livello di quartiere (`/llm/decide_escalation`);
  * un endpoint per la **pianificazione del coordinamento multi‑quartiere** (`/llm/plan_coordination`);
  * validazione e normalizzazione delle risposte del modello in formato JSON strutturato.

Il LLM Engine vero e proprio non è incluso nei container del progetto: viene raggiunto tramite HTTP all’URL configurato (default: `http://host.docker.internal:11434`).


## 2. Struttura della repository

Struttura logica della directory principale:

```text
.
├── docker-compose.yml        # Orchestrazione di tutti i servizi
├── README.md                 # Questo documento
├── docs/
│   ├── written_report.pdf    # Relazione tecnica
│   └── diagram_screenshots/  # Screenshot dei diagrammi (architettura, sequenza, ed ER)
├── data/
│   └── urban_monitoring.db   # Database SQLite (montato nel container web-backend)
├── mosquitto/
│   └── mosquitto.conf        # Configurazione del broker MQTT
├── sims/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # Simulatore di sensori MQTT
│       └── __init__.py
├── mas/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # Avvio del MAS e dei thread degli agenti
│       ├── agent.py          # DistrictMonitoringAgent, CityCoordinatorAgent, Message, SensorEvent
│       ├── mqtt_bridge.py    # Listener MQTT e adattatore verso il router interno
│       ├── router.py         # Router eventi/controllo verso gli agenti di quartiere
│       ├── persistence.py    # Client HTTP verso il backend per Event/Action
│       ├── llm_client.py     # Client HTTP verso il LLM Gateway
│       ├── config.py         # Parametri di configurazione (MQTT, backend, LLM)
│       └── __init__.py
├── web/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── app/
│       ├── main.py           # Applicazione FastAPI + dashboard HTML
│       ├── database.py       # Configurazione SQLAlchemy (SQLite)
│       ├── models.py         # Modelli ORM (Event, Action)
│       ├── schemas.py        # Schemi Pydantic per API REST
│       ├── static/           # File statici (CSS, JS)
│       └── templates/        # Template Jinja2 (dashboard e viste dati)
└── llm_gateway/
    ├── Dockerfile
    ├── requirements.txt
    └── app/
        ├── main.py           # API FastAPI per decide_escalation e plan_coordination
        ├── config.py         # Caricamento e validazione delle impostazioni LLM
        ├── llm_client.py     # Client verso il motore LLM esterno
        ├── schemas.py        # Schemi Pydantic per richieste e risposte LLM
        └── __init__.py
```

## 3. Prerequisiti

### 3.1 Software necessario (esecuzione con Docker)

Per eseguire l’intero stack tramite Docker Compose sono richiesti:

* **Git** (per clonare il repository);
* **Docker** (versione recente, ad es. ≥ 20.x);
* **Docker Compose** (plugin integrato in Docker Desktop oppure `docker compose` CLI).

Per l’esecuzione del modello LLM esterno, nella configurazione di default si assume:

* **Ollama** (o servizio equivalente) in ascolto su `http://localhost:11434`, con il modello:

  ```bash
  qwen2.5:0.5b
  ```

In caso non si utilizzi Ollama, è sufficiente predisporre un endpoint HTTP compatibile e aggiornare le variabili d’ambiente del LLM Gateway (vedi sezione 4.2).

---

### 3.2 Software necessario (esecuzione senza Docker)

Per l’esecuzione diretta dei servizi su host, senza Docker, sono richiesti:

* **Git** per clonare il repository;
* **Python 3.10+** con `pip` attivo;
* **Mosquitto** installato su host;
* un **LLM Engine** accessibile via HTTP. In configurazione di riferimento si assume:

  * **Ollama** in ascolto su `http://localhost:11434`;
  * modello `qwen2.5:0.5b`.

Le stesse indicazioni sul motore LLM valgono sia per l’esecuzione con Docker sia per l’esecuzione diretta.

---

### 3.3 Requisiti hardware indicativi

Il carico computazionale del sistema è contenuto; tuttavia, per un utilizzo fluido, si consiglia:

* almeno **4 GB di RAM** disponibili per i container Docker o per i processi Python;
* spazio su disco sufficiente per il database SQLite e per eventuali modelli LLM locali (nel caso di Ollama, alcuni GB a seconda del modello scelto).

## 4. Configurazione

### 4.1 Variabili d’ambiente principali

Le variabili chiave sono impostate in `docker-compose.yml` per l’esecuzione containerizzata e possono essere ridefinite tramite un file `.env` o variabili d’ambiente esterne. Le stesse variabili sono richieste anche in esecuzione senza Docker e vanno impostate a livello di shell.

**Servizi MAS e simulatori**

* `MQTT_BROKER_HOST`<br>
  Host del broker MQTT. <br>
  Default (Docker): `mqtt-broker`. <br>
  Default (senza Docker): `localhost`.

* `MQTT_BROKER_PORT` <br>
  Porta TCP del broker MQTT. Default: `1883`.

* `PUBLISH_INTERVAL_SECONDS` (solo `sim-sensors`) <br>
  Intervallo in secondi tra due pubblicazioni consecutive dei sensori. Default: `5`.

* `WEB_BACKEND_URL` (solo `mas-core`) <br>
  URL del backend web. <br>
  Default (Docker): `http://web-backend:8000`. <br>
  Default (senza Docker): `http://localhost:8000`.

* `LLM_GATEWAY_URL` (solo `mas-core`) <br>
  URL del LLM Gateway. <br>
  Default (Docker): `http://llm-gateway:8000`. <br>
  Default (senza Docker): `http://localhost:8001` (o porta configurata).

**Servizio LLM Gateway**

* `LLM_API_BASE` <br>
  Base URL del motore LLM esterno. <br>
  Default (Docker): `http://host.docker.internal:11434`. <br>
  Default (senza Docker): `http://localhost:11434`.

* `LLM_MODEL_NAME` <br>
  Nome del modello LLM da utilizzare. Default: `qwen2.5:0.5b`. 

* `LLM_TIMEOUT_SECONDS` <br>
  Timeout in secondi per le chiamate al LLM Engine. Default: `60`.

---

### 4.2 Configurazione del LLM Engine (Ollama o equivalenti)

Con la configurazione di default il LLM Gateway si aspetta:

* un servizio LLM raggiungibile da host su `http://localhost:11434`;
* lo stesso servizio raggiungibile dai container su `http://host.docker.internal:11434`.

Esempio con **Ollama**:

1. Installare Ollama sulla macchina host.

2. Scaricare il modello di riferimento:

   ```bash
   ollama pull qwen2.5:0.5b
   ```

3. Avviare il server Ollama (se non già in esecuzione):

   ```bash
   ollama serve
   ```

4. Verificare che la chiamata HTTP da host:

   ```bash
   curl http://localhost:11434/api/tags
   ```

   restituisca l’elenco dei modelli disponibili.

Se si desidera utilizzare un endpoint diverso (ad esempio un LLM remoto), è necessario aggiornare le variabili d’ambiente del LLM Gateway.

**Esempio in Docker (`docker-compose.yml`):**

```yaml
environment:
  - LLM_API_BASE=http://<nuovo-endpoint>
  - LLM_MODEL_NAME=<nome-modello>
  - LLM_TIMEOUT_SECONDS=60
```

**Esempio in esecuzione senza Docker (Linux/macOS, Bash):**

```bash
export LLM_API_BASE=http://<nuovo-endpoint>
export LLM_MODEL_NAME=<nome-modello>
export LLM_TIMEOUT_SECONDS=60
```

**Esempio in esecuzione senza Docker (Windows, PowerShell):**

```powershell
$env:LLM_API_BASE="http://<nuovo-endpoint>"
$env:LLM_MODEL_NAME="<nome-modello>"
$env:LLM_TIMEOUT_SECONDS="60"
```

## 5. Database, persistenza e broker MQTT

### 5.1 Database SQLite

Il backend web utilizza un database **SQLite** collocato in:

```text
./data/urban_monitoring.db
```

Nel container `web-backend` il database è montato come volume in `/app/data`, con URL:

```python
SQLALCHEMY_DATABASE_URL = "sqlite:///./data/urban_monitoring.db"
```

Il file `urban_monitoring.db` viene creato e popolato automaticamente alla prima esecuzione del backend. È possibile:

* effettuare un backup del database copiando il file nella directory `data/`;
* eliminare il file per ripartire da uno stato "pulito" (si perderanno però tutti gli eventi e le azioni registrate).

---

### 5.2 Broker MQTT (Eclipse Mosquitto)

Il servizio `mqtt-broker` utilizza l’immagine ufficiale **eclipse-mosquitto:2** e carica la configurazione da:

```text
./mosquitto/mosquitto.conf
```

Nel file di configurazione è possibile regolare, ad esempio:

* politiche di autenticazione e ACL;
* livelli di log;
* impostazioni di persistenza del broker.

Nell’esecuzione con Docker, le directory di dati e log sono montate su volumi Docker (`mosquitto_data`, `mosquitto_log`) per preservare lo stato tra esecuzioni successive. Nell’esecuzione senza Docker, è possibile riutilizzare lo stesso file di configurazione avviando Mosquitto direttamente su host.

## 6. Build & Deploy con Docker Compose

### 6.1 Clonare la repository

```bash
git clone <URL_REPOSITORY> urban-mas-iot-llm
cd urban-mas-iot-llm
```

Assicurarsi che nella root sia presente il file `docker-compose.yml`.

---

### 6.2 Avvio completo dello stack (con Docker)

Con il motore LLM già in esecuzione sull’host (vedi sezione 4.2), è possibile avviare l’intero sistema con:

```bash
docker compose up --build
```

L’opzione `--build` forza la ricostruzione delle immagini Docker per `sim-sensors`, `mas-core`, `web-backend` e `llm-gateway` sulla base dei rispettivi `Dockerfile` e `requirements.txt`.

Il comando avvia i seguenti container:

* `mqtt-broker`
* `web-backend` (porta host: `8000`)
* `mas-core`
* `sim-sensors`
* `llm-gateway` (porta host: `8100`)

---

### 6.3 Accesso alla dashboard e verifica rapida (con Docker)

Una volta che i container sono in esecuzione:

* Aprire il browser su:

  ```text
  http://localhost:8000
  ```

* La dashboard del backend web dovrebbe mostrare:

  * gli eventi generati dai simulatori;
  * eventuali azioni di escalation e coordinamento;
  * indicatori sintetici dello stato urbano.

Per verificare lo stato dei container:

```bash
docker compose ps
```

Per ispezionare i log del MAS:

```bash
docker compose logs mas-core
```

Per verificare che il LLM Gateway sia raggiungibile:

```bash
curl http://localhost:8100/docs
```

Dovrebbe essere visualizzata la documentazione interattiva OpenAPI esposta da FastAPI.

---

### 6.4 Arresto dei servizi (con Docker)

Per arrestare tutti i container mantenendo i volumi (incluso il database):

```bash
docker compose down
```

Per arrestare i container e rimuovere anche i volumi (inclusi database e dati Mosquitto):

```bash
docker compose down -v
```

**Attenzione:** l’opzione `-v` elimina definitivamente i dati persistenti.

## 7. Esecuzione dei componenti senza Docker (opzionale)

L’esecuzione senza Docker è pensata per scenari di sviluppo o debug. In questo caso tutti i servizi vengono eseguiti come processi Python (più Mosquitto su host).

### 7.1 Clonare la repository

Anche per l’esecuzione senza Docker il primo passo consiste nel clonare il repository:

```bash
git clone <URL_REPOSITORY> urban-mas-iot-llm
cd urban-mas-iot-llm
```

---

### 7.2 Creazione di un ambiente virtuale Python

```bash
python -m venv .venv
source .venv/bin/activate   # su Windows (PowerShell): .venv\\Scripts\\Activate.ps1
```

Installare i requisiti dei singoli servizi:

```bash
pip install -r sims/requirements.txt
pip install -r mas/requirements.txt
pip install -r web/requirements.txt
pip install -r llm_gateway/requirements.txt
```

---

### 7.3 Avvio del broker MQTT su host

Installare Mosquitto su host e avviarlo con la configurazione fornita:

```bash
mosquitto -c mosquitto/mosquitto.conf
```

Verificare che sia in ascolto sulla porta `1883` su `localhost`.

---

### 7.4 Impostazione delle variabili d’ambiente (senza Docker)

Prima di avviare i servizi Python è necessario impostare **tutte** le variabili d’ambiente utilizzate dal sistema, descritte in sezione 4.1.

**Esempio (Linux/macOS, Bash):**

```bash
export MQTT_BROKER_HOST=localhost
export MQTT_BROKER_PORT=1883
export PUBLISH_INTERVAL_SECONDS=5

export WEB_BACKEND_URL=http://localhost:8000
export LLM_GATEWAY_URL=http://localhost:8001

export LLM_API_BASE=http://localhost:11434
export LLM_MODEL_NAME=qwen2.5:0.5b
export LLM_TIMEOUT_SECONDS=60
```

**Esempio (Windows, PowerShell):**

```powershell
$env:MQTT_BROKER_HOST="localhost"
$env:MQTT_BROKER_PORT="1883"
$env:PUBLISH_INTERVAL_SECONDS="5"

$env:WEB_BACKEND_URL="http://localhost:8000"
$env:LLM_GATEWAY_URL="http://localhost:8001"

$env:LLM_API_BASE="http://localhost:11434"
$env:LLM_MODEL_NAME="qwen2.5:0.5b"
$env:LLM_TIMEOUT_SECONDS="60"
```

Le variabili devono essere impostate nei terminali dai quali verranno avviati `web-backend`, `llm-gateway`, `mas-core` e `sim-sensors`.

---

### 7.5 Avvio dei servizi applicativi su host

In quattro terminali separati, dopo aver attivato l’ambiente virtuale e impostato le variabili d’ambiente:

* **Backend web**

  ```bash
  cd web
  uvicorn app.main:app --host 0.0.0.0 --port 8000
  ```

* **LLM Gateway**

  ```bash
  cd llm_gateway
  uvicorn app.main:app --host 0.0.0.0 --port 8001
  ```

* **MAS core**

  ```bash
  cd mas
  python -m app.main
  ```

* **Simulatori di sensori**

  ```bash
  cd sims
  python -m app.main
  ```

La dashboard sarà accessibile da browser all’indirizzo:

```text
http://localhost:8000
```

## 8. Verifica degli scenari principali

Per testare il comportamento del sistema è possibile osservare gli scenari chiave direttamente dalla dashboard e dai log, sia in esecuzione con Docker sia in esecuzione diretta su host.

* **Scenario non critico**

  * I valori simulati restano sotto le soglie; il MAS registra gli eventi ma non genera escalation né azioni di coordinamento.
  * La dashboard mostra un flusso di eventi regolare, con severità bassa o moderata.

* **Scenario critico con LLM attivo**

  * Valori oltre soglia producono eventi critici.
  * I DistrictMonitoringAgent possono interrogare il LLM tramite il LLM Gateway per affinare la severità e decidere l’escalation.
  * Il CityCoordinatorAgent può richiedere un piano di coordinamento multi‑quartiere a `/llm/plan_coordination`, generando una o più azioni registrate in `actions`.

* **Scenario di fallimento LLM con fallback**

  * Arrestando il motore LLM o alterando `LLM_API_BASE`, le chiamate al LLM falliscono.
  * Il MAS attiva le politiche di fallback:

    * decisioni basate su soglie e regole deterministiche;
    * motivazioni esplicite nel campo `reason` delle azioni, che evidenziano l’uso di fallback.

## 9. Comandi utili (esecuzione con Docker)

Questa sezione riporta alcuni comandi ricorrenti **esclusivamente per la gestione dello stack tramite Docker Compose**.

```bash
# Ricostruire e avviare tutti i servizi
docker compose up --build

# Vedere i log in tempo reale del MAS
docker compose logs -f mas-core

# Vedere i log del LLM Gateway
docker compose logs -f llm-gateway

# Controllare lo stato dei container 
docker compose ps

# Arrestare lo stack mantenendo i dati
docker compose down

# Arrestare lo stack eliminando volumi e dati
docker compose down -v
```

Questo README fornisce le informazioni essenziali per il **build & deploy** del sistema, sia in modalità containerizzata sia in esecuzione diretta su host, insieme alle indicazioni operative per la verifica del corretto funzionamento dei servizi e degli scenari principali.