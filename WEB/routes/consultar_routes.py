from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from controllers import consultar_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/consultar/rtu", response_class=HTMLResponse, name="consultar_rtu_page")
def consultar_rtu_page(request: Request):
    context = {
        "request": request,
        "active_section": "consultar",
        "active_page": "consultar_rtu",
        "page_title": "Consultar RTU/SAS",
        "page_subtitle": "Selecciona RTU/SAS y genera el reporte desde SCADA.",
        "empresas": consultar_controller.get_empresas(),
    }
    return templates.TemplateResponse("consultar_rtu.html", context)


@router.get("/consultar/rtu/list")
def listar_rtus(empresa: str, search: str | None = None, limit: int = Query(500, ge=1, le=5000)):
    if not empresa:
        raise HTTPException(status_code=400, detail="Empresa requerida.")
    data = consultar_controller.load_rtus(empresa=empresa, search=search, limit=limit)
    return data


@router.post("/consultar/rtu/actualizar")
def actualizar_rtu_dataset(empresa: str):
    if not empresa:
        raise HTTPException(status_code=400, detail="Empresa requerida.")

    def _pipeline():
        yield from consultar_controller.actualizar_rtu_dataset(empresa)

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.post("/consultar/rtu/run")
def ejecutar_consultar_rtu(empresa: str, rtus: list[str]):
    if not empresa or not rtus:
        raise HTTPException(status_code=400, detail="Empresa y RTUs son requeridas.")

    def _pipeline():
        yield from consultar_controller.consultar_rtu_pipeline(empresa, rtus)

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/consultar/rtu/result/download")
def descargar_consultar_rtu_result(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(consultar_controller.AUTOADA_DIR).joinpath(file_path).resolve()
    resolved = file_path.resolve()
    allowed_root = Path(consultar_controller.AUTOADA_DIR).resolve()
    try:
        resolved.relative_to(allowed_root)
    except ValueError:
        raise HTTPException(status_code=403, detail="Ruta no permitida.")
    if not resolved.exists() or not resolved.is_file():
        raise HTTPException(status_code=404, detail="Archivo no encontrado.")
    return FileResponse(
        str(resolved),
        filename=resolved.name,
        media_type="application/octet-stream",
    )
