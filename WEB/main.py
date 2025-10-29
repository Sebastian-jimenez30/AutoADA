# autoada_web/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routes import importar_routes
import sys, os

# Añadir la carpeta del proyecto AutoADA al PYTHONPATH
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
AUTOADA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "AutoADA"))
if AUTOADA_DIR not in sys.path:
    sys.path.insert(0, AUTOADA_DIR)

app = FastAPI(title="AutoADA Web")

# Archivos estáticos y plantillas
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Incluir rutas
app.include_router(importar_routes.router)

# Ejecución manual (para desarrollo)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
