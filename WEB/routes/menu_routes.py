from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from controllers import menu_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/menu", response_class=HTMLResponse)
def menu_page(request: Request):
    context = {
        "request": request,
        "active_page": "menu",
        "active_section": "menu",
        "page_title": "Dashboard operativo",
        "page_subtitle": "Visualiza el estado de los datos locales y ejecuta acciones clave del Automatismo DOT.",
        "empresas": menu_controller.get_empresas(),
        "dominio": "CC",
    }
    return templates.TemplateResponse("menu.html", context)


@router.get("/menu/status")
def menu_status():
    try:
        data = menu_controller.get_status()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return JSONResponse(data)


@router.post("/menu/actualizar")
def menu_actualizar():
    generator = menu_controller.actualizar_datos_pipeline()
    return StreamingResponse(generator, media_type="text/plain; charset=utf-8")
