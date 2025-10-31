from __future__ import annotations

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from controllers import buscar_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/buscar/key", response_class=HTMLResponse, name="buscar_key_page")
def buscar_key_page(request: Request):
    context = {
        "request": request,
        "active_section": "buscar",
        "active_page": "buscar_key",
        "page_title": "Buscar Key",
        "page_subtitle": "Localiza claves en los datasets recientes y genera el reporte Find_Key.xlsx.",
        "empresas": list(buscar_controller.get_empresas()),
        "dominios": list(buscar_controller.get_dominios()),
    }
    return templates.TemplateResponse("buscar_key.html", context)


@router.post("/buscar/key/run")
def ejecutar_buscar_key(
    request: Request,
    empresa: str = Form(...),
    dominio: str = Form(...),
    keys: str = Form(...),
    actualizar: str | None = Form(None),
):
    force_refresh = bool(actualizar)
    generator = buscar_controller.buscar_key_pipeline(empresa, dominio, keys, force_refresh)
    return StreamingResponse(generator, media_type="text/plain; charset=utf-8")
