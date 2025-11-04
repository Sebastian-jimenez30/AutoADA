from __future__ import annotations

import os

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
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


@router.get("/buscar/key/result/data")
def obtener_resultado_buscar_key():
    data = buscar_controller.load_result_preview()
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    # Sanitizar ruta antes de exponerla
    data["path"] = os.path.basename(data.get("path") or "")
    data["download_url"] = "/buscar/key/result/download"
    return data


@router.get("/buscar/key/result/download")
def descargar_resultado_buscar_key():
    path = buscar_controller.get_result_path()
    if not path:
        raise HTTPException(status_code=404, detail="No hay archivo disponible.")
    filename = os.path.basename(path)
    return FileResponse(path, filename=filename, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
