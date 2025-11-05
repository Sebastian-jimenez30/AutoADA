from __future__ import annotations

import os

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
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


@router.get("/buscar/keys", response_class=HTMLResponse, name="buscar_keys_page")
def buscar_keys_page(request: Request):
    context = {
        "request": request,
        "active_section": "buscar",
        "active_page": "buscar_keys",
        "page_title": "Buscar Keys",
        "page_subtitle": "Procesa un archivo Excel con múltiples keys y genera el reporte Find_Key.xlsx.",
        "empresas": list(buscar_controller.get_empresas()),
        "dominios": list(buscar_controller.get_dominios()),
    }
    return templates.TemplateResponse("buscar_keys.html", context)


@router.post("/buscar/keys/run")
def ejecutar_buscar_keys(
    request: Request,
    empresa: str = Form(...),
    dominio: str = Form(...),
    actualizar: str | None = Form(None),
    archivo: UploadFile = File(...),
):
    if not archivo or not archivo.filename:
        raise HTTPException(status_code=400, detail="Debes subir un archivo Excel válido.")

    extension = Path(archivo.filename).suffix.lower()
    if extension not in {".xlsx", ".xlsm", ".xls"}:
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx, .xlsm, .xls).")

    os.makedirs(buscar_controller.RESULT_DIR, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=extension, dir=buscar_controller.RESULT_DIR
        ) as tmp_file:
            archivo.file.seek(0)
            shutil.copyfileobj(archivo.file, tmp_file)
            tmp_path = tmp_file.name
    finally:
        try:
            archivo.file.close()
        except Exception:
            pass

    if not tmp_path or not os.path.exists(tmp_path):
        raise HTTPException(status_code=500, detail="No fue posible almacenar el archivo para su procesamiento.")

    force_refresh = bool(actualizar)
    archivo_nombre = archivo.filename

    def _pipeline_with_cleanup():
        try:
            yield from buscar_controller.buscar_keys_pipeline(
                empresa, dominio, tmp_path, archivo_nombre, force_refresh
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline_with_cleanup(), media_type="text/plain; charset=utf-8")


@router.get("/buscar/key/result/data")
def obtener_resultado_buscar_key(sheet: str | None = Query(None)):
    data = buscar_controller.load_result_preview(sheet=sheet)
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
