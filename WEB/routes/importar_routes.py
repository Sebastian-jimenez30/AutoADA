# autoada_web/routes/importar_routes.py
from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from controllers import importar_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")

@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse("importar.html", {"request": request})

@router.post("/importar", response_class=HTMLResponse)
def ejecutar_importacion(request: Request, empresa: str = Form(...)):
    # Llama al controlador (logica backend)
    result = importar_controller.ejecutar_importar(empresa)
    return templates.TemplateResponse(
        "importar.html",
        {"request": request, "empresa": empresa, "result": result},
    )
