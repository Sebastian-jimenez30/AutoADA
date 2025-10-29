# autoada_web/main.py
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from routes import login_routes, importar_routes, convertir_routes, menu_routes
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
app.include_router(menu_routes.router)
app.include_router(login_routes.router)
app.include_router(importar_routes.router)
app.include_router(convertir_routes.router)

from fastapi.responses import RedirectResponse

@app.get("/")
def root():
    return RedirectResponse(url="/login")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
