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
    }
    return templates.TemplateResponse("hsh_crear.html", context)


@router.post("/hsh/crear/run")
def ejecutar_hsh_crear(
    request: Request,
    aplicar: str | None = Form(None),
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
    archivo_nombre = archivo.filename

    def _pipeline():
        try:
            yield from hsh_controller.crear_tags_pipeline(
                empresa="",
                dominio="CC",
                archivo_path=tmp_path,
                archivo_nombre=archivo_nombre,
                aplicar=aplicar_flag,
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.post("/hsh/crear/pi")
def consultar_pi_crear():
    def _pipeline():
        yield from hsh_controller.crear_tag_pi()

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


@router.get("/hsh/eliminar", response_class=HTMLResponse, name="hsh_eliminar_page")
def hsh_eliminar_page(request: Request):
    context = {
        "request": request,
        "active_section": "hsh",
        "active_page": "hsh_eliminar_tag",
        "page_title": "HSH - Eliminar Tag",
        "page_subtitle": "Valida y elimina tags HSH existentes a partir de un archivo Excel.",
    }
    return templates.TemplateResponse("hsh_eliminar.html", context)


@router.get("/hsh/cambiar", response_class=HTMLResponse, name="hsh_cambiar_page")
def hsh_cambiar_page(request: Request):
    context = {
        "request": request,
        "active_section": "hsh",
        "active_page": "hsh_cambiar_key",
        "page_title": "HSH - Cambiar Key",
        "page_subtitle": "Valida o aplica cambios de keys HSH (principal y respaldo).",
    }
    return templates.TemplateResponse("hsh_cambiar.html", context)


@router.get("/hsh/validar", response_class=HTMLResponse, name="hsh_validar_page")
def hsh_validar_page(request: Request):
    context = {
        "request": request,
        "active_section": "hsh",
        "active_page": "hsh_validar",
        "page_title": "HSH - Validar",
        "page_subtitle": "Sincroniza SCADA/HSH y ejecuta las validaciones automáticas.",
    }
    return templates.TemplateResponse("hsh_validar.html", context)


@router.post("/hsh/validar/run")
def ejecutar_hsh_validar(request: Request):
    def _pipeline():
        yield from hsh_controller.validar_hsh_pipeline()
    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/hsh/validar/result")
def obtener_hsh_validar_result(
    sheet: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    data = hsh_controller.load_validar_result_preview(sheet=sheet, limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/hsh/validar/result/download")
def descargar_hsh_validar_result(path: str):
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


@router.post("/hsh/cambiar/run")
def ejecutar_hsh_cambiar(
    request: Request,
    aplicar: str | None = Form(None),
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
    archivo_nombre = archivo.filename

    def _pipeline():
        try:
            yield from hsh_controller.cambiar_key_pipeline(
                empresa="",
                dominio="CC",
                archivo_path=tmp_path,
                archivo_nombre=archivo_nombre,
                aplicar=aplicar_flag,
            )
        finally:
            # No borres el archivo si el flujo quedó pendiente de confirmación
            try:
                if not hsh_controller.is_cambiar_pending():
                    os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/hsh/cambiar/result")
def obtener_hsh_cambiar_result(
    sheet: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    data = hsh_controller.load_cambiar_result_preview(sheet=sheet, limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/hsh/cambiar/result/download")
def descargar_hsh_cambiar_result(path: str):
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


@router.post("/hsh/cambiar/pi")
def consultar_pi_cambiar():
    def _pipeline():
        yield from hsh_controller.cambiar_key_pi()
    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.post("/hsh/cambiar/confirm")
def confirmar_hsh_cambiar():
    def _pipeline():
        yield from hsh_controller.confirmar_cambiar_pipeline()
        # limpiar archivo temporal solo si ya no está pendiente
        if not hsh_controller.is_cambiar_pending():
          hsh_controller.cleanup_cambiar_file()
    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.post("/hsh/eliminar/run")
def ejecutar_hsh_eliminar(
    request: Request,
    aplicar: str | None = Form(None),
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
    archivo_nombre = archivo.filename

    def _pipeline():
        try:
            yield from hsh_controller.eliminar_tags_pipeline(
                empresa="",
                dominio="CC",
                archivo_path=tmp_path,
                archivo_nombre=archivo_nombre,
                aplicar=aplicar_flag,
            )
        finally:
            try:
                os.remove(tmp_path)
            except Exception:
                pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/hsh/eliminar/result")
def obtener_hsh_eliminar_result(
    sheet: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    data = hsh_controller.load_eliminar_result_preview(sheet=sheet, limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/hsh/eliminar/result/download")
def descargar_hsh_eliminar_result(path: str):
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
