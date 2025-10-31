from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/menu", response_class=HTMLResponse)
def menu_page(request: Request):
    context = {
        "request": request,
        "active_page": "inicio",
        "page_title": "Dashboard operativo",
        "page_subtitle": "Visualiza el estado de los datos locales y ejecuta acciones clave del Automatismo DOT.",
    }
    return templates.TemplateResponse("menu.html", context)
