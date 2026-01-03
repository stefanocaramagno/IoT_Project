from fastapi import FastAPI
from fastapi.responses import HTMLResponse

app = FastAPI(title="Urban Monitoring MAS - Web Backend")

@app.get("/", response_class=HTMLResponse)
async def root():
    return '''
    <html>
      <head>
        <title>Urban Monitoring MAS</title>
      </head>
      <body>
        <h1>Urban Monitoring MAS - Web Backend è in esecuzione</h1>
        <p>Fase 2: il MAS ha un primo agente che ascolta MQTT e logga gli eventi.</p>
      </body>
    </html>
    '''
