from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from controllers import unifilares_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/unifilares/validar", response_class=HTMLResponse, name="unifilares_validar_page")
def unifilares_validar_page(request: Request):
    context = {
        "request": request,
        "active_section": "unifilares",
        "active_page": "unifilares_validar",
        "page_title": "Unifilares - Validar",
        "page_subtitle": "Valida archivos unifilares y genera reportes de hallazgos.",
        "empresas": list(unifilares_controller.get_empresas()),
        "dominios": list(unifilares_controller.get_dominios()),
    }
    return templates.TemplateResponse("unifilares_validar.html", context)


@router.post("/unifilares/validar/run")
def ejecutar_unifilares_validar(
    request: Request,
    empresa: str = Form(...),
    dominio: str = Form(...),
    actualizar: str | None = Form(None),
    archivos: list[UploadFile] | None = File(None),
):
    stored_paths: list[str] = []
    os.makedirs(unifilares_controller.UNIFILARES_UPLOAD, exist_ok=True)
    if archivos:
        for archivo in archivos:
            if not archivo or not archivo.filename:
                continue
            extension = Path(archivo.filename).suffix.lower()
            with tempfile.NamedTemporaryFile(delete=False, suffix=extension or "", dir=unifilares_controller.UNIFILARES_UPLOAD) as tmp_file:
                archivo.file.seek(0)
                shutil.copyfileobj(archivo.file, tmp_file)
                stored_paths.append(tmp_file.name)
            try:
                archivo.file.close()
            except Exception:
                pass
    # si no hay archivos, permitimos continuar solo si actualizar está presente
    if not stored_paths and not actualizar:
        raise HTTPException(status_code=400, detail="Debes subir al menos un archivo o elegir actualizar BD.")

    actualizar_flag = bool(actualizar)

    def _pipeline():
        try:
            yield from unifilares_controller.validar_unifilares_pipeline(
                empresa=empresa,
                dominio=dominio,
                archivos=stored_paths,
                actualizar=actualizar_flag,
            )
        finally:
            for path in stored_paths:
                try:
                    os.remove(path)
                except Exception:
                    pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/unifilares/validar/result")
def obtener_unifilares_validar_result(
    sheet: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    data = unifilares_controller.load_unifilares_result_preview(sheet=sheet, limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/unifilares/validar/result/download")
def descargar_unifilares_validar_result(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(unifilares_controller.AUTOADA_DIR).joinpath(file_path).resolve()
    resolved = file_path.resolve()
    allowed_root = Path(unifilares_controller.AUTOADA_DIR).resolve()
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


@router.post("/unifilares/stop")
def detener_unifilares():
    unifilares_controller.request_stop()
    return {"status": "OK", "message": "Proceso detenido a solicitud del usuario."}
