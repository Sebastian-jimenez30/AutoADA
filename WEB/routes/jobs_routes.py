from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from controllers import jobs_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/jobs/crear", response_class=HTMLResponse, name="jobs_crear_page")
def jobs_crear_page(request: Request):
    context = {
        "request": request,
        "active_section": "jobs",
        "active_page": "jobs_crear",
        "page_title": "Jobs - Crear señales",
        "page_subtitle": "Valida y genera las cargas SCADA para nuevas señales a partir de un Excel.",
        "empresas": list(jobs_controller.get_empresas()),
    }
    return templates.TemplateResponse("jobs_crear.html", context)


@router.get("/jobs/eliminar", response_class=HTMLResponse, name="jobs_eliminar_page")
def jobs_eliminar_page(request: Request):
    context = {
        "request": request,
        "active_section": "jobs",
        "active_page": "jobs_eliminar",
        "page_title": "Jobs - Eliminar señales",
        "page_subtitle": "Valida y genera archivos de eliminación SCADA a partir de un Excel.",
        "empresas": list(jobs_controller.get_empresas()),
    }
    return templates.TemplateResponse("jobs_eliminar.html", context)


@router.get("/jobs/cambiar-nombre", response_class=HTMLResponse, name="jobs_cambiar_nombre_page")
def jobs_cambiar_nombre_page(request: Request):
    context = {
        "request": request,
        "active_section": "jobs",
        "active_page": "jobs_cambiar_nombre",
        "page_title": "Jobs - Cambiar nombre",
        "page_subtitle": "Aplica cambios de nombre en SCADA a partir de un Excel.",
        "empresas": list(jobs_controller.get_empresas()),
    }
    return templates.TemplateResponse("jobs_cambiar_nombre.html", context)


@router.post("/jobs/crear/run")
def ejecutar_jobs_crear(
    request: Request,
    empresa: str = Form(...),
    actualizar: str | None = Form(None),
    archivo: UploadFile = File(...),
):
    if not archivo or not archivo.filename:
        raise HTTPException(status_code=400, detail="Debes subir un archivo Excel válido.")

    extension = Path(archivo.filename).suffix.lower()
    if extension not in {".xlsx", ".xlsm", ".xls"}:
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx, .xlsm, .xls).")

    os.makedirs(jobs_controller.JOBS_UPLOAD_DIR, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension, dir=jobs_controller.JOBS_UPLOAD_DIR) as tmp_file:
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

    actualizar_flag = bool(actualizar)
    archivo_nombre = archivo.filename

    def _pipeline():
        try:
            yield from jobs_controller.crear_senales_pipeline(
                empresa=empresa,
                actualizar=actualizar_flag,
                archivo_path=tmp_path,
                archivo_nombre=archivo_nombre,
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.post("/jobs/eliminar/run")
def ejecutar_jobs_eliminar(
    request: Request,
    empresa: str = Form(...),
    actualizar: str | None = Form(None),
    archivo: UploadFile = File(...),
):
    if not archivo or not archivo.filename:
        raise HTTPException(status_code=400, detail="Debes subir un archivo Excel válido.")

    extension = Path(archivo.filename).suffix.lower()
    if extension not in {".xlsx", ".xlsm", ".xls"}:
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx, .xlsm, .xls).")

    os.makedirs(jobs_controller.JOBS_UPLOAD_DIR, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension, dir=jobs_controller.JOBS_UPLOAD_DIR) as tmp_file:
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

    actualizar_flag = bool(actualizar)
    archivo_nombre = archivo.filename

    def _pipeline():
        try:
            yield from jobs_controller.eliminar_senales_pipeline(
                empresa=empresa,
                actualizar=actualizar_flag,
                archivo_path=tmp_path,
                archivo_nombre=archivo_nombre,
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.post("/jobs/cambiar-nombre/run")
def ejecutar_jobs_cambiar_nombre(
    request: Request,
    empresa: str = Form(...),
    actualizar: str | None = Form(None),
    archivo: UploadFile = File(...),
):
    if not archivo or not archivo.filename:
        raise HTTPException(status_code=400, detail="Debes subir un archivo Excel válido.")

    extension = Path(archivo.filename).suffix.lower()
    if extension not in {".xlsx", ".xlsm", ".xls"}:
        raise HTTPException(status_code=400, detail="El archivo debe ser un Excel (.xlsx, .xlsm, .xls).")

    os.makedirs(jobs_controller.JOBS_UPLOAD_DIR, exist_ok=True)
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=extension, dir=jobs_controller.JOBS_UPLOAD_DIR) as tmp_file:
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

    actualizar_flag = bool(actualizar)
    archivo_nombre = archivo.filename

    def _pipeline():
        try:
            yield from jobs_controller.cambiar_nombre_pipeline(
                empresa=empresa,
                actualizar=actualizar_flag,
                archivo_path=tmp_path,
                archivo_nombre=archivo_nombre,
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/jobs/crear/result")
def obtener_jobs_crear_result(
    sheet: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    data = jobs_controller.load_jobs_crear_result_preview(sheet=sheet, limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/jobs/eliminar/result")
def obtener_jobs_eliminar_result(
    limit: int = Query(500, ge=1, le=5000),
):
    data = jobs_controller.load_jobs_eliminar_result_preview(limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/jobs/cambiar-nombre/result")
def obtener_jobs_cambiar_nombre_result(
    limit: int = Query(500, ge=1, le=5000),
):
    data = jobs_controller.load_jobs_cambiar_result_preview(limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/jobs/crear/result/download")
def descargar_jobs_crear_result(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(jobs_controller.AUTOADA_DIR).joinpath(file_path).resolve()
    resolved = file_path.resolve()
    allowed_root = Path(jobs_controller.AUTOADA_DIR).resolve()
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


@router.get("/jobs/eliminar/result/download")
def descargar_jobs_eliminar_result(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(jobs_controller.AUTOADA_DIR).joinpath(file_path).resolve()
    resolved = file_path.resolve()
    allowed_root = Path(jobs_controller.AUTOADA_DIR).resolve()
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


@router.get("/jobs/cambiar-nombre/result/download")
def descargar_jobs_cambiar_nombre_result(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(jobs_controller.AUTOADA_DIR).joinpath(file_path).resolve()
    resolved = file_path.resolve()
    allowed_root = Path(jobs_controller.AUTOADA_DIR).resolve()
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
