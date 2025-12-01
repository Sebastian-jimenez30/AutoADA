from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from controllers import pruebas_controller

router = APIRouter()
templates = Jinja2Templates(directory="templates")


@router.get("/pruebas/itcosas-v1", response_class=HTMLResponse, name="pruebas_itcosas_v1_page")
def pruebas_itcosas_v1_page(request: Request):
    context = {
        "request": request,
        "active_section": "pruebas",
        "active_page": "pruebas_itcosas_v1",
        "page_title": "Pruebas - ITCOSAS v1",
        "page_subtitle": "Ejecuta el pipeline de ITCOSAS v1 (IOA, SOE Local, HIS, SOE Monarch, Checklist).",
        "empresas": list(pruebas_controller.get_empresas()),
        "dominios": list(pruebas_controller.get_dominios()),
    }
    return templates.TemplateResponse("pruebas_itcosas_v1.html", context)


@router.post("/pruebas/itcosas-v1/run")
def ejecutar_pruebas_itcosas_v1(
    request: Request,
    empresa: str = Form(...),
    dominio: str = Form(...),
    fecha: str = Form(...),
    hora_inicio: str = Form(...),
    hora_fin: str = Form(...),
    checklist: UploadFile = File(...),
    eventos: UploadFile = File(...),
    varexp: UploadFile = File(...),
    tmw: UploadFile = File(...),
):
    uploads = {"checklist": checklist, "eventos": eventos, "varexp": varexp, "tmw": tmw}
    stored: dict[str, str] = {}
    os.makedirs(pruebas_controller.PRUEBAS_UPLOAD, exist_ok=True)
    try:
        for key, uf in uploads.items():
            if not uf or not uf.filename:
                raise HTTPException(status_code=400, detail=f"Archivo {key} es obligatorio.")
            ext = Path(uf.filename).suffix
            with tempfile.NamedTemporaryFile(delete=False, suffix=ext, dir=pruebas_controller.PRUEBAS_UPLOAD) as tmp:
                uf.file.seek(0)
                shutil.copyfileobj(uf.file, tmp)
                stored[key] = tmp.name
    finally:
        for uf in uploads.values():
            try:
                uf.file.close()
            except Exception:
                pass

    def _pipeline():
        try:
            yield from pruebas_controller.itcosas_v1_pipeline(
                empresa=empresa,
                dominio=dominio,
                fecha=fecha,
                hora_inicio=hora_inicio,
                hora_fin=hora_fin,
                checklist=stored.get("checklist"),
                eventos=stored.get("eventos"),
                varexp=stored.get("varexp"),
                tmw=stored.get("tmw"),
            )
        finally:
            for path in stored.values():
                try:
                    os.remove(path)
                except Exception:
                    pass

    return StreamingResponse(_pipeline(), media_type="text/plain; charset=utf-8")


@router.get("/pruebas/itcosas-v1/result")
def obtener_pruebas_itcosas_v1_result(
    sheet: str | None = Query(None),
    limit: int = Query(500, ge=1, le=5000),
):
    data = pruebas_controller.load_pruebas_itcosas_v1_preview(sheet=sheet, limit=limit)
    if data is None:
        raise HTTPException(status_code=404, detail="No hay resultados disponibles.")
    return data


@router.get("/pruebas/itcosas-v1/result/download")
def descargar_pruebas_itcosas_v1_result(path: str):
    if not path:
        raise HTTPException(status_code=400, detail="Ruta inválida.")
    file_path = Path(path)
    if not file_path.is_absolute():
        file_path = Path(pruebas_controller.AUTOADA_DIR).joinpath(file_path).resolve()
    resolved = file_path.resolve()
    allowed_root = Path(pruebas_controller.AUTOADA_DIR).resolve()
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
