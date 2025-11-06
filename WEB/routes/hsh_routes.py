from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from controllers import hsh_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/hsh/crear", response_class=HTMLResponse, name="hsh_crear_page")
def hsh_crear_page(request: Request):
    context = {
        "request": request,
        "active_section": "hsh",
        "active_page": "hsh_crear_tag",
        "page_title": "HSH - Crear Tag",
        "page_subtitle": "Valida e inserta nuevos tags HSH a partir de un archivo Excel.",
        "empresas": list(hsh_controller.get_empresas()),
        "dominios": list(hsh_controller.get_dominios()),
    }
    return templates.TemplateResponse("hsh_crear.html", context)


@router.post("/hsh/crear/run")
def ejecutar_hsh_crear(
    request: Request,
    empresa: str = Form(...),
    dominio: str = Form(...),
    aplicar: str | None = Form(None),
    actualizar: str | None = Form(None),
    archivo: UploadFile = File(...),
):
    if not archivo or not archivo.filename:
        raise HTTPException(status_code=400, detail="Debes subir un archivo Excel válido.")

    extension = Path(archivo.filename).suffix.lower()
    if extension not in {".xlsx", ".xlsm", ".xls"}:
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx, .xlsm, .xls).")

    os.makedirs(hsh_controller.HSH_OUTPUT_DIR, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension, dir=hsh_controller.HSH_OUTPUT_DIR) as tmp_file:
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

    aplicar_flag = aplicar is not None and aplicar != ""
    force_refresh = True
    archivo_nombre = archivo.filename

    def _pipeline():
        try:
            yield from hsh_controller.crear_tags_pipeline(
                empresa=empresa,
                dominio=dominio,
                archivo_path=tmp_path,
                archivo_nombre=archivo_nombre,
                aplicar=aplicar_flag,
                forzar_actualizacion=force_refresh,
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/hsh/crear/result")
def obtener_hsh_crear_result(
    sheet: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    data = hsh_controller.load_crear_result_preview(sheet=sheet, limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/hsh/crear/result/download")
def descargar_hsh_crear_result(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(hsh_controller.AUTOADA_DIR).joinpath(file_path).resolve()
    resolved = file_path.resolve()
    allowed_root = Path(hsh_controller.AUTOADA_DIR).resolve()
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
