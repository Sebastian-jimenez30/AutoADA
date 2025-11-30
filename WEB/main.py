import os
import sys
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import RedirectResponse

# ============================================================
# CONFIGURACIÓN DE RUTAS BASE
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Añadir la carpeta de AutoADA si se necesita
AUTOADA_DIR = os.path.abspath(os.path.join(BASE_DIR, "..", "AutoADA"))
if AUTOADA_DIR not in sys.path:
    sys.path.insert(0, AUTOADA_DIR)

# --- Importa tus rutas ---
from routes import login_routes, importar_routes, convertir_routes, menu_routes, buscar_routes, hsh_routes, jobs_routes

# ============================================================
# CREACIÓN DE LA APP
# ============================================================

app = FastAPI(title="AutoADA Web", version="1.0.0")

# --- MONTAR ESTÁTICOS ANTES DE CREAR templates ---
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# --- PLANTILLAS ---
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# ============================================================
# INCLUSIÓN DE RUTAS
# ============================================================

app.include_router(login_routes.router)
app.include_router(importar_routes.router)
app.include_router(convertir_routes.router)
app.include_router(buscar_routes.router)
app.include_router(menu_routes.router)
app.include_router(hsh_routes.router)
app.include_router(jobs_routes.router)

# ============================================================
# RUTA RAÍZ
# ============================================================

@app.get("/")
def root():
    """Redirige al login por defecto."""
    return RedirectResponse(url="/login")

# ============================================================
# EJECUCIÓN LOCAL
# ============================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info",
    )
